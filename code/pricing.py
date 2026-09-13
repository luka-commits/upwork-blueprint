#!/usr/bin/env python3
"""Turn a scoped hour estimate into an internal price guide for one Upwork job.

The model estimates the work from the full posting. This script does the math,
keeps the current profile rate as the source and writes only through pipeline.py.

    python3 code/pricing.py <job_id> --hours 8 12 18 --confidence medium \
      --milestone "Foundation|4" --milestone "Build and QA|8" \
      --assumption "One GoHighLevel sub-account"
"""
import argparse
import json
import math
import os
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = pathlib.Path(os.environ.get('BLUEPRINT_DATA') or ROOT / 'data')
ME = pathlib.Path(os.environ.get('BLUEPRINT_ME') or ROOT / 'context' / 'me.md')
PIPELINE = ROOT / 'code' / 'pipeline.py'
BUFFERS = {'high': 0.05, 'medium': 0.15, 'low': 0.25}


def abort(message):
    raise SystemExit(f'ABORT: {message}')


def money_number(value):
    match = re.search(r'\d[\d,]*(?:\.\d+)?', str(value or ''))
    return float(match.group(0).replace(',', '')) if match else None


def member_rate():
    profile = DATA / 'profile.json'
    if profile.is_file():
        try:
            value = json.loads(profile.read_text(encoding='utf-8'))
            raw = value.get('data', {}).get('personalData', {}).get('chargeRate', {}).get('rawValue')
            rate = money_number(raw)
            if rate:
                return rate
        except (json.JSONDecodeError, OSError):
            pass
    if ME.is_file():
        match = re.search(r'(?im)^\*\*Hourly rate:\*\*\s*\$?([\d,.]+)', ME.read_text(encoding='utf-8'))
        if match:
            return float(match.group(1).replace(',', ''))
    abort('the current hourly rate is missing from data/profile.json and context/me.md.')


def rounded_price(value):
    """Round quotes to a useful $25 boundary without hiding the source math."""
    return int(math.ceil(value / 25.0) * 25)


def parse_milestone(raw):
    label, separator, hours = raw.rpartition('|')
    if not separator or not label.strip():
        abort(f'--milestone needs Label|hours, got {raw!r}.')
    try:
        amount = float(hours)
    except ValueError:
        abort(f'--milestone hours must be a number, got {hours!r}.')
    if amount <= 0:
        abort('milestone hours must be greater than zero.')
    return {'label': ' '.join(label.split()), 'hours': amount}


def calculate(rate, hours, confidence, milestones, assumptions, contract_type):
    low, likely, high = hours
    if rate <= 0 or low <= 0 or not low <= likely <= high:
        abort('--hours must be three positive values ordered low, likely, high.')
    if not 2 <= len(milestones) <= 5:
        abort('use two to five roadmap milestones.')
    milestone_hours = sum(item['hours'] for item in milestones)
    if abs(milestone_hours - likely) > 0.01:
        abort(f'milestone hours total {milestone_hours:g}; they must equal the likely estimate {likely:g}.')
    if not assumptions:
        abort('add at least one scope assumption so the estimate can be challenged.')

    buffer = BUFFERS[confidence]
    recommended_total = rounded_price(likely * rate * (1 + buffer))
    low_total = rounded_price(low * rate)
    high_total = max(recommended_total, rounded_price(high * rate * (1 + buffer)))
    allocated = []
    assigned = 0
    cumulative_hours = 0
    for item in milestones:
        cumulative_hours += item['hours']
        cumulative_amount = round(recommended_total * cumulative_hours / likely)
        amount = cumulative_amount - assigned
        assigned = cumulative_amount
        allocated.append({**item, 'amount': amount})

    return {
        'version': 1,
        'currency': 'USD',
        'contract_type': contract_type,
        'hourly_rate': round(rate, 2),
        'rate_source': 'Current Upwork profile',
        'hours': {'low': low, 'likely': likely, 'high': high},
        'confidence': confidence,
        'risk_buffer_percent': round(buffer * 100),
        'price_range': {'low': low_total, 'high': high_total},
        'recommended_total': recommended_total,
        'recommended_hourly_bid': round(rate, 2) if contract_type == 'hourly' else None,
        'roadmap': allocated,
        'assumptions': [' '.join(value.split()) for value in assumptions if value.strip()],
        'status': 'Internal estimate, approval required',
    }


def save(job_id, estimate):
    payload = json.dumps({'price_estimate': estimate}, ensure_ascii=False)
    result = subprocess.run([sys.executable, str(PIPELINE), 'detail', job_id, '--file', '-'],
                            input=payload, capture_output=True, text=True)
    if result.returncode:
        abort((result.stderr or result.stdout or 'pipeline write failed').strip())
    return result.stdout.strip()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('job_id')
    parser.add_argument('--hours', nargs=3, required=True, type=float, metavar=('LOW', 'LIKELY', 'HIGH'))
    parser.add_argument('--confidence', choices=tuple(BUFFERS), default='medium')
    parser.add_argument('--contract-type', choices=('fixed', 'hourly', 'unknown'), default='unknown')
    parser.add_argument('--milestone', action='append', required=True)
    parser.add_argument('--assumption', action='append', required=True)
    args = parser.parse_args(argv)
    if not args.job_id.isdigit():
        parser.error('job id must contain digits only.')
    estimate = calculate(member_rate(), args.hours, args.confidence,
                         [parse_milestone(value) for value in args.milestone],
                         args.assumption, args.contract_type)
    print(save(args.job_id, estimate))
    print(f'Price guide: ${estimate["recommended_total"]:,} from {estimate["hours"]["likely"]:g} likely hours '
          f'at ${estimate["hourly_rate"]:.2f}/hr plus {estimate["risk_buffer_percent"]}% scope risk.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
