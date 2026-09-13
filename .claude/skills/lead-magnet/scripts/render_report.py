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


TEMPLATE = Path(__file__).resolve().parents[1] / "template" / "dist" / "index.html"


def safe_asset(value: Any) -> str:
    text = str(value or "").strip()
    return text if text.startswith(("data:image/png;base64,", "data:image/jpeg;base64,")) else ""


def score_number(value: float | None) -> int:
    return 0 if value is None else round(value * 100)


def proposal_data(
    business: str,
    cro: dict[str, Any],
    search: dict[str, Any],
    measured_at: str,
    location: str = "",
    site: dict[str, Any] | None = None,
) -> dict[str, Any]:
    map_value, top_three, checked = maps_score(search)
    profile_value, profile_rows_list = profile_score(search)
    website_value, website_checks = website_score(cro)
    total_value = overall_score([map_value, profile_value, website_value])
    grid = search.get("geoGrid") if isinstance(search.get("geoGrid"), dict) else {}
    gbp_source = search.get("gbp") if isinstance(search.get("gbp"), dict) else {}
    profile = gbp_source.get("profile") if isinstance(gbp_source.get("profile"), dict) else {}
    ranks = list(grid.get("ranks") or [])
    complete_grid = ranks if map_value is not None else None
    winners = []
    for item in grid.get("winners", []):
        if not isinstance(item, dict) or not item.get("name") or not isinstance(item.get("topThreePoints"), int):
            continue
        winners.append({
            "name": str(item["name"]),
            "topThreePoints": item["topThreePoints"],
            "bestRank": item.get("bestRank") if isinstance(item.get("bestRank"), int) else None,
            "rating": item.get("rating") if isinstance(item.get("rating"), (int, float)) else None,
            "reviews": item.get("reviews") if isinstance(item.get("reviews"), int) else None,
            "category": item.get("category") or None,
        })
    client = grid.get("client") if isinstance(grid.get("client"), dict) else None
    geo_grid = {
        "keyword": str(grid.get("keyword") or "Local service search"),
        "businessName": business,
        "ranks": complete_grid,
        "mapImage": safe_asset(grid.get("mapImage")) or None,
        "note": str(grid.get("note") or ("25 locations checked across the service area." if complete_grid else "The complete 25-point map grid was not measured.")),
        "winners": winners,
        "client": client,
    }
    graded_rows = [
        {"label": str(row.get("label") or "Check"), "value": str(row.get("value") or "No detail returned."), "status": row["status"]}
        for row in profile_rows_list if row.get("status") in {"good", "warn", "bad"}
    ]
    rating = profile.get("rating")
    reviews = profile.get("reviews")
    panel = None
    if isinstance(rating, (int, float)) and isinstance(reviews, int):
        panel = {
            "name": str(profile.get("name") or business),
            "subtitle": " · ".join(str(value) for value in (profile.get("category"), profile.get("city") or location) if value),
            "ratingValue": float(rating),
            "reviewsCount": reviews,
            "description": profile.get("description") or None,
            "mapImage": safe_asset(profile.get("main_image")) or None,
            "photoLabel": f"{profile.get('photos')} public photos" if isinstance(profile.get("photos"), int) else None,
        }
    gbp = None
    if graded_rows:
        gbp = {
            "panel": panel,
            "auditRows": graded_rows,
            "auditNote": str(gbp_source.get("auditNote") or "Every row describes public profile evidence."),
            "clientName": str(profile.get("name") or business),
            "note": "",
        }
    elements = []
    for item in website_checks:
        elements.append({
            "key": item.get("key") or None,
            "label": str(item.get("label") or "Website check"),
            "present": item.get("present") is True,
            "applies": item.get("applies") is not False,
            "consequence": str(item.get("consequence") or item.get("evidence") or "No detail returned."),
        })
    speed_source = cro.get("speed") if isinstance(cro.get("speed"), dict) else {}
    scores = speed_source.get("scores") if isinstance(speed_source.get("scores"), dict) else {}
    numeric_scores = [value for value in scores.values() if isinstance(value, (int, float))]
    speed = None
    if speed_source.get("ok") and numeric_scores:
        speed = {
            "lcp": str(speed_source.get("lcp") or "Not returned"),
            "score": round(sum(numeric_scores) / len(numeric_scores)),
            "scores": scores,
            "screenshot": safe_asset(speed_source.get("screenshot")) or None,
            "desktopScreenshot": safe_asset(speed_source.get("desktopScreenshot")) or None,
            "frames": [],
            "note": str(speed_source.get("note") or "Google Lighthouse mobile measurement."),
        }
    speed_note = "Rendered website and mobile Lighthouse evidence from this run."
    if speed_source and not speed_source.get("ok"):
        speed_note = f"Mobile speed not measured: {speed_source.get('why') or 'no result was returned'}."
    try:
        date_label = dt.date.fromisoformat(measured_at).strftime("%d %B %Y").lstrip("0")
    except ValueError:
        date_label = measured_at
    host = (urlparse(str(cro.get("url") or "")).hostname or "").removeprefix("www.")
    return {
        "slug": "private-audit",
        "language": "en",
        "clientName": business,
        "clientDomain": host,
        "clientFaviconUrl": "",
        "preparedBy": "Your freelancer",
        "preparedByCompany": "",
        "dateLabel": date_label,
        "expiryLabel": "",
        "heroLead": conclusion(total_value),
        "scorecard": {
            "overall": score_number(total_value),
            "overallReason": conclusion(total_value),
            "pillars": [],
        },
        "money": {},
        "cro": {
            "elements": elements,
            "have": sum(1 for item in elements if item["present"] and item["applies"]),
            "total": sum(1 for item in elements if item["applies"]),
            "speed": speed,
            "read": conclusion(website_value),
            "sourcesLine": speed_note,
        } if elements or speed else None,
        "findings": {
            "rows": [],
            "items": [],
            "serp": None,
            "visibility": None,
            "geoGrid": geo_grid,
            "gbp": gbp,
            "missing": [],
        },
        "timeline": {"rows": [], "expectation": ""},
        "investment": {"options": [], "terms": ""},
        "proof": {"items": [], "credentials": []},
        "faq": [],
        "close": {"costReminder": "", "ctaLabel": "Reply here on Upwork", "ctaUrl": "#reply"},
    }


def render(
    business: str,
    cro: dict[str, Any],
    search: dict[str, Any],
    measured_at: str,
    location: str = "",
    site: dict[str, Any] | None = None,
) -> str:
    if not TEMPLATE.is_file():
        raise RuntimeError(f"Lead magnet template is missing: {TEMPLATE}. Run npm run build in its parent directory.")
    template = TEMPLATE.read_text(encoding="utf-8")
    if template.count("__LEAD_MAGNET_DATA__") != 1:
        raise RuntimeError("Lead magnet template must contain one data placeholder.")
    payload = json.dumps(proposal_data(business, cro, search, measured_at, location, site), ensure_ascii=False, separators=(",", ":"))
    payload = payload.replace("</", "<\\/")
    page = template.replace("__LEAD_MAGNET_DATA__", payload)
    return page.replace("<title>Private website audit</title>", f"<title>Private website audit for {clean(business)}</title>")


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
