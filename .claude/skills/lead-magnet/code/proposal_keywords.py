#!/usr/bin/env python3
"""Choose the three search insights for /proposal without giving away a full map.

One run gathers site, Business Profile and ranking vocabulary, selects up to
four source-diverse seeds, expands them, records every deterministic drop,
checks the three strongest survivors on one live SERP each, then stores separate
money and map selections for pull_search.py.  The cache is an audit trail, not a
human gate.
"""
from __future__ import annotations

import argparse
import json
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable

from pull_search import get as dfs_get
from pull_search import post

DIRECTORY_HOSTS = (
    "reddit.", "youtube.", "linkedin.", "facebook.", "instagram.", "tiktok.",
    "quora.", "medium.", "wikipedia.", "yelp.", "clutch.co", "g2.com",
    "trustpilot.", "indeed.", "glassdoor.", "capterra.", "upwork.com",
    "fiverr.com", "thumbtack.", "angi.com", "houzz.", "designrush.",
    "goodfirms.", "sortlist.", "expertise.com",
)
STOPWORDS = {
    "a", "an", "and", "at", "by", "der", "die", "das", "den", "des", "ein",
    "eine", "einer", "for", "fur", "für", "im", "in", "mit", "of", "on", "the",  # multilingual-data
    "to", "und", "von", "your", "you", "wir", "our", "us",  # multilingual-data
}
JUNK = {
    "job", "jobs", "career", "careers", "salary", "salaries", "gehalt", "karriere",
    "stellenangebot", "ausbildung", "degree", "studium", "book", "buch", "books",
    "diy", "selber", "selbst machen", "tool", "tools", "software download", "free",  # multilingual-data
    "kostenlos", "gratis", "supplier", "suppliers", "wholesale", "wholesaler",
    # People training to do the job themselves, not people hiring somebody to do
    # it. Measured 01.09.2026 on a nutrition practice: with volume data restored,
    # the three strongest survivors were "ernaehrungsberater fernstudium",
    # German training terms can have real demand but target the wrong buyer.
    # and it would have become the page's money search.
    "fernstudium", "fernlehrgang", "studieren", "weiterbildung", "umschulung",
    "lehrgang", "praktikum", "certification", "become a", "become an",
}
INFO_MARKERS = (
    "how ", "what ", "why ", "guide", "definition", "meaning", "wikipedia",
    "wie ", "was ", "warum ", "ratgeber", "erklart", "erklärt",  # multilingual-data
)
REMOTE_MARKERS = (
    "online", "remote", "virtual", "worldwide", "global", "international",
    "onlinekurs", "online coaching", "virtuell", "weltweit", "international",
)
NATIONAL_MARKERS = (
    "nationwide", "countrywide", "across the uk", "across germany", "uk-wide",
    "bundesweit", "deutschlandweit", "österreichweit", "schweizweit",  # multilingual-data
)
LOCAL_CATEGORY_MARKERS = (
    "plumber", "electrician", "roofer", "dentist", "clinic", "restaurant",
    "salon", "barber", "locksmith", "hvac", "heating", "boiler", "cleaner",
    "landscaper", "physiotherapist", "chiropractor", "garage", "mechanic",
    "klempner", "installateur", "elektriker", "dachdecker", "zahnarzt",
    "praxis", "restaurant", "friseur", "schlüsseldienst", "heizung",  # multilingual-data
    "reinigung", "physiotherapie", "werkstatt",
)
NONLOCAL_CATEGORY_MARKERS = (
    "business", "consultant", "consulting", "coach", "training", "software",
    "marketing", "advertising", "manufacturer", "wholesaler", "e-commerce",
    "unternehmensberatung", "berater", "coaching", "seminar", "software",
    "marketing", "werbung", "hersteller", "großhandel",  # multilingual-data
)
VAGUE_SEED_TOKENS = {
    "better", "business", "businesses", "company", "companies", "future",
    "grow", "growth", "help", "leader", "leaders", "people", "solution",
    "solutions", "success", "welcome",
}


def folded(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.casefold())
    return "".join(ch for ch in text if not unicodedata.combining(ch))


NEAR_ME_MARKERS = ("near me", "close by me", "closest to me", "nearby", "in my area", "in meiner nahe", "in der nahe")
GENERIC_TAIL = {"shop", "store", "service", "servic", "company", "compani", "local", "best", "top", "cheap", "emergency", "hour", "hours", "the"}


