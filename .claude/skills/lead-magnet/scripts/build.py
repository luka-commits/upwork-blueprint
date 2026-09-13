#!/usr/bin/env python3
"""Build and publish one checked SEO audit from a saved Upwork lead source."""

from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from urllib.parse import urlparse


SKILL = Path(__file__).resolve().parents[1]
ROOT = Path(__file__).resolve().parents[4]
ID = re.compile(r"^[0-9]{6,25}$")
REQUIRED_KEYS = (
    ("FIRECRAWL_API_KEY",),
    ("APIFY_API_TOKEN_PAID", "APIFY_TOKEN", "APIFY_API_TOKEN"),
    ("DATAFORSEO_LOGIN",),
    ("DATAFORSEO_PASSWORD",),
)


def runtime_error(env: dict[str, str], *, find_spec=importlib.util.find_spec, which=shutil.which) -> str:
    packages = [name for name, module in (("Pillow", "PIL"), ("Playwright", "playwright"))
                if find_spec(module) is None]
    if packages:
        return f"Install {', '.join(packages)} from .claude/skills/lead-magnet/requirements.txt before starting the paid audit."
    if not env.get("PAGESPEED_API_KEY", "").strip() and which("lighthouse") is None:
        return "Add PAGESPEED_API_KEY to .env or install local Lighthouse before starting the paid audit."
    return ""


def load_env(path: Path, env: dict[str, str]) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            env.setdefault(key, value.strip().strip('"').strip("'"))


def command(parts: list[str], *, cwd: Path, env: dict[str, str], stdout: Path | None = None) -> str:
    result = subprocess.run(parts, cwd=cwd, env=env, text=True, capture_output=True)
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(detail[-1800:] or f"{Path(parts[1]).name} exited {result.returncode}")
    if stdout is not None:
        stdout.write_text(result.stdout, encoding="utf-8")
    return result.stdout


def get_job(job_id: str, env: dict[str, str]) -> dict:
    raw = command([sys.executable, str(ROOT / "code" / "pipeline.py"), "get", job_id], cwd=ROOT, env=env)
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise RuntimeError("The pipeline did not return one lead.")
    return value


def normalise_website(value: str) -> tuple[str, str]:
    parsed = urlparse(value.strip())
    host = (parsed.hostname or "").casefold().removeprefix("www.")
    if parsed.scheme != "https" or not host or "." not in host or parsed.username or parsed.password:
        raise RuntimeError("Save the business's public HTTPS website before running the audit.")
    return value.strip(), host


def profile_domain(profile: dict) -> str:
    value = str(profile.get("website") or "").strip()
    if not value:
        return ""
    parsed = urlparse(value if "://" in value else f"https://{value}")
    return (parsed.hostname or "").casefold().removeprefix("www.")


def validate_profile(profile: dict, expected_domain: str) -> None:
    actual = profile_domain(profile)
    if actual != expected_domain:
        raise RuntimeError(
            f"The confirmed Google profile links to {actual or 'no website'}, not {expected_domain}. Nothing was audited."
        )
    if not profile.get("place_id") or not profile.get("coordinate") or not profile.get("name"):
        raise RuntimeError("The exact Google profile needs a place ID, coordinates and business name.")


def validate_site(path: Path) -> dict:
    site = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(site, dict) or not isinstance(site.get("pages"), list) or not site["pages"]:
        raise RuntimeError("The website pull returned no reachable pages.")
    return site


def jobs_dir(env: dict[str, str]) -> Path:
    return Path(env.get("BLUEPRINT_JOBDIR") or ROOT / "jobs")


def missing_credentials(env: dict[str, str]) -> list[str]:
    return [" or ".join(group) for group in REQUIRED_KEYS
            if not any(str(env.get(name) or "").strip() for name in group)]


def artifact_is_current(path: Path, source_updated_at: str) -> bool:
    if not path.is_file() or not source_updated_at:
        return False
    try:
        source_time = dt.datetime.fromisoformat(source_updated_at.replace("Z", "+00:00"))
        return path.stat().st_mtime >= source_time.timestamp()
    except (OSError, ValueError):
        return False


def publish(job_id: str, env: dict[str, str]) -> str:
    output = command(
        [sys.executable, str(ROOT / "code" / "lead_magnet_deploy.py"), job_id],
        cwd=ROOT,
        env=env,
    )
    match = re.search(r"Published (https://[^\s]+)", output)
    if not match:
        raise RuntimeError("The audit deploy finished without a public URL.")
    return match.group(1)


