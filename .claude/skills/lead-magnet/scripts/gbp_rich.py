#!/usr/bin/env python3
"""Fill genuinely missing public GBP detail with one exact Apify place pull.

The ordinary lead cache is the first source. This script is only called when
that compact object does not already contain public photos, review text and
owner updates. It never searches by business name and therefore cannot attach
the wrong listing to a report.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

try:
    from instrument import count_call, record_cost, step
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from instrument import count_call, record_cost, step


ACTOR = "compass~crawler-google-places"
API = "https://api.apify.com/v2"
# Refuse to start when the monthly balance is too low. A profile pull is cheap,
# but a run that hits the limit halfway through leaves incomplete evidence.
APIFY_MINDESTREST_USD = 3.0
UA = "Mozilla/5.0 (compatible; PocketCEOProfileEvidence/1.0)"


def token() -> str:
    return next((os.environ.get(name, "").strip() for name in (
        "APIFY_API_TOKEN_PAID", "APIFY_TOKEN", "APIFY_API_TOKEN",
    ) if os.environ.get(name, "").strip()), "")


def apify_leer(api_token: str) -> str:
    """Return an empty string when monthly budget remains, otherwise the reason."""
    if not api_token:
        return "no Apify token; the profile pull cannot run"
    try:
        with urllib.request.urlopen(urllib.request.Request(
                f"{API}/users/me?token={urllib.parse.quote(api_token)}",
                headers={"User-Agent": UA}), timeout=20) as response:
            plan = (json.loads(response.read() or b"{}").get("data") or {}).get("plan") or {}
    except Exception as error:  # noqa: BLE001 - no budget answer means no claim
        return f"could not verify the Apify budget: {error}"
    grenze = plan.get("maxMonthlyUsageUsd")
    genutzt = plan.get("monthlyUsageCreditsUsd")
    if grenze is None or genutzt is None:
        return "the Apify account did not return a monthly budget; verify it before running"
    rest = float(grenze) - float(genutzt)
    if rest < APIFY_MINDESTREST_USD:
        return (f"Apify has {rest:.2f} USD left of its {grenze} monthly budget, below the "
                f"{APIFY_MINDESTREST_USD:.0f} a run needs. Top it up or raise the cap.")
    return ""


def request(path: str, api_token: str, body: dict | None = None) -> dict | list:
    headers = {"Authorization": f"Bearer {api_token}", "User-Agent": UA}
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(
        f"{API}/{path}",
        data=json.dumps(body).encode() if body is not None else None,
        headers=headers,
    )
    with urllib.request.urlopen(req, timeout=90) as response:
        return json.loads(response.read().decode())


# A social page or a directory listing is not a website the report can audit;
# such a "website" resolves to no domain at all. Same list as prepare-event.py,
# which runs outside the engine and cannot import this module.
NOT_A_WEBSITE = (
    "facebook.com", "instagram.com", "linkedin.com", "twitter.com", "x.com", "tiktok.com",
    "youtube.com", "yell.com", "checkatrade.com", "trustpilot.com", "google.com", "goo.gl",
)


def domain_of(value: str) -> str:
    value = str(value or "").strip()
    if not value:
        return ""
    if "://" not in value:
        value = f"https://{value}"
    host = urllib.parse.urlparse(value).hostname or ""
    host = re.sub(r"^www\.", "", host, flags=re.I).casefold()
    if any(host == blocked or host.endswith("." + blocked) for blocked in NOT_A_WEBSITE):
        return ""
    return host


def run_actor(body: dict, api_token: str) -> list[dict]:
    count_call("apify/google-places-profile", tasks=1)
    with step("gbp_profile_start"):
        run = request(f"acts/{ACTOR}/runs", api_token, body)["data"]
    deadline = time.monotonic() + 240
    while time.monotonic() < deadline:
        time.sleep(5)
        status = request(f"actor-runs/{run['id']}", api_token)["data"]
        if status["status"] not in {"RUNNING", "READY"}:
            break
    else:
        raise RuntimeError("Apify Google profile pull timed out")
    if status["status"] != "SUCCEEDED":
        raise RuntimeError(f"Apify Google profile pull ended as {status['status']}")
    record_cost("apify/google-places-profile", status.get("usageTotalUsd") or 0)
    items = request(f"datasets/{status['defaultDatasetId']}/items?clean=true&format=json", api_token)
    return [item for item in items if isinstance(item, dict)]


def discover_by_website(domain: str, api_token: str, *, location: str = "", business: str = "") -> dict:
    """Resolve one exact public profile from a website, without guessing a business type.

    Identity is always the website. A supplied town only narrows which of the
    exact-website profiles is meant; when the town has no such profile the call
    fails with the locations it did find instead of picking one (Leon, 03.09.2026:
    the audit ran on the Southport branch, the owner meant Flint). The business
    name widens the Maps search when a town is known, never the match.
    """
    expected = domain_of(domain)
    search_strings = [expected]
    if business and location:
        search_strings.append(f"{business} {location}")
    items = run_actor({
        "searchStringsArray": search_strings,
        "maxCrawledPlacesPerSearch": 20,
        "scrapePlaceDetailPage": True,
        "scrapeContacts": False,
        "maxReviews": 6,
        "reviewsSort": "newest",
        "maxImages": 12,
        "includeWebResults": False,
        "language": "en",
    }, api_token)
    matches = [item for item in items if domain_of(item.get("website")) == expected]
    unique = {str(item.get("placeId") or item.get("cid") or index): item for index, item in enumerate(matches)}
    matches = list(unique.values())
    if not matches:
        raise RuntimeError(f"Apify found no Google profile whose public website is {expected}")
    if location:
        needle = location.casefold()
        located = [item for item in matches if needle in " ".join(str(item.get(key) or "") for key in ("address", "city", "neighborhood", "state")).casefold()]
        if not located:
            labels = "; ".join(f"{item.get('title') or 'Unnamed'} - {item.get('address') or item.get('city') or 'location unknown'}" for item in matches[:5])
            raise RuntimeError(f"No Google profile with website {expected} in {location}; found: {labels}. Pass the confirmed place ID for the intended branch.")
        matches = located
    if len(matches) > 1:
        labels = "; ".join(f"{item.get('title') or 'Unnamed'} - {item.get('address') or item.get('city') or 'location unknown'}" for item in matches[:5])
        raise RuntimeError(f"Multiple Google profiles use {expected}; pass a location or confirmed place ID. Matches: {labels}")
    return merge({}, matches[0])


def discover_by_place_id(place_id: str, api_token: str) -> dict:
    items = run_actor({
        "placeIds": [place_id],
        "scrapePlaceDetailPage": True,
        "scrapeContacts": False,
        "maxReviews": 6,
        "reviewsSort": "newest",
        "maxImages": 12,
        "includeWebResults": False,
        "language": "en",
    }, api_token)
    if len(items) != 1 or str(items[0].get("placeId") or "") != place_id:
        raise RuntimeError("Apify profile response did not match the confirmed place ID")
    return merge({}, items[0])


def discover_by_maps_url(maps_url: str, api_token: str) -> dict:
    items = run_actor({
        "startUrls": [{"url": maps_url}],
        "scrapePlaceDetailPage": True,
        "scrapeContacts": False,
        "maxReviews": 6,
        "reviewsSort": "newest",
        "maxImages": 12,
        "includeWebResults": False,
        "language": "en",
    }, api_token)
    if len(items) != 1 or not items[0].get("placeId"):
        raise RuntimeError("Apify did not resolve the Google Maps URL to one exact profile")
    return merge({}, items[0])


def is_rich(profile: dict) -> bool:
    return bool(profile.get("rich_evidence") or (
        profile.get("image_urls")
        and profile.get("review_items")
        and profile.get("opening_hours")
        and "owner_updates" in profile
    ))


def review_items(raw: dict) -> list[dict]:
    result = []
    for review in raw.get("reviews") or []:
        if not isinstance(review, dict):
            continue
        author = review.get("name") or review.get("reviewerName") or review.get("author")
        text = review.get("text") or review.get("reviewText") or review.get("description")
        if not author or not text:
            continue
        owner = review.get("responseFromOwnerText") or review.get("ownerResponse") or review.get("reviewResponse")
        if isinstance(owner, dict):
            owner = owner.get("text") or owner.get("comment")
        result.append({
            "author": str(author),
            "rating": review.get("stars") or review.get("rating") or 0,
            "when": review.get("publishedAtDate") or review.get("relativePublishTimeDescription") or review.get("publishedAt") or "",
            "text": str(text),
            "owner_response": str(owner) if owner else None,
        })
    return result[:6]


def owner_updates(raw: dict) -> list[dict]:
    result = []
    for update in raw.get("ownerUpdates") or []:
        if not isinstance(update, dict) or not update.get("text"):
            continue
        result.append({
            "date": update.get("date") or "",
            "text": str(update["text"]),
            "image_url": update.get("imageUrl"),
            "button_text": update.get("buttonText"),
            "button_link": update.get("buttonLink"),
        })
    return result[:3]


def booking_links(raw: dict) -> list[str]:
    values = [
        *(raw.get("bookingLinks") or []),
        *(raw.get("tableReservationLinks") or []),
        raw.get("reserveTableUrl"),
    ]
    result = []
    for value in values:
        href = value if isinstance(value, str) else (value or {}).get("url") or (value or {}).get("link")
        if isinstance(href, str) and href.startswith("http") and href not in result:
            result.append(href)
    return result[:3]


def merge(profile: dict, raw: dict) -> dict:
    location = raw.get("location") if isinstance(raw.get("location"), dict) else {}
    images = []
    for value in [raw.get("imageUrl"), *(raw.get("imageUrls") or [])]:
        if isinstance(value, str) and value.startswith("http") and value not in images:
            images.append(value)
    categories = [str(value) for value in (raw.get("categories") or []) if value]
    coordinate = profile.get("coordinate")
    if location.get("lat") is not None and location.get("lng") is not None:
        coordinate = f"{location['lat']},{location['lng']}"
    measured_fields = set(profile.get("measured_fields") or [])
    field_sources = {
        "place_id": ("placeId",),
        "name": ("title",),
        "category": ("categoryName",),
        "categories": ("categories", "categoryName"),
        "reviews": ("reviewsCount",),
        "rating": ("totalScore",),
        "photos": ("imagesCount",),
        "description": ("ownerDescription", "description"),
        "is_claimed": ("claimThisBusiness",),
        "service_area_business": ("isServiceAreaBusiness", "serviceArea", "serviceAreas"),
        "address": ("address",),
        "city": ("city",),
        "country_code": ("countryCode",),
        "coordinate": ("location",),
        "opening_hours": ("openingHours",),
        "website": ("website",),
        "phone": ("phone",),
        "review_items": ("reviews",),
        "owner_updates": ("ownerUpdates",),
        "owner_update_count": ("ownerUpdates",),
        "booking_links": ("bookingLinks", "tableReservationLinks", "reserveTableUrl"),
        "attributes": ("additionalInfo", "attributes"),
        "service_items": ("services", "serviceItems"),
    }
    measured_fields.update(key for key in field_sources if key in profile)
    measured_fields.update(
        field for field, raw_keys in field_sources.items()
        if any(raw_key in raw for raw_key in raw_keys)
    )
    merged = {
        **profile,
        "place_id": raw.get("placeId") or profile.get("place_id"),
        "name": raw.get("title") or profile.get("name"),
        "category": raw.get("categoryName") or profile.get("category"),
        "categories": categories or profile.get("categories") or [],
        "category_count": len(categories or profile.get("categories") or []),
        "reviews": raw.get("reviewsCount") if raw.get("reviewsCount") is not None else profile.get("reviews"),
        "rating": raw.get("totalScore") if raw.get("totalScore") is not None else profile.get("rating"),
        "photos": raw.get("imagesCount") if raw.get("imagesCount") is not None else profile.get("photos"),
        "description": raw.get("ownerDescription") or raw.get("description") or profile.get("description"),
        "is_claimed": not bool(raw.get("claimThisBusiness")) if "claimThisBusiness" in raw else profile.get("is_claimed"),
        "service_area_business": bool(raw.get("isServiceAreaBusiness") or raw.get("serviceArea") or raw.get("serviceAreas") or profile.get("service_area_business")),
        "address": raw.get("address") or profile.get("address"),
        "city": raw.get("city") or profile.get("city"),
        "country_code": raw.get("countryCode") or profile.get("country_code"),
        "coordinate": coordinate,
        "hours": "available" if raw.get("openingHours") else profile.get("hours"),
        "opening_hours": raw.get("openingHours") or profile.get("opening_hours") or [],
        "website": raw.get("website") or profile.get("website"),
        "phone": raw.get("phone") or profile.get("phone"),
        "main_image": raw.get("imageUrl") or profile.get("main_image"),
        "image_urls": images or profile.get("image_urls") or [],
        "photo_categories": raw.get("imageCategories") or profile.get("photo_categories") or [],
        "review_items": review_items(raw) or profile.get("review_items") or [],
        "owner_updates": owner_updates(raw) or profile.get("owner_updates") or [],
        "booking_links": booking_links(raw) or profile.get("booking_links") or [],
        "review_topics": raw.get("reviewsTags") or profile.get("review_topics") or [],
        "owner_update_count": len(raw.get("ownerUpdates") or profile.get("owner_updates") or []),
        "market_hint": "local",
        "market_reason": "Confirmed local Google profile with coordinates",
        "rich_evidence": True,
        "measured_fields": sorted(measured_fields),
    }
    return {key: value for key, value in merged.items() if value is not None}


def enrich(profile: dict, api_token: str) -> dict:
    if is_rich(profile):
        return profile
    place_id = str(profile.get("place_id") or "").strip()
    if not place_id:
        raise RuntimeError("Rich profile pull requires a confirmed place_id")
    body = {
        "placeIds": [place_id],
        "scrapePlaceDetailPage": True,
        "scrapeContacts": False,
        "maxReviews": 6,
        "reviewsSort": "newest",
        "maxImages": 12,
        "includeWebResults": False,
        "language": "en",
    }
    items = run_actor(body, api_token)
    if len(items) != 1 or items[0].get("placeId") != place_id:
        raise RuntimeError("Apify rich profile response did not match the confirmed place_id")
    return merge(profile, items[0])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile-json")
    parser.add_argument("--discover-domain")
    parser.add_argument("--place-id")
    parser.add_argument("--location", default="")
    args = parser.parse_args()
    api_token = token()
    # Check budget first. Starting near the monthly limit risks an incomplete report.
    leer = apify_leer(api_token)
    if leer:
        raise SystemExit(f"Refusing to start: {leer}")
    if args.discover_domain:
        if not api_token:
            raise RuntimeError("APIFY token is required to discover a Google profile from a website")
        print(json.dumps(discover_by_website(args.discover_domain, api_token, location=args.location), ensure_ascii=False))
        return 0
    if args.place_id:
        if not api_token:
            raise RuntimeError("APIFY token is required to fetch a Google profile")
        print(json.dumps(discover_by_place_id(args.place_id, api_token), ensure_ascii=False))
        return 0
    if not args.profile_json:
        parser.error("one of --profile-json, --discover-domain or --place-id is required")
    profile = json.loads(Path(args.profile_json).read_text())
    if is_rich(profile):
        print(json.dumps(profile, ensure_ascii=False))
        return 0
    if not api_token:
        print(json.dumps(profile, ensure_ascii=False))
        return 0
    print(json.dumps(enrich(profile, api_token), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, OSError, KeyError, json.JSONDecodeError, urllib.error.URLError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