def near_me(keyword: str) -> bool:
    """Google's synthetic "near me" variants measure the same intent as the bare term.

    "locksmith close to me", "locksmith near by me", "nearby": all of them.
    """
    text = folded(keyword)
    if any(marker in text for marker in NEAR_ME_MARKERS):
        return True
    return bool(re.search(r"\b(near|close|closest|nearby|nearest)\b", text)) and bool(re.search(r"\b(me|my|by)\b", text))


def brand_words(text: str) -> set[str]:
    """Name words down to two letters, so "VB" in "VB Locksmith Services" counts."""
    return {word for word in re.findall(r"[a-z0-9]+", folded(text)) if len(word) >= 2 and word not in STOPWORDS}


def own_brand(keyword: str, business: str, family: set[str] | None = None) -> bool:
    """The business's own name is not a search the report should measure against.

    Only the distinctive part of the name counts: "vb" in "VB Locksmith
    Services", "fineprint" in "FINEPRINT HK". "locksmith" alone is the trade,
    not the brand (it was dropped as a brand on 05.09.2026).
    """
    trade = {word for word in (family or set())} | GENERIC_TAIL
    distinctive = {
        word for word in brand_words(business or "")
        if word not in trade and (len(word) < 3 or tokens(word) - trade)
    }
    return bool(distinctive) and bool(brand_words(keyword) & distinctive)


JUNK_SEED = re.compile(r"\b(404|not found|blocked|error|forbidden|page not|access denied|just a moment)\b", re.I)


def category_like(keyword: str, family: set[str], seed: str | None = None, primary: str | None = None) -> bool:
    """Every meaningful word belongs to the trade's own vocabulary, or Google
    suggested the term for the category itself and it reads like a service.

    "coffee shop" for a cafe: yes, even when the site scrape gave no words
    (FINEPRINT's contact pages were 404s, 05.09.2026). "tram view cafe" or
    "moonary coffee": no, those are other people's names.
    """
    words = tokens(keyword) - GENERIC_TAIL
    if words and words <= family:
        return True
    if seed and primary and folded(seed) == folded(primary):
        # Suggested for the category: at most one word we do not know, and the
        # term is either a single word or carries a generic service tail.
        # "coffee shop": one unknown word plus "shop", accepted. "tram view
        # cafe" and "moonary coffee": two unknown words, names.
        raw = set(re.findall(r"[a-z0-9]+", folded(keyword)))
        unknown = words - family
        return len(unknown) <= 1 and (len(raw) == 1 or bool(raw & GENERIC_TAIL))
    return False


def tokens(text: str) -> set[str]:
    out = set()
    for raw in re.findall(r"[a-z0-9]+", folded(text)):
        if len(raw) < 3 or raw in STOPWORDS:
            continue
        # Light stemming only for overlap. It joins training/trainings and
        # Fuehrungskraft/Fuehrungskraefte without pretending to be a language model.
        raw = re.sub(r"(ern|en|er|es|e|s)$", "", raw) if len(raw) > 5 else raw
        out.add(raw)
    return out


def lab_rows(payload: dict, source: str, seed: str) -> list[dict]:
    items = ((payload.get("tasks") or [{}])[0].get("result") or [{}])[0].get("items") or []
    rows = []
    for item in items:
        kd = item.get("keyword_data") or item
        keyword = kd.get("keyword")
        info = kd.get("keyword_info") or {}
        if keyword:
            rows.append({
                "keyword": keyword.strip(), "volume": info.get("search_volume"),
                "cpc": info.get("cpc"), "source": source, "seed": seed,
            })
    return rows


def filter_candidates(rows: list[dict], context_phrases: list[str],
                      market: str, excluded_places: list[str], known_places: list[str] | None = None,
                      served_places: list[str] | None = None) -> tuple[list[dict], list[dict]]:
    context = set().union(*(tokens(p) for p in context_phrases))
    excluded = [folded(p) for p in excluded_places]
    known = sorted({folded(p) for p in (known_places or []) if p}, key=len, reverse=True)
    served = {folded(p) for p in (served_places or []) if p}
    protected = set().union(*(tokens(p) for p in context_phrases))
    kept, dropped, seen = [], [], set()
    for row in rows:
        keyword = row["keyword"].strip()
        key = folded(keyword)
        if key in seen:
            dropped.append({**row, "reason": "duplicate"})
            continue
        seen.add(key)
        junk = next((j for j in sorted(JUNK, key=lambda value: (-len(value), value))
                     if re.search(rf"(?<![a-z0-9]){re.escape(folded(j))}(?![a-z0-9])", key)
                     and not (tokens(j) & protected)), None)
        if junk:
            dropped.append({**row, "reason": f"junk intent: {junk}"})
            continue
        overlap = tokens(keyword) & context
        if not overlap:
            dropped.append({**row, "reason": "off-business: no service/category token in common"})
            continue
        wrong = next((p for p in excluded if p and p in key), None) if market == "local" else None
        if market == "local" and not wrong:
            # Mask the served places first, then scan for foreign ones. Without
            # the mask "Locksmith Haywards Heath" was dropped as "wrong place:
            # heath" because the taxonomy also knows a place called Heath, and
            # the report fell back to a bare "locksmith" grid (Page Security,
            # 05.09.2026).
            scan = key
            for place in sorted(served, key=len, reverse=True):
                scan = re.sub(rf"(?<![a-z0-9]){re.escape(place)}(?![a-z0-9])", " ", scan)
            wrong = next((place for place in known
                          if place not in served
                          and re.search(rf"(?<![a-z0-9]){re.escape(place)}(?![a-z0-9])", scan)), None)
        if wrong:
            dropped.append({**row, "reason": f"wrong place: {wrong}"})
            continue
        kept.append({**row, "noVolumeData": row.get("volume") is None})
    return kept, dropped


