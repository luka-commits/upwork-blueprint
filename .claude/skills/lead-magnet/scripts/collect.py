#!/usr/bin/env python3
"""Run the evidence chain once and finish with a compact operator briefing.

The order is fixed: pull_cro writes cro.json, proposal_keywords needs that file
and writes the keyword cache, then pull_search reads the cache. The market is
always passed explicitly with --market rather than inferred.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import time
import unicodedata

try:
    from instrument import step
except ModuleNotFoundError:  # importlib-based local tests do not add this folder to sys.path
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    from instrument import step

ERRORS: list[str] = []
NOTES: list[str] = []
# A second call in the same run may reuse the measurement. A later run may not.
CRO_MAX_ALTER_S = 6 * 3600


def werkbank_laden() -> None:
    """Restore the optional local browser toolchain saved by setup.sh."""
    file_path = pathlib.Path("scripts/.werkbank")
    if not file_path.exists():
        return
    for line in file_path.read_text().splitlines():
        name, _, value = line.partition("=")
        if not name or not value:
            continue
        if name == "PATH":
            # Extend rather than replace the current shell path.
            fehlend = [t for t in value.split(":") if t and t not in os.environ["PATH"].split(":")]
            os.environ["PATH"] = ":".join([*fehlend, os.environ["PATH"]])
        elif not os.environ.get(name, "").startswith(("http", "/")):
            os.environ[name] = value


def lauf(befehl: list[str], ziel: pathlib.Path | None, name: str) -> bool:
    """Run one chain step, writing stdout to its evidence file."""
    print(f"→ {name}", file=sys.stderr)
    with step(name):
        ergebnis = subprocess.run(befehl, capture_output=True, text=True)
    if ergebnis.stderr.strip():
        print(ergebnis.stderr.strip()[-1500:], file=sys.stderr)
    if ergebnis.returncode != 0:
        ERRORS.append(f"{name}: Exit {ergebnis.returncode}")
        return False
    if ziel is not None:
        ziel.write_text(ergebnis.stdout)
        if len(ergebnis.stdout) < 200:
            ERRORS.append(f"{name}: output is too thin at {len(ergebnis.stdout)} characters")
            return False
    else:
        print(ergebnis.stdout.strip()[:4000])
    return True


def sicher(wert, grenze: int = 400) -> str:
    """Never print embedded image data into the run log."""
    text = json.dumps(wert, ensure_ascii=False) if not isinstance(wert, str) else wert
    if "data:image" in text or "base64," in text:
        return "<embedded image data omitted>"
    return text[:grenze]


def tempo_nachholen(cro_datei: pathlib.Path, url: str) -> None:
    """Retry the local Lighthouse measurement once when the first result is empty."""
    daten = laden(cro_datei, "cro.json")
    if not daten or (daten.get("speed") or {}).get("ok"):
        return
    if not shutil.which("lighthouse"):
        ERRORS.append("Speed: local Lighthouse is unavailable; run setup first")
        return

    print("→ Mobile speed second attempt", file=sys.stderr)
    try:
        roh = subprocess.run(
            ["lighthouse", url, "--quiet", "--output=json", "--output-path=stdout",
             "--only-categories=performance,accessibility,best-practices,seo", "--form-factor=mobile",
             "--screenEmulation.mobile",
             "--chrome-flags=--headless=new --no-sandbox --ignore-certificate-errors"],
            capture_output=True, text=True, timeout=180)
        bericht_json = json.loads(roh.stdout)
    except Exception as fehler:                              # noqa: BLE001
        ERRORS.append(f"Speed: the second attempt also failed ({fehler})")
        return

    pruefungen = bericht_json.get("audits") or {}
    lcp = (pruefungen.get("largest-contentful-paint") or {}).get("numericValue")
    kategorien = bericht_json.get("categories") or {}
    punkte = (kategorien.get("performance") or {}).get("score")
    scores = {
        name: round(((kategorien.get(name) or {}).get("score") or 0) * 100)
        for name in ("performance", "accessibility", "best-practices", "seo")
        if (kategorien.get(name) or {}).get("score") is not None
    }
    if lcp is None:
        ERRORS.append("Speed: the second attempt returned no timing")
        return
    daten["speed"] = {"ok": True, "lcp": f"{lcp / 1000:.1f} s",
                      "score": round((punkte or 0) * 100), "scores": scores, "frames": [],
                      "note": "zweiter Anlauf, ohne Filmstreifen"}
    cro_datei.write_text(json.dumps(daten))


def strip_filmstrip(cro_datei: pathlib.Path) -> dict:
    """Drop unused PageSpeed thumbnails but preserve the rendered page proof."""
    try:
        before = cro_datei.stat().st_size
        data = json.loads(cro_datei.read_text())
        speed = data.get("speed") or {}
        frames = speed.get("frames") or []
        if not frames or not speed.get("screenshot"):
            return {"stripped": False, "before_bytes": before, "after_bytes": before}
        speed["frames"] = []
        temporary = cro_datei.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(data, ensure_ascii=False))
        temporary.replace(cro_datei)
        return {
            "stripped": True,
            "before_bytes": before,
            "after_bytes": cro_datei.stat().st_size,
            "frames_removed": len(frames),
        }
    except (OSError, json.JSONDecodeError, TypeError) as error:
        NOTES.append(f"Could not remove unused filmstrip frames: {error}")
        return {"stripped": False}


def pruefliste_passt(cro_datei: pathlib.Path) -> bool:
    """Reuse only evidence created with the current checklist."""
    try:
        gemessen = {e.get("key") for e in (json.loads(cro_datei.read_text()).get("elements") or [])}
        quelle = (pathlib.Path("code/pull_cro.py").read_text()
                  if pathlib.Path("code/pull_cro.py").exists() else "")
        erwartet = set(re.findall(r'^\s*\("([a-z_]+)",\s*"', quelle, re.M))
        return bool(erwartet) and erwartet.issubset(gemessen)
    except (OSError, json.JSONDecodeError, TypeError):
        return False


def laden(pfad: pathlib.Path, name: str) -> dict:
    try:
        return json.loads(pfad.read_text())
    except (OSError, json.JSONDecodeError) as fehler:
        ERRORS.append(f"{name}: unreadable ({fehler})")
        return {}


def _compact(value: str) -> str:
    folded = unicodedata.normalize("NFKD", value.casefold())
    ascii_value = "".join(ch for ch in folded if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]", "", ascii_value)


def _looks_like_brand_query(row: dict, business: str) -> bool:
    """Use the already-pulled SERP to reject own and competitor brand terms."""
    raw_keyword = str(row.get("keyword") or "")
    keyword = _compact(raw_keyword)
    keyword_words = re.findall(r"[a-z0-9]+", unicodedata.normalize(
        "NFKD", raw_keyword.casefold()
    ).encode("ascii", "ignore").decode())
    if not keyword:
        return True
    own = _compact(business)
    if own and (
        own == keyword
        or (len(keyword_words) >= 2 and (own in keyword or keyword in own))
    ):
        return True
    for item in row.get("resultItems") or []:
        if item.get("type") not in {"local_pack", "maps", "map"}:
            continue
        names = [item.get("title")]
        names.extend(
            candidate.get("title")
            for candidate in item.get("items") or []
            if isinstance(candidate, dict)
        )
        for name in names:
            title = _compact(str(name or ""))
            if len(title) >= 5 and (
                title == keyword
                or (len(keyword_words) >= 2 and (title in keyword or keyword in title))
            ):
                return True
    return False


def grid_term_without_city(term: str, city: str) -> str:
    """The grid searches from a coordinate, so the term carries no town.

    "Locksmith Coventry" from a point 4 km north of Coventry returned three
    junk results; the bare "locksmith" returned the full local ranking
    (measured 05.09.2026). The town-qualified term stays the organic check.
    """
    term = (term or "").strip()
    city = (city or "").strip()
    if not term or not city:
        return term
    stripped = re.sub(rf"\s+{re.escape(city)}\s*$", "", term, flags=re.I).strip()
    return stripped or term


def choose_grid_keyword(cache: dict, business: str) -> str | None:
    """Pick the strongest checked generic search with a real local pack."""
    if cache.get("market") != "local":
        return None
    searches = cache.get("searches") or []
    preferred = _compact(str(cache.get("mapKeyword") or ""))
    ordered = [
        row for row in searches
        if preferred and _compact(str(row.get("keyword") or "")) == preferred
    ]
    ordered.extend(row for row in searches if row not in ordered)
    for row in ordered:
        if row.get("hasLocalPack") and not _looks_like_brand_query(row, business):
            return str(row.get("keyword") or "").strip() or None
    return None


def keyword_cache_reusable(
    cache: dict,
    *,
    market: str,
    auto_grid: bool,
    business: str,
    location: str = "",
) -> bool:
    """Reuse evidence only when it can still produce the promised report."""
    if cache.get("stage") != "complete" or cache.get("market") != market:
        return False
    if location and cache.get("location") != location:
        return False
    if market == "local" and auto_grid:
        return bool(cache.get("mapKeyword") and choose_grid_keyword(cache, business))
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", required=True, help="vollstaendige Startseite")
    ap.add_argument("--domain", required=True)
    ap.add_argument("--business", required=True)
    ap.add_argument("--location", required=True, help="DataForSEO-Location, z. B. United Kingdom")
    ap.add_argument("--language", default="English")
    ap.add_argument("--market", required=True, choices=("local", "national", "remote"),
                    help="explicit market decision from the confirmed business profile")
    ap.add_argument("--coordinate", default="", help="lat,lng aus gbp_profile.py")
    ap.add_argument("--grid", default="",
                    help="keyword for the 25-point grid; without it the run stops after keyword research")
    ap.add_argument("--auto-grid", action="store_true",
                    help="use the strongest verified generic local-pack term, or omit an unsafe grid")
    ap.add_argument("--country-code", default="")
    ap.add_argument("--radius", type=float, default=0.0,
                    help="km vom Zentrum zu den aeusseren Rasterpunkten; 0 = Vorgabe von pull_search")
    ap.add_argument("--zoom", type=int, default=0, help="Kartenzoom je Rasterpunkt; 0 = Vorgabe von pull_search")
    ap.add_argument("--outdir", required=True)
    a = ap.parse_args()

    werkbank_laden()

    # Aus engine/ aufrufen, sonst zeigen die relativen Pfade ins Leere.
    if not pathlib.Path("code/pull_cro.py").exists():
        print("Run from the skill directory: code/pull_cro.py is not visible here",
              file=sys.stderr)
        return 2

    out = pathlib.Path(a.outdir)
    out.mkdir(parents=True, exist_ok=True)
    os.environ["POCKET_CEO_METRICS_DIR"] = str(out)
    cro_datei, cache_datei, search_datei = (out / "cro.json", out / "keyword-cache.json",
                                            out / "search.json")
    # Der Seitentext faellt beim CRO-Lauf ohnehin an. Er bleibt aus cro.json
    # Keep page text outside cro.json, which is the client-facing checklist.
    site_datei = out / "site.json"

    # A second call with --grid reuses evidence from the same run.
    # Die Wiederverwendung ist fuer den zweiten Aufruf im selben Lauf gedacht,
    # The age and checklist guards prevent an old measurement from being reused.
    frisch = (cro_datei.exists() and cro_datei.stat().st_size > 200
              and (time.time() - cro_datei.stat().st_mtime) < CRO_MAX_ALTER_S
              and pruefliste_passt(cro_datei))
    if frisch:
        print("-> pull_cro reused from this run", file=sys.stderr)
        cro_ok = True
    else:
        cro_ok = lauf(["python3", "code/pull_cro.py", a.url, "--embed-frames",
                       "--site-out", str(site_datei)],
                      cro_datei, "pull_cro")
    if not cro_ok:
        # Keyword research cannot start without complete CRO evidence.
        bericht({}, {}, {}, out)
        return 1

    tempo_nachholen(cro_datei, a.url)
    strip_result = strip_filmstrip(cro_datei)
    if strip_result.get("stripped"):
        print(
            f"→ Filmstreifen entfernt: {strip_result['before_bytes']} → "
            f"{strip_result['after_bytes']} Bytes",
            file=sys.stderr,
        )

    keyword_befehl = ["python3", "code/proposal_keywords.py", a.domain,
                      "--cro", str(cro_datei), "--cache", str(cache_datei),
                      "--location", a.location, "--language", a.language,
                      "--business", a.business, "--market", a.market]
    profile_datei = out / "gbp-profile.json"
    if profile_datei.exists():
        keyword_befehl += ["--profile-json", str(profile_datei)]
    if a.country_code:
        keyword_befehl += ["--country-code", a.country_code]
    existing_cache = (
        laden(cache_datei, "keyword-cache.json")
        if cache_datei.exists() and cache_datei.stat().st_size > 200
        else {}
    )
    if keyword_cache_reusable(
        existing_cache,
        market=a.market,
        auto_grid=a.auto_grid,
        business=a.business,
        location=a.location,
    ):
        print("-> proposal_keywords reused a valid cache", file=sys.stderr)
        keywords_ok = True
    else:
        if existing_cache:
            print("-> proposal_keywords refreshes an incomplete grid cache", file=sys.stderr)
        keywords_ok = lauf(keyword_befehl, None, "proposal_keywords")

    # Never guess the grid term. mapKeyword is a candidate, not a verdict.
    cache = laden(cache_datei, "keyword-cache.json") if keywords_ok else {}
    grid = a.grid
    if keywords_ok and a.auto_grid and not grid:
        grid = choose_grid_keyword(cache, a.business)
        if grid:
            print(f"→ Map grid term verified automatically: {grid!r}", file=sys.stderr)
        elif cache.get("market") == "local":
            NOTES.append("No safe generic local-pack term; map grid omitted")

    if keywords_ok and not grid and not a.auto_grid:
        print("\n=== Stopped before the map grid ===")
        print(f"mapKeyword: {cache.get('mapKeyword')!r}")
        print(f"moneyKeyword: {cache.get('moneyKeyword')!r}")
        print(f"Market: {cache.get('market')} - {cache.get('marketReason')}")
        print("A term containing any brand name is invalid.")
        print("Choose the strongest generic service term.")
        print("Continue with the same command plus --grid \"<term>\"; existing evidence remains available.")
        return 0

    search: dict = {}
    if keywords_ok:
        search_befehl = ["python3", "code/pull_search.py", a.domain,
                         "--keyword-cache", str(cache_datei), "--embed-map",
                         "--location", a.location, "--language", a.language,
                         "--business", a.business, "--lead-magnet"]
        if profile_datei.exists():
            search_befehl += ["--profile-json", str(profile_datei)]
        if grid:
            search_befehl += ["--grid", grid_term_without_city(grid, str(cache.get("profileCity") or ""))]
        if a.coordinate:
            search_befehl += ["--coordinate", a.coordinate]
        if a.radius:
            search_befehl += ["--radius", str(a.radius)]
        if a.zoom:
            search_befehl += ["--zoom", str(a.zoom)]
        lauf(search_befehl, search_datei, "pull_search")
        search = laden(search_datei, "search.json")
    else:
        ERRORS.append("pull_search: skipped because keyword research failed")

    bericht(laden(cro_datei, "cro.json"), laden(cache_datei, "keyword-cache.json"), search, out)
    return 0 if not ERRORS else 1


def bericht(cro: dict, cache: dict, search: dict, out: pathlib.Path) -> None:
    """Print a compact operator briefing and the evidence paths."""
    try:
        _bericht(cro, cache, search, out)
    except Exception as fehler:                              # noqa: BLE001
        # The evidence remains valid if this convenience summary fails.
        print(f"\n=== Briefing incomplete ({fehler}) ===")
        print(f"The evidence still remains at: {out}/cro.json, {out}/keyword-cache.json, "
              f"{out}/search.json")


def _bericht(cro: dict, cache: dict, search: dict, out: pathlib.Path) -> None:
    print("\n=== Briefing ===")
    # `have` and `total` are numbers, while older snapshots may use a list.
    have, gesamt = cro.get("have"), cro.get("total")
    fehlend = cro.get("missing")
    if isinstance(have, int) and isinstance(gesamt, int):
        print(f"Conversion: {have} of {gesamt} elements found")
    elif isinstance(have, list):
        print(f"Conversion: {len(have)} found")
    if isinstance(fehlend, list) and fehlend:
        print(f"  missing: {sicher(fehlend[:8])}")
    speed = cro.get("speed") or {}
    if speed:
        print(f"Mobile speed: {speed.get('score')} / LCP {speed.get('lcp')}")
    for feld in ("observed", "findings"):
        if cro.get(feld):
            print(f"Visible findings: {sicher(cro[feld])}")
            break

    if cache:
        print(f"Market: {cache.get('market')} - {cache.get('marketReason')}")
        print(f"Money keyword: {cache.get('moneyKeyword')} | Map keyword: {cache.get('mapKeyword')}")
        if cache.get("errors"):
            ERRORS.append(f"keyword-cache reported errors: {cache['errors']}")

    raster = (search.get("geoGrid") or {})
    if raster:
        raenge = [r for r in (raster.get("ranks") or []) if isinstance(r, int)]
        top3 = sum(1 for r in raenge if r <= 3)
        print(f"Map grid '{raster.get('keyword')}': top 3 at {top3} of {len(raenge)} points")
    if search.get("missing"):
        print(f"Missing organic evidence: {sicher(search['missing'])}")
    if search.get("reviews"):
        print(f"Review comparison: {sicher(search['reviews'])}")

    print(f"\nFiles: {out}/cro.json, {out}/keyword-cache.json, {out}/search.json")
    print("\nMissing sources:")
    print("\n".join(f"  - {z}" for z in ERRORS) if ERRORS else "  none")
    if NOTES:
        print("\nIntentional omissions:")
        print("\n".join(f"  - {z}" for z in NOTES))


if __name__ == "__main__":
    raise SystemExit(main())