def run(job_id: str, *, dry_run: bool = False) -> Path | None:
    if not ID.fullmatch(job_id):
        raise RuntimeError("Use the numeric Upwork job ID.")
    env = dict(os.environ)
    load_env(ROOT / ".env", env)
    load_env(Path.home() / ".config" / "credentials.env", env)
    env["SEO_BLUEPRINT_WORKSPACE"] = str(ROOT)
    job = get_job(job_id, env)
    if job.get("status") not in {"replied", "offer"}:
        raise RuntimeError("Lead magnets are available only for In conversation or Offer leads.")
    source = job.get("lead_magnet_source")
    if not isinstance(source, dict):
        raise RuntimeError("Save the business website and location in the cockpit first.")
    website, domain = normalise_website(str(source.get("website") or ""))
    location = str(source.get("location") or "").strip()
    if not location:
        raise RuntimeError("Add the business city and country so local rankings use the right market.")
    missing = missing_credentials(env)
    if dry_run:
        print(json.dumps({
            "job": job_id,
            "website": website,
            "location": location,
            "paid_services": ["Firecrawl", "Apify", "DataForSEO"],
            "missing_credentials": missing,
            "would_send_or_publish": False,
            "production_run_publishes": True,
        }))
        return None
    folder = jobs_dir(env) / job_id
    final = folder / "lead-magnet.html"
    if not job.get("lead_magnet_url") and artifact_is_current(
            final, str(job.get("lead_magnet_source_updated_at") or "")):
        command([sys.executable, str(ROOT / "code" / "preflight.py"), "vercel"], cwd=ROOT, env=env)
        public_url = publish(job_id, env)
        print(json.dumps({"report": str(final), "published": True, "public_url": public_url,
                          "reused_existing_audit": True, "sent": False}))
        return final
    if missing:
        raise RuntimeError(f"Add {', '.join(missing)} to .env before starting the paid audit.")
    runtime_problem = runtime_error(env)
    if runtime_problem:
        raise RuntimeError(runtime_problem)
    command([sys.executable, str(ROOT / "code" / "preflight.py"), "lead-magnet"], cwd=ROOT, env=env)

    folder.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    stage = folder / f".lead-magnet-build-{stamp}"
    stage.mkdir(mode=0o700)
    env["POCKET_CEO_METRICS_DIR"] = str(stage)
    profile_file = stage / "gbp-profile.json"
    profile_args = [sys.executable, str(SKILL / "scripts" / "gbp_rich.py")]
    place_id = str(source.get("place_id") or "").strip()
    if place_id:
        profile_args.extend(["--place-id", place_id])
    else:
        profile_args.extend(["--discover-domain", domain, "--location", location])
    command(profile_args, cwd=SKILL, env=env, stdout=profile_file)
    profile = json.loads(profile_file.read_text(encoding="utf-8"))
    validate_profile(profile, domain)

    collect_args = [
        sys.executable, str(SKILL / "scripts" / "collect.py"),
        "--url", website,
        "--domain", domain,
        "--business", str(profile["name"]),
        "--location", location,
        "--language", str(source.get("language") or "English"),
        "--market", "local",
        "--coordinate", str(profile["coordinate"]),
        "--auto-grid",
        "--outdir", str(stage),
    ]
    if profile.get("country_code"):
        collect_args.extend(["--country-code", str(profile["country_code"])])
    command(collect_args, cwd=SKILL, env=env)
    for name in ("cro.json", "site.json", "search.json", "keyword-cache.json", "gbp-profile.json"):
        target = stage / name
        if not target.is_file() or target.stat().st_size < 20:
            raise RuntimeError(f"The paid run did not produce complete {name}. Evidence remains in {stage.name}.")
    try:
        validate_site(stage / "site.json")
    except (RuntimeError, OSError, ValueError, json.JSONDecodeError) as error:
        raise RuntimeError(f"{error} Evidence remains in {stage.name}.") from error

    report_tmp = folder / f".lead-magnet-{stamp}.html.tmp"
    command([
        sys.executable, str(SKILL / "scripts" / "render_report.py"),
        "--business", str(profile["name"]),
        "--evidence", str(stage),
        "--output", str(report_tmp),
        "--measured-at", dt.date.today().isoformat(),
        "--location", location,
    ], cwd=ROOT, env=env)
    page = report_tmp.read_text(encoding="utf-8")
    if page.count('data-audit-section="') != 3 or "Reply here on Upwork." not in page:
        raise RuntimeError(f"Report validation failed. Evidence remains in {stage.name}.")
    report_tmp.replace(final)
    evidence_root = folder / "lead-magnet-data"
    evidence_root.mkdir(exist_ok=True)
    stage.rename(evidence_root / stamp)
    public_url = publish(job_id, env)
    print(json.dumps({"report": str(final), "evidence": str(evidence_root / stamp), "sent": False,
                      "published": True, "public_url": public_url}))
    return final


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("job_id")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        run(args.job_id, dry_run=args.dry_run)
    except (RuntimeError, OSError, ValueError, json.JSONDecodeError) as error:
        print(f"Lead magnet stopped: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