def rank_candidates(rows: list[dict], market: str) -> list[dict]:
    # One job value applies to the whole proposal, so it cannot distinguish
    # local keywords. CPC is only a private advertiser-bid signal; volume breaks
    # ties. National/remote uses volume as an order-of-magnitude ordering signal.
    if market == "local":
        # The bid signal leads, but it needs a floor under it. Measured
        # 01.09.2026 on a nutrition practice: "stoffwechselanalyse krankenkasse
        # tk" (20 searches a month, CPC 7.04) outranked "ernaehrungsberatung
        # muenchen" (1,000 a month, CPC 3.04) and became the money search - a
        # page built on a term fifty times rarer than the one the town actually
        # types. So anything under a tenth of the best measured demand ranks
        # after the rest, and CPC decides everything above that line, which is
        # the original intent: bid signal first, volume only as the tiebreak.
        best = max((r.get("volume") or 0) for r in rows) if rows else 0
        floor = best / 10
        return sorted(rows, key=lambda r: ((r.get("volume") or 0) < floor,
                                           -(r.get("cpc") or 0), -(r.get("volume") or -1),
                                           r["keyword"]))
    return sorted(rows, key=lambda r: (-(r.get("volume") or -1), -(r.get("cpc") or 0), r["keyword"]))


def inspect_serp(keyword: str, payload: dict, domain: str, volume=None, cpc=None) -> dict:
    problem = labs_problem(payload)
    if problem:
        raise RuntimeError(f"SERP task refused: {problem}")
    result = ((payload.get("tasks") or [{}])[0].get("result") or [{}])[0]
    items = result.get("items") or []
    organic = [i for i in items if i.get("type") == "organic"][:10]
    own = domain.replace("www.", "")
    position = next((i.get("rank_group") for i in organic
                     if own in (i.get("domain") or "").replace("www.", "")), None)
    directories = 0
    supplier_pages = 0
    for item in organic:
        host = (item.get("domain") or "").casefold()
        text = f"{item.get('title') or ''} {item.get('description') or ''}".casefold()
        if any(skip in host for skip in DIRECTORY_HOSTS):
            directories += 1
        elif not any(marker in text for marker in INFO_MARKERS):
            supplier_pages += 1
    paid = sum(1 for i in items if i.get("type") in {"paid", "google_ads"})
    has_map = any(i.get("type") in {"local_pack", "maps", "map"} for i in items)
    return {
        "keyword": keyword, "volume": volume, "cpc": cpc,
        "clientPosition": position, "hasLocalPack": has_map,
        "supplierPages": supplier_pages, "directoryPages": directories,
        "paidResults": paid,
        "eligibleMoney": supplier_pages >= 6 and directories + paid < 6,
        "resultItems": items,
    }


def volume_band(value) -> str:
    if value is None:
        return "volume not reported"
    if value < 10:
        return "fewer than 10 searches reported"
    if value < 100:
        return "tens of searches a month"
    if value < 1000:
        return "hundreds of searches a month"
    return "more than 1,000 searches a month"


