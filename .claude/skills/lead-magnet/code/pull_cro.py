#!/usr/bin/env python3
"""Pull the conversion layer of a client's page: the 15-element checklist and
the real mobile loading filmstrip.

    python3 code/pull_cro.py https://example.com
    python3 code/pull_cro.py https://example.com --frames website/public/images/proposal

Two things come back, and both are measured, never inferred:

  1. Which of the 15 conversion elements the page actually carries. Every
     element reports present/absent PLUS the evidence that decided it, so a
     wrong call is arguable instead of invisible.
  2. The mobile filmstrip from PageSpeed Insights - the real frames of the
     page painting, with their timings, plus LCP. Frames are written as jpgs
     and referenced by path; without PAGESPEED_API_KEY the anonymous quota is
     usually exhausted, and then this half says so rather than guessing.

Output is JSON on stdout - the shape the proposal's CRO section consumes.
Exit 1 only when the page itself could not be fetched. A failed PageSpeed run
degrades the speed half and keeps the checklist.
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import html as html_lib
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from workspace import workspace_root

ROOT = workspace_root()
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

# The 15 elements, in Jono's order: the nine a decent page usually has, then
# the six that are almost always missing and are where the money leaks.
# Each: (key, label, why it matters when absent).
#
# The labels are printed on the client's page, so they are named the way the
# client would name them. "CTA", "above the fold", "social proof" and "lead
# magnet" are our words for our own trade, and a reader who has to decode a
# label stops reading the list.
ELEMENTS = [
    ("cta_above_fold", "Something to click before you scroll",
     "Nothing to click before the first scroll - the readiest visitors leave first"),
    ("cta_repeated", "The same invitation further down the page",
     "One invitation at the top only - anyone convinced further down has nowhere to go"),
    ("click_to_call", "A phone number you can tap to call",
     "The phone number is not tappable, so a phone visitor has to copy it by hand"),
    ("lead_form", "A form they can fill in",
     "No form on the page - every enquiry has to start with a phone call"),
    ("testimonials", "Written customer reviews on the website",
     "No customer words on the page - the visitor only has your word for it"),
    ("social_proof_numbers", "A count of jobs, customers or years in business",
     "No counts (jobs done, years, customers) - scale has to be taken on faith"),
    ("review_badges", "Your Google or Trustpilot rating on the website",
     "No third-party rating on the page - the proof lives somewhere the visitor has to go find"),
    ("faq", "Answers to the questions people always ask",
     "No answers on the page - the doubts that stop a booking stay unanswered"),
    ("online_booking", "A way to book a time without calling",
     "Nothing to book - the visitor has to wait for office hours"),
    ("video_top", "A short owner or team introduction video",
     "No video found - a video of you near the top is the quickest way to show there are people behind the site"),
    ("video_testimonials", "A customer video review",
     "One or zero videos - a customer saying it on camera carries further than the same words in text"),
    ("logo_wall", "Customer, partner or membership logos",
     "No recognisable names on the page - the credibility they would lend you is sitting unused"),
    ("response_time", "A promise of how fast you reply",
     'No reply-time promise - "we answer within the hour" beats a competitor who answers in two days'),
    ("lead_magnet", "Something free worth leaving an email for",
     "Nothing free in exchange for an email - a guide or a calculator gets far more of them"),
    ("email_capture", "A way to collect an email address",
     "Nothing holds on to a visitor who is interested but not ready today"),
    ("form_short", "A form short enough to finish",
     "The form asks for more than four things - every extra field loses submissions"),
    ("form_button_says_outcome", "A button that names what happens next",
     'The button says "Submit" instead of the outcome, so the last click is the vaguest one'),
    ("phone_speed", "A page that loads in under two seconds on a phone",
     "The page takes longer than two seconds on a phone, and most of the visit is spent waiting"),
]

CTA_WORDS = (r"book|call|quote|get started|contact|schedule|request|enquire|inquire|"
             r"free estimate|shop|add to cart|order|view menu|see menu|reserve|"
             r"termin|anfrage|angebot|jetzt")
VIDEO = r"<video[\s>]|youtube\.com/embed|youtu\.be/|player\.vimeo\.com|wistia|loom\.com/embed"


# Whether each page came back rendered. Two runs over the same site returned
# 5/15 and 8/15 depending on whether the render succeeded, and nothing on the
# page said which had happened - so a client's score, and three "you are missing
# this" findings, turned on a silent failure. The run now reports it.
RENDERED: list[bool] = []

# Hosts that never answer a plain fetch. One timeout is a measurement; twelve is
# a waste of a minute.
DEAF_HOSTS: set[str] = set()


def fetch_raw(url: str) -> tuple[str, str]:
    """The markup the server sends, no rendering.

    Enough for anything that only reads links or text: the link map, the price
    probe, the sitemap walk. Sending those through the renderer burnt a credit
    per page and hit the rate limit, which then made the checks that DO need
    rendering fall back to raw - the one place it matters.

    Six seconds, then Firecrawl. Measured on munichleadership.com: the server
    answers curl and Firecrawl in about a second each and simply never replies
    to urllib, so every plain fetch sat out the full thirty-second timeout.
    Seven of them in the link map and four in the price probe turned a
    one-minute audit into six minutes of waiting on a socket. Firecrawl was
    never the slow part; this was.

    Remembered per host, because a server that ignores urllib once ignores it
    every time: without that, twelve pages each paid the six seconds again.
    """
    host = url.split("/")[2] if "//" in url else url
    if host not in DEAF_HOSTS:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en,de"})
        try:
            with urllib.request.urlopen(req, timeout=6) as r:
                return r.read().decode("utf-8", "replace"), r.geturl()
        except urllib.error.HTTPError:
            raise                                            # a real 404 is an answer
        except Exception:                                    # noqa: BLE001
            DEAF_HOSTS.add(host)
    html = firecrawl_html(url)
    if html:
        return html, url
    raise RuntimeError(f"neither a plain fetch nor a render returned {url}")


def fetch(url: str) -> tuple[str, str]:
    """The page as a visitor sees it: rendered where we can, raw where we cannot.

    A plain fetch returns the markup the server sent, and on a site that paints
    itself with JavaScript that markup is a shell. Every conversion element then
    reads as absent, and the audit tells somebody their booking widget and their
    form are missing when both are on the page - the single fastest way to lose
    a reader who knows their own site.

    Firecrawl renders it first. It costs a credit and about two seconds, and it
    is the difference between auditing their website and auditing their HTML.
    Without a key, or if it fails, this falls back to the plain fetch rather
    than stopping: a shell we can label beats no audit.
    """
    rendered = firecrawl_html(url)
    RENDERED.append(bool(rendered))
    if rendered:
        return rendered, url
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en,de"})
    # A busy shared host answers 503 for a second and is fine on the next
    # knock. On 07.09.2026 two such seconds cost a prospect his whole report:
    # the run stopped, nothing was sent, and the site answered 200 when checked
    # by hand minutes later. Only the transient codes are retried, so a genuine
    # 404 or 403 still fails immediately.
    last: Exception | None = None
    for attempt, pause in enumerate((0, 3, 9)):
        if pause:
            time.sleep(pause)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8", "replace"), r.geturl()
        except urllib.error.HTTPError as error:
            last = error
            if error.code not in (429, 500, 502, 503, 504, 522, 524):
                raise
            print(f"fetch {url}: HTTP {error.code}, attempt {attempt + 1} of 3", file=sys.stderr)
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            last = error
            print(f"fetch {url}: {error}, attempt {attempt + 1} of 3", file=sys.stderr)
    raise last if last else RuntimeError(f"fetch {url} failed")


def firecrawl_key() -> str:
    key = os.environ.get("FIRECRAWL_API_KEY", "")
    if key:
        return key
    # This portable skill reads only the repository-owned configuration. It
    # must never inherit personal machine credentials when transferred.
    for path in (ROOT / ".env",):
        if path.exists():
            for line in path.read_text().splitlines():
                if "FIRECRAWL_API_KEY=" in line and not line.strip().startswith("#"):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def firecrawl_leer() -> str:
    """Return an empty string when credit remains, otherwise the reason.

    One test request answers the budget question before a full run starts.
    """
    key = firecrawl_key()
    if not key:
        return "no FIRECRAWL_API_KEY; every page would be checked unrendered"
    body = json.dumps({"url": "https://example.com", "formats": ["rawHtml"],
                       "waitFor": 0, "timeout": 8000}).encode()
    req = urllib.request.Request(
        "https://api.firecrawl.dev/v2/scrape", data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            payload = json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as error:
        return f"Firecrawl answered HTTP {error.code}: {error.read().decode('utf-8', 'replace')[:160]}"
    except Exception as error:  # noqa: BLE001 - no rendered page means no report
        return f"Firecrawl is unreachable ({error})"
    if payload.get("success"):
        return ""
    return f"Firecrawl refused: {str(payload.get('error') or payload)[:160]}"


def firecrawl_html(url: str) -> str | None:
    key = firecrawl_key()
    if not key:
        return None
    # Twenty-five seconds, not sixty. Five pages at a minute each turned one
    # prospect's audit into a six-minute wait, and a page that needs more than
    # twenty-five seconds to paint has told us something already.
    body = json.dumps({"url": url, "formats": ["rawHtml"], "onlyMainContent": False,
                       "waitFor": 800, "timeout": 20000}).encode()
    req = urllib.request.Request(
        "https://api.firecrawl.dev/v2/scrape", data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=28) as r:
            payload = json.loads(r.read())
    except Exception:                                        # noqa: BLE001
        return None
    html = (payload.get("data") or {}).get("rawHtml")
    return html if html and len(html) > 500 else None


def snippet(html: str, pattern: str, width: int = 70) -> str:
    m = re.search(pattern, html, re.I | re.S)
    if not m:
        return ""
    s = re.sub(r"\s+", " ", html[max(0, m.start() - 15): m.start() + width]).strip()
    return s[:120]


# Keep this narrow: a generic error word is not enough to reject a real page.
FEHLERSEITE = re.compile(
    r"\b404\b|page\s*not\s*found|\bnot\s*found\b|seite\s*n" r"icht\s*gefunden"
    r"|ni" r"chts?\s*gefunden|\boops\b", re.I)


def ist_fehlerseite(html: str) -> bool:
    """Return whether the fetched document is an error page.

    Only the title is checked so legitimate body copy about errors does not
    make a service page disappear.
    """
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    if not m:
        return False
    titel = re.sub(r"\s+", " ", html_lib.unescape(m.group(1))).strip()
    # The company name usually follows a separator in the title.
    kopf = re.split(r"\s[--|·]\s", titel)[0]
    return bool(FEHLERSEITE.search(kopf))


def visible_text(html: str) -> str:
    """Approximate visitor-visible text without scripts, styles or templates."""
    cleaned = re.sub(r"<(script|style|template|noscript)\b[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    return html_lib.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", cleaned))).strip()


FORM_FIELD_LIMIT = 4  # Shipped Pocket CEO operating benchmark
PHONE_SECONDS = 2.0   # Shipped Pocket CEO operating benchmark
SUBMIT_FILLER = r"^\s*(submit|send|absenden|senden|go|ok)\s*$"


def enquiry_form_shape(html: str) -> dict:
    """Field count and button wording of the first customer enquiry form.

    The operating benchmark ranks the short form above almost everything else, and both
    numbers were already in the pull: until 07.09.2026 a nine-field form with a
    "Submit" button scored exactly like a three-field one with "Get my quote".
    """
    for attrs, body in re.findall(r"<form\b([^>]*)>(.*?)</form>", html, re.I | re.S):
        form_html = f"{attrs} {body}"
        context = f"{attrs} {visible_text(body)}".lower()
        if re.search(r"cart|search|newsletter|subscribe|customer_login|localization", context):
            continue
        fields = [tag for tag in re.findall(r"<(?:input|textarea|select)\b([^>]*)>", body, re.I | re.S)
                  if not re.search(r"type=[\"']?(hidden|submit|button|image)", tag, re.I)]
        if len(fields) < 2:
            continue
        buttons = re.findall(r"<button\b[^>]*>(.*?)</button>", body, re.I | re.S)
        buttons += re.findall(r"<input\b[^>]*type=[\"']?submit[^>]*value=[\"']([^\"']+)", body, re.I)
        words = [visible_text(item).strip() for item in buttons]
        words = [word for word in words if word]
        return {"fields": len(fields), "button": words[0] if words else "",
                "outcome_button": bool(words) and not re.match(SUBMIT_FILLER, words[0], re.I)}
    return {}


def form_kinds(html: str) -> tuple[list[str], list[str]]:
    """Separate customer enquiry forms from utility and newsletter forms."""
    enquiry, email = [], []
    for attrs, body in re.findall(r"<form\b([^>]*)>(.*?)</form>", html, re.I | re.S):
        form_html = f"{attrs} {body}"
        text = visible_text(body)
        inputs = re.findall(r"<(?:input|textarea|select)\b([^>]*)>", body, re.I | re.S)
        types = " ".join(re.findall(r"type=[\"']?([^\"'\s>]+)", form_html, re.I)).lower()
        names = " ".join(re.findall(r"(?:name|id|placeholder)=[\"']([^\"']+)", form_html, re.I)).lower()
        context = f"{attrs} {text} {names}".lower()
        is_email = "email" in types or bool(re.search(r"newsletter|subscribe|sign up|mailing list", context))
        utility = bool(re.search(r"cart|search|product|newsletter|subscribe|customer_login|localization", context))
        has_message = "textarea" in form_html.lower() or bool(re.search(r"message|enquiry|inquiry|details|how can|what happened", context))
        has_contact = bool(re.search(r"tel|phone|mobile|email", f"{types} {names}"))
        if is_email:
            email.append(text or "email signup form")
        if (has_message and has_contact) or (len(inputs) >= 2 and has_contact and not utility):
            enquiry.append(text or "contact form")
    return enquiry, email


def detect(html: str) -> dict[str, dict]:
    """Every check returns present + the evidence that decided it."""
    clean_html = re.sub(r"<(script|style|template|noscript)\b[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    head = clean_html[: max(6000, len(clean_html) // 4)]
    text = visible_text(html)
    ctas = re.findall(rf"<(?:a|button)\b[^>]*>[^<]{{0,60}}(?:{CTA_WORDS})[^<]{{0,60}}</(?:a|button)>", clean_html, re.I)
    enquiry_forms, email_forms = form_kinds(clean_html)
    embeds = re.findall(r"hubspot|typeform|gravityform|wpforms|ninja_forms|jotform", html, re.I)
    videos = re.findall(VIDEO, html, re.I)
    imgs = re.findall(r'<img[^>]+(?:src|data-src)="([^"]+)"', html, re.I)

    out: dict[str, dict] = {}

    def put(key: str, present: bool, evidence: str) -> None:
        out[key] = {"present": bool(present), "evidence": evidence}

    put("cta_above_fold", bool(re.search(rf">\s*[^<]{{0,40}}(?:{CTA_WORDS})", head, re.I)),
        snippet(head, rf">\s*[^<]{{0,40}}(?:{CTA_WORDS})") or "no action link in the first screens")
    put("cta_repeated", len(ctas) >= 3, f"{len(ctas)} action links on the page")
    put("click_to_call", 'href="tel:' in html.lower(),
        snippet(html, r'href="tel:[^"]+') or "no tel: link")
    put("lead_form", bool(enquiry_forms) or bool(embeds),
        (enquiry_forms[0][:120] if enquiry_forms else (f"embed: {embeds[0].lower()}" if embeds else "no customer enquiry form")))
    # Filled from the speed reading after it exists; the markup cannot answer it.
    out["phone_speed"] = {"present": False, "evidence": "not measured yet", "applies": False}
    shape = enquiry_form_shape(clean_html)
    if shape:
        put("form_short", shape["fields"] <= FORM_FIELD_LIMIT,
            f"the enquiry form asks for {shape['fields']} things")
        put("form_button_says_outcome", shape["outcome_button"],
            f'the button says "{shape["button"]}"' if shape["button"] else "the form has no readable button")
    else:
        # A missing form is already one finding under lead_form. Counting it
        # three times would make one gap look like three.
        out["form_short"] = {"present": False, "evidence": "no enquiry form to measure", "applies": False}
        out["form_button_says_outcome"] = {"present": False, "evidence": "no enquiry form to measure", "applies": False}
    put("testimonials", bool(re.search(r"testimonial|what (our|my) (client|customer|patient)|kundenstimmen", text, re.I)),
        snippet(text, r"testimonial|what (our|my) (client|customer|patient)|kundenstimmen") or "no testimonial wording")
    m = re.search(r"\b\d{2,3}(?:,\d{3})?\+?\s*(clients?|customers?|projects?|jobs?|years?|kunden|jahre)\b", text, re.I)
    put("social_proof_numbers", bool(m), (m.group(0) if m else "no counted proof"))
    put("review_badges", bool(re.search(r"trustpilot|capterra|trustindex|elfsight|google review|shopper approved|provenexpert", html, re.I)),
        snippet(html, r"trustpilot|capterra|trustindex|elfsight|google review|provenexpert") or "no review widget")
    faq_de = "h\u00e4ufige fragen"
    put("faq", bool(re.search(rf"\bfaq\b|frequently asked|{faq_de}", text, re.I)),
        snippet(text, rf"\bfaq\b|frequently asked|{faq_de}") or "no FAQ heading")
    put("online_booking", bool(re.search(r"calendly|acuityscheduling|cal\.com|squarespace-?scheduling|housecallpro|setmore|book(ing)? online|jetzt buchen", html, re.I)),
        snippet(html, r"calendly|acuityscheduling|cal\.com|housecallpro|setmore|book(ing)? online") or "no booking tool")
    put("video_top", bool(re.search(VIDEO, head, re.I)),
        snippet(head, VIDEO) or "no video in the first screens")
    put("video_testimonials", len(videos) >= 2,
        f"{len(videos)} video embed(s) on the page")
    logo_words = re.search(r"as seen (in|on)|trusted by|featured in|our partners|clients include|bekannt aus|partner", text, re.I)
    logo_imgs = [s for s in imgs if re.search(r"logo|brand|partner", s, re.I)]
    put("logo_wall", bool(logo_words) and len(logo_imgs) >= 3,
        (f"{len(logo_imgs)} logo-named images" + (", wording present" if logo_words else ", no wording")))
    m = re.search(r"(reply|respond|answer|call (you )?back|antwort|melden)\D{0,40}\b\d{1,3}\s*(second|minute|hour|min|std|stunde)", text, re.I)
    put("response_time", bool(m), (re.sub(r"\s+", " ", m.group(0)) if m else "no response-time promise"))
    # A free first consultation is a lead magnet, and the pattern only knew about
    # guides and checklists. It reported "nothing free in exchange for an email"
    # on a practice whose home page offers a free fifteen-minute first
    # appointment in so many words.
    put("lead_magnet", bool(re.search(
        r"free (guide|checklist|ebook|e-book|report|calculator|audit|template|consultation|"
        r"quote|assessment|trial|sample|session)|no.obligation|"
        r"kostenlose[rsn]? ?(leitfaden|checkliste|ratgeber|erstgespr|beratung|analyse|probe|"
        r"termin|kennenlern)|unverbindlich", text, re.I)),
        snippet(text, r"free (guide|checklist|ebook|report|calculator|audit|template)|kostenlose") or "nothing free on offer")
    # \bsubscribe\b on purpose: "50K+ YouTube subscribers" is not an email capture.
    put("email_capture", bool(email_forms) or bool(re.search(r"newsletter|\bsubscribe\b|join (our|the) (list|email)|e-?mail erhalten", text, re.I)),
        (email_forms[0][:120] if email_forms else snippet(text, r"newsletter|\bsubscribe\b|join (our|the) (list|email)") or "no email capture"))
    return out


# What is verifiable about the later links in the chain without being inside
# the business: whether anything measures, whether a form reaches a system, and
# whether anything books. Absence here is a finding, not a guess - it is read
# off their own page.
STACK = {
    "analytics": {"Google Analytics": r"gtag\(|googletagmanager|google-analytics",
                  "Meta Pixel": r"connect\.facebook\.net/[^\"']*fbevents",
                  "Microsoft Clarity": r"clarity\.ms/tag",
                  "Hotjar": r"static\.hotjar\.com",
                  "Plausible": r"plausible\.io/js"},
    "crm": {"HubSpot": r"js\.hs-scripts|hsforms",
            "GoHighLevel": r"leadconnectorhq|msgsndr",
            "Salesforce": r"salesforce\.com|pardot",
            "Zoho": r"zoho\.com/crm|zohopublic",
            "Klaviyo": r"klaviyo\.com/media"},
    "booking": {"Calendly": r"calendly\.com", "Cal.com": r"cal\.com/embed",
                "Acuity": r"acuityscheduling", "Setmore": r"setmore\.com",
                "Housecall Pro": r"housecallpro"},
}


def detect_stack(html: str, base: str | None = None) -> dict:
    out: dict = {area: [name for name, pat in tools.items() if re.search(pat, html, re.I)]
                 for area, tools in STACK.items()}
    # Whether the AI answer engines are allowed in at all. The scorecard has a
    # reading for this and it was written by hand, which is how a client ended up
    # being told what ChatGPT does with their site without anyone checking.
    if base:
        root = "/".join(base.split("/")[:3])
        try:
            with urllib.request.urlopen(
                urllib.request.Request(root + "/robots.txt", headers={"User-Agent": UA}), timeout=5) as r:
                robots = r.read().decode("utf8", "ignore").lower()
            blocked = []
            for bot in ("gptbot", "oai-searchbot", "claudebot", "perplexitybot", "google-extended"):
                m = re.search(rf"user-agent:\s*{bot}\b(.*?)(?=user-agent:|$)", robots, re.S)
                if m and re.search(r"^\s*disallow:\s*/\s*$", m.group(1), re.M):
                    blocked.append(bot)
            out["aiCrawlers"] = not blocked
            out["aiCrawlersBlocked"] = blocked
        except Exception:                                    # noqa: BLE001
            pass
    return out


COOKIE_WORDS = ("accept", "agree", "allow", "got it", "ok", "einverstanden", "akzeptieren",
                "zustimmen", "alle akzeptieren", "close")


def settle_for_capture(page, budget_ms: int = 25_000) -> None:
    """Dismiss the cookie banner and wait for the page to actually finish drawing.

    The measured failure (Lost Car Key Specialist, 07.09.2026): the site needs
    39.8 s to paint its largest element, the capture ran after 8 s of network
    idle, and the stored proof showed a grey hero, a cookie card over the corner
    and two thirds white. A screenshot of a half-drawn page is not evidence of a
    slow site, it is evidence of a fast camera.
    """
    for word in COOKIE_WORDS:
        try:
            button = page.get_by_role("button", name=re.compile(rf"^\s*{re.escape(word)}\b", re.I))
            if button.count():
                button.first.click(timeout=1_500)
                break
        except Exception:  # noqa: BLE001 - no banner is the normal case
            continue
    try:
        page.wait_for_load_state("load", timeout=budget_ms)
    except Exception:  # noqa: BLE001
        pass
    # Lazy images only start loading once their placeholder scrolls into view.
    try:
        page.evaluate("""async () => {
          const step = Math.round(window.innerHeight * 0.9);
          for (let y = 0; y < document.body.scrollHeight; y += step) {
            window.scrollTo(0, y);
            await new Promise(done => setTimeout(done, 120));
          }
          window.scrollTo(0, 0);
        }""")
    except Exception:  # noqa: BLE001
        pass
    try:
        page.wait_for_function(
            "() => [...document.images].every(img => img.complete)", timeout=budget_ms)
    except Exception:  # noqa: BLE001 - a never-loading image must not lose the capture
        pass
    try:
        page.wait_for_load_state("networkidle", timeout=8_000)
    except Exception:  # noqa: BLE001 - busy sites may never become idle
        pass


def capture_is_usable(image) -> bool:
    """Reject a capture that is mostly one flat colour, which means nothing drew."""
    try:
        sample = image.convert("RGB").resize((64, 64))
        colours = sample.getcolors(64 * 64) or []
        if not colours:
            return True
        dominant = max(count for count, _ in colours)
        return dominant / float(64 * 64) < 0.92
    except Exception:  # noqa: BLE001 - a check that fails never blocks the evidence
        return True


def browser_probe(url: str, embed_screenshot: bool = False) -> dict:
    """Check rendered UI and resources loaded after the page starts running."""
    result = {"ok": False, "html": "", "resources": [], "forms": [], "actions": [],
              "analytics": [], "desktopScreenshot": None}
    try:
        from PIL import Image
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 1000}, device_scale_factor=1)
            resources: list[str] = []
            page.on("request", lambda request: resources.append(request.url))
            page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            settle_for_capture(page)
            forms = page.locator("form:visible").evaluate_all("""forms => forms.map(form => ({
              text: (form.innerText || '').trim().slice(0, 240),
              action: form.getAttribute('action') || '',
              fields: [...form.querySelectorAll('input, textarea, select')].map(el => ({
                type: el.getAttribute('type') || el.tagName.toLowerCase(),
                name: el.getAttribute('name') || '',
                placeholder: el.getAttribute('placeholder') || ''
              }))
            }))""")
            actions = page.locator("a[href]:visible, button:visible").evaluate_all("""elements => elements.map(el => ({
              text: (el.innerText || el.getAttribute('aria-label') || '').trim().replace(/\\s+/g, ' ').slice(0, 120),
              href: el.getAttribute('href') || '',
              top: Math.round(el.getBoundingClientRect().top)
            })).filter(item => item.text)""")
            content = page.content()
            screenshot = None
            if embed_screenshot:
                raw = page.screenshot(full_page=True, type="jpeg", quality=55)
                image = Image.open(io.BytesIO(raw)).convert("RGB")
                if capture_is_usable(image):
                    scale = min(1.0, 900 / image.width, 7000 / image.height)
                    if scale < 1:
                        image = image.resize((round(image.width * scale), round(image.height * scale)), Image.Resampling.LANCZOS)
                    output = io.BytesIO()
                    image.save(output, format="JPEG", quality=58, optimize=True, progressive=True)
                    screenshot = "data:image/jpeg;base64," + base64.b64encode(output.getvalue()).decode("ascii")
                else:
                    print("desktop capture came back blank, kept out of the report", file=sys.stderr)
            browser.close()
        runtime = "\n".join(resources) + "\n" + content
        analytics = [name for name, pattern in STACK["analytics"].items() if re.search(pattern, runtime, re.I)]
        result.update(ok=True, html=content, resources=resources, forms=forms, actions=actions,
                      analytics=analytics, desktopScreenshot=screenshot)
    except Exception as exc:  # noqa: BLE001 - fallback HTML checks remain usable
        result["why"] = str(exc)
    return result


def api_key() -> str:
    """The PageSpeed key, from the environment or from .env beside this repo.

    Read only from os.environ, the key sitting in .env was never picked up, so
    every run went out anonymous and hit the shared quota. The failure looked
    exactly like a real quota problem - "429, queries per day" - which is why it
    survived several sessions of being worked around instead of fixed.
    """
    key = os.environ.get("PAGESPEED_API_KEY", "")
    if key:
        return key
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("PAGESPEED_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def lighthouse_local(url: str, embed_frames: bool = False) -> dict:
    """Lighthouse on this machine, when Google's API will not answer.

    Same engine, same numbers, no quota and no key - it drives the Chrome that
    is already installed. Slower (about forty seconds) and it produces no
    filmstrip, so it is the fallback rather than the default: the strip of
    loading frames is the exhibit, the number alone is only a number.

    The alternative is Chrome's real-user report, which is better evidence
    still because it is what actual visitors experienced rather than a lab
    simulation. It needs the CrUX API switched on for the Google Cloud project
    behind the key, which may not be enabled for the current operator.
    """
    import shutil
    import subprocess
    if not shutil.which("lighthouse"):
        return {"ok": False, "why": "no local lighthouse either"}
    try:
        out = subprocess.run(
            ["lighthouse", url, "--quiet", "--output=json", "--output-path=stdout",
             "--only-categories=performance,accessibility,best-practices,seo", "--form-factor=mobile",
             "--screenEmulation.mobile",
             "--chrome-flags=--headless=new --no-sandbox --ignore-certificate-errors"],
            capture_output=True, text=True, timeout=120)
        data = json.loads(out.stdout)
    except Exception as exc:                                 # noqa: BLE001
        return {"ok": False, "why": f"local lighthouse failed: {exc}"}
    audits = data.get("audits", {})
    lcp = (audits.get("largest-contentful-paint") or {}).get("numericValue")
    categories = data.get("categories") or {}
    score = (categories.get("performance") or {}).get("score")
    scores = {
        key: round(((categories.get(key) or {}).get("score") or 0) * 100)
        for key in ("performance", "accessibility", "best-practices", "seo")
        if (categories.get(key) or {}).get("score") is not None
    }
    if lcp is None:
        return {"ok": False, "why": "local lighthouse returned no paint timing"}
    frames = []
    if embed_frames:
        for item in (audits.get("screenshot-thumbnails", {}).get("details", {}).get("items", []) or []):
            raw = item.get("data", "")
            if raw.startswith("data:image"):
                frames.append({"ms": item.get("timing"), "file": raw})
    screenshot = audits.get("final-screenshot", {}).get("details", {}).get("data")
    if not embed_frames or not str(screenshot).startswith("data:image"):
        screenshot = None
    return {"ok": True, "lcp": f"{lcp / 1000:.1f} s", "score": round((score or 0) * 100),
            "scores": scores,
            "frames": frames, "screenshot": screenshot, "source": "local",
            "note": f"Measured on this machine with Lighthouse. Your homepage is usable {lcp / 1000:.1f} s "
                    "after somebody taps it."}


def desktop_page_screenshot(url: str, embed: bool = False) -> str | None:
    """Capture the current desktop page once, without another paid API call.

    Lighthouse deliberately returns a phone screenshot. The proposal compares
    the current desktop page with the proposed page structure, then keeps the
    phone view in a separate disclosure. Reusing the phone image in both places
    made those two exhibits look different while showing the same evidence.

    The image is resized before it enters JSON so a long client page does not
    turn one Supabase row into a multi-megabyte payload. Failure is optional:
    the measured mobile image remains available and the report says when no
    reliable desktop capture was returned.
    """
    if not embed:
        return None
    try:
        from PIL import Image
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 1000}, device_scale_factor=1)
            page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            settle_for_capture(page)
            raw = page.screenshot(full_page=True, type="jpeg", quality=55)
            browser.close()

        image = Image.open(io.BytesIO(raw)).convert("RGB")
        if not capture_is_usable(image):
            print("desktop screenshot came back blank, kept out of the report", file=sys.stderr)
            return None
        max_width, max_height = 900, 7000
        scale = min(1.0, max_width / image.width, max_height / image.height)
        if scale < 1:
            image = image.resize(
                (max(1, round(image.width * scale)), max(1, round(image.height * scale))),
                Image.Resampling.LANCZOS,
            )
        output = io.BytesIO()
        image.save(output, format="JPEG", quality=58, optimize=True, progressive=True)
        return "data:image/jpeg;base64," + base64.b64encode(output.getvalue()).decode("ascii")
    except Exception as exc:  # noqa: BLE001 - optional evidence, never abort the audit
        print(f"desktop screenshot unavailable: {exc}", file=sys.stderr)
        return None


def pagespeed(url: str, frames_dir: Path | None, embed_frames: bool = False) -> dict:
    key = api_key()
    api = ("https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
           f"?url={urllib.parse.quote(url, safe='')}&strategy=mobile"
           "&category=performance&category=accessibility&category=best-practices&category=seo")
    if key:
        api += f"&key={key}"
    try:
        with urllib.request.urlopen(api, timeout=120) as r:
            data = json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:200]
        return {"ok": False, "why": f"PageSpeed HTTP {e.code}: {body}"}
    except Exception as e:                                   # noqa: BLE001
        return {"ok": False, "why": f"PageSpeed unreachable: {e}"}
    if "lighthouseResult" not in data:
        return {"ok": False, "why": data.get("error", {}).get("message", "no lighthouse result")[:200]}

    audits = data["lighthouseResult"]["audits"]
    items = audits.get("screenshot-thumbnails", {}).get("details", {}).get("items", [])
    frames = []
    for i, it in enumerate(items):
        # A frame of blank white compresses to about a kilobyte. Those are the
        # milliseconds before the browser painted anything, and showing them
        # reads as a broken image rather than as a slow page.
        raw = it.get("data", "")
        if raw.startswith("data:image") and len(base64.b64decode(raw.split(",", 1)[1])) < 2500:
            continue
        entry = {"ms": it["timing"]}
        if embed_frames and it.get("data", "").startswith("data:image"):
            entry["file"] = it["data"]
        elif frames_dir is not None and it.get("data", "").startswith("data:image"):
            frames_dir.mkdir(parents=True, exist_ok=True)
            name = f"cro-frame-{i:02d}.jpg"
            (frames_dir / name).write_bytes(base64.b64decode(it["data"].split(",", 1)[1]))
            # The web path is whatever follows the site's public/ folder, so the
            # value can go straight into the data file as an <img src>.
            full = (frames_dir / name).resolve()
            parts = full.as_posix().split("/public/", 1)
            entry["file"] = "/" + parts[1] if len(parts) == 2 else name
            entry["path"] = str(full)
        frames.append(entry)

    def val(k: str) -> str | None:
        return audits.get(k, {}).get("displayValue")

    # The finished page as one tall phone screenshot - the "what your visitors
    # see" exhibit next to the strip.
    shot = None
    final = audits.get("final-screenshot", {}).get("details", {}).get("data", "")
    if embed_frames and final.startswith("data:image"):
        shot = final
    elif frames_dir is not None and final.startswith("data:image"):
        frames_dir.mkdir(parents=True, exist_ok=True)
        (frames_dir / "cro-final.jpg").write_bytes(base64.b64decode(final.split(",", 1)[1]))
        parts = (frames_dir / "cro-final.jpg").resolve().as_posix().split("/public/", 1)
        shot = "/" + parts[1] if len(parts) == 2 else "cro-final.jpg"

    categories = data["lighthouseResult"].get("categories") or {}
    scores = {
        key: round(((categories.get(key) or {}).get("score") or 0) * 100)
        for key in ("performance", "accessibility", "best-practices", "seo")
        if (categories.get(key) or {}).get("score") is not None
    }
    return {"ok": True, "screenshot": shot, "lcp": val("largest-contentful-paint"),
            "speed_index": val("speed-index"), "fcp": val("first-contentful-paint"),
            "score": round((data["lighthouseResult"]["categories"]["performance"]["score"] or 0) * 100),
            "scores": scores,
            "frames": frames, "source": "pagespeed"}


def published_prices(base: str) -> dict:
    """What they charge, taken off their own site.

    The money model's biggest input is what one job is worth. It used to be typed
    in by whoever ran the command, and on the first real build that guess was
    $999 against published prices of $9,500 - the model was out by a factor of
    ten, in the direction that makes us look like we did not read their site.

    Plenty of businesses publish nothing, and then this returns nothing and the
    figure stays an openly labelled assumption. Never inferred from the industry.
    """
    seen: dict[int, str] = {}
    for path in ("/pricing", "/services", "/", "/about"):
        try:
            html, _ = fetch_raw(base.rstrip("/") + path)
        except Exception:                                    # noqa: BLE001
            continue
        body = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
        text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body))
        for raw in re.findall(r"\$\s?([\d,]{3,})(?:\.\d\d)?\b", text):
            value = int(raw.replace(",", ""))
            # Revenue bands ("$25K - $50K a month"), phone numbers and years are
            # not prices. A job worth under 200 or over 200k is one of those.
            if not 200 <= value <= 200_000 or value in seen:
                continue
            i = text.find(f"${raw}")
            seen[value] = text[max(0, i - 80):i + 80].strip()
        if seen:
            break
    if not seen:
        return {"found": False}
    values = sorted(seen)
    mid = values[len(values) // 2]
    return {"found": True, "values": values, "typical": mid, "evidence": seen[mid]}


def link_map(base: str, html: str) -> dict:
    """Which of their pages can be reached by clicking, and which cannot.

    The finding that lands hardest in a cold audit is usually "the one page that
    says what you sell has nothing pointing at it". It was read off the site by
    hand for the first client, which means the second client would have got that
    sentence about somebody else's website or not at all.

    Compares the sitemap (what they think they publish) against the links on
    their own pages (what a visitor can actually get to). No sitemap is a finding
    of its own, not a reason to skip the check.
    """
    root = "/".join(base.split("/")[:3])
    # A site reached at www.example.com routinely lists its pages as example.com
    # in the sitemap, and vice versa. Comparing the two literally made a sitemap
    # that exists and returns 200 come back as "no sitemap found" - which is a
    # false finding, not just a missed one.
    bare = root.replace("://www.", "://")

    def same_site(u: str) -> bool:
        return u.startswith(root) or u.startswith(bare)

    def path_of(u: str) -> str:
        for pre in (root, bare):
            if u.startswith(pre):
                p = u[len(pre):].split("?")[0].rstrip("/")
                return p or "/"
        return u

    listed: list[str] = []
    for name in ("/sitemap.xml", "/sitemap_index.xml"):
        try:
            with urllib.request.urlopen(
                urllib.request.Request(root + name, headers={"User-Agent": UA}), timeout=20) as r:
                xml = r.read().decode("utf8", "ignore")
        except Exception:                                    # noqa: BLE001
            continue
        found = [u for u in re.findall(r"<loc>\s*([^<\s]+)", xml) if same_site(u)]
        # A sitemap index points at more sitemaps rather than at pages.
        if not found and "<sitemapindex" in xml:
            for child in [u for u in re.findall(r"<loc>\s*([^<\s]+)", xml) if same_site(u)][:5]:
                try:
                    with urllib.request.urlopen(
                        urllib.request.Request(child, headers={"User-Agent": UA}), timeout=20) as r:
                        found += [u for u in re.findall(r"<loc>\s*([^<\s]+)", r.read().decode("utf8", "ignore"))
                                  if same_site(u)]
                except Exception:                            # noqa: BLE001
                    continue
        listed = found
        if listed:
            break
    if not listed:
        return {"ok": False, "why": "no sitemap found, so we cannot tell what they meant to publish"}

    # Twelve pages, not forty.
    #
    # The proposal is not a site audit. Forty pages plus two hops of crawling
    # stalled for a quarter of an hour on a real prospect, and the reachability
    # finding does not get better past the main pages: a business with an
    # unreachable offer page has it in the first dozen, and one with a hundred
    # blog posts does not need each one checked to sell a call.
    #
    # The full sweep belongs in /audit, which is what the client pays for after
    # they say yes. This one has to finish in a minute.
    pages = sorted({path_of(u) for u in listed}, key=lambda p: (p.count("/"), len(p)))[:12]
    # Follow the links from the home page and from every page the home page
    # reaches. Two hops is what a visitor does before giving up, and it is what
    # the claim "nobody can get there by clicking" actually means.
    # Records WHICH page links to each one, not just that something did. Without
    # that the check cannot be argued with or checked, and the first version of
    # it silently counted a page as reachable that nothing on the site links to.
    found_by: dict[str, str] = {"/": "the home page"}
    frontier = ["/"]
    seen_html = {"/": html}
    # One hop, and a wall clock. Two hops over a big sitemap is where the run
    # disappeared for fifteen minutes, and the home page's own links answer the
    # question this exhibit asks: can a visitor get there by clicking.
    deadline = time.time() + 40
    for _ in range(1):
        nxt = []
        for path in frontier:
            if time.time() > deadline:
                break
            page = seen_html.get(path)
            if page is None:
                try:
                    page, _final = fetch_raw(root + path)
                except Exception:                            # noqa: BLE001
                    continue
                seen_html[path] = page
            for href in re.findall(r'href=["\']([^"\'#]+)', page):
                # An absolute link somewhere else entirely is not a link to their
                # own page, however similar the path looks. A link to
                # skool.com/x/about is not a link to their /about.
                if href.startswith(("http", "//")):
                    if not same_site(href):
                        continue
                    href = path_of(href)
                elif href.startswith(("mailto:", "tel:")):
                    continue
                target = ("/" + href.lstrip("/")).split("?")[0].rstrip("/") or "/"
                if target in pages and target not in found_by:
                    found_by[target] = path
                    nxt.append(target)
        frontier = nxt
        if not frontier:
            break

    orphans = [p for p in pages if p not in found_by]

    # A page can be missing from the sitemap AND unlinked, which is worse than
    # either and invisible to a check that only walks the sitemap. On the first
    # real audit /about was exactly that, and the hand-written finding about it
    # got the reason wrong in two different ways because nothing measured it.
    stranded = []
    for guess in ("/about", "/pricing", "/services", "/contact", "/team", "/work"):
        if guess in pages or guess in found_by:
            continue
        try:
            body, _f = fetch_raw(root + guess)
        except Exception:                                    # noqa: BLE001
            continue
        if len(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body))) > 500:
            stranded.append(guess)

    return {"ok": True, "pages": len(pages), "reachable": len(found_by),
            "orphans": orphans, "stranded": stranded, "foundBy": found_by}


def seed_evidence(pages_html: dict[str, str], links: dict) -> list[dict[str, str]]:
    """Return source-labelled site vocabulary for automatic seed selection.

    Titles, H1s and service-like slugs stay attached to their evidence so the
    selection remains auditable even though the proposal run does not pause.
    """
    generic = {
        "home", "welcome", "about", "about us", "contact", "contact us", "blog",
        "privacy", "terms", "imprint", "impressum", "startseite", "uber uns",
        "ueber uns", "kontakt", "leistungen", "services",
    }
    seen: set[str] = set()
    found: list[dict[str, str]] = []

    def clean(value: str) -> str:
        value = re.sub(r"<[^>]+>", " ", value)
        value = html_lib.unescape(value)
        return re.sub(r"\s+", " ", value).strip(" \t\r\n-|--:")

    def add(value: str, source: str, page: str) -> None:
        value = clean(value)
        key = value.casefold()
        if not value or key in generic or key in seen or len(value) < 4 or len(value) > 100:
            return
        if len(value.split()) > 12:
            return
        seen.add(key)
        found.append({"phrase": value, "source": source, "page": page})

    for path, page_html in pages_html.items():
        meta_keywords = re.search(
            r"<meta[^>]+name=[\"']keywords[\"'][^>]+content=[\"']([^\"']+)",
            page_html, re.I,
        )
        if meta_keywords:
            for phrase in meta_keywords.group(1).split(",")[:8]:
                add(phrase, "meta keyword", path)
        title = re.search(r"<title[^>]*>(.*?)</title>", page_html, re.I | re.S)
        h1s = re.findall(r"<h1[^>]*>(.*?)</h1>", page_html, re.I | re.S)
        if title:
            add(title.group(1), "title", path)
        for h1 in h1s[:2]:
            add(h1, "h1", path)

    skip_paths = ("about", "contact", "blog", "privacy", "terms", "impress", "team", "faq")
    for path in (links.get("foundBy") or {}):
        slug = path.strip("/").replace("-", " ").replace("_", " ")
        if slug and not any(part in slug.casefold() for part in skip_paths):
            add(slug, "service-page slug", path)

    return found[:20]


def service_candidates(pages_html: dict[str, str]) -> list[str]:
    """Return bookable service labels evidenced by the business website.

    These populate the prepared GBP service list. Search keywords are not
    services: they often contain towns, ``near me`` or research phrasing that
    must never leak into the public profile.
    """
    generic = {
        "service", "services", "our services", "learn more", "read more",
        "find out more", "view service", "view services", "what we do",
        "leistungen", "unsere leistungen", "mehr erfahren",
    }
    blocked = ("near me", "privacy", "cookie", "contact", "about", "blog")
    seen: set[str] = set()
    result: list[str] = []

    def clean(value: str) -> str:
        value = re.sub(r"<[^>]+>", " ", value)
        value = html_lib.unescape(value)
        return re.sub(r"\s+", " ", value).strip(" \t\r\n-|--:›»")

    def add(value: str) -> None:
        label = clean(value)
        key = label.casefold()
        if (
            not label or key in generic or key in seen or len(label) < 3
            or len(label) > 70 or len(label.split()) > 8
            or any(word in key for word in blocked)
        ):
            return
        seen.add(key)
        result.append(label)

    for page_html in pages_html.values():
        for attrs, body in re.findall(r"<a\b([^>]*)>(.*?)</a>", page_html, re.I | re.S):
            href = re.search(r"href=[\"']([^\"']+)", attrs, re.I)
            path = (href.group(1) if href else "").casefold()
            if re.search(r"/(services?|leistungen?)(?:/|$)", path) and not re.search(r"/(services?|leistungen?)/?$", path):
                add(body)
        # Service landing pages often expose their bookable list as card
        # headings without wrapping the heading itself in the link.
        for heading in re.findall(r"<h[23][^>]*>(.*?)</h[23]>", page_html, re.I | re.S):
            text = clean(heading)
            if re.search(r"lock|repair|install|replace|cut|security|boarding|access|beratung|coaching|behandlung|service", text, re.I):
                add(text)
    return result[:40]


# Two pages of dense copy per page is plenty for anything written about the
# business, and it stops one sprawling blog from carrying a whole row on its own.
SITE_TEXT_LIMIT = 20000


def write_site_text(path: str, final_url: str, pages_html: dict[str, str],
                    rendered_home: str | None = None) -> None:
    """Keep what the business says about itself, from pages already fetched.

    The checklist json is what the client is served (`proposals.data`), so the
    text goes to its own file and from there into its own column. Structure:
    one entry per page with its path, title, meta description and visible text.
    """
    def meta_description(html: str) -> str:
        m = re.search(r"<meta[^>]+name=[\"']description[\"'][^>]+content=[\"']([^\"']{0,400})",
                      html, re.I) or re.search(
                      r"<meta[^>]+content=[\"']([^\"']{0,400})[\"'][^>]+name=[\"']description[\"']",
                      html, re.I)
        return html_lib.unescape(m.group(1)).strip() if m else ""

    def title_of(html: str) -> str:
        m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
        return re.sub(r"\s+", " ", html_lib.unescape(m.group(1))).strip()[:200] if m else ""

    seiten = []
    for pfad, page_html in pages_html.items():
        # A page painted by JavaScript hands the raw fetch almost nothing. The
        # rendered home markup is the honest source where we have it.
        quelle = (rendered_home if pfad == "/" and rendered_home
                  and len(visible_text(rendered_home)) > len(visible_text(page_html))
                  else page_html)
        text = visible_text(quelle)
        if len(text) < 200:
            continue
        seiten.append({"path": pfad, "title": title_of(quelle),
                       "metaDescription": meta_description(quelle),
                       "text": text[:SITE_TEXT_LIMIT],
                       "truncated": len(text) > SITE_TEXT_LIMIT})
    payload = {"url": final_url, "fetchedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
               "pages": seiten,
               "chars": sum(len(s["text"]) for s in seiten)}
    Path(path).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url")
    ap.add_argument("--frames", help="directory for the filmstrip jpgs; omit to skip writing them")
    ap.add_argument("--embed-frames", action="store_true",
                    help="store PageSpeed images as data URLs for a remote renderer")
    ap.add_argument("--no-speed", action="store_true", help="checklist only, no PageSpeed call")
    ap.add_argument("--site-out",
                    help="write the visible text of the fetched pages to this file. The pages are "
                         "already loaded for the checklist, so this costs nothing extra. Kept out "
                         "of the checklist json on purpose: that one is served to the client as "
                         "proposals.data, and page text there would be dead weight on every view.")
    a = ap.parse_args()

    # Check credit before pages. A run without rendering evidence must not
    # generate guessed findings.
    credit_error = firecrawl_leer()
    if credit_error:
        raise SystemExit(f"Refusing to start: {credit_error}")

    # A site with no certificate is not a site we cannot audit, it is a site with
    # a finding. munichleadershipgroup.com answers only on http, and the run died
    # with "connection refused" rather than reporting the one thing every visitor
    # sees first: the browser warning before the page even loads.
    url = a.url if a.url.startswith("http") else "https://" + a.url
    no_https = False
    try:
        html, final = fetch(url)
    except Exception as first:                               # noqa: BLE001
        if url.startswith("https://"):
            try:
                html, final = fetch("http://" + url[len("https://"):])
                # Only a finding if we END on http. munichleadershipgroup.com
                # answers only on http and then redirects to a different domain
                # that has a certificate - reporting "no certificate" there
                # would have been a false alarm about somebody else's site.
                no_https = not final.startswith("https://")
            except Exception as second:                      # noqa: BLE001
                print(f"could not fetch {url}: {first} / {second}", file=sys.stderr)
                return 1
        else:
            print(f"could not fetch {url}: {first}", file=sys.stderr)
            return 1

    # The fifteen checks run across the pages a visitor would actually use, not
    # the home page alone.
    #
    # Checking only the home page reported "no form they can fill in" and "no way
    # to book a time" for a practice whose booking form sits on /kontakt. A false
    # "you are missing this" on something they have is the fastest way to lose
    # the reader, and it is worse than saying nothing.
    # Their real pages, from their own sitemap, ranked by how likely a buyer is
    # to be on one. Guessing at /kontakt and /contact works in two languages and
    # fails in every other, and it misses whatever they actually called the page.
    links = link_map(final, html)
    WANTED = ("kontakt", "contact", "termin", "book", "anfrage", "quote", "appointment",
              "leistung", "service", "preis", "pricing", "angebot")
    candidates = [p for p in (links.get("foundBy") or {}) if p != "/"]
    candidates.sort(key=lambda p: (not any(w in p.lower() for w in WANTED), len(p)))

    pages_html = {"/": html}
    for guess in candidates or ("/kontakt", "/contact", "/leistungen", "/services"):
        try:
            body, _f = fetch(url.rstrip("/") + guess)
        except Exception:                                    # noqa: BLE001
            continue
        if len(body) > 800 and not ist_fehlerseite(body):
            pages_html[guess] = body
        # Three pages: the home page and the two most likely to carry a form or
        # a booking link. Each one is a render, and five of them was the whole
        # six minutes. The candidates are already sorted by that likelihood.
        if len(pages_html) >= 3:
            break

    probe = browser_probe(final, embed_screenshot=a.embed_frames)
    found = detect(probe.get("html") or html)
    if probe.get("ok"):
        actions = probe.get("actions") or []
        action_hits = [item for item in actions if re.search(CTA_WORDS, item.get("text", ""), re.I)]
        first_action = next((item for item in action_hits if 0 <= item.get("top", 99999) <= 1000), None)
        found["cta_above_fold"] = {
            "present": bool(first_action),
            "evidence": first_action.get("text", "")[:120] if first_action else "no visible action before the first scroll",
        }
        found["cta_repeated"] = {
            "present": len(action_hits) >= 3,
            "evidence": f"{len(action_hits)} visible action links or buttons on the page",
        }
        phone = next((item for item in actions if str(item.get("href", "")).lower().startswith("tel:")), None)
        found["click_to_call"] = {
            "present": bool(phone),
            "evidence": phone.get("href", "")[:120] if phone else "no visible tap-to-call link",
        }
    for path, body in pages_html.items():
        if path == "/":
            continue
        for key, res in detect(body).items():
            if key in {"cta_above_fold", "cta_repeated", "video_top"}:
                continue
            if res["present"] and not found[key]["present"]:
                found[key] = {"present": True,
                              "evidence": f"on {path}: {res['evidence']}"[:160]}
    rows = [{"key": k, "label": label, "consequence": why,
             "present": found[k]["present"], "evidence": found[k]["evidence"],
             **({"applies": False} if found[k].get("applies") is False else {})}
            for k, label, why in ELEMENTS]
    have = sum(1 for r in rows if r["present"])

    speed = {"ok": False, "why": "skipped (--no-speed)"} if a.no_speed else \
        pagespeed(final, Path(a.frames) if a.frames else None, embed_frames=a.embed_frames)
    # Google's API refusing is not a reason to ship an audit with no speed
    # reading. Same engine on this machine, no quota - it loses the filmstrip
    # and keeps the number, and the page says which one it got.
    if not speed.get("ok"):
        speed = lighthouse_local(final, embed_frames=a.embed_frames) if not a.no_speed else speed
    if speed.get("ok"):
        speed["desktopScreenshot"] = probe.get("desktopScreenshot")

    # The shipped operating benchmark, applied where the reader can see it. The number
    # was measured and printed and then never graded, so a page taking forty
    # seconds carried the same enquiry score as one taking one and a half.
    seconds = None
    match = re.search(r"([\d.]+)\s*s", str(speed.get("lcp") or ""))
    if match:
        seconds = float(match.group(1))
    for row in rows:
        if row["key"] != "phone_speed":
            continue
        if seconds is None:
            row.update(present=False, applies=False, evidence="no phone load time was measured")
        else:
            row.pop("applies", None)
            row.update(present=seconds <= PHONE_SECONDS,
                       evidence=f"the largest thing on the page appears after {seconds:.1f} s")
    have = sum(1 for row in rows if row["present"])

    # A page that paints itself with JavaScript can hide a form or a booking
    # widget from this fetch. Say so rather than reporting a false absence.
    visible = len(re.sub(r"\s+", " ", re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)))
    warning = None
    if visible < 4000 and re.search(r"__NEXT_DATA__|data-reactroot|ng-version|__NUXT__", html):
        warning = ("The page renders through JavaScript and this fetch sees little markup - "
                   "check the absent elements by eye before they go in front of a client.")
    # The one that actually bit: three elements reported missing on a site that
    # had all three, because the render failed quietly and the checks ran on the
    # server's markup instead. Absent elements are only trustworthy on a
    # rendered page, so an unrendered run says so rather than scoring silently.
    # A completely unrendered site leaves the whole website section unverified.
    # Stop before scoring rather than hiding that gap behind a warning.
    if RENDERED and not any(RENDERED):
        raise SystemExit(
            f"Refusing to write a CRO check: none of the {len(RENDERED)} pages rendered, so "
            "every 'missing' element would be a guess. Check the site by hand or retry.")
    if RENDERED and not all(RENDERED):
        warning = (f"{len(RENDERED) - sum(RENDERED)} of {len(RENDERED)} pages could not be read "
                   "in full, so this check covers the pages that were.")

    stack = detect_stack((probe.get("html") or html) + "\n" + "\n".join(probe.get("resources") or []), final)
    if probe.get("analytics"):
        stack["analytics"] = probe["analytics"]

    # The pages were fetched for the checklist and then thrown away. Everything
    # written in the operator's own words lived in them, and a newsletter or any
    # other piece written for that business needs exactly that. Keeping the text
    # costs no request; re-fetching it later costs one scrape per business.
    if a.site_out:
        write_site_text(a.site_out, final, pages_html, probe.get("html"))
    json.dump({"url": final, "elements": rows, "have": have, "total": len(rows),
               "speed": speed, "stack": stack, "warning": warning,
               "visitorProbe": {"ok": bool(probe.get("ok")), "forms": probe.get("forms", []),
                                "why": probe.get("why")},
               "rendered": {"pages": len(RENDERED), "withJs": sum(RENDERED)},
               "noHttps": no_https,
               "prices": published_prices(final), "links": links,
               "seedCandidates": seed_evidence(pages_html, links),
               "serviceCandidates": service_candidates(pages_html)},
              sys.stdout, indent=2, ensure_ascii=False)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
