#!/usr/bin/env python3
"""Render one private, evidence-only local SEO audit as self-contained HTML."""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain one JSON object")
    return value


def clean(value: Any) -> str:
    return html.escape(str(value or "").strip(), quote=True)


def safe_image(value: Any) -> str:
    text = str(value or "").strip()
    return clean(text) if text.startswith(("data:image/png;base64,", "data:image/jpeg;base64,")) else ""


def percent(value: float | None) -> str:
    return "Not measured" if value is None else f"{round(value * 100)}%"


def maps_score(search: dict[str, Any]) -> tuple[float | None, int, int]:
    grid = search.get("geoGrid") if isinstance(search.get("geoGrid"), dict) else {}
    all_ranks = grid.get("ranks") if isinstance(grid.get("ranks"), list) else []
    checked = int(grid.get("checkedPoints") or 0)
    requested = int(grid.get("requestedPoints") or 0)
    if checked != 25 or requested != 25 or len(all_ranks) != 25:
        return None, 0, 0
    ranks = [rank for rank in all_ranks if isinstance(rank, int) and rank > 0]
    top_three = sum(1 for rank in ranks if rank <= 3)
    return top_three / checked, top_three, checked


def profile_score(search: dict[str, Any]) -> tuple[float | None, list[dict[str, Any]]]:
    profile = search.get("gbp") if isinstance(search.get("gbp"), dict) else {}
    rows = [row for row in profile.get("auditRows", []) if isinstance(row, dict)]
    graded = [row for row in rows if row.get("status") in {"good", "warn", "bad"}]
    if not graded:
        return None, rows
    points = sum({"good": 1.0, "warn": 0.5, "bad": 0.0}[row["status"]] for row in graded)
    return points / len(graded), rows


def website_score(cro: dict[str, Any]) -> tuple[float | None, list[dict[str, Any]]]:
    rows = [row for row in cro.get("elements", []) if isinstance(row, dict) and row.get("applies") is not False]
    if not rows:
        return None, []
    found = sum(1 for row in rows if row.get("present") is True)
    return found / len(rows), rows


def overall_score(values: list[float | None]) -> float | None:
    measured = [value for value in values if value is not None]
    return sum(measured) / len(measured) if measured else None


def conclusion(score: float | None) -> str:
    if score is None:
        return "The audit needs more evidence before it can draw a conclusion."
    if score >= 0.8:
        return "The foundations are strong. A few focused improvements can make them work harder."
    if score >= 0.55:
        return "Customers can find and assess the business, but several gaps still cost enquiries."
    return "The business is harder to find and choose than it needs to be."


def fixes(search: dict[str, Any], cro: dict[str, Any]) -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    map_value, top_three, checked = maps_score(search)
    grid = search.get("geoGrid") if isinstance(search.get("geoGrid"), dict) else {}
    if map_value is not None and map_value < 0.8:
        keyword = str(grid.get("keyword") or "the checked service search")
        result.append(("Local visibility", f"The business reached the top three at {top_three} of {checked} checked points for {keyword}."))
    _, profile_rows = profile_score(search)
    for row in profile_rows:
        if row.get("status") in {"bad", "warn"}:
            result.append((str(row.get("label") or "Business Profile"), str(row.get("value") or "This profile check needs attention.")))
        if len(result) >= 4:
            return result
    _, website_rows = website_score(cro)
    for row in website_rows:
        if row.get("present") is False:
            evidence = str(row.get("evidence") or row.get("consequence") or "This website element was not found.")
            result.append((str(row.get("label") or "Website"), evidence))
        if len(result) >= 4:
            break
    return result