def names_a_business(row: dict) -> bool:
    """Is this keyword somebody's company name rather than a service people search for?

    Measured 01.09.2026 on a Fort Lauderdale locksmith: `mapKeyword` came back as
    "keyme locksmiths", a direct competitor's brand. Nobody ranks for a rival's name, so
    the twenty-five-point grid came back empty and the page claimed total invisibility
    that was not real. Shown to the owner that is the finding that ends the meeting,
    because he knows his phone rings.

    The tell is in the SERP we already fetched: on a brand query the top map result IS
    the brand, so its title and the keyword collapse onto each other once punctuation
    and spacing are removed. A genuine service term ("locksmith near me") never matches
    a single business title that way.
    """
    raw_keyword = folded(row.get("keyword") or "")
    keyword = re.sub(r"[^a-z0-9]", "", raw_keyword)
    keyword_words = re.findall(r"[a-z0-9]+", raw_keyword)
    if not keyword:
        return False
    for item in row.get("resultItems") or []:
        if item.get("type") not in {"local_pack", "maps", "map"}:
            continue
        for candidate in (item.get("title"), *(e.get("title") for e in item.get("items") or []
                                               if isinstance(e, dict))):
            title = re.sub(r"[^a-z0-9]", "", folded(str(candidate or "")))
            if len(title) < 5:
                continue
            if title == keyword or (
                len(keyword_words) >= 2 and (title in keyword or keyword in title)
            ):
                return True
    return False


def usable_seed(phrase: str) -> bool:
    """Reject slogans that name an outcome but no saleable service."""
    words = {word for word in re.findall(r"[a-z0-9]+", folded(phrase))
             if len(word) >= 3 and word not in STOPWORDS}
    return bool(words and not words.issubset(VAGUE_SEED_TOKENS))


def primary_category_location_query(cache: dict) -> str | None:
    """Build the local map term from the GBP primary category and profile city."""
    category = str(
        cache.get("primaryCategory")
        or next(iter(cache.get("gbpCategories") or []), "")
    ).strip()
    location_parts = [
        part.strip() for part in str(cache.get("location") or "").split(",")
        if part.strip()
    ]
    city = str(
        cache.get("profileCity")
        or (location_parts[0] if len(location_parts) > 1 else "")
    ).strip()
    if not category or not city:
        return None
    if tokens(city).issubset(tokens(category)):
        return category
    return f"{category} {city}"


def infer_market(cro: dict, profile: dict | None, explicit: str | None = None) -> tuple[str, str]:
    """Declare the market before expansion from evidence already in the run."""
    if explicit:
        return explicit, "set by the proposal run"
    phrases = [row.get("phrase", "") for row in cro.get("seedCandidates", [])]
    profile = profile or {}
    haystack = folded(" ".join([
        *phrases,
        str(profile.get("description") or ""),
        str(profile.get("category") or ""),
        *[str(value) for value in (profile.get("additional_categories") or [])],
    ]))
    remote = next((marker for marker in REMOTE_MARKERS if folded(marker) in haystack), None)
    if remote:
        return "remote", f"site/profile says '{remote}'"
    national = next((marker for marker in NATIONAL_MARKERS if folded(marker) in haystack), None)
    if national:
        return "national", f"site/profile says '{national}'"
    category_text = folded(" ".join([
        str(profile.get("category") or ""),
        *[str(value) for value in (profile.get("additional_categories") or [])],
    ]))
    local_category = next((marker for marker in LOCAL_CATEGORY_MARKERS
                           if folded(marker) in category_text), None)
    if local_category:
        return "local", f"Business Profile category contains '{local_category}'"
    city = str((profile.get("address_info") or {}).get("city") or "").strip()
    if city and folded(city) in haystack:
        return "local", f"site/profile vocabulary names {city}"
    has_location = bool(profile.get("address") or city or profile.get("latitude"))
    nonlocal_category = next((marker for marker in NONLOCAL_CATEGORY_MARKERS
                              if folded(marker) in category_text), None)
    if has_location and not nonlocal_category:
        return "local", "Business Profile describes a located service without a national/remote signal"
    return "national", "no local-service or remote-delivery signal was found"


def labs_problem(payload: dict) -> str | None:
    """A DataForSEO task that refuses its own input answers HTTP 200 with an
    error inside the task, so `post` never raises and `result` is simply empty.
    Reading that as "no data" is how a broken pull passes for a finished one."""
    task = (payload.get("tasks") or [{}])[0]
    status = task.get("status_code")
    if status is None or status == 20000:
        return None
    return f"{status} {task.get('status_message')}"


