#!/usr/bin/env python3
"""Generate a fictional, self-contained lead-magnet example for a pitch page."""

from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path

from render_report import render


def example_evidence(business: str, service: str, conversion: str) -> tuple[dict, dict, dict]:
    category = business.removeprefix("Example ").strip() or "Service Company"
    service_path = "/" + "-".join(service.lower().split())
    cro = {
        "url": "",
        "elements": [
            {
                "label": f"Clear {conversion}",
                "present": True,
                "evidence": f"A clear {conversion} is visible on the homepage.",
            },
            {
                "label": "Fast mobile page",
                "present": False,
                "evidence": "The largest item appears after 5.2 seconds on mobile.",
            },
            {
                "label": "Proof near the next step",
                "present": False,
                "evidence": f"Reviews are not visible beside the {conversion}.",
            },
            {
                "label": "Service-area pages",
                "present": True,
                "evidence": "Dedicated pages explain the main services and towns covered.",
            },
        ],
        "speed": {"ok": True, "scores": {"performance": 61, "seo": 92}, "desktopScreenshot": ""},
    }
    search = {
        "geoGrid": {
            "keyword": service,
            "ranks": [1, 2, 8, 12, None] * 5,
            "requestedPoints": 25,
            "checkedPoints": 25,
            "winners": [
                {"name": f"Northside {category}", "domain": "Measured competitor"},
                {"name": f"City {category}", "domain": "Measured competitor"},
            ],
        },
        "gbp": {
            "auditRows": [
                {"label": "Phone", "value": "A public phone is listed.", "status": "good"},
                {"label": "Updates", "value": "No recent update was found.", "status": "warn"},
                {"label": "Booking link", "value": "No booking link was found.", "status": "bad"},
                {"label": "Reviews", "value": "Recent reviews describe the core service.", "status": "good"},
            ]
        },
    }
    site = {
        "pages": [
            {"path": "/", "title": "Homepage"},
            {"path": service_path, "title": service.title()},
            {"path": "/contact", "title": conversion.title()},
        ]
    }
    return cro, search, site


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--business", default="Example Roofing")
    parser.add_argument("--service", default="roof repair")
    parser.add_argument("--location", default="Austin, Texas")
    parser.add_argument("--conversion", default="estimate request")
    args = parser.parse_args()

    cro, search, site = example_evidence(args.business, args.service, args.conversion)
    page = render(
        args.business,
        cro,
        search,
        dt.date.today().isoformat(),
        args.location,
        site,
    )
    page = page.replace("Private local visibility audit", "Example local visibility audit")
    page = page.replace("Private audit for", "Example audit for")
    page = page.replace(
        "Pocket CEO operating heuristics",
        "the operating heuristics used for this audit",
    )
    if "Pocket CEO" in page or "https://" in page or "<script" in page:
        raise RuntimeError("demo report contains internal or external content")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(page, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