def rank_grid(search: dict[str, Any]) -> str:
    grid = search.get("geoGrid") if isinstance(search.get("geoGrid"), dict) else {}
    ranks = list(grid.get("ranks") or [])[:25]
    if maps_score(search)[0] is None:
        return '<p class="empty">The complete 25-point map grid was not measured.</p>'
    cells = []
    for rank in ranks:
        if isinstance(rank, int) and rank > 0:
            tone = "great" if rank <= 3 else "mid" if rank <= 10 else "low"
            label = str(rank)
        else:
            tone, label = "none", "-"
        cells.append(f'<span class="rank {tone}" aria-label="Rank {clean(label)}">{clean(label)}</span>')
    return '<div class="rank-grid">' + "".join(cells) + "</div>"


def map_winners(search: dict[str, Any]) -> str:
    grid = search.get("geoGrid") if isinstance(search.get("geoGrid"), dict) else {}
    winners = [item for item in grid.get("winners", []) if isinstance(item, dict)][:4]
    if not winners:
        return '<p class="empty">No competitor leaders were returned.</p>'
    parts = []
    for item in winners:
        name = clean(item.get("name") or item.get("title") or item.get("domain") or "Unnamed business")
        detail = item.get("topThree") or item.get("top3") or item.get("points")
        suffix = f"{clean(detail)} top-three points" if detail is not None else clean(item.get("domain") or "Measured competitor")
        parts.append(f"<li><strong>{name}</strong><span>{suffix}</span></li>")
    return '<ul class="leaders">' + "".join(parts) + "</ul>"


def profile_rows(search: dict[str, Any]) -> str:
    _, rows = profile_score(search)
    if not rows:
        return '<p class="empty">No exact public Google Business Profile was measured.</p>'
    parts = []
    for row in rows:
        status = row.get("status") if row.get("status") in {"good", "warn", "bad"} else "unknown"
        parts.append(
            f'<li><span class="status {status}" aria-hidden="true"></span><div><strong>{clean(row.get("label") or "Check")}</strong>'
            f'<em>{clean(status)}</em><p>{clean(row.get("value") or "No detail returned.")}</p></div></li>'
        )
    return '<ul class="checks">' + "".join(parts) + "</ul>"


def website_rows(cro: dict[str, Any]) -> str:
    _, rows = website_score(cro)
    if not rows:
        return '<p class="empty">No rendered website evidence was measured.</p>'
    parts = []
    for row in rows:
        status = "good" if row.get("present") is True else "bad"
        label = "Found" if status == "good" else "Missing"
        parts.append(
            f'<li><span class="status {status}" aria-hidden="true"></span><div><strong>{clean(row.get("label") or "Check")}</strong>'
            f'<em>{label}</em><p>{clean(row.get("evidence") or row.get("consequence") or "No detail returned.")}</p></div></li>'
        )
    return '<ul class="checks">' + "".join(parts) + "</ul>"


def score_ring(value: float | None) -> str:
    number = "?" if value is None else f"{round(value * 100)}<small>/100</small>"
    label = "Not measured" if value is None else "Audit score"
    degree = 0 if value is None else round(value * 360)
    return f'<div class="score-ring" style="--score:{degree}deg"><strong>{number}</strong><span>{label}</span></div>'


def section_summary(number: str, title: str, source: str, result: str, consequence: str) -> str:
    return (
        f'<summary><span class="section-number">{number}</span><span class="summary-copy"><strong>{clean(title)}</strong>'
        f'<small>{clean(source)}</small></span><span class="summary-result"><b>{clean(result)}</b>'
        f'<small>{clean(consequence)}</small></span><span class="chevron">+</span></summary>'
    )


def pages_checked(site: dict[str, Any]) -> str:
    pages = [page for page in site.get("pages", []) if isinstance(page, dict)]
    if not pages:
        return '<p class="source-note">Reachable pages were not returned.</p>'
    labels = []
    for page in pages[:6]:
        path = str(page.get("path") or "/")
        title = str(page.get("title") or "").strip()
        labels.append(f"<li><strong>{clean(path)}</strong><span>{clean(title or 'Page title not returned')}</span></li>")
    return f'<div class="pages-checked"><h3>Pages checked</h3><ul>{"".join(labels)}</ul></div>'