def resolve_serp_location(
    requested: str,
    locations: list[dict],
    *,
    country_code: str | None = None,
) -> str:
    """Return the exact SERP location name DataForSEO publishes.

    Labs accepts a country, while live SERPs require the complete taxonomy
    name. For example, the human shorthand ``Liverpool,United Kingdom`` must
    become ``Liverpool,England,United Kingdom``. The taxonomy call is already
    part of local keyword filtering, so this adds no paid request.
    """
    wanted = [part.strip() for part in requested.split(",") if part.strip()]
    if not wanted:
        return requested
    wanted_city = folded(wanted[0])
    wanted_country = folded(wanted[-1])
    wanted_iso = (country_code or "").strip().casefold()
    candidates: list[str] = []
    for row in locations:
        name = str(row.get("location_name") or "").strip()
        parts = [part.strip() for part in name.split(",") if part.strip()]
        if not name or not parts or folded(parts[0]) != wanted_city:
            continue
        row_iso = str(row.get("country_iso_code") or "").strip().casefold()
        if wanted_iso and row_iso and row_iso != wanted_iso:
            continue
        if wanted_country and folded(parts[-1]) != wanted_country:
            continue
        if row.get("location_type") not in {None, "City", "Municipality", "District", "Neighborhood"}:
            continue
        candidates.append(name)
    if not candidates:
        return requested
    exact = next((name for name in candidates if folded(name) == folded(requested)), None)
    return exact or min(candidates, key=lambda name: (name.count(","), len(name), name))


def discover(a, call: Callable = post) -> dict:
    cro = json.loads(Path(a.cro).read_text())
    errors = []
    spend = 0
    ranked = call("dataforseo_labs/google/ranked_keywords/live", [{
        "target": a.domain, "location_name": a.location, "language_name": a.language,
        "limit": 20, "order_by": ["keyword_data.keyword_info.search_volume,desc"],
    }])
    spend += ranked.get("cost", 0)
    problem = labs_problem(ranked)
    if problem:
        raise RuntimeError(f"ranked keywords refused: {problem}")
    ranking_rows = lab_rows(ranked, "ranking", "")
    categories = []
    profile = None
    if getattr(a, "profile_json", None):
        summary = json.loads(Path(a.profile_json).read_text())
        categories = list(dict.fromkeys(
            category for category in (
                summary.get("category"), *(summary.get("categories") or [])
            )
            if isinstance(category, str) and category.strip()
        ))
        coordinate = str(summary.get("coordinate") or "").split(",")
        profile = {
            "category": summary.get("category"),
            "additional_categories": categories[1:],
            "address": summary.get("address"),
            "address_info": {
                "city": summary.get("city"),
                "country_code": summary.get("country_code"),
            },
            "latitude": coordinate[0] if len(coordinate) == 2 else None,
        }
    elif a.business:
        try:
            profile_payload = call("business_data/google/my_business_info/live", [{
                "keyword": a.business, "location_name": a.location, "language_name": a.language,
            }])
            spend += profile_payload.get("cost", 0)
            profile_items = ((profile_payload.get("tasks") or [{}])[0].get("result") or [{}])[0].get("items") or []
            profile = profile_items[0] if profile_items else None
        except (Exception, SystemExit) as error:
            errors.append(f"Business Profile categories failed: {str(error)[:160]}")
        if profile:
            raw_categories = [profile.get("category"), *(profile.get("additional_categories") or [])]
            categories = [
                (c.get("title") or c.get("name")) if isinstance(c, dict) else c
                for c in raw_categories
            ]
            categories = [c for c in categories if isinstance(c, str) and c.strip()]

    primary_category = categories[0] if categories else None
    evidence = [
        {"phrase": row.get("phrase"), "source": "website", "detail": row.get("source"), "page": row.get("page")}
        for row in cro.get("seedCandidates", []) if row.get("phrase")
    ]
    evidence += [{"phrase": c, "source": "google business profile"} for c in categories]
    evidence += [{"phrase": r["keyword"], "source": "existing ranking"} for r in ranking_rows[:8]]
    # Source diversity is the point of automatic selection. Taking the first four rows
    # simply returned four page headings and silently dropped the GBP/ranking
    # correction the engine was built to add.
    suggested, seen = [], set()
    buckets = {
        source: [row for row in evidence if row["source"] == source]
        for source in ("website", "google business profile", "existing ranking")
    }
    order = ["website", "google business profile", "existing ranking", "website"]
    for source in order:
        for row in buckets[source]:
            key = folded(row["phrase"])
            if key not in seen and usable_seed(row["phrase"]):
                seen.add(key)
                suggested.append(row["phrase"])
                break
        if len(suggested) == 4:
            break
    market, market_reason = infer_market(cro, profile, getattr(a, "market", None))
    address_info = (profile or {}).get("address_info") or {}
    return {
        "stage": "seeds_selected", "domain": a.domain,
        "location": a.location, "language": a.language, "business": a.business,
        "seedEvidence": evidence, "selectedSeeds": suggested,
        "gbpCategories": categories, "primaryCategory": primary_category,
        "rankedCandidates": ranking_rows,
        "market": market, "marketReason": market_reason,
        "profileCity": address_info.get("city"),
        "countryCode": address_info.get("country_code"),
        "cro": a.cro, "errors": errors, "spend": round(spend, 4),
    }


