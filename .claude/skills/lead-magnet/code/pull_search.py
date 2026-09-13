#!/usr/bin/env python3
"""Pull the four search exhibits: positions, landing pages, competitor reach,
and the map pack's review counts.

    python3 code/pull_search.py diegesundheitswerkstatt.org \\
        --competitors slimpuls-gilching.de gesund-in-germering.de \\
        --location Germany --language German \\
        --maps "ernaehrungsberatung" --coordinate 48.13,11.38

Costs real money. Reference prices, DataForSEO, August 2026:

  ranked_keywords        ~$0.011 + $0.0001 per returned row, ONE domain per call
  domain_rank_overview   ~$0.011, several domains per request
  serp/google/maps/live  ~$0.002, ONE task per request

A run over one client and three competitors is under $0.10. It prints the spend
it caused, so nobody discovers the bill later. `--dry-run` shows the plan and
calls nothing.
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import io
import json
import os
import re
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse

try:
    from instrument import count_call, record_cost
except ModuleNotFoundError:  # importlib-based local tests do not add this folder to sys.path
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from instrument import count_call, record_cost
from workspace import workspace_root

ROOT = workspace_root()
API = "https://api.dataforseo.com/v3"

# Words that mark a page or a query as buying rather than reading. A page that
# sells is worth a different number than a page that informs, and the exhibit
# says which is which rather than averaging them into one meaningless figure.
MONEY_WORDS = ("preis", "kosten", "buchen", "termin", "beratung", "angebot", "leistung",
               "service", "kontakt", "price", "cost", "book", "quote", "hire", "near me",
               "in der naehe", "nahe")


def creds() -> tuple[str, str]:
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("DATAFORSEO_LOGIN="):
                os.environ.setdefault("DATAFORSEO_LOGIN", line.split("=", 1)[1])
            if line.startswith("DATAFORSEO_PASSWORD="):
                os.environ.setdefault("DATAFORSEO_PASSWORD", line.split("=", 1)[1])
    login, pw = os.environ.get("DATAFORSEO_LOGIN"), os.environ.get("DATAFORSEO_PASSWORD")
    if not login or not pw:
        sys.exit("DATAFORSEO_LOGIN and DATAFORSEO_PASSWORD missing from .env")
    return login, pw


def authorization() -> str:
    """Return one verbatim Authorization value when a hosted vault supplies it.

    Managed-agent vault values are substituted only at network egress. Encoding
    separate placeholder credentials would destroy that substitution, so hosted
    runs inject the already-encoded header as DATAFORSEO_AUTHORIZATION.
    """
    header = os.environ.get("DATAFORSEO_AUTHORIZATION")
    if header:
        return header
    login, pw = creds()
    token = base64.b64encode(f"{login}:{pw}".encode()).decode()
    return f"Basic {token}"


def post(path: str, body: list[dict]) -> dict:
    count_call(path, tasks=len(body))
    req = urllib.request.Request(
        f"{API}/{path}", data=json.dumps(body).encode(),
        headers={"Authorization": authorization(), "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            response = json.loads(r.read())
    except urllib.error.HTTPError as e:
        sys.exit(f"{path} failed: HTTP {e.code} {e.read().decode('utf-8', 'replace')[:300]}")
    reported_cost = response.get("cost")
    if reported_cost is None:
        reported_cost = sum(float(task.get("cost") or 0) for task in response.get("tasks") or [])
    record_cost(path, reported_cost)
    return response


def labs_post(path: str, body: dict) -> dict:
    """Make one Labs call and stop on any task-level refusal."""
    wanted = (body.get("location_name") or "").strip()
    response = post(path, [{**body, "location_name": wanted}])
    task = (response.get("tasks") or [{}])[0]
    status = task.get("status_code")
    if status is not None and status != 20000:
        problem = f"{status} {task.get('status_message')} at '{wanted}'"
        raise RuntimeError(f"{path.split('/')[-2]} refused: {problem}")
    return response


def get(path: str) -> dict:
    """Authenticated DataForSEO GET, used for free taxonomy endpoints."""
    count_call(path, tasks=0)
    req = urllib.request.Request(
        f"{API}/{path}", headers={"Authorization": authorization(),
                                  "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=180) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as error:
        sys.exit(f"{path} failed: HTTP {error.code} "
                 f"{error.read().decode('utf-8', 'replace')[:300]}")


def kind(text: str) -> str:
    t = text.lower()
    return "money" if any(w in t for w in MONEY_WORDS) else "info"


def choose_comparable_competitors(
        sized: list[tuple[str, int, int]], rivals: list[str], client_visits: int
) -> list[tuple[str, int, int]]:
    """Return at most two competitors a client could plausibly overtake.

    `sized` is (domain, estimated visits, ranked-keyword count).  Kept pure so
    the ordering invariant can be regression-tested without spending on an API
    call: a client with measured traffic must take the comparable-size branch,
    never the zero-traffic fallback.
    """
    if not sized:
        return []
    if client_visits:
        near = [s for s in sized if client_visits * 0.2 <= s[1] <= client_visits * 5]
    else:
        near = sorted(sized, key=lambda s: s[1])[:3]
    near = near or sorted(sized, key=lambda s: s[1])
    if client_visits:
        near.sort(key=lambda s: rivals.index(s[0]))
    else:
        near.sort(key=lambda s: s[1])

    picked = near[:1]
    for cand in near[1:]:
        lo, hi = sorted((max(picked[0][1], 1), max(cand[1], 1)))
        if hi <= lo * 20:
            picked.append(cand)
        if len(picked) == 2:
            break
    return picked


def normalise_domain(value: str | None) -> str:
    """Return one comparable host without guessing from a business name."""
    if not value:
        return ""
    candidate = value.strip().lower()
    parsed = urlparse(candidate if "://" in candidate else f"//{candidate}")
    host = parsed.hostname or candidate.split("/", 1)[0].split(":", 1)[0]
    return host.removeprefix("www.").rstrip(".")


def map_review(
    item: dict,
    client_domain: str,
    client_cid: str | int | None = None,
) -> dict | None:
    """Keep map identity with the row and mark the client only on exact IDs."""
    name = item.get("title")
    if not name:
        return None
    rating = item.get("rating") or {}
    cid = item.get("cid")
    domain = normalise_domain(item.get("domain") or item.get("url"))
    is_client = bool(
        (client_cid is not None and cid is not None and str(cid) == str(client_cid))
        or (domain and domain == normalise_domain(client_domain))
    )
    return {
        "name": name,
        "cid": cid,
        "domain": domain or None,
        "isClient": is_client,
        "rating": rating.get("value"),
        "reviews": rating.get("votes_count") or 0,
    }


def parse_grid_tasks(
    grid_response: dict,
    business: str | None,
    domain: str,
    expected: int = 25,
) -> tuple[list[int | None], list[dict]]:
    """Preserve grid order and reuse the centre task for review evidence."""
    ranks: list[int | None] = []
    centre_items: list[dict] = []
    needle = (business or domain.split(".")[0]).lower()
    tasks = grid_response.get("tasks") or []
    for index in range(expected):
        task = tasks[index] if index < len(tasks) else {}
        items = ((task.get("result") or [{}])[0].get("items") or [])
        if index == expected // 2:
            centre_items = items
        found = None
        for item in items:
            title = (item.get("title") or "").lower()
            site = (item.get("url") or item.get("domain") or "").lower()
            if needle in title or domain.lower() in site:
                found = item.get("rank_group")
                break
        ranks.append(found)
    return ranks, centre_items


def grid_summary(
    grid_response: dict,
    business: str | None,
    domain: str,
    client_cid: str | int | None = None,
    expected: int = 25,
    profile_reviews: int | None = None,
    profile_rating: float | None = None,
) -> dict:
    """Per point: who holds the top three. Across points: who wins the map.

    The winners are the competitors a customer meets first; the client block
    is the same measure for the business itself. Both come from the grid
    responses already paid for, nothing extra is fetched.
    """
    needle = (business or domain.split(".")[0]).lower()
    tasks = grid_response.get("tasks") or []
    points: list[dict] = []
    tally: dict[str, dict] = {}
    client_ranks: list[int] = []
    client_top3 = 0
    client_rating = None
    client_reviews = None
    for index in range(expected):
        task = tasks[index] if index < len(tasks) else {}
        items = [item for item in ((task.get("result") or [{}])[0].get("items") or []) if item.get("title")]
        top = []
        rank = None
        for item in items:
            title = str(item.get("title") or "")
            site = (item.get("url") or item.get("domain") or "").lower()
            cid = item.get("cid")
            is_client = (
                (client_cid is not None and cid is not None and str(cid) == str(client_cid))
                or needle in title.lower()
                or (domain.lower() in site if domain else False)
            )
            position = item.get("rank_group")
            if is_client and rank is None and position:
                rank = position
                rating = item.get("rating") or {}
                client_rating = rating.get("value", client_rating)
                client_reviews = rating.get("votes_count", client_reviews)
            if position and position <= 3 and not is_client:
                rating = item.get("rating") or {}
                key = str(cid or title.lower())
                entry = tally.setdefault(key, {
                    "name": title, "cid": cid, "topThreePoints": 0, "bestRank": None,
                    "rating": rating.get("value"), "reviews": rating.get("votes_count") or 0,
                    # Google's primary category of the winner, for the mirror
                    # check against the client's exact public profile.
                    "category": item.get("category") or None,
                    # The winner's website, so its normal-search standing can
                    # be measured beside the client's.
                    "domain": normalise_domain(item.get("domain") or item.get("url")) or None,
                })
                entry["topThreePoints"] += 1
                entry["bestRank"] = position if entry["bestRank"] is None else min(entry["bestRank"], position)
                top.append(title)
        if rank is not None:
            client_ranks.append(rank)
            if rank <= 3:
                client_top3 += 1
        points.append({"rank": rank, "top": top[:3]})
    ranked = sorted(tally.values(), key=lambda row: (-row["topThreePoints"], row["bestRank"] or 99, -(row["reviews"] or 0)))
    winners = ranked[:3]
    # How deep the market is, not only who leads it. Twenty-five of twenty-five
    # reads as dominance until you know the whole map holds three businesses;
    # the number was tallied and then thrown away in the original audit tests.
    return {
        "points": points,
        "winners": winners,
        "rivals": len(ranked),
        "rivalsNamed": [row["name"] for row in ranked],
        "client": {
            "topThreePoints": client_top3,
            "averageRank": round(sum(client_ranks) / len(client_ranks), 1) if client_ranks else None,
            # Client reviews come from the profile attached to the confirmed
            # place ID. Map results can expose a different listing, so they are
            # only a cross-check for the client. They remain the only available
            # source for competitors.
            "rating": profile_rating if profile_rating is not None else client_rating,
            "reviews": profile_reviews if profile_reviews is not None else client_reviews,
            "mapRating": client_rating,
            "mapReviews": client_reviews,
            "listingMismatch": bool(
                profile_reviews and client_reviews
                and max(profile_reviews, client_reviews) > 2 * max(1, min(profile_reviews, client_reviews))
            ),
        },
    }


def validated_grid_tasks(
    responses: list[tuple[dict, str | None]],
) -> tuple[list[dict], float, list[str]]:
    """Accept an empty SERP as evidence; reject unavailable grid points."""
    if len(responses) != 25:
        raise RuntimeError(f"The map grid returned {len(responses)} of 25 required checks; it was not scored.")
    tasks: list[dict] = []
    failures: list[str] = []
    spend = 0.0
    for index, (response, transport_problem) in enumerate(responses):
        spend += float(response.get("cost") or 0)
        available = response.get("tasks") or []
        task = available[0] if available else {}
        status = task.get("status_code") if task else None
        # DataForSEO 40102 means the search completed but Google returned no
        # results for this coordinate. On a visibility map that is evidence of
        # absence, not a failed measurement: parse_grid_tasks renders it red.
        if transport_problem or not task or status not in (20000, 40102):
            reason = transport_problem or task.get("status_message") or "missing task result"
            failures.append(f"point {index + 1}: {reason}")
        tasks.append(task)
    if failures:
        raise RuntimeError(
            f"{len(failures)} of {len(responses)} map checks failed; "
            f"the grid was not scored ({failures[0]})"
        )
    return tasks, spend, failures


def fetch_grid_point(
    point: dict,
    call=None,
) -> tuple[dict, str | None]:
    """Make exactly one paid grid request and return its transport result."""
    call = call or post
    try:
        return call("serp/google/maps/live/advanced", [point]), None
    except (SystemExit, urllib.error.URLError, TimeoutError, ConnectionError,
            json.JSONDecodeError) as error:
        return {"tasks": []}, str(error)[:160]
    except Exception as error:                              # noqa: BLE001
        return {"tasks": []}, str(error)[:160]


def organic_summary(items: list, business: str | None, terms: list[str], total: int | None = None) -> dict:
    """What the website itself ranks for in normal Google results.

    Brand searches (the business's own name) are marked, because a site that
    comes up only for its own name is found by nobody who does not already
    know it; that is the reading the report gives. `terms` are the category
    words (grid and maps terms) that never count as brand.
    """
    # "VB Locksmith Services": "vb" is the brand, "locksmith" the category,
    # "services" a filler word every trade uses. Two-letter brands are common.
    generic = {w for term in terms if term for w in re.findall(r"[a-z0-9]+", term.lower())}
    generic |= {"services", "service", "ltd", "limited", "llc", "inc", "co", "the", "and", "of", "gmbh", "ug"}
    brand = {w for w in re.findall(r"[a-z0-9]+", (business or "").lower()) if len(w) >= 2 and w not in generic}
    rows = []
    for it in items:
        el = (it.get("ranked_serp_element") or {}).get("serp_item") or {}
        data = it.get("keyword_data") or {}
        keyword = data.get("keyword")
        position = el.get("rank_group")
        if not keyword or not position:
            continue
        words = set(re.findall(r"[a-z0-9]+", keyword.lower()))
        rows.append({
            "keyword": keyword, "position": int(position),
            "volume": (data.get("keyword_info") or {}).get("search_volume"),
            "brand": bool(brand & words),
        })
    rows.sort(key=lambda r: (r["position"], -(r["volume"] or 0)))
    page_one = [r for r in rows if r["position"] <= 10]
    return {
        "total": total if total is not None else len(rows),
        "pageOne": len(page_one),
        "brandOnly": bool(rows) and all(r["brand"] for r in (page_one or rows)),
        "top": rows[:5],
    }


DIRECTORY_HOSTS = (
    "yell.com", "checkatrade.com", "trustatrader.com", "bark.com", "thomsonlocal.com", "yelp.com",
    "yelp.co.uk", "facebook.com", "trustpilot.com", "locksmiths.co.uk", "ratedpeople.com",
    "mybuilder.com", "freeindex.co.uk", "cylex-uk.co.uk", "hotfrog.co.uk", "scoot.co.uk", "192.com",
    "nextdoor.co.uk", "instagram.com", "linkedin.com", "google.com", "wikipedia.org",
    "tripadvisor.com", "tripadvisor.co.uk", "openrice.com", "gelbeseiten.de", "11880.com",
    "dasoertliche.de", "meinestadt.de", "houzz.com", "houzz.co.uk", "reddit.com", "which.co.uk",
)


def is_directory(domain: str) -> bool:
    host = normalise_domain(domain)
    return any(host == d or host.endswith("." + d) for d in DIRECTORY_HOSTS)


def comparable_winner(winners: list, overview_by: dict, client_keywords: int, client_page_one: int = 0) -> dict | None:
    """The map winner whose website is the fair yardstick for the keyword gap.

    It must hold more page-one searches than the client, or there is no gap
    to show. Among those, the winner within twenty times the client's
    keyword count comes first (a national chain ranking for "key cutter near
    me" across the country tells a Coventry locksmith nothing); failing that,
    the smallest site above the client.
    """
    sized = []
    for winner in winners:
        domain = winner.get("domain")
        metrics = overview_by.get(domain) if domain else None
        if not metrics or not metrics.get("keywords"):
            continue
        if int(metrics.get("pageOne") or 0) <= client_page_one or int(metrics["keywords"]) <= max(client_keywords, 1):
            continue
        sized.append((winner, int(metrics["keywords"])))
    floor = max(client_keywords, 1)
    fair = [w for w, n in sized if n <= floor * 20]
    if fair:
        return fair[0]
    above = sorted(sized, key=lambda pair: pair[1])
    return above[0][0] if above else None


def organic_section(
    organic: dict,
    winners: list,
    overview_by: dict,
    serp_items: list,
    gap_items: list,
    client_positions: dict,
    business: str | None,
    terms: list[str],
    domain: str,
    term: str | None,
    client_volumes: dict | None = None,
    town: str = "",
) -> dict:
    """Assemble the normal-search picture from the pulls already made.

    Winners: the map winners' sites on the client's measure. Page one: who
    occupies the town term, directories marked. Gap: searches the comparable
    winner holds on page one that the client does not, local terms only,
    because "near me" volumes are national and would mislead. Demand: how
    many people a month type the town term, the yardstick that does not
    depend on other local sites being any good.
    """
    host = normalise_domain(domain)
    filler_words = {"services", "service", "the", "in", "for", "a", "of"}
    stem_word = lambda w: w[:-1] if len(w) > 3 and w.endswith("s") else w  # noqa: E731
    intent = lambda text: tuple(sorted(stem_word(w) for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in filler_words))  # noqa: E731
    demand = None
    if term:
        wanted = intent(term)
        found = [int(v) for k, v in (client_volumes or {}).items() if intent(k) == wanted and v]
        for it in gap_items:
            data = it.get("keyword_data") or {}
            if intent(str(data.get("keyword") or "")) == wanted:
                found.append(int((data.get("keyword_info") or {}).get("search_volume") or 0))
        # The town term is the only local yardstick. Bare "locksmith" is a
        # country figure: on 07.09.2026 a Cirencester report told the owner his
        # town searched 33,100 times a month, which is the whole of the UK, and
        # the town-qualified phrase sat in the same cache with no volume pulled.
        town_name = str(town or "").split(",")[0].strip()
        local = []
        if town_name:
            wanted_local = intent(f"{term} {town_name}")
            for key, value in (client_volumes or {}).items():
                if intent(key) == wanted_local and value:
                    local.append(int(value))
            for it in gap_items:
                data = it.get("keyword_data") or {}
                if intent(str(data.get("keyword") or "")) == wanted_local:
                    local.append(int((data.get("keyword_info") or {}).get("search_volume") or 0))
        if any(local):
            demand = {"keyword": f"{term} {town_name}".strip(), "volume": max(local),
                      "scope": "local"}
        elif any(found):
            demand = {"keyword": term, "volume": max(found)}
            # A term that already names the town is the local yardstick. Only a
            # term without it, measured while the town is known, is the country
            # figure that has to say so.
            if town_name:
                demand["scope"] = "local" if town_name.lower() in term.lower() else "national"
    client_keywords = int((overview_by.get(host) or overview_by.get(domain) or {}).get("keywords") or organic.get("total") or 0)
    rows = []
    for winner in winners[:3]:
        metrics = overview_by.get(winner.get("domain") or "") or {}
        rows.append({
            "name": winner.get("name"), "domain": winner.get("domain"),
            "keywords": metrics.get("keywords"), "pageOne": metrics.get("pageOne"), "visits": metrics.get("visits"),
            "farLarger": bool(metrics.get("keywords")) and metrics["keywords"] > max(client_keywords, 1) * 20,
        })
    winner_domains = {w.get("domain") for w in winners if w.get("domain")}
    page_one = []
    client_position = None
    for item in serp_items:
        if item.get("type") != "organic":
            continue
        d = normalise_domain(item.get("domain") or item.get("url"))
        position = item.get("rank_group")
        if not d or not position:
            continue
        kind = "you" if d == host else "winner" if d in winner_domains else "directory" if is_directory(d) else "business"
        if kind == "you" and client_position is None:
            client_position = position
        page_one.append({"position": position, "domain": d, "kind": kind})
    client_page_one = int((overview_by.get(host) or {}).get("pageOne") or organic.get("pageOne") or 0)
    comparable = comparable_winner(winners, overview_by, client_keywords, client_page_one)
    generic = {w for t in terms if t for w in re.findall(r"[a-z0-9]+", t.lower())}
    winner_brand = set()
    if comparable:
        winner_brand = {w for w in re.findall(r"[a-z0-9]+", (comparable.get("name") or "").lower()) if len(w) >= 2 and w not in generic}
    town_words = {w for w in re.findall(r"[a-z0-9]+", (term or "").lower()) if w not in generic and len(w) >= 3}
    filler = {"services", "service", "the", "in", "for", "a", "of"}
    stem = lambda w: w[:-1] if len(w) > 3 and w.endswith("s") else w  # noqa: E731

    def brand_hit(words: set[str]) -> bool:
        # "eyden locksmiths coventry" against the winner "Eydens": match on the
        # stem, four letters and up, so a plural or a possessive still counts.
        return any(len(b) >= 4 and (w.startswith(b[:4]) or b.startswith(w[:4])) for b in winner_brand for w in words if len(w) >= 4)

    gap = []
    seen: set[tuple] = set()
    for it in gap_items:
        data = it.get("keyword_data") or {}
        keyword = str(data.get("keyword") or "")
        position = ((it.get("ranked_serp_element") or {}).get("serp_item") or {}).get("rank_group")
        volume = (data.get("keyword_info") or {}).get("search_volume") or 0
        words = set(re.findall(r"[a-z0-9]+", keyword.lower()))
        if not keyword or not position or position > 10 or volume < 10:
            continue
        if re.search(r"\b(near me|close to me|nearest|closest|near by|nearby)\b", keyword.lower()):
            continue
        if brand_hit(words):
            continue
        if not (words & generic) and not (words & town_words):
            continue
        # "coventry locksmith", "locksmiths coventry" and "coventry locksmith
        # services" are one search to an owner; one row, the highest volume.
        key = tuple(sorted(stem(w) for w in words if w not in filler))
        if key in seen:
            continue
        seen.add(key)
        mine = client_positions.get(keyword.lower())
        if mine is not None and mine <= 10:
            continue
        gap.append({"keyword": keyword, "volume": volume, "winnerPosition": int(position), "yourPosition": mine})
    gap.sort(key=lambda r: -r["volume"])
    return {
        "clientKeywords": client_keywords,
        "clientVisits": (overview_by.get(host) or {}).get("visits"),
        "winners": rows,
        "serp": {"keyword": term, "pageOne": page_one[:10], "clientPosition": client_position} if term and page_one else None,
        "comparable": {"name": comparable.get("name"), "domain": comparable.get("domain")} if comparable else None,
        "gap": gap[:5],
        "demand": demand,
    }


def review_activity(profile: dict, today: dt.date | None = None) -> dict:
    """Recency and owner replies from the newest reviews already fetched.

    Jono's layer 11 asks for both; the stored sample is the newest handful
    (Apify returns them newest first), so "none in 90 days" is a real finding
    while a full count is not claimed.
    """
    today = today or dt.date.today()
    sample = [item for item in (profile.get("review_items") or []) if isinstance(item, dict)]
    recent = 0
    answered = 0
    dated = 0
    for item in sample:
        when = str(item.get("when") or "")[:10]
        try:
            age = (today - dt.date.fromisoformat(when)).days
            dated += 1
            if age <= 90:
                recent += 1
        except ValueError:
            pass
        if str(item.get("owner_response") or "").strip():
            answered += 1
    return {"sampled": len(sample), "dated": dated, "recent90": recent, "answered": answered}


# These are Pocket CEO operating heuristics, not Google requirements or causal
# claims. Their provenance and limits ship with this skill in
# `references/measurement-benchmarks.md`.
BENCHMARK = {
    "category_slots": 10,        # 1 primary + 9 secondary, spec "Categories"
    "photos_strong": 100,        # Pocket CEO operating target
    "photos_present": 10,        # below this the profile reads as unattended
    "services_minimum": 30,      # spec "Services": minimum 30
    "services_target": 50,       # spec "Services": 50 to use plus 20 extras
    "description_limit": 750,    # spec "Description": Google's own cap
    "description_hook": 100,     # spec "Description": the "see more" cut
}

# A name that carries the trade or the town is the one edit that costs the
# whole profile rather than a ranking, so it gets its own verdict every time
# (spec "The name verdict, state it either way, every single time").
TRADE_WORDS = (
    "locksmith", "plumber", "plumbing", "electrician", "electrical", "roofer", "roofing",
    "hvac", "heating", "cooling", "cleaner", "cleaning", "towing", "tow", "removals",
    "landscaping", "gardener", "builder", "building", "painter", "painting", "glazier",
    "mechanic", "garage", "dentist", "dental", "chiropractor", "physio", "solicitor",
    "accountant", "removal", "carpet", "pest control", "scaffolding", "flooring",
)
NAME_KEYWORD_MARKERS = ("near me", "best ", "cheap ", "24/7", "24 hour", "no 1", "no.1", "#1")


def name_verdict_row(profile: dict, town: str = "", measured: bool = True) -> tuple:
    """State the business name clean or not, with the risk spelled out."""
    name = str(profile.get("name") or "").strip()
    if not name:
        status = "warn" if measured else "unknown"
        return ("Business name", "The public business name could not be read.", status)
    lowered = name.lower()
    town = str(town or profile.get("city") or "").strip()
    # A locksmith using the word "Locksmith" is normal, not a suspension risk.
    # The name becomes risky only when it adds a location or advertising claim.
    flags = [marker.strip() for marker in NAME_KEYWORD_MARKERS if marker in lowered]
    has_town = bool(town) and town.lower() in lowered
    if has_town:
        flags += [word for word in TRADE_WORDS if word in lowered]
    if not flags and not has_town:
        example = f"{name} {town} {TRADE_WORDS[0].title()}".strip() if town else f"{name} Near Me"
        return ("Business name",
                f"The name matches the public business identity check. "
                f"Never change it to something like \"{example}\": a keyword in the name "
                f"risks the whole profile, not just a ranking.",
                "good")
    parts = []
    if has_town:
        parts.append(f"the town \"{town}\"")
    if flags:
        parts.append("the words " + ", ".join(f"\"{item}\"" for item in list(dict.fromkeys(flags))[:3]))
    return ("Business name",
            f"The public name carries {' and '.join(parts)}. If that is not the registered, "
            f"signwritten name, it is a suspension risk and needs checking before anything else.",
            "warn")


def photos_row(photos, measured: bool = True) -> tuple:
    """Photos against the delivery benchmark, not against a tenth of it."""
    if photos is None:
        status = "warn" if measured else "unknown"
        return ("Photos", "The public photo count could not be verified.", status)
    count = int(photos or 0)
    strong, present = BENCHMARK["photos_strong"], BENCHMARK["photos_present"]
    if count >= strong:
        return ("Photos", f"The profile shows {count} public photos, above the Pocket CEO benchmark of {strong}.", "good")
    if count >= present:
        return ("Photos", f"The profile shows {count} public photos; the Pocket CEO operating benchmark is {strong}.", "warn")
    return ("Photos", f"The profile shows {count} public photos, below the Pocket CEO operating benchmark of {strong}.", "bad")


def services_row(services: list, measured: bool = True) -> tuple:
    """Services against the spec's minimum and target, not against zero."""
    count = len(services)
    minimum, target = BENCHMARK["services_minimum"], BENCHMARK["services_target"]
    if not count:
        status = "warn" if measured else "unknown"
        return ("Services", "No public service or offer list was returned.", status)
    if count >= target:
        return ("Services", f"The profile lists {count} public services, meeting the Pocket CEO benchmark of {target}.", "good")
    if count >= minimum:
        return ("Services", f"The profile lists {count} public services; the Pocket CEO target is {target}.", "warn")
    return ("Services", f"The profile lists {count} public services, below the Pocket CEO baseline of {minimum}.", "bad")


def booking_row(profile: dict, measured: bool = True) -> tuple:
    """Report whether the exact public profile exposes a booking route."""
    links = profile.get("booking_links") or profile.get("bookingLinks") or []
    if isinstance(links, str):
        links = [links]
    links = [str(item) for item in links if item]
    if links:
        return ("Booking link", f"Customers can book straight from the profile via {links[0]}.", "good")
    if not measured:
        return ("Booking link", "Booking links were not returned by the profile source.", "unknown")
    return ("Booking link",
            "No booking link is published on the Google Business Profile.", "warn")


def attributes_row(profile: dict, measured: bool = True) -> tuple:
    """Only what is set is public; what the category offers is dashboard-only."""
    # The lookup nests the real names under `available_attributes`, so reading
    # the top-level keys reported "available_attributes" as an attribute.
    attributes = profile.get("attributes") or {}
    names: list[str] = []
    if isinstance(attributes, dict):
        available = attributes.get("available_attributes")
        source = available if isinstance(available, (dict, list)) else attributes
        if isinstance(source, dict):
            for key, value in source.items():
                if isinstance(value, list):
                    names += [str(item) for item in value if item]
                elif value:
                    names.append(str(key))
        else:
            names += [str(item) for item in source if item]
    else:
        names = [str(item) for item in attributes if item]
    names = sorted({name for name in names if name and not name.endswith("_attributes")})
    if names:
        return ("Attributes",
                f"The profile publishes {len(names)} attributes, including {', '.join(names[:3])}. "
                f"Which further ones this category offers is only visible in the owner's dashboard.",
                "good")
    if not measured:
        return ("Attributes", "Public attributes were not returned by the profile source.", "unknown")
    return ("Attributes",
            "No public attributes were found. The full list this category offers is only visible "
            "in the owner's dashboard, so this one is confirmed together, not audited from outside.",
            "warn")


def reviews_row(profile: dict, measured: bool = True) -> tuple:
    if not measured:
        return ("Reviews", "Review count and rating were not returned by the profile source.", "unknown")
    count = profile.get("reviews") or 0
    rating = profile.get("rating") or "not verified"
    value = f"The profile has {count} Google reviews with an average rating of {rating} stars."
    status = "good" if count >= 20 else "bad"
    activity = review_activity(profile)
    if activity["dated"]:
        newest = activity["dated"]
        value += (
            f" Of the {newest} newest, {activity['recent90']} arrived in the last 90 days"
            f" and {activity['answered']} have an owner reply."
        )
        if status == "good" and (activity["recent90"] == 0 or activity["answered"] == 0):
            status = "warn"
    return ("Reviews", value, status)


def gbp_from_summary(profile: dict, fallback_name: str) -> dict:
    """Render GBP evidence from the profile lookup already paid for upstream."""
    categories = profile.get("categories") or []
    photos = profile.get("photos")
    description = profile.get("description") or ""
    services = [str(value) for value in (profile.get("service_items") or []) if value]
    updates = profile.get("owner_updates") or []
    update_count = int(profile.get("owner_update_count") or len(updates))
    rich = bool(profile.get("rich_evidence"))
    measured_fields = set(profile.get("measured_fields") or [])

    def measured(*keys: str) -> bool:
        if measured_fields:
            return any(key in measured_fields for key in keys)
        if rich:
            return any(profile.get(key) not in (None, "", [], {}) for key in keys)
        return any(key in profile for key in keys)

    service_area = bool(profile.get("service_area_business"))
    address_value = (
        "hidden correctly for a service-area business"
        if service_area and not profile.get("address")
        else profile.get("address") or "none listed"
    )
    address_status = (
        "good" if profile.get("address") or service_area
        else "bad" if measured("address", "service_area_business")
        else "unknown"
    )
    hours = profile.get("opening_hours") or []
    hours_value = " · ".join(
        str(item) if isinstance(item, str)
        else f"{item.get('day') or ''} {item.get('hours') or item.get('time') or ''}".strip()
        for item in hours
    )
    category_review_candidates = [
        str(category) for category in (profile.get("category_review_candidates") or [])
        if str(category) in categories[1:]
    ]
    limit, hook = BENCHMARK["description_limit"], BENCHMARK["description_hook"]
    town_in_hook = bool(profile.get("city")) and str(profile["city"]).lower() in description[:hook].lower()
    town = str(profile.get("city") or "").strip()
    if not description:
        description_status = "bad" if measured("description") else "unknown"
        description_value = ("No business description is published." if description_status == "bad"
                             else "The business description was not returned by the profile source.")
    elif len(description) > limit:
        description_status = "warn"
        description_value = (f"The public description uses {len(description)} characters, above the "
                             f"Pocket CEO field-limit check of {limit}.")
    elif town and not town_in_hook:
        description_status = "warn"
        description_value = (f"The public description is {len(description)} characters, but the first {hook} "
                             f"are all a customer sees before \"more\", and they do not say what the "
                             f"business does in {town}.")
    else:
        description_status = "good"
        description_value = (f"The public description explains the business in {len(description)} characters, "
                             f"and the first {hook} carry the point.")
    # Categories are judged against the trade, the way the cold mail does it:
    # slots used out of Google's ten, against the median of the same trade in
    # the same country, with the count of trade categories this profile lacks.
    cohort = profile.get("cohort") or {}
    used_categories = len(categories)
    cohort_median = cohort.get("median_categories")
    missing_trade_categories = [
        item.get("name") for item in (cohort.get("top_categories") or [])
        if item.get("name") and item.get("name") not in categories
    ]
    # The trade median is context, never the verdict. Grading against it told a
    # profile with three of ten slots that it was "in line with the trade", and
    # the offer that followed was to fill the other seven.
    slots = BENCHMARK["category_slots"]
    trade_note = (f" Most businesses of this kind use {cohort_median}." if cohort_median else "")
    missing_note = (f" {len(missing_trade_categories)} categories customers search for are missing "
                    f"and prepared for the working session." if missing_trade_categories else "")
    if category_review_candidates:
        categories_value = (f"The profile lists {', '.join(categories)}. The stored evidence explicitly "
                            f"marks {', '.join(category_review_candidates)} for owner confirmation.")
        categories_status = "warn"
    elif not categories:
        categories_value = "No categories were returned by the profile source."
        categories_status = "warn" if measured("categories") else "unknown"
    else:
        categories_value = (f"The profile uses {used_categories} of the {slots}-slot Pocket CEO audit benchmark."
                            f"{trade_note}{missing_note}")
        categories_status = "good" if used_categories >= slots else "warn"
    rows = [
        ("Claimed", "The profile is verified." if profile.get("is_claimed") is True else
         "The profile is not verified, so public edits are less protected." if profile.get("is_claimed") is False else
         "Verification status was not returned by the profile source.",
         "good" if profile.get("is_claimed") is True else "bad" if profile.get("is_claimed") is False else "unknown"),
        ("Address", f"The public address is {address_value}." if address_value != "none listed" else
         "No public address or service area was found." if address_status == "bad" else
         "Address and service-area details were not returned by the profile source.", address_status),
        ("Phone", f"The public phone number is {profile.get('phone')}." if profile.get("phone") else
         "No phone number is published." if measured("phone") else "Phone data was not returned by the profile source.",
         "good" if profile.get("phone") else "bad" if measured("phone") else "unknown"),
        ("Website", f"The profile links to {profile.get('website')}." if profile.get("website") else
         "No website is linked." if measured("website") else "Website data was not returned by the profile source.",
         "good" if profile.get("website") else "bad" if measured("website") else "unknown"),
        ("Hours", f"The public hours are {hours_value}." if hours_value else
         "No public opening hours were found." if measured("opening_hours") else
         "Opening hours were not returned by the profile source.",
         "good" if hours_value else "warn" if measured("opening_hours") else "unknown"),
        photos_row(photos, measured("photos")),
        reviews_row(profile, measured("reviews", "rating", "review_items")),
        ("Description", description_value, description_status),
        ("Categories", categories_value, categories_status),
        services_row(services, measured("service_items")),
        booking_row(profile, measured("booking_links", "bookingLinks")),
        attributes_row(profile, measured("attributes")),
        name_verdict_row(profile, measured=measured("name")),
        ("Updates", f"The profile has {update_count} recent public business updates in the stored evidence." if updates else
         "No recent public business update was found." if measured("owner_updates", "owner_update_count") else
         "Recent business updates were not returned by the profile source.",
         "good" if updates else "warn" if measured("owner_updates", "owner_update_count") else "unknown"),
    ]
    return {
        # The renderer needs the complete cached profile, not only the nine
        # score rows. Keeping it here makes the report shell deterministic:
        # sparse evidence is shown as sparse evidence inside the same profile,
        # never by swapping in a smaller component.
        "profile": profile,
        "panel": {
            "name": profile.get("name") or fallback_name,
            "subtitle": " · ".join(x for x in (profile.get("category"), profile.get("city")) if x),
            "ratingValue": profile.get("rating"),
            "reviewsCount": profile.get("reviews"),
            "description": description or None,
            "mapImage": profile.get("main_image") or None,
            "attribution": profile.get("name") or fallback_name,
            "photoLabel": f"{photos} public photos" if photos is not None else None,
        },
        "auditRows": [{"label": label, "value": value, "status": status}
                      for label, value, status in rows],
        "auditNote": "Every row describes public profile evidence; account-only settings remain marked for confirmation.",
        "clientName": profile.get("name") or fallback_name,
        "clientGhost": "",
        "note": "",
    }


def map_image(lat: float, lng: float, half_lat: float, half_lng: float,
              out_dir: Path | None, embed: bool = False) -> str | None:
    """The client's own town, stitched from OpenStreetMap tiles.

    The ranking grid is twenty-five coloured badges. On plain paper they are an
    abstraction; over the streets the reader knows, they are their own town with
    the gaps marked. Same data, and only one of the two gets looked at.

    Standard slippy-map tiles, so no key and no service to depend on. Usage
    policy asks for a real user agent and low volume: this is one screenful once
    per audit. Attribution is required and is rendered on the exhibit.
    """
    import math
    try:
        from PIL import Image
    except ImportError:
        return None

    zoom = 12
    for z in range(15, 9, -1):
        span = (half_lng * 2) / 360 * (2 ** z)
        if span <= 3.2:                                      # keep it to ~4 tiles wide
            zoom = z
            break

    def to_tile(la: float, lo: float) -> tuple[float, float]:
        n = 2 ** zoom
        x = (lo + 180.0) / 360.0 * n
        r = math.radians(la)
        y = (1.0 - math.asinh(math.tan(r)) / math.pi) / 2.0 * n
        return x, y

    x0, y1 = to_tile(lat + half_lat, lng - half_lng)
    x1, y0 = to_tile(lat - half_lat, lng + half_lng)
    xs, xe = int(math.floor(x0)), int(math.floor(x1))
    ys, ye = int(math.floor(y1)), int(math.floor(y0))
    if (xe - xs + 1) * (ye - ys + 1) > 20:
        return None

    canvas = Image.new("RGB", ((xe - xs + 1) * 256, (ye - ys + 1) * 256), "#eee")
    for tx in range(xs, xe + 1):
        for ty in range(ys, ye + 1):
            url = f"https://tile.openstreetmap.org/{zoom}/{tx}/{ty}.png"
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "pocket-ceo-audit/1.0"})
                with urllib.request.urlopen(req, timeout=20) as r:
                    tile = Image.open(io.BytesIO(r.read())).convert("RGB")
            except Exception:                                # noqa: BLE001
                continue
            canvas.paste(tile, ((tx - xs) * 256, (ty - ys) * 256))

    # Crop to the grid's own extent so the badges sit over the right streets.
    left = int((x0 - xs) * 256)
    top = int((y1 - ys) * 256)
    right = int((x1 - xs) * 256)
    bottom = int((y0 - ys) * 256)
    if right - left < 80 or bottom - top < 80:
        return None
    canvas = canvas.crop((left, top, right, bottom))

    if embed:
        encoded = io.BytesIO()
        canvas.convert("RGB").save(encoded, "JPEG", quality=78, optimize=True)
        return "data:image/jpeg;base64," + base64.b64encode(encoded.getvalue()).decode()
    if out_dir is None:
        return None
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "geo-grid-map.jpg"
    canvas.convert("RGB").save(path, "JPEG", quality=78, optimize=True)
    return f"/images/proposal/{path.name}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("domain")
    ap.add_argument("--competitors", nargs="*", default=[])
    ap.add_argument("--location", default="Germany")
    ap.add_argument("--language", default="German")
    ap.add_argument("--money-keyword", dest="money",
                    help="the one search a buyer types. Sets the whole money model and "
                         "picks the competitors, so name it rather than guessing at domains")
    ap.add_argument("--keyword-cache",
                    help="completed JSON from proposal_keywords.py; supplies the measured "
                         "money/map searches and the three client-facing themes")
    ap.add_argument("--frames", help="directory for the grid map image")
    ap.add_argument("--embed-map", action="store_true",
                    help="store the grid map as a data URL for a remote renderer")
    ap.add_argument("--grid", help="keyword for the 25-point map ranking grid "
                                   "(needs --coordinate; about $0.05 a run)")
    ap.add_argument("--radius", type=float, default=5.0,
                    help="km from the centre to the outer grid points (Local Falcon's 'grid "
                         "radius'). 5 km covers a town for a trade; 2.5 km fits a cafe or shop; "
                         "10 km for a service-area business. Measured 05.09.2026: 15 km put 16 "
                         "of 25 points in other towns and read as invisibility")
    ap.add_argument("--zoom", type=int, default=12,
                    help="Google Maps zoom for each grid point. Measured 05.09.2026 on a Coventry "
                         "locksmith: 17z returns 4 results, 14z drops a business 4 km away, "
                         "12-13z return the full 20 with the real proximity order")
    ap.add_argument("--business", help="their name as Google shows it, for finding them in the grid")
    ap.add_argument("--maps", help="keyword for the map-pack review comparison")
    ap.add_argument("--coordinate", help="lat,lng for the maps search")
    ap.add_argument("--profile-json", help="compact GBP evidence already fetched by gbp_profile.py")
    ap.add_argument("--backlinks", action="store_true",
                    help="referring domains per domain, plus the anchor texts of the client "
                         "(~$0.024 per domain, plus $0.024 for the anchors)")
    ap.add_argument("--limit", type=int, default=25)
    ap.add_argument(
        "--lead-magnet",
        action="store_true",
        help="only produce fields rendered by the three-section cold lead magnet",
    )
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    keyword_cache = None
    if a.keyword_cache:
        keyword_cache = json.loads(Path(a.keyword_cache).read_text())
        if keyword_cache.get("stage") != "complete":
            sys.exit("keyword cache is incomplete; run proposal_keywords.py again")
        a.money = a.money or keyword_cache.get("moneyKeyword")
        if keyword_cache.get("market") == "local" and keyword_cache.get("mapKeyword"):
            a.grid = a.grid or keyword_cache["mapKeyword"]
            # The V2 collector may replace a branded mapKeyword with a verified
            # generic query. Keep the review comparison on that same safe query.
            a.maps = a.maps or a.grid

    # The cold lead magnet renders the map, its search themes and the exact GBP.
    # It does not render whole-domain traffic, organic competitor sizing, money
    # tables or the separate review comparison. Those remain available when the
    # V2 overlay is called without this explicit flag.
    if a.lead_magnet:
        a.maps = None

    domains = [a.domain] + a.competitors
    if a.dry_run:
        if a.lead_magnet:
            print("would call: maps grid x25 concurrently; profile and keyword research are reused")
            return 0
        print(f"would call: ranked_keywords x1, domain_rank_overview x{len(domains)}"
              f"{', maps x1' if a.maps else ''} - about "
              f"${0.011 + 0.011 * len(domains) + (0.002 if a.maps else 0):.3f}")
        return 0

    spend = 0.0
    client_positions: dict = {}
    client_volumes: dict = {}
    out: dict = {"domain": a.domain, "landingPages": [], "keywords": [],
                 "keywordCounts": [], "reviews": [], "missing": []}
    if a.lead_magnet:
        out["leadMagnetFastPath"] = True
        # One Labs call for the client's own rankings in normal Google results
        # (about a cent): the "where the website ranks" box beside the map.
        res = labs_post("dataforseo_labs/google/ranked_keywords/live", {
            "target": a.domain, "location_name": a.location, "language_name": a.language,
            "limit": 30, "order_by": ["ranked_serp_element.serp_item.rank_group,asc"],
        })
        spend += res.get("cost", 0)
        result = ((res.get("tasks") or [{}])[0].get("result") or [{}])[0] or {}
        out["organic"] = organic_summary(
            result.get("items") or [], a.business, [a.grid or "", a.maps or ""],
            total=result.get("total_count"),
        )
        # Every keyword the client holds, for the gap against the winner, and
        # its volume, for the demand line.
        for it in result.get("items") or []:
            data = it.get("keyword_data") or {}
            kw = str(data.get("keyword") or "").lower()
            pos = ((it.get("ranked_serp_element") or {}).get("serp_item") or {}).get("rank_group")
            if kw and pos:
                client_positions[kw] = int(pos)
                client_volumes[kw] = int((data.get("keyword_info") or {}).get("search_volume") or 0)
    if keyword_cache:
        out["keywordResearch"] = {
            "market": keyword_cache.get("market"),
            "themes": keyword_cache.get("themes") or [],
            "selectedSeeds": (keyword_cache.get("selectedSeeds")
                              or keyword_cache.get("confirmedSeeds") or []),
            "moneyKeyword": keyword_cache.get("moneyKeyword"),
            "mapKeyword": keyword_cache.get("mapKeyword"),
            "selectionNote": keyword_cache.get("selectionNote"),
            "errors": keyword_cache.get("errors") or [],
        }
        out["missing"].extend(keyword_cache.get("errors") or [])

    # 1 + 2. What the client ranks for, and where those visits land.
    #
    # This MUST run before the money-search block. Competitor sizing reads the
    # client's measured traffic; the old order read keywordCounts while it was
    # still empty, so every client was treated as a zero-traffic site.
    if not a.lead_magnet:
        res = labs_post("dataforseo_labs/google/ranked_keywords/live", {
            "target": a.domain, "location_name": a.location, "language_name": a.language,
            "limit": a.limit, "order_by": ["ranked_serp_element.serp_item.rank_group,asc"],
        })
        spend += res.get("cost", 0)
        items = ((res.get("tasks") or [{}])[0].get("result") or [{}])[0].get("items") or []
        pages: dict[str, int] = {}
        for it in items:
            el = it.get("ranked_serp_element", {}).get("serp_item", {})
            pos, kw = el.get("rank_group"), it.get("keyword_data", {}).get("keyword")
            if not pos or not kw:
                continue
            out["keywords"].append({"keyword": kw, "kind": kind(kw), "position": pos})
            url = el.get("relative_url") or "/"
            vol = it.get("keyword_data", {}).get("keyword_info", {}).get("search_volume") or 0
            pages[url] = pages.get(url, 0) + int(
                vol * (0.28 if pos <= 3 else 0.05 if pos <= 10 else 0.01)
            )
        out["keywords"] = out["keywords"][:8]
        out["landingPages"] = [
            {"path": path, "kind": kind(path), "visits": f"~{visits}/mo"}
            for path, visits in sorted(pages.items(), key=lambda item: -item[1])[:6]
        ]
        if not items:
            town = a.location.split(",")[0].strip()
            out["missing"].append(
                f"we found no search around {town} where {a.domain} comes up in the results we checked"
            )

    # 3a. Load the CLIENT overview before sizing result-page competitors. This
    # is the row `mine` actually reads; moving ranked_keywords alone would not
    # fix the bug because keywordCounts comes from domain_rank_overview.
    overview_cache: dict[str, dict] = {}

    def domain_overview(target: str) -> dict:
        nonlocal spend
        if target in overview_cache:
            return overview_cache[target]
        response = labs_post("dataforseo_labs/google/domain_rank_overview/live",
                             {"target": target, "location_name": a.location,
                              "language_name": a.language})
        spend += response.get("cost", 0)
        result = (response.get("tasks", [{}])[0].get("result") or [{}])[0]
        metrics = ((result.get("items") or [{}])[0].get("metrics") or {}).get("organic") or {}
        overview_cache[target] = metrics
        return metrics

    if not a.lead_magnet:
        client_metrics = domain_overview(a.domain)
        if client_metrics.get("count") is None:
            out["missing"].append(
                f"no traffic estimate exists for {a.domain}, so it has no bar in the comparison")
        else:
            out["keywordCounts"].append({
                "domain": a.domain,
                "keywords": client_metrics["count"],
                "visits": round(client_metrics.get("etv") or 0),
                "isClient": True,
            })

    # 0. The one search a buyer types. Everything about the money hangs off this,
    #    and so does the competitor list.
    #
    #    The old model took the leader's WHOLE domain traffic minus the client's
    #    and called the difference lost revenue. On the first audit the two firms
    #    happened to be a similar size and it looked reasonable. Run against a new
    #    site and a national agency it claimed $749,680 a month, which is when the
    #    principle became obvious: a competitor's total traffic comes from
    #    thousands of searches that have nothing to do with this client.
    #
    #    What a reader can check instead: this search runs N times a month, the
    #    top three take about this share of the clicks, you are not in it.
    if a.money and not a.lead_magnet:
        cached_search = next((row for row in (keyword_cache or {}).get("searches", [])
                              if row.get("keyword") == a.money), None)
        if cached_search:
            result = {"items": cached_search.get("resultItems") or []}
        else:
            res = post("serp/google/organic/live/advanced", [{
                "keyword": a.money, "location_name": a.location,
                "language_name": a.language, "depth": 20,
            }])
            spend += res.get("cost", 0)
            task = res["tasks"][0]
            result = (task.get("result") or [{}])[0]
        organic = [i for i in (result.get("items") or []) if i.get("type") == "organic"]

        # Whoever ranks here IS the competitive set for this search. Named by hand
        # it is a guess; taken from the result it is what the buyer actually sees.
        # Out: the client, the places everyone ranks (forums, video, social) and
        # the directories that list agencies rather than being one.
        SKIP = ("reddit.", "youtube.", "linkedin.", "facebook.", "instagram.", "tiktok.",
                "quora.", "medium.", "wikipedia.", "yelp.", "clutch.co", "g2.com",
                "trustpilot.", "indeed.", "glassdoor.", "semrush.com", "capterra.",
                # Marketplaces and listings rank for service terms without being
                # a supplier. upwork.com came third on the first real run.
                "upwork.com", "fiverr.com", "thumbtack.", "angi.com", "houzz.",
                "designrush.", "goodfirms.", "sortlist.", "expertise.com")
        own = a.domain.replace("www.", "")
        rivals, position = [], None
        for it in organic:
            dom = (it.get("domain") or "").replace("www.", "")
            if dom.endswith(own) or own.endswith(dom):
                position = position or it.get("rank_group")
                continue
            if any(s in dom for s in SKIP) or dom in rivals:
                continue
            rivals.append(dom)

        # The organic result does not carry the volume, so it takes its own call.
        # This is the number the whole money section rests on and the one the
        # reader can look up themselves, so it is worth the two tenths of a cent.
        info = ({"search_volume": cached_search.get("volume"), "cpc": cached_search.get("cpc")}
                if cached_search else {})
        if not cached_search:
            try:
                vres = post("keywords_data/google_ads/search_volume/live", [{
                    "keywords": [a.money], "location_name": a.location, "language_name": a.language,
                }])
                spend += vres.get("cost", 0)
                rows = (vres["tasks"][0].get("result") or [])
                if rows:
                    info = {"search_volume": rows[0].get("search_volume"), "cpc": rows[0].get("cpc")}
            except Exception:                                # noqa: BLE001
                pass
        # The result itself, rendered on the page. It was noted as "not pulled
        # this run - one more call would add it", which tells the client we
        # skipped a step and leaves the strongest exhibit off the page. The
        # request was already made; keeping the rows costs nothing.
        ai = next((i.get("text") or i.get("asin") for i in (result.get("items") or [])
                   if i.get("type") == "ai_overview"), None)
        out["serp"] = {
            "keyword": a.money,
            "aiOverview": ai,
            "clientAbsent": (None if position else
                             f"Not found in the result checked on {dt.date.today().isoformat()}."),
            "rows": [{
                "position": i.get("rank_group"),
                "domain": (i.get("domain") or ""),
                "title": (i.get("title") or "")[:110],
                "snippet": (i.get("description") or "")[:190],
                "breadcrumb": i.get("breadcrumb") or i.get("url") or "",
            } for i in organic[:5]],
        }

        out["money"] = {
            "keyword": a.money,
            "volume": info.get("search_volume"),
            "cpc": info.get("cpc"),
            "clientPosition": position,
            "inTop": position is not None and position <= 20,
            "rivals": rivals[:5],
            "rankingPageEstimatedVisits": next((i.get("etv") for i in organic
                                                  if (i.get("domain") or "").replace("www.", "") in rivals
                                                  and i.get("etv") is not None), None),
        }
        # Pick competitors the client could actually overtake, not the biggest
        # names on the page.
        #
        # Taking the top two produced coalitiontechnologies.com at 118,803 visits
        # a month beside a site with no rankings at all. Every number in that
        # table is true and the comparison is useless: nobody reads "they have
        # 5,244 keywords and you have none" as a plan, they read it as a reason
        # not to bother. Earlier audit tests showed the same failure.
        #
        # So: price every candidate, then choose the ones nearest the client's
        # own size. Whoever ranks for the money term is already proof the search
        # is winnable; the useful ones are the smallest of them.
        if not domains[1:] and rivals:
            sized = []
            for dom in rivals[:6]:
                met = domain_overview(dom)
                if met.get("count") is not None:
                    sized.append((dom, round(met.get("etv") or 0), met["count"]))

            mine = next((k["visits"] for k in out["keywordCounts"] if k.get("isClient")), 0) or 0
            picked = choose_comparable_competitors(sized, rivals, mine)
            domains += [p[0] for p in picked]

            skipped = [s for s in sized if s[0] not in [p[0] for p in picked]]
            out["money"]["comparable"] = [{"domain": p[0], "visits": p[1]} for p in picked]
            if skipped:
                out["money"]["skippedAsIncomparable"] = [
                    {"domain": s[0], "visits": s[1]} for s in sorted(skipped, key=lambda s: -s[1])[:4]
                ]

        if info.get("search_volume") is None:
            out["money"]["volumeNotReported"] = True

    # 3b. How many searches each selected competitor shows up for at all.
    # One request per domain, not one request with several tasks. Batched, the API
    # returns an empty result for some of the domains - measured 29 August 2026,
    # two domains batched gave data for one of them, and which one moved between
    # runs. Called singly both came back identical twice. That silently produced a
    # comparison table with a missing competitor and a money model running on a
    # number nobody had measured.
    for t in (() if a.lead_magnet else domains):
        if any(row.get("domain") == t for row in out["keywordCounts"]):
            continue
        metrics = domain_overview(t)
        count = metrics.get("count")
        if count is None:
            # The client's own domain is in `domains` too, and the block above
            # already said what it found for them. Saying it a second time in
            # slightly different words reads as us repeating the bad news.
            if t != a.domain:
                out["missing"].append(f"no traffic estimate exists for {t}, so it is left out of the comparison")
        else:
            # etv comes from the same call as the count. The comparison table and
            # the money model both read it, so the page cannot end up showing one
            # traffic figure and calculating with another.
            out["keywordCounts"].append({"domain": t, "keywords": count,
                                         "visits": round(metrics.get("etv") or 0),
                                         "isClient": t == a.domain})
    out["keywordCounts"].sort(key=lambda k: -k["keywords"])

    # 4. Who links to whom. The comparison table has a "links from other sites"
    #    column, so a script has to fill it - it was being typed in by hand, which
    #    is how a wrong count reached a page we send to strangers.
    if a.backlinks and not a.lead_magnet:
        for t in domains:
            res = post("backlinks/summary/live",
                       [{"target": t, "internal_list_limit": 1, "backlinks_status_type": "live"}])
            spend += res.get("cost", 0)
            r = (res.get("tasks", [{}])[0].get("result") or [{}])[0]
            row = next((k for k in out["keywordCounts"] if k["domain"] == t), None)
            if row and r.get("referring_domains") is not None:
                row["referringDomains"] = r["referring_domains"]
                row["backlinks"] = r.get("backlinks")
            elif r.get("referring_domains") is None:
                out["missing"].append(f"no backlink data came back for {t}")

        # One anchor text repeated across many separate sites is a link farm, and
        # it is the only backlink finding worth a sentence on the page. Reported as
        # what was counted, never as what the owner knew about it.
        res = post("backlinks/anchors/live",
                   [{"target": a.domain, "limit": 10, "order_by": ["backlinks,desc"]}])
        spend += res.get("cost", 0)
        items = ((res.get("tasks", [{}])[0].get("result") or [{}])[0].get("items") or [])
        for it in items:
            anchor = (it.get("anchor") or "").strip()
            refs = it.get("referring_domains") or 0
            # A brand or URL anchor is the normal case, not a finding - and those
            # are short. Filtering on "contains their domain" instead missed the
            # real one, because a link-farm anchor stuffs the domain in among the
            # keywords: "...Premium PBN Network Service automatable.co Rank First
            # Page Google Fast SEO Link Building Buy Backlinks Online Cheap".
            if len(anchor) <= 40 or anchor.lower().startswith("http"):
                continue
            if refs >= 5:
                out["anchorCluster"] = {"anchor": anchor, "backlinks": it.get("backlinks"),
                                        "referringDomains": refs}
                break

    # 4b. The Business Profile and the map ranking grid.
    #
    # The two exhibits a local business owner cares about most, and nothing was
    # producing them: the components had been built and no pull ever filled
    # them, so the section simply never appeared. On a remote business that is
    # correct. On a plumber it removes the point of the audit.
    #
    # The grid is the same idea as LocalFalcon: run the same search from
    # twenty-five points across their area and record where they come. It is one
    # map request per point, so about five cents for the picture that makes the
    # whole thing land.
    centre_map_items = []
    profile_summary = None
    if a.profile_json:
        try:
            profile_summary = json.loads(Path(a.profile_json).read_text())
        except (OSError, json.JSONDecodeError) as error:
            LABS_PROBLEMS.append(f"profile summary unreadable: {str(error)[:160]}")
    if a.grid and (a.coordinate or a.business):
        # The centre is THEIR address, looked up from their own listing.
        #
        # Typed by hand it was wrong on the first real run: the grid was centred
        # on Gilching for a practice registered in Gauting, so twenty-five
        # searches measured the wrong town and the map underneath showed streets
        # the reader does not recognise. A coordinate is exactly the kind of
        # thing nobody proofreads.
        lat0 = lng0 = None
        # gbp_profile.py already resolved the listing and returns its coordinates.
        # Prefer that evidence instead of paying for and waiting on another lookup.
        if a.coordinate:
            lat0, lng0 = (float(x) for x in a.coordinate.split(","))
        elif a.business:
            res = post("serp/google/maps/live/advanced", [{
                "keyword": a.business, "language_name": a.language,
                "location_name": a.location, "depth": 10,
            }])
            spend += res.get("cost", 0)
            for it in ((res["tasks"][0].get("result") or [{}])[0].get("items") or []):
                if a.business.lower() in (it.get("title") or "").lower():
                    lat0, lng0 = it.get("latitude"), it.get("longitude")
                    out.setdefault("gbpLookup", {})["address"] = it.get("address")
                    break
        if lat0 is None:
            out["missing"].append(f"could not find \"{a.business}\" on the map, so no ranking grid")
            a.grid = None

    if a.grid and lat0 is not None:
        # Five by five, --radius km from the centre to the outer points, the way
        # Local Falcon defines a grid radius. A degree of latitude is about
        # 111 km everywhere; longitude shrinks with the cosine of latitude.
        import math
        # The zoom decides what a point can see at all. Measured 05.09.2026
        # (VB Locksmith Services, Coventry, "locksmith"): at 14z the business
        # vanished 4 km from its door, at 12z it was rank 8 there, rank 14 at
        # 8 km and gone at 12 km, where Nuneaton's own locksmiths take over.
        # That decay is the heat map; the old 15 km / 14z grid drew the viewport.
        step_lat = a.radius / 111.0 / 2
        step_lng = step_lat / max(math.cos(math.radians(lat0)), 0.2)
        points = []
        for row_i in range(5):
            for col in range(5):
                lat = lat0 + (2 - row_i) * step_lat
                lng = lng0 + (col - 2) * step_lng
                points.append({
                    "keyword": a.grid, "language_name": a.language,
                    "location_coordinate": f"{lat:.5f},{lng:.5f},{a.zoom}z", "depth": 20,
                })

        # DataForSEO's Live SERP contract allows one task per request. Run the
        # independent points concurrently (bounded below its account limit),
        # then restore their original order for the map. Cost and evidence are
        # identical to a serial run; only idle network time is removed.
        with ThreadPoolExecutor(max_workers=min(10, len(points))) as pool:
            responses = list(pool.map(fetch_grid_point, points))
        grid_tasks, grid_spend, grid_failures = validated_grid_tasks(responses)
        spend += grid_spend
        grid_response = {"tasks": grid_tasks}
        ranks, centre_map_items = parse_grid_tasks(
            grid_response, a.business, a.domain, expected=25
        )
        summary = grid_summary(
            grid_response, a.business, a.domain,
            client_cid=(out.get("gbpLookup") or {}).get("cid"), expected=25,
            profile_reviews=(profile_summary or {}).get("reviews"),
            profile_rating=(profile_summary or {}).get("rating"),
        )
        out["geoGrid"] = {
            "keyword": a.grid,
            "businessName": a.business or a.domain,
            "ranks": ranks,
            "checkedPoints": len(points) - len(grid_failures),
            "requestedPoints": len(points),
            "centre": [lat0, lng0],
            "radiusKm": a.radius,
            "zoom": a.zoom,
            "points": summary["points"],
            "winners": summary["winners"],
            "rivals": summary.get("rivals"),
            "rivalsNamed": summary.get("rivalsNamed"),
            "client": summary["client"],
            "note": (
                f"Twenty-five searches for \"{a.grid}\" from twenty-five points within "
                f"{a.radius:g} km of your location."
                + (f" Across all of them {summary['rivals']} other "
                   f"{'business' if summary['rivals'] == 1 else 'businesses'} ever reached the "
                   f"top three, so this is how deep the field is."
                   if summary.get("rivals") is not None else "")
            ),
        }
        # The real map behind the badges. Without it the grid is coloured
        # squares floating on paper, and the whole point of this exhibit is that
        # the reader recognises their own town in it.
        if a.frames or a.embed_map:
            img = map_image(lat0, lng0, step_lat * 2.6, step_lng * 2.6,
                            Path(a.frames) if a.frames else None, embed=a.embed_map)
            if img:
                out["geoGrid"]["mapImage"] = img
                out["geoGrid"]["attribution"] = "Map data © OpenStreetMap contributors"

    # 4b. Normal Google results, measured against the map winners' websites:
    # their standing on the client's measure, who holds page one for the town
    # term, and the local searches a comparable winner has that the client
    # lacks. Four small calls, run together, about seven cents.
    if a.lead_magnet and isinstance(out.get("organic"), dict):
        winners = (out.get("geoGrid") or {}).get("winners") or []
        host = normalise_domain(a.domain)
        winner_domains = [w["domain"] for w in winners if w.get("domain") and w["domain"] != host][:3]

        def overview(target: str) -> tuple[str, dict, float]:
            res = labs_post("dataforseo_labs/google/domain_rank_overview/live", {
                "target": target, "location_name": a.location, "language_name": a.language,
            })
            items = (((res.get("tasks") or [{}])[0].get("result") or [{}])[0] or {}).get("items") or []
            metrics = ((items[0] if items else {}).get("metrics") or {}).get("organic") or {}
            return target, {
                "keywords": metrics.get("count") or 0,
                "pageOne": sum(int(metrics.get(k) or 0) for k in ("pos_1", "pos_2_3", "pos_4_10")),
                "visits": int(round(metrics.get("etv") or 0)),
            }, float(res.get("cost") or 0)

        with ThreadPoolExecutor(max_workers=4) as pool:
            overviews = list(pool.map(overview, [host] + winner_domains))
        spend += sum(cost for _, _, cost in overviews)
        overview_by = {target: metrics for target, metrics, _ in overviews}

        serp_items: list = []
        if a.money and a.coordinate:
            lat, lng = a.coordinate.split(",")[:2]
            res = post("serp/google/organic/live/advanced", [{
                "keyword": a.money, "location_coordinate": f"{lat},{lng}",
                "language_name": a.language, "depth": 10,
            }])
            spend += res.get("cost", 0)
            serp_items = (((res.get("tasks") or [{}])[0].get("result") or [{}])[0] or {}).get("items") or []

        gap_items: list = []
        comparable = comparable_winner(
            winners, overview_by, overview_by.get(host, {}).get("keywords") or 0,
            overview_by.get(host, {}).get("pageOne") or 0,
        )
        if comparable and comparable.get("domain"):
            res = labs_post("dataforseo_labs/google/ranked_keywords/live", {
                "target": comparable["domain"], "location_name": a.location, "language_name": a.language,
                "limit": 100, "order_by": ["keyword_data.keyword_info.search_volume,desc"],
            })
            spend += res.get("cost", 0)
            gap_items = (((res.get("tasks") or [{}])[0].get("result") or [{}])[0] or {}).get("items") or []

        out["organic"].update(organic_section(
            out["organic"], winners, overview_by, serp_items, gap_items, client_positions,
            a.business, [a.grid or "", a.maps or ""], host, a.money, client_volumes,
            a.location or "",
        ))

    # 4c. Their Business Profile, field by field.
    #
    # Jono's spec named this source and nobody built it: the panel on the page
    # was hand-seeded, so the exhibit would have come out empty for the first
    # real local client. Same failure as the ranking grid, one layer down.
    #
    # There is no posts endpoint - my_business_updates 404s - so the audit says
    # posts could not be checked rather than guessing at them.
    if profile_summary:
        out["gbp"] = gbp_from_summary(profile_summary, a.business or a.domain)
    elif a.business:
        res = post("business_data/google/my_business_info/live", [{
            "keyword": a.business, "location_name": a.location, "language_name": a.language,
        }])
        spend += res.get("cost", 0)
        items = ((res.get("tasks", [{}])[0].get("result") or [{}])[0].get("items") or [])
        b = items[0] if items else None
        if b:
            rating = (b.get("rating") or {})
            photos = b.get("total_photos")
            hours = b.get("work_time", {}).get("work_hours")
            # One grader, two sources. These rows used to be built here with
            # their own thresholds, and the two paths disagreed with each other
            # inside the same report object: the same profile scored differently
            # depending on which source answered first. The lookup is reshaped
            # into the summary the grader already reads.
            address = b.get("address") or ""
            out["gbp"] = gbp_from_summary({
                "name": b.get("title") or a.business,
                "category": b.get("category"),
                "categories": ([b.get("category")] if b.get("category") else [])
                              + list(b.get("additional_categories") or []),
                "city": (address.split(",")[-2].strip() if address.count(",") >= 2 else ""),
                "address": address,
                "phone": b.get("phone"),
                "website": b.get("url"),
                "opening_hours": hours or [],
                "photos": photos,
                "reviews": rating.get("votes_count") or 0,
                "rating": rating.get("value"),
                "description": b.get("description") or "",
                "is_claimed": b.get("is_claimed"),
                "attributes": b.get("attributes") or {},
                "booking_links": b.get("book_online_link") or [],
                "service_items": [],
                "owner_updates": [],
                "rich_evidence": False,
            }, a.business or a.domain)
            out["gbp"]["auditNote"] = (
                "Every row describes public profile evidence. Posts and account-only "
                "settings are marked for confirmation rather than graded."
            )

    # 5. The map pack and the one thing it ranks on.
    # A coordinate pins the search to a spot, which is better when the client has
    # a service area. But requiring one is why this pull kept getting skipped, and
    # a skipped pull is why the reviews column was empty. A place name works just
    # as well: measured 29 August 2026 against the same search run through Apify's
    # Maps scraper, both returned the same listings with the same review counts.
    if a.maps:
        where = {}
        if a.coordinate:
            lat, lng = a.coordinate.split(",")
            where["location_coordinate"] = f"{lat.strip()},{lng.strip()},{a.zoom}z"
        elif a.location:
            where["location_name"] = a.location
        if centre_map_items and a.maps == a.grid:
            items = centre_map_items
        else:
            res = post("serp/google/maps/live/advanced", [{
                "keyword": a.maps, "language_name": a.language, "depth": 10, **where,
            }])
            spend += res.get("cost", 0)
            items = ((res["tasks"][0].get("result") or [{}])[0].get("items") or [])
        client_cid = (out.get("gbpLookup") or {}).get("cid")
        for it in items[:4]:
            review = map_review(it, a.domain, client_cid)
            if review:
                out["reviews"].append(review)
        if not out["reviews"]:
            out["missing"].append(f"no map pack came back for '{a.maps}' - "
                                  "either the client has no service area, or the keyword is wrong")

    # "no search data came back for x.de" printed twice, because two blocks each
    # noticed the same absence. Order is kept; only repeats go.
    out["missing"] = list(dict.fromkeys(out["missing"]))
    out["spend"] = round(spend, 4)
    json.dump(out, sys.stdout, indent=2, ensure_ascii=False)
    print()
    print(f"spent ${spend:.4f} on this run", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