def render(
    business: str,
    cro: dict[str, Any],
    search: dict[str, Any],
    measured_at: str,
    location: str = "",
    site: dict[str, Any] | None = None,
) -> str:
    map_value, top_three, checked = maps_score(search)
    profile_value, _ = profile_score(search)
    website_value, website_checks = website_score(cro)
    total_value = overall_score([map_value, profile_value, website_value])
    grid = search.get("geoGrid") if isinstance(search.get("geoGrid"), dict) else {}
    quick_fixes = fixes(search, cro)
    fixes_html = "".join(
        f'<li><span>{index}</span><div><strong>{clean(title)}</strong><p>{clean(detail)}</p></div></li>'
        for index, (title, detail) in enumerate(quick_fixes, 1)
    ) or '<li class="empty">No evidence-backed quick fix was found.</li>'
    map_image = safe_image(grid.get("mapImage"))
    website_image = safe_image((cro.get("speed") or {}).get("desktopScreenshot"))
    map_visual = f'<img class="evidence-image" src="{map_image}" alt="Measured local search area">' if map_image else ""
    site_visual = f'<img class="site-shot" src="{website_image}" alt="Rendered business website">' if website_image else ""
    speed = cro.get("speed") if isinstance(cro.get("speed"), dict) else {}
    speed_scores = speed.get("scores") if isinstance(speed.get("scores"), dict) else {}
    speed_html = "".join(
        f'<div><strong>{clean(value)}</strong><span>{clean(label.replace("-", " ").title())}</span></div>'
        for label, value in speed_scores.items()
    )
    if not speed.get("ok"):
        reason = speed.get("why") or "no PageSpeed or Lighthouse result was returned"
        speed_html = f'<p class="source-note">Mobile speed not measured: {clean(reason)}.</p>'
    pages_html = pages_checked(site or {})
    maps_consequence = (
        f"Top three at {top_three} of {checked} checked points."
        if map_value is not None else "No verified local grid was available."
    )
    profile_consequence = "Public trust signals, checked field by field." if profile_value is not None else "No exact profile was available."
    website_consequence = (
        f"{sum(1 for row in website_checks if row.get('present') is True)} of {len(website_checks)} enquiry checks passed."
        if website_value is not None else "The rendered site could not be scored."
    )
    try:
        measured = clean(dt.date.fromisoformat(measured_at).strftime("%d %B %Y").lstrip("0"))
    except ValueError:
        measured = clean(measured_at)
    website_host = (urlparse(str(cro.get("url") or "")).hostname or "Website not returned").removeprefix("www.")
    profile = ((search.get("gbp") or {}).get("profile") or {}) if isinstance(search.get("gbp"), dict) else {}
    measured_location = location or str(profile.get("city") or profile.get("address") or "Location not returned")
    query = str(grid.get("keyword") or "Query not returned")
    profile_rows_list = profile_score(search)[1]
    profile_graded = [row for row in profile_rows_list if row.get("status") in {"good", "warn", "bad"}]
    profile_points = sum({"good": 1.0, "warn": 0.5, "bad": 0.0}[row["status"]] for row in profile_graded)
    profile_result = "Not measured" if profile_value is None else f"{profile_points:g}/{len(profile_graded)} checks"
    website_found = sum(1 for row in website_checks if row.get("present") is True)
    website_result = "Not measured" if website_value is None else f"{website_found}/{len(website_checks)} checks"
    map_result = "Not measured" if map_value is None else f"{top_three}/{checked} top-three"
    checked_label = f"{checked} points" if checked else "Not measured"
    name = clean(business)
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Local visibility audit for {name}</title>
<style>
:root{{--paper:#f3efe6;--paper-2:#ece5d7;--ink:#1c1712;--muted:#6f675c;--line:#d6cdbf;--amber:#d6922f;--green:#4d785e;--red:#a95b4e;--white:#fffdf8}}
*{{box-sizing:border-box}}html{{background:var(--paper);color:var(--ink);font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}body{{margin:0}}main{{width:min(1120px,calc(100% - 48px));margin:0 auto;padding:72px 0 48px}}h1,h2,h3,p{{margin:0}}.eyebrow{{font-size:12px;font-weight:750;letter-spacing:.14em;text-transform:uppercase;color:var(--amber)}}.hero{{display:grid;grid-template-columns:1fr 220px;gap:64px;align-items:end;padding:36px 0 64px;border-bottom:1px solid var(--line)}}h1{{max-width:780px;font-family:Georgia,serif;font-size:clamp(48px,6vw,78px);font-weight:500;letter-spacing:-.045em;line-height:.96}}.hero-copy>p{{max-width:650px;margin-top:24px;font-size:19px;line-height:1.55;color:var(--muted)}}.meta{{margin-top:22px;font-size:13px!important}}.score-ring{{--score:0deg;width:188px;height:188px;border-radius:50%;display:grid;place-content:center;text-align:center;background:radial-gradient(circle at center,var(--paper) 0 61%,transparent 62%),conic-gradient(var(--amber) var(--score),var(--line) 0)}}.score-ring strong{{font-family:Georgia,serif;font-size:58px;font-weight:500;line-height:.9}}.score-ring span{{margin-top:10px;font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:var(--muted)}}.fixes{{padding:58px 0}}.fixes h2{{font-family:Georgia,serif;font-size:34px;font-weight:500}}.fixes>p{{margin-top:10px;color:var(--muted)}}.fixes ol{{display:grid;grid-template-columns:repeat(2,1fr);gap:14px;margin:28px 0 0;padding:0;list-style:none}}.fixes li{{display:flex;gap:18px;min-height:126px;padding:24px;background:var(--white);border:1px solid var(--line);border-radius:12px}}.fixes li>span{{width:30px;height:30px;display:grid;place-items:center;flex:none;border-radius:50%;background:var(--ink);color:white;font-size:13px}}.fixes li strong{{font-size:15px}}.fixes li p{{margin-top:8px;color:var(--muted);font-size:14px;line-height:1.5}}.audits{{border-top:1px solid var(--line)}}details{{border-bottom:1px solid var(--line)}}summary{{display:grid;grid-template-columns:44px 1fr minmax(260px,420px) 24px;gap:18px;align-items:center;padding:28px 2px;cursor:pointer;list-style:none}}summary::-webkit-details-marker{{display:none}}.section-number{{width:34px;height:34px;display:grid;place-items:center;border:1px solid var(--line);border-radius:50%;font-family:Georgia,serif}}.summary-copy,.summary-result{{display:grid;gap:5px}}.summary-copy strong{{font-family:Georgia,serif;font-size:28px;font-weight:500}}summary small{{color:var(--muted);line-height:1.35}}.summary-result b{{font-size:17px}}.chevron{{font-size:24px;transition:transform .25s cubic-bezier(.23,1,.32,1)}}details[open] .chevron{{transform:rotate(45deg)}}.audit-body{{padding:4px 0 48px 62px;animation:audit-reveal .24s cubic-bezier(.23,1,.32,1) both}}@keyframes audit-reveal{{from{{opacity:0;transform:translateY(-6px)}}to{{opacity:1;transform:translateY(0)}}}}.split{{display:grid;grid-template-columns:1.1fr .9fr;gap:24px}}.evidence-card{{padding:24px;background:var(--white);border:1px solid var(--line);border-radius:12px;overflow:hidden}}.evidence-card h3{{margin-bottom:18px;font-size:12px;letter-spacing:.12em;text-transform:uppercase}}.rank-grid{{display:grid;grid-template-columns:repeat(5,1fr);gap:9px}}.rank{{aspect-ratio:1;display:grid;place-items:center;border-radius:50%;font-weight:750;font-size:14px}}.rank.great{{background:#dcebdd;color:#27543a}}.rank.mid{{background:#f4dfb5;color:#705017}}.rank.low{{background:#ecd2ca;color:#743f37}}.rank.none{{background:#ebe7de;color:#8a8276}}.evidence-note{{margin-top:18px;color:var(--muted);font-size:13px;line-height:1.45}}.evidence-image,.site-shot{{width:100%;max-height:420px;object-fit:cover;border:1px solid var(--line);border-radius:8px;margin-top:18px}}.leaders,.checks{{margin:0;padding:0;list-style:none}}.leaders li{{display:flex;justify-content:space-between;gap:16px;padding:14px 0;border-bottom:1px solid var(--line)}}.leaders span{{color:var(--muted);font-size:13px;text-align:right}}.checks{{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}}.checks li{{display:flex;gap:13px;padding:18px;background:var(--white);border:1px solid var(--line);border-radius:10px}}.checks p{{margin-top:5px;color:var(--muted);font-size:13px;line-height:1.45}}.status{{width:10px;height:10px;margin-top:4px;border-radius:50%;background:#aaa;flex:none}}.status.good{{background:var(--green)}}.status.warn{{background:var(--amber)}}.status.bad{{background:var(--red)}}.speed-row{{display:flex;gap:10px;margin:20px 0}}.speed-row div{{display:grid;gap:4px;min-width:110px;padding:14px;background:var(--paper-2);border-radius:8px}}.speed-row span{{font-size:11px;text-transform:capitalize;color:var(--muted)}}.method{{margin-top:38px;padding-top:24px;border-top:1px solid var(--line)}}.method summary{{display:flex;padding:12px 0;font-weight:650}}.method p{{max-width:780px;padding:12px 0;color:var(--muted);font-size:14px;line-height:1.6}}.empty{{color:var(--muted)}}footer{{display:flex;justify-content:space-between;align-items:center;margin-top:52px;padding:34px 0;border-top:1px solid var(--line)}}footer strong{{font-family:Georgia,serif;font-size:30px;font-weight:500}}footer span{{color:var(--muted);font-size:12px}}@media(prefers-reduced-motion:reduce){{.audit-body{{animation:none}}.chevron{{transition:none}}}}@media(max-width:760px){{main{{width:min(100% - 28px,1120px);padding-top:32px}}.hero{{grid-template-columns:1fr;gap:32px}}.score-ring{{width:140px;height:140px}}.fixes ol,.split,.checks{{grid-template-columns:1fr}}summary{{grid-template-columns:36px 1fr 22px}}.summary-result{{grid-column:2}}.chevron{{grid-column:3;grid-row:1}}.audit-body{{padding-left:0}}footer{{align-items:flex-start;gap:20px;flex-direction:column}}}}
:root{{--amber:#7c511a}}.score-ring strong{{font-size:42px}}.score-ring strong small{{font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;font-size:14px;font-weight:650;color:var(--muted)}}.provenance{{display:flex;flex-wrap:wrap;gap:10px 20px;margin:24px 0 0}}.provenance div{{display:grid;gap:3px;max-width:220px}}.provenance dt{{font-size:10px;font-weight:750;letter-spacing:.09em;text-transform:uppercase;color:var(--muted)}}.provenance dd{{overflow:hidden;margin:0;font-size:12px;font-weight:650;text-overflow:ellipsis;white-space:nowrap}}.checks em{{display:block;margin-top:3px;color:var(--muted);font-size:10px;font-style:normal;font-weight:750;letter-spacing:.08em;text-transform:uppercase}}.rank.none{{color:#5f5a52}}.rank-legend{{display:flex;flex-wrap:wrap;gap:7px 14px;margin-top:14px;color:var(--muted);font-size:11px}}.rank-legend span::before{{content:'';display:inline-block;width:8px;height:8px;margin-right:5px;border-radius:50%;background:#ebe7de}}.rank-legend .great::before{{background:#4d785e}}.rank-legend .mid::before{{background:#9a6a1e}}.rank-legend .low::before{{background:#a95b4e}}.source-note{{width:100%;padding:14px;background:var(--paper-2);border-radius:8px;color:var(--muted);font-size:13px}}.pages-checked{{margin:8px 0 20px;padding:18px;background:var(--white);border:1px solid var(--line);border-radius:10px}}.pages-checked h3{{font-size:11px;letter-spacing:.1em;text-transform:uppercase}}.pages-checked ul{{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0 0;padding:0;list-style:none}}.pages-checked li{{display:flex;gap:7px;padding:7px 10px;background:var(--paper-2);border-radius:7px;font-size:12px}}.pages-checked span{{color:var(--muted)}}
</style></head><body><main>
<p class="eyebrow">Private local visibility audit</p>
<section class="hero"><div class="hero-copy"><h1>How customers find {name}.</h1><p>{clean(conclusion(total_value))}</p><dl class="provenance"><div><dt>Website</dt><dd>{clean(website_host)}</dd></div><div><dt>Location</dt><dd>{clean(measured_location)}</dd></div><div><dt>Search</dt><dd>{clean(query)}</dd></div><div><dt>Checked</dt><dd>{clean(checked_label)}</dd></div><div><dt>Date</dt><dd>{measured}</dd></div></dl></div>{score_ring(total_value)}</section>
<section class="fixes"><h2>What needs attention</h2><p>The clearest opportunities from this measurement.</p><ol>{fixes_html}</ol></section>
<section class="audits">
<details data-audit-section="maps">{section_summary('01','Get found','Local Maps',map_result,maps_consequence)}<div class="audit-body"><div class="split"><div class="evidence-card"><h3>{clean(grid.get('keyword') or 'Local search grid')}</h3>{rank_grid(search)}<div class="rank-legend"><span class="great">1-3</span><span class="mid">4-10</span><span class="low">11+</span><span class="none">Not found</span></div><p class="evidence-note">{clean(grid.get('note') or 'Search ranks are a point-in-time local snapshot.')}</p>{map_visual}</div><div class="evidence-card"><h3>Who leads the checked area</h3>{map_winners(search)}</div></div></div></details>
<details data-audit-section="profile">{section_summary('02','Build trust','Google Business Profile',profile_result,profile_consequence)}<div class="audit-body">{profile_rows(search)}</div></details>
<details data-audit-section="website">{section_summary('03','Win enquiries','Website',website_result,website_consequence)}<div class="audit-body"><div class="speed-row">{speed_html}</div>{pages_html}{site_visual}{website_rows(cro)}</div></details>
</section>
<details class="method"><summary>How this was measured</summary><p>Local Maps is the share of 25 checked points in the top three. Profile checks score 1 for good, 0.5 for attention and 0 for failed. Website is the share of applicable enquiry checks found. The overall score is the equal average of measured sections only. Google Business Profile checks use the exact public listing linked to this website. Website checks cover rendered pages and what a visitor can see, not what happens after an enquiry. Profile and website thresholds are Pocket CEO operating heuristics, not Google requirements or causal proof. Rankings are a snapshot, and search estimates are not first-party analytics. Missing sources stay unscored.</p></details>
<footer><strong>Reply here on Upwork.</strong><span>Private audit for {name}</span></footer>
</main></body></html>'''


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--business", required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--measured-at", default=dt.date.today().isoformat())
    parser.add_argument("--location", default="")
    args = parser.parse_args()
    cro = read_json(args.evidence / "cro.json")
    search = read_json(args.evidence / "search.json")
    site = read_json(args.evidence / "site.json")
    page = render(args.business, cro, search, args.measured_at, args.location, site)
    if page.count('data-audit-section="') != 3:
        raise RuntimeError("report must contain exactly three audit sections")
    args.output.write_text(page, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