def expand(a, cache: dict, call: Callable = post, get_call: Callable = dfs_get) -> dict:
    supplied = getattr(a, "seeds", None) or cache.get("selectedSeeds") or []
    # Error-page titles and the business's own name are not service seeds:
    # "404 Not Found - FINEPRINT" and "FINEPRINT HK" pulled a brand cloud and
    # nothing about coffee (05.09.2026). The primary category always seeds.
    business_seed_name = str(cache.get("business") or "")
    primary_seed = str(cache.get("primaryCategory") or "").strip()
    seeds = list(dict.fromkeys(
        s.strip() for s in supplied
        if s.strip() and not JUNK_SEED.search(s)
        and not (own_brand(s, business_seed_name) and not (tokens(s) - brand_words(business_seed_name)))
    ))
    if primary_seed and folded(primary_seed) not in {folded(s) for s in seeds}:
        seeds.insert(0, primary_seed)
    seeds = seeds[:4]
    market = getattr(a, "market", None) or cache.get("market") or "national"
    if not seeds:
        note = "No usable service seed was found in the site, Business Profile or rankings."
        return {
            **cache, "stage": "complete", "market": market, "selectedSeeds": [],
            "candidates": [], "dropped": [], "searches": [], "themes": [],
            "moneyKeyword": None, "mapKeyword": None, "selectionNote": note,
            "errors": [*(cache.get("errors") or []), note],
        }

    def one(seed_endpoint):
        seed, endpoint = seed_endpoint
        body = {"keyword": seed, "location_name": cache["location"],
                "language_name": cache["language"], "limit": 40}
        if endpoint == "related_keywords":
            body["depth"] = 2
        try:
            response = call(f"dataforseo_labs/google/{endpoint}/live", [body])
        except (Exception, SystemExit) as error:
            return {}, endpoint, seed, str(error)[:160]
        task = (response.get("tasks") or [{}])[0]
        status = task.get("status_code")
        if status is None or status == 20000:
            return response, endpoint, seed, None
        problem = f"{status} {task.get('status_message')} at '{cache['location']}'"
        return {}, endpoint, seed, f"{problem} for '{seed}'"

    jobs = [(seed, endpoint) for seed in seeds for endpoint in ("keyword_suggestions", "related_keywords")]
    with ThreadPoolExecutor(max_workers=min(8, len(jobs))) as pool:
        pulled = list(pool.map(one, jobs))
    failures = [error for _, _, _, error in pulled if error]
    if failures:
        raise RuntimeError(f"keyword expansion refused: {failures[0]}")
    spend = sum(payload.get("cost", 0) for payload, _, _, _ in pulled)
    errors = list(cache.get("errors") or [])
    rows = []
    for payload, endpoint, seed, error in pulled:
        if error:
            errors.append(f"{endpoint} failed for '{seed}': {error}")
        rows.extend(lab_rows(payload, endpoint, seed))
    measured = {folded(row["keyword"]) for row in rows}
    # Add an automatically selected seed only when neither endpoint returned it. The
    # old order added the metric-less seed first and then discarded its measured
    # twin as a duplicate, quietly losing volume and CPC for the core term.
    rows.extend({"keyword": seed, "volume": None, "cpc": None,
                 "source": "selected seed", "seed": seed}
                for seed in seeds if folded(seed) not in measured)

    preferred_map_keyword = (
        primary_category_location_query(cache) if market == "local" else None
    )
    if preferred_map_keyword and folded(preferred_map_keyword) not in {
        folded(row["keyword"]) for row in rows
    }:
        rows.append({
            "keyword": preferred_map_keyword,
            "volume": None,
            "cpc": None,
            "source": "google business profile primary category + profile city",
            "seed": cache.get("primaryCategory"),
        })

    context = seeds + cache.get("gbpCategories", [])
    known_places = []
    raw_locations: list[dict] = []
    serp_location = cache["location"]
    country_code = getattr(a, "country_code", None)
    country_code = country_code or cache.get("countryCode")
    if market == "local" and country_code:
        try:
            locations = get_call(f"serp/google/locations/{country_code.lower()}")
            problem = labs_problem(locations)
            if problem:
                raise RuntimeError(problem)
            raw_locations = ((locations.get("tasks") or [{}])[0].get("result") or [])
            for location in raw_locations:
                name = location.get("location_name") or ""
                # Districts and neighbourhoods are search locations too. Keeping
                # only City/Municipality let terms such as "locksmith hackney
                # central" through for a Chichester business. Only broad regions
                # are excluded from the wrong-place check.
                if name and (location.get("location_type") not in {
                    "Country", "State", "Region", "DMA Region",
                }):
                    known_places.append(name.split(",", 1)[0].strip())
        except (Exception, SystemExit) as error:
            errors.append(f"location taxonomy failed: {str(error)[:160]}")
        serp_location = resolve_serp_location(
            cache["location"], raw_locations, country_code=country_code
        )
    kept, dropped = filter_candidates(
        rows, context, market, a.exclude_place, known_places,
        getattr(a, "served_place", []) or [cache.get("profileCity")])
    ranked = rank_candidates(kept, market)
    # Google reads "ernaehrungsberatung muenchen" and "muenchen ernaehrungs-
    # beratung" as one search, and the data agrees - identical volume, identical
    # bid. Presented as three separate insights they read as padding, which is
    # exactly what the page must never look like. Collapsed after ranking, so
    # the survivor is the strongest of the twins rather than whichever the
    # expansion happened to return first. Measured 01.09.2026: the shortlist was
    # the same search three times over.
    shortlist, signatures = [], set()
    preferred_row = next(
        (row for row in ranked
         if preferred_map_keyword
         and folded(row["keyword"]) == folded(preferred_map_keyword)),
        None,
    )
    # The trade's vocabulary: its categories, the seeds, and the service words
    # its own site uses ("coffee" for a cafe), minus the business's own name.
    business_name = str(cache.get("business") or "")
    site_vocab: set[str] = set()
    try:
        cro_payload = json.loads(Path(str(cache.get("cro") or "")).read_text()) if cache.get("cro") else {}
        for group in ("serviceCandidates", "seedCandidates"):
            for entry in cro_payload.get(group) or []:
                site_vocab |= tokens(str(entry.get("name") if isinstance(entry, dict) else entry))
    except (OSError, ValueError, TypeError):
        site_vocab = set()
    category_vocab = set().union(*(tokens(phrase) for phrase in cache.get("gbpCategories") or [])) if cache.get("gbpCategories") else set()
    family = (set().union(*(tokens(phrase) for phrase in context)) if context else set()) | site_vocab | category_vocab
    family -= (tokens(business_name) - category_vocab - GENERIC_TAIL)
    # The strongest generic term customers actually type is checked alongside
    # the category term, so the map can run on the one with real demand.
    primary_category = str(cache.get("primaryCategory") or "")
    volume_leader = next((
        row for row in sorted(ranked, key=lambda item: -(item.get("volume") or 0))
        if (row.get("volume") or 0) > 0
        and category_like(row["keyword"], family, row.get("seed"), primary_category)
        and not near_me(row["keyword"])
        and not own_brand(row["keyword"], business_name, family)
    ), None)
    head = [row for row in (preferred_row, volume_leader) if row]
    ordered = head + [row for row in ranked if row not in head]
    for row in ordered:
        if own_brand(row["keyword"], business_name, family):
            dropped.append({**row, "reason": "own brand"})
            continue
        if near_me(row["keyword"]):
            dropped.append({**row, "reason": "near-me variant of a term already measured"})
            continue
        signature = " ".join(sorted(tokens(row["keyword"])))
        if signature in signatures:
            dropped.append({**row, "reason": "duplicate: same words in another order"})
            continue
        signatures.add(signature)
        shortlist.append(row)
        # One spare, because a rival's brand name only shows itself in the SERP.
        if len(shortlist) == 4:
            break

    def serp(row):
        payload: dict = {}
        try:
            payload = call("serp/google/organic/live/advanced", [{
                "keyword": row["keyword"], "location_name": serp_location,
                "language_name": cache["language"], "depth": 20,
            }])
            return (inspect_serp(row["keyword"], payload, cache["domain"],
                                 row.get("volume"), row.get("cpc")),
                    payload.get("cost", 0), None)
        except (Exception, SystemExit) as error:
            return (None, payload.get("cost", 0),
                    f"SERP failed for '{row['keyword']}': {str(error)[:160]}")

    checked = []
    for row in shortlist:
        result = serp(row)
        if result[2]:
            raise RuntimeError(result[2])
        checked.append(result)
    searches = [row for row, _, _ in checked if row]
    spend += sum(cost for _, cost, _ in checked)
    # A rival's brand name shows itself only in the SERP: the top map result
    # and the keyword collapse onto each other. Those rows measure nothing.
    searches = [row for row in searches if not names_a_business(row)]
    # A term with two or more words we do not know and no local pack is
    # somebody's name or somewhere else ("tram view cafe", 12,100 a month,
    # no map pack). A service term always has a pack or trade words.
    searches = [
        row for row in searches
        if row["hasLocalPack"]
        or len(tokens(row["keyword"]) - GENERIC_TAIL - family) <= 1
    ]
    money = next((row for row in searches if row["eligibleMoney"]), None)
    # The map runs on the strongest term customers actually type for this
    # trade ("coffee shop" 27,100 a month beats an unmeasured "Cafe"), never a
    # near-me variant; the category-plus-town term is the fallback.
    generic_pack = [row for row in searches if row["hasLocalPack"] and not near_me(row["keyword"])]
    # Start with the category the business chose. Measuring an emergency
    # locksmith against a broader category and then recommending that category
    # produced a misleading detour in the original audit tests. Use it only
    # when people actually search for the term; an unmeasured category produces
    # a grid with no useful meaning.
    map_search = next((
        row for row in generic_pack
        if preferred_map_keyword
        and folded(row["keyword"]) == folded(preferred_map_keyword)
        and (row.get("volume") or 0) > 0
    ), None)
    if map_search is None:
        map_search = max(
            (row for row in generic_pack
             if category_like(row["keyword"], family, row.get("seed"), primary_category) and (row.get("volume") or 0) > 0),
            key=lambda row: row.get("volume") or 0, default=None,
        )
    if map_search is None:
        map_search = next((
            row for row in generic_pack
            if preferred_map_keyword and folded(row["keyword"]) == folded(preferred_map_keyword)
        ), None)
    if map_search is None:
        map_search = next(iter(generic_pack), None)
    if map_search is None:
        map_search = next((row for row in searches if row["hasLocalPack"]), None)
    themes = [{
        "keyword": row["keyword"], "demand": volume_band(row.get("volume")),
        "clientPosition": row.get("clientPosition"),
        "surfaces": [s for s, yes in (("map pack", row["hasLocalPack"]), ("organic results", True)) if yes],
    } for row in searches[:3]]
    return {
        **cache, "stage": "complete", "market": market, "selectedSeeds": seeds,
        "serpLocation": serp_location,
        "candidates": ranked, "dropped": dropped, "searches": searches,
        "themes": themes, "moneyKeyword": money["keyword"] if money else None,
        "mapKeyword": map_search["keyword"] if map_search and market == "local" else None,
        "mapKeywordSource": (
            "GBP primary category + profile city"
            if map_search and preferred_map_keyword
            and folded(map_search["keyword"]) == folded(preferred_map_keyword)
            else "strongest category-like search with a local pack"
            if map_search and category_like(map_search["keyword"], family)
            else "checked local-pack fallback" if map_search else None
        ),
        "selectionNote": (None if money else
                          "No checked search had six supplier pages in the top ten; no single money winner is claimed."),
        "errors": errors,
        "spend": round(cache.get("spend", 0) + spend, 4),
    }


def run(a, call: Callable = post, get_call: Callable = dfs_get) -> dict:
    """Run discovery and expansion without pausing for member input."""
    cache = discover(a, call)
    return expand(a, cache, call, get_call)


def write_cache(path: str, payload: dict) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    temporary.replace(target)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("domain")
    ap.add_argument("--cro", required=True)
    ap.add_argument("--cache", required=True)
    ap.add_argument("--location", default="Germany")
    ap.add_argument("--language", default="German")
    ap.add_argument("--business")
    ap.add_argument("--profile-json", help="pre-fetched compact GBP evidence from gbp_profile.py")
    ap.add_argument("--seeds", nargs="*", help="optional operator override; normally selected automatically")
    ap.add_argument("--market", choices=("local", "national", "remote"))
    ap.add_argument("--exclude-place", action="append", default=[])
    ap.add_argument("--served-place", action="append", default=[])
    ap.add_argument("--country-code",
                    help="two-letter ISO code; local runs use the free DataForSEO location "
                         "taxonomy to reject cities outside --served-place")
    a = ap.parse_args()
    payload = run(a)
    write_cache(a.cache, payload)
    print(json.dumps({k: payload.get(k) for k in (
        "stage", "selectedSeeds", "market", "marketReason", "themes", "moneyKeyword",
        "mapKeyword", "serpLocation", "selectionNote", "errors", "spend")
        if payload.get(k) is not None},
        indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
