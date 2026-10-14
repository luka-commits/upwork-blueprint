#!/usr/bin/env python3
"""Synthetic analytics proof. No Upwork, downloads, deploys, credentials or real data writes."""
import contextlib
import datetime as dt
import hashlib
import importlib
import io
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time
from unittest import mock
from zoneinfo import ZoneInfo

ROOT = pathlib.Path(__file__).resolve().parents[1]
CODE = ROOT / 'code'
sys.path.insert(0, str(CODE))
ORIGINAL_RUN = subprocess.run
REAL_JOBS = ROOT / 'data' / 'jobs.json'
REAL_HASH = hashlib.sha256(REAL_JOBS.read_bytes()).hexdigest() if REAL_JOBS.exists() else None
REAL_DATA_HASHES = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in (ROOT / 'data').rglob('*') if path.is_file()}
TODAY = dt.datetime.now(ZoneInfo('Europe/Berlin')).date()
BASE = dt.datetime.combine(TODAY - dt.timedelta(days=2), dt.time(12), dt.timezone.utc)

EXAMPLE_CALL_READ = (
    "The client described a recurring manual task and named its weekly cost. "
    "The member asked about the desired result, which gave the conversation a useful direction. "
    "The next question should establish who owns the inputs and who will approve the work. "
    "Keep the scope tied to that result before discussing a price or promising a delivery date. "
    "A clear owner makes the next step easier to check and reduces the chance of waiting without an answer. "
    "Use the client's exact words when confirming the problem, then ask one concrete question about the remaining uncertainty. "
    "The transcript supports this coaching example; it does not establish a budget, a signed contract, or a completed delivery. "
    "Confirm those details in the thread before treating them as agreed facts."
)

ANALYTICS_TODAY = dt.date(2026, 10, 14)

@contextlib.contextmanager
def fixture(label):
    with tempfile.TemporaryDirectory(prefix=f'blueprint-synthetic-{label}-') as temp:
        path = pathlib.Path(temp)
        env = dict(os.environ)
        for key in ('BLOB_READ_WRITE_TOKEN', 'WHISPER_MODEL'):
            env.pop(key, None)
        env.update(BLUEPRINT_CONTEXT=str(path / 'context'), BLUEPRINT_DATA=str(path / 'data'),
                   BLUEPRINT_JOBS=str(path / 'data' / 'jobs.json'), BLUEPRINT_JOBDIR=str(path / 'jobs'),
                   KEEP_CHAT_HOURS='24', TZ='Europe/Berlin')
        for name in ('context', 'data', 'jobs'):
            (path / name).mkdir()
        (path / 'context' / 'me.md').write_text('# SYNTHETIC analytics fixture\n', encoding='utf-8')
        with mock.patch.dict(os.environ, env, clear=True):
            time.tzset()
            yield path
    time.tzset()

def run(script, *args, value=None, env=None, success=True):
    result = ORIGINAL_RUN([sys.executable, str(CODE / script), *map(str, args)],
                          input=json.dumps(value) if value is not None else None,
                          text=True, capture_output=True, env=env)
    if success and result.returncode:
        raise AssertionError(f'{script} failed ({result.returncode}):\n{result.stdout}\n{result.stderr}')
    return result

def maya_preview_review(index, kind='application'):
    """Varied, quote-backed SEO coaching for the disposable Maya preview.

    The caller writes ``source`` as the actual artifact before recording ``review``.
    No summary counts live here: analytics derives them from the recorded reviews.
    """
    scenarios = (
        ('Collection pages disappeared from search after our theme change',
         'Lead with the indexing problem before introducing yourself', 'missing', 1),
        ('Our clinic appears below nearby practices in local search',
         'Keep the relevant local search example', 'met', 2),
        ('Product variants compete with each other in search results',
         'Match the audit deliverable to the variant problem', 'partly', 4),
        ('Search Console shows excluded category pages after the migration',
         'End with one question about the affected pages', 'missing', 6),
        ('Our buying guides attract visits but few product page clicks',
         'Keep the audit scope tied to the affected pages', 'met', 1),
    )
    problem, finding, state, weak = scenarios[index % len(scenarios)]
    subjects = ('linen bedding collections', 'dental implant service pages', 'running shoe variants',
                'garden furniture categories', 'hiking equipment buying guides', 'ceramic dinnerware collections',
                'physiotherapy treatment pages', 'skincare product variants', 'coffee subscription categories',
                'cycling accessory buying guides', 'organic cotton collections', 'bakery catering pages',
                'leather bag variants', 'office lighting categories', 'camping tent buying guides',
                'handmade jewellery collections', 'estate agent neighbourhood pages', 'haircare product variants',
                'kitchen storage categories', 'trail shoe buying guides', 'children’s clothing collections',
                'veterinary consultation pages', 'tea gift set variants', 'home fragrance categories',
                'paddleboard buying guides', 'wool blanket collections', 'accountancy service pages',
                'bathroom tap variants', 'pet food categories', 'camera accessory buying guides',
                'recycled stationery collections', 'roof repair service pages', 'protein powder variants',
                'indoor plant categories', 'travel backpack buying guides', 'silk scarf collections',
                'optician eye test pages', 'water bottle variants', 'desk organiser categories',
                'dog harness buying guides')
    subject = subjects[index % 100 % len(subjects)]
    title = ('Shopify collection indexing audit', 'Local service SEO audit', 'Product variant SEO audit',
             'Migration category SEO audit', 'Buying guide content audit')[index % len(scenarios)] + ': ' + subject
    page_count = 2 + index % 19
    slot = index % len(scenarios)
    opener = (f'I am Maya, an SEO consultant applying to review your {subject}.' if slot == 0 else
              f'Your {subject} need an audit because {problem[0].lower() + problem[1:]}.')
    proof = (f'My local search audit sample shows listing and service-page fixes for {subject}.' if slot == 1 else
             f'My comparable SEO audit sample shows a prioritised fix list for {subject}.')
    screening = f'I can start Monday and have Search Console experience relevant to {subject}.'
    scope = (f'My bid for {subject} covers SEO improvements; I will work out the deliverables later.' if slot == 2 else
             f'My fixed bid covers {page_count} pages for {subject}, an evidence sheet and a prioritised fix list.')
    closing = (f'Can we book a call to discuss your {subject}?' if slot == 3 else
               f'Which page in your {subject} should I check first?')
    source = '\n'.join((opener, proof, screening, scope, closing, 'Maya'))
    quote = (opener, proof, scope, closing, opener)[slot]
    read = f'{finding}. The review is grounded in the submitted audit copy.'
    review = {'state': 'pass', 'reviewable': True, 'quote': quote,
              'key_finding': finding, 'free_read': read,
              'better_line': (
                  f'I will check why your {subject} disappeared from search after the theme change.',
                  f'My local search audit sample shows listing and service-page fixes relevant to your {subject}.',
                  f'The audit of your {subject} will deliver an evidence sheet and a prioritised list of canonical fixes.',
                  f'Which excluded page in your {subject} should I check first?',
                  f'The audit will cover {page_count} pages in your {subject}, their product links and a prioritised fix list.'
              )[slot],
              'next_message': 'Which affected page should the audit address first?',
              'points': [{'point': p, 'state': state if p == weak else 'not_needed' if p == 7 else 'met',
                          'quote': (opener, proof, screening, scope, 'Maya', closing, scope)[p - 1],
                          'reason': finding if p == weak else 'No Loom was requested or sent.' if p == 7 else
                                    'The sent application records this check.'}
                         for p in range(1, 8)]}
    if kind == 'conversation':
        slot = index % 4
        clients = (
            'Can you start with our excluded collection pages before checking the rest of the store?',
            'Does the local audit cover both clinic listings and their landing pages?',
            'Can you check the variant canonical tags and meet to confirm the product scope?',
            'Can we agree the buying guide audit in writing? A call would not help this decision.',
        )
        answers = (
            'Yes, I will check the excluded collection pages first. Who can share Search Console access?',
            'Yes, the audit includes both clinic listings and their landing pages. Which clinic location takes priority?',
            'Yes, I will check the variant canonical tags. Which product range matters most? Tuesday at ten or Wednesday at two on Upwork?',
            'Yes, we can agree the buying guide audit in writing here on Upwork. Which guide should take priority?',
        )
        findings = ('Offer two concrete call times after answering the question',
                    'Ask for a call time after narrowing the clinic scope',
                    'Keep the clear answer and two available call times',
                    'Keep the decision in writing when a call adds nothing')
        own = answers[slot]
        quote = clients[slot]
        review.update(read=True, last_writer='me', key_finding=findings[slot],
                      better_line=(
                          'I will check the excluded collection pages first; would Tuesday at ten or Wednesday at two suit you on Upwork?',
                          'The audit covers both clinic listings and landing pages; would Tuesday at ten or Wednesday at two suit you on Upwork?',
                          'I will check the variant canonical tags; shall we confirm the product range Tuesday at ten or Wednesday at two on Upwork?',
                          'We can agree the buying guide audit in writing here on Upwork; which guide should take priority?'
                      )[slot],
                      free_read=findings[slot] + '. The complete thread supports this read.',
                      next_message=('Would Tuesday at ten or Wednesday at two suit you on Upwork?'
                                    if slot < 2 else 'I will send the agreed audit scope here on Upwork.'),
                      points={key: {'state': ('missing' if slot < 2 else 'not_needed' if slot == 3 else 'met')
                                           if key == 'call_times' else 'met',
                                    'quote': quote if slot == 3 and key == 'call_times' else own,
                                    'reason': ('The client explicitly prefers a written decision; no call is needed.' if slot == 3 else findings[slot])
                                              if key == 'call_times' else 'The reply addresses this check.'}
                              for key in ('answered_question', 'qualifying_question', 'call_times')})
        review = {key:review[key] for key in ('read','last_writer','key_finding','better_line','free_read','next_message','points')}
        return {'quote': quote, 'own': own, 'source': quote + '\n' + own, 'review': review}
    if kind == 'proposal':
        missing = index % 2 == 1
        scope = ('Audit the Shopify collection and indexing issues.' if not missing else
                 'Audit the clinic listings and local landing pages.')
        price = '$1,800 fixed.' if not missing else '$1,400 fixed.'
        decision = 'We will decide Friday on Upwork.'
        finding = 'Agree a decision date before waiting for approval' if missing else 'Keep the audit scope tied to the affected pages'
        quote = scope
        source = scope + '\n' + price + ('\n' + decision if not missing else '')
        review.update(quote=quote, key_finding=finding, free_read=finding + '. The scope is specific to this audit.',
                      scope=scope, price=price, decision_date=None if missing else decision,
                      better_line='When will you decide on this clinic listings and local landing page audit here on Upwork?' if missing else
                                  'The fixed scope covers the Shopify collection indexing audit; I will wait for your Friday decision on Upwork.',
                      next_message='Can we agree a day to decide on this audit here on Upwork?' if missing else
                                   'I will wait for your Friday decision here on Upwork.',
                      points=[{'point': p, 'label': ('Scope', 'Price', 'Decision date')[p - 1], 'state': 'missing' if missing and p == 3 else 'met',
                               'quote': scope if p == 3 and missing else (scope, price, decision)[p - 1],
                               'reason': 'No decision date was agreed.' if p == 3 and missing else 'The proposal records this term.'}
                              for p in range(1, 4)])
        if missing: review.pop('decision_date')
        if missing:
            review['points'][2].update(pattern_sentence='you left the decision date open.',
                                       better_line='When will you decide on this audit here on Upwork?')
    if kind == 'call':
        slot = index % 3
        reads = (
            'The client narrowed the audit to collection pages and explained the lost search traffic. '
            'Maya confirmed the page list and budget before giving a fixed price. '
            'Keep that order because it ties the price to a scope the client has already accepted.',
            'The clinic owner gave a clear local search problem, but Maya quoted a price before checking the available budget. '
            'The client also left the purchase decision date open. Ask for the budget range after confirming the locations and before offering a package. '
            'The written follow-up should resolve that gap rather than assume the price was accepted.',
            'This follow-up call revisits the retailer’s existing buying guide audit offer. '
            'The retailer wants a content audit rather than a technical migration. '
            'Maya separated those needs and named the buying guides in scope. '
            'The client will share the guide list on Upwork before Maya updates the existing proposal. '
            'Keep the follow-up tied to those inputs instead of promising a delivery date too early.',
        )
        # Full reads remain in the requested 120-180 word envelope.
        context = (' The transcript records the client’s own explanation of the search issue and Maya’s response. '
                   'It supports the agreed next action, but it does not establish a signed contract or delivered results. '
                   'Use the same page list when preparing the written scope so the client can compare it with the conversation. '
                   'If a required input changes, confirm the change in the Upwork thread before treating it as agreed. '
                   'The next message should keep that one decision easy to answer and leave the remaining work for the agreed review.')
        steps = ('Maya sends the collection audit scope on Upwork by Friday.',
                 'Client confirms the clinic audit budget on Upwork by Thursday.',
                 'Client shares the buying guide list on Upwork by Wednesday.')
        messages = ('Thanks for confirming the pages and budget. I will send the collection audit scope here by Friday.',
                    'Before I prepare the clinic audit scope, which budget range should it fit?',
                    'Please share the buying guide list here by Wednesday, then I will confirm the audit scope.')
        agenda = ('Let us cover the collection indexing issue, scope, budget and next step.',
                  'Let us cover the clinic visibility issue, locations, budget and next step.',
                  'Let us cover the buying guides, content scope, budget and next step.')[slot]
        current = ('Our collection pages dropped out of search after the theme change.',
                   'Both clinics rank below nearby practices despite accurate listings.',
                   'Our buying guides get visits but send few people to the product pages.')[slot]
        cost = ('We lost about forty collection-page visits a day and need those visitors back.',
                'We miss about five appointment enquiries a week and want more local bookings.',
                'We lose about twenty product clicks a week and want the guides to drive purchases.')[slot]
        call_scope = ('I will audit the twelve affected collection pages and prioritise indexing fixes.',
                      'I will audit both clinic listings and six local landing pages.',
                      'I will audit eight buying guides and their links to product pages.')[slot]
        proof = ('My Shopify audit sample shows how I diagnosed collection indexing after a theme change.',
                 'My clinic audit sample connects listing corrections with local landing-page fixes.',
                 'My retailer audit sample shows how guide structure and links support product discovery.')[slot]
        budget_question = ('What budget have you set aside for these collection pages?',
                           'What budget have you set aside for the clinic audit?',
                           'Is the twelve hundred dollar budget agreed in our Upwork thread still right for these guides?')[slot]
        budget_answer = ('We have set aside eighteen hundred dollars for these pages.',
                         'We have not decided the budget or when we will purchase the audit.',
                         'Yes, the twelve hundred dollar budget in our Upwork thread still stands.')[slot]
        price_line = ('The collection audit will cost eighteen hundred dollars fixed.',
                      'The clinic audit will cost fourteen hundred dollars fixed.',
                      'The buying guide audit will cost twelve hundred dollars fixed.')[slot]
        decision_line = ('I am the sole decision maker and will decide on the collection audit this Friday.',
                         'I own the clinics, but the budget and purchase decision timeline are still unresolved.',
                         'I approve this myself and will decide on the buying guide audit next Monday.')[slot]
        no_objections = ('I have no objections to the collection audit scope; send it in writing.',
                         'I have no objections to the clinic page scope; I still need to confirm the budget.',
                         'I have no objections to the buying guide scope; I will share the page list.')[slot]
        finding = ('Keep the audit scope tied to the affected pages', 'Confirm budget before quoting the audit',
                   'Keep the input owner and next Upwork step clear')[slot]
        turns = [('Maya', '00:12', agenda), ('Maya', '00:24', 'What is happening now and what would a useful result look like?'),
                 ('Client', '00:40', current), ('Maya', '01:05', 'What does that problem cost you each week?'),
                 ('Client', '01:22', cost), ('Maya', '02:00', call_scope),
                 ('Client', '02:20', 'Yes, that is the page scope I need.'), ('Maya', '02:42', proof)]
        if slot == 2:
            turns.insert(0, ('Maya', '00:05', 'This is our follow-up on the existing buying guide audit offer; today we will confirm the remaining inputs.'))
        if slot == 1:
            turns += [('Maya', '03:05', price_line), ('Maya', '03:22', budget_question), ('Client', '03:40', budget_answer)]
        else:
            turns += [('Maya', '03:05', budget_question), ('Client', '03:22', budget_answer), ('Maya', '03:40', price_line)]
        turns += [('Maya', '04:00', 'Who will decide on the purchase, and when will you decide?'),
                  ('Client', '04:20', decision_line), ('Maya', '04:42', 'Do you have any objections to the scope?'),
                  ('Client', '05:00', no_objections), ('Maya', '05:18', 'Let us agree the next action here on Upwork.'),
                  ('Client', '05:35', steps[slot])]
        title = ('Shopify collection audit', 'Clinic local SEO audit', 'Buying guide content audit')[slot]
        source = f'Call at: 2026-10-{(6, 7, 9)[slot]:02d}T11:00:00+02:00\nMember: Maya\nComplete: yes\nLanguage: English\n' + '\n'.join(
            f'{speaker}: [{time}] {line}' for speaker, time, line in turns) + '\n'
        quote = price_line if slot == 1 else budget_question
        review = {'reviewable': True, 'key_finding': finding,
                  'better_line': (
                      'I will send the agreed collection page audit scope here on Upwork by Friday.',
                      'Before I quote a price for the clinic audit, what budget range have you set aside?',
                      'Please share the buying guide list here on Upwork by Wednesday so I can update the existing audit scope.'
                  )[slot],
                  'free_read': reads[slot] + context, 'next_message': messages[slot],
                  'next_step': steps[slot], 'agreed_step': steps[slot],
                  'fix': finding, 'example': 'Which budget range should this audit scope fit?',
                  'moments': [{'quote': quote, 'better_wording': messages[slot]}],
                  'points': [{'point': p, 'state': 'missing' if slot == 1 and p == 5 else
                                                   'missing' if slot == 1 and p == 6 else 'not needed' if p == 8 else 'met',
                              'quote': (agenda, current, cost, call_scope, quote, decision_line, proof, no_objections, steps[slot])[p - 1],
                              'reason': 'No decision date was agreed.' if slot == 1 and p == 6 else
                                        'The client explicitly raised no scope objections, so no objection handling was needed.' if p == 8 else
                                        'The price preceded the budget question; the client has not decided a budget.' if slot == 1 and p == 5 else
                                        'The client named the sole decision maker and purchase decision date.' if p == 6 else
                                        'The client confirmed the budget before Maya gave the price.' if p == 5 else
                                        'The transcript records this check.'}
                             for p in range(1, 10)]}
        if slot == 1:
            review['points'][5].update(pattern_sentence='you left the decision date open.',
                                      better_line='When will you decide on this audit here on Upwork?')
    return {'title': title, 'quote': quote, 'source': source, 'review': review}

def seed(rows):
    run('pipeline.py', 'add', '--file', '-', value=rows)

def records():
    import pipeline
    return {job['id']: job for job in pipeline.load()}

def record(jid, values):
    return run('pipeline.py', 'record', jid, '--file', '-', value=values)

def analytics_stamp(day, hour=10, minute=0):
    return dt.datetime.combine(day, dt.time(hour, minute), ZoneInfo('Europe/Berlin')).isoformat()

def analytics_sync_marker(folder):
    import analytics
    (folder / 'data/sync.json').write_text(json.dumps({'synced_at': analytics.run_timestamp(ANALYTICS_TODAY).isoformat()}))

def analytics_rows():
    """Eight weekly cohorts; every expected event is fixed before running analytics."""
    rows = []
    for week in range(8):
        day = dt.date(2026, 8, 24) + dt.timedelta(weeks=week)
        for source, count in (('outbound', 40), ('invite', 20), ('direct_offer', 20)):
            for index in range(count):
                jid = str(970000000 + week * 1000 + len(rows) % 1000)
                row = {'id': jid, 'source': source, 'title': 'Operations dashboard and audit automation',
                       'client': {'name': 'SYNTHETIC PRIVATE CLIENT NAME'},
                       'description': 'SYNTHETIC PRIVATE CLIENT WORDS',
                       'found_at': analytics_stamp(day), 'status': 'applied',
                       'history': [], 'last_activity_at': analytics_stamp(day),
                       'notes': 'SYNTHETIC member evidence',
                       'log': [{'at': analytics_stamp(day), 'text': 'analytics job_fit: ' +
                                json.dumps({'state': 'pass' if index < 36 else 'fail',
                                            'reason': 'Fits the member lane'})}]}
                def event(name, at):
                    row[name + '_at'] = at
                    row[name + '_observation'] = {'source': 'member', 'verified': True}
                    if name == 'call_booked': row[name + '_observation']['kind'] = 'booking-confirmed'
                if source == 'outbound':
                    event('applied', analytics_stamp(day))
                    row['application_facts'] = {'source': source, 'posted_age_band': '<10m' if index < 32 else '10-60m',
                                                'proposals_band': '<5' if index < 30 else '5-15'}
                    row['history'].append({'status': 'applied', 'at': row['applied_at']})
                    if index < 32:
                        event('replied', analytics_stamp(day, 10, 1))
                        row.update(first_reply_s=180, first_reply_at=analytics_stamp(day, 10, 4))
                    if index < 24:
                        event('call_booked', analytics_stamp(day + dt.timedelta(days=1)))
                        row['call_scheduled_at'] = analytics_stamp(day + dt.timedelta(days=1), 11)
                    if index < 22:
                        event('call_held', analytics_stamp(day + dt.timedelta(days=1), 11))
                        event('call_ended', analytics_stamp(day + dt.timedelta(days=1), 11, 5))
                    if index < 21:
                        event('proposal_sent', analytics_stamp(day + dt.timedelta(days=1), 11, 10))
                    won = index < 18
                    if index in (22, 23):
                        row['call_no_show'] = True
                    row['follow_up_history'] = [{'action': 'sent', 'lane': 'silent',
                                                 'due_on': (day + dt.timedelta(days=1)).isoformat(),
                                                 'on': (day + dt.timedelta(days=1 if index < 36 else 2)).isoformat(),
                                                 'at': analytics_stamp(day + dt.timedelta(days=1 if index < 36 else 2))}]
                elif source == 'invite':
                    row['application_date_unknown'] = True
                    row['invited_at'] = analytics_stamp(day)
                    if index < 15:
                        event('call_booked', analytics_stamp(day + dt.timedelta(days=1)))
                    if index < 12:
                        event('offered', analytics_stamp(day + dt.timedelta(days=1), 12))
                        row['history'].append({'status': 'offer', 'at': analytics_stamp(day + dt.timedelta(days=1), 12)})
                    won = index < 10
                else:
                    row['application_date_unknown'] = True
                    event('offered', analytics_stamp(day))
                    row['history'].append({'status': 'offer', 'at': analytics_stamp(day)})
                    won = index < 16
                if won:
                    row['status'] = 'won'
                    row['contract_id'] = 'synthetic-' + jid
                    event('won', analytics_stamp(day + dt.timedelta(days=2)))
                    row['history'].append({'status': 'won', 'at': analytics_stamp(day + dt.timedelta(days=2))})
                    row['won_value'] = {'type': 'fixed', 'amount': 100, 'currency': 'USD',
                                        'start_date': (day + dt.timedelta(days=2)).isoformat()}
                elif row.get('call_booked_at'):
                    row['status'] = 'call'
                elif source != 'outbound':
                    row['status'] = 'offer' if row['history'] else 'new'
                elif row.get('replied_at'):
                    row['status'] = 'replied'
                rows.append(row)
    return rows

def analytics_interval(k, n):
    """Independent Wilson oracle, in percent, from the frozen formula."""
    if not n:
        return None, None
    z = 1.959963984540054
    p = k / n
    divisor = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / divisor
    half = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** .5) / divisor
    return 100 * (centre - half), 100 * (centre + half)

def analytics_exact_interval(k, n):
    import math
    if not n: return None, None
    def tail(p, lower):
        terms = range(k, n + 1) if lower else range(k + 1)
        return sum(math.exp(math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1) + i * math.log(p) + (n - i) * math.log1p(-p)) for i in terms)
    def solve(lower):
        lo, hi = 0., 1.
        for _ in range(60):
            mid = (lo + hi) / 2
            if (tail(mid, lower) < .025) == lower: lo = mid
            else: hi = mid
        return 100 * (lo + hi) / 2
    return (0. if k == 0 else solve(True), 100. if k == n else solve(False))

def analytics_rate_state(k, n, target):
    low, high = analytics_interval(k, n)
    return 'undecided' if not n else 'pass' if low >= target else 'fail' if high < target else 'undecided'

def analytics_event(row, event):
    if event == 'offer' and row.get('offered_at'):
        return dt.datetime.fromisoformat(row['offered_at'])
    if row.get(event + '_at'):
        return dt.datetime.fromisoformat(row[event + '_at'])
    values = [dt.datetime.fromisoformat(item['at']) for item in row.get('history', [])
              if item.get('status') == event]
    return min(values) if values else None

def analytics_rate_oracle(rows, today, baseline=False):
    end = dt.datetime.combine(today - dt.timedelta(days=28 if baseline else 0), dt.time(), ZoneInfo('Europe/Berlin'))
    start = end - dt.timedelta(days=28)
    cutoff = end
    definitions = {
        'reply_rate': ('applied', 7, 20, ('replied',), 'outbound'),
        'reply_to_call': ('replied', 14, 50, ('call_booked', 'offer', 'won'), 'outbound'),
        'booked_to_held': ('call_booked', 2, 90, ('call_held',), 'outbound'),
        'held_to_proposal': ('call_held', 7, 90, ('proposal_sent',), 'outbound'),
        'proposal_to_won': ('proposal_sent', 21, 30, ('won',), 'outbound'),
        'invite_to_call': ('invited', 14, 50, ('call_booked', 'offer', 'won'), 'invite'),
        'offer_to_contract': ('offer', 21, 80, ('won',), 'inbound'),
    }
    expected = {}
    for key, (entry, maturity, target, successes, source) in definitions.items():
        cohort = [row for row in rows if not row.get('imported')
                  and (source is None or (source == 'inbound' and row.get('source', 'outbound') != 'outbound') or row.get('source', 'outbound') == source)
                  and analytics_event(row, entry) and start - dt.timedelta(days=maturity) <= analytics_event(row, entry) < end - dt.timedelta(days=maturity)]
        k = sum(any(analytics_event(row, event) and analytics_event(row, entry) <= analytics_event(row, event) <= analytics_event(row, entry) + dt.timedelta(days=maturity)
                    for event in successes)
                for row in cohort)
        expected[key] = (k, len(cohort), target)
    return expected

def analytics_payload(snapshot, agree=True):
    """A member-approved synthetic coaching addition, without client words."""
    value = json.loads(json.dumps(snapshot))
    primary = value['verdict'].get('kpi') or 'reply_rate'
    keys = [primary] + [key for key in ('reply_rate', 'reply_to_call', 'booked_to_held', 'held_to_proposal')
                        if key != primary][:2]
    value['goals_next'] = [{'stage': value['kpis'][key]['label'], 'kpi': key,
                            'change': 'Use the agreed next step', 'primary': index == 0,
                            'cue': 'When this stage starts', 'action': 'Offer the agreed next step',
                            'fallback': 'Offer one smaller next step',
                            'review_on': (dt.date.fromisoformat(value['window']['end']) + dt.timedelta(days=8)).isoformat()}
                           for index, key in enumerate(keys)]
    value['report'] = 'SYNTHETIC weekly coaching report; nothing new this week.'
    value['community_card']['next_focus'] = value['kpis'][primary]['label']
    value['community_card']['question_id'] = 'reply_rate-1'
    value['insights_top'] = [{'kind': 'habit', 'text': 'One clear next step keeps work moving',
                              'target': {'view': 'overview', 'element': primary}}]
    value['kpis']['reply_rate']['insight'] = 'One clear next step keeps work moving'
    value['reviews'] = {kind: {'fix': 'Make one next step clear',
                               'example': 'I can offer Tuesday at ten.',
                               'evidence_lead_ids': [], 'goal_ref': keys[index % 3]}
                        for index, kind in enumerate(('application', 'conversation', 'call', 'proposal'))}
    import analytics
    today=dt.date.fromisoformat(value['generated_at'][:10])
    agreement={'week':value['week'],'goals':[dict(goal,start=today.isoformat()) for goal in value['goals_next']]}
    analytics.validate_goals(agreement)
    ledger=analytics.read_lines('goals.jsonl')
    prior=next((row for row in ledger if row.get('week')==value['week']),None)
    if agree:
        agreement_data=pathlib.Path(os.environ.get('BLUEPRINT_DATA','')).resolve()
        assert agreement_data.is_relative_to(pathlib.Path(tempfile.gettempdir()).resolve()) and agreement_data != (ROOT/'data').resolve() and agreement_data.parent.name.startswith(('blueprint-synthetic-', 'analytics-eight-week-')),'Synthetic agreement helper cannot write member storage'
        if prior is None:analytics.add_goals(agreement)
        else:
            value['goals_next'] = [{k:v for k,v in goal.items() if k != 'start'} for goal in prior['goals']]
            value['community_card']['next_focus'] = next(goal['stage'] for goal in prior['goals'] if goal['primary'])
    return analytics.prepare_snapshot(value, today)

def analytics_decisions():
    import analytics
    assert analytics.rate_state(5, 18, 30) == 'undecided'
    assert analytics.rate_state(0, 0, 30) == 'undecided'
    assert analytics.rate_state(0, 40, 30) == 'fail'
    assert analytics.rate_state(40, 40, 90) == 'pass'
    for k, n in ((5, 18), (0, 40), (40, 40), (17, 40), (96, 120)):
        low, high = analytics.wilson(k, n)
        expected = analytics_interval(k, n)
        assert abs(low - expected[0]) < .05 and abs(high - expected[1]) < .05, (k, n, low, high, expected)
    funnel = ('reply_rate', 'reply_to_call', 'booked_to_held', 'held_to_proposal',
              'proposal_to_won', 'invite_to_call', 'offer_to_contract')
    with fixture('analytics-verdict'):
        base = analytics.compute(ANALYTICS_TODAY)
        for selected in funnel:
            kpis = json.loads(json.dumps(base['kpis']))
            for key in funnel:
                kpis[key].update(k=40, n=40, value=100, low=91.2, high=100, state='pass')
            for key in ('speed_10min', 'first_reply', 'follow_ups_on_time', 'proposal_on_time'):
                kpis[key].update(state='pass')
            kpis[selected].update(k=0, n=40, value=0, low=0, high=8.8, state='fail')
            result = analytics.verdict(kpis)
            assert result['kpi'] == selected and result['state'] == 'confirmed', result
            assert result['mode'] == 'funnel', result
        kpis[funnel[0]].update(state='missing', reason='No measured source')
        kpis[funnel[1]].update(state='undecided')
        kpis[funnel[2]].update(state='fail')
        result = analytics.verdict(kpis)
        assert result['kpi'] == funnel[2]
        assert result['undecided_before'] == list(funnel[:2]), result
        for key in funnel:
            kpis[key].update(state='undecided')
        kpis['weekly_volume'].update(state='fail', value=2, k=2, n=25)
        result = analytics.verdict(kpis)
        assert result['mode'] == 'levers' and result['state'] == 'levers', result
        for key in funnel:
            kpis[key].update(state='pass')
        kpis['weekly_volume'].update(state='pass')
        result = analytics.verdict(kpis)
        assert result['state'] == 'none', result

def analytics_boundaries():
    import analytics
    with fixture('analytics-boundaries') as folder:
        analytics_sync_marker(folder)
        zone = ZoneInfo('Europe/Berlin')
        def at(text):
            return dt.datetime.fromisoformat(text).replace(tzinfo=zone).isoformat()
        entries = [('2026-09-16T00:00:00', False), ('2026-09-15T23:59:59', False),
                   ('2026-10-07T00:00:00', False), ('2026-10-07T00:00:01', False),
                   ('2026-10-14T00:00:00', False), ('2026-09-17T10:00:00', True),
                   ('2026-08-19T00:00:00', False), ('2026-09-09T00:00:00', False),
                   ('2026-09-09T00:00:01', False), ('2026-08-23T10:00:00', True)]
        rows = [{'id': str(971000000 + index), 'status': 'replied', 'source': 'outbound',
                 'found_at': at(text), 'applied_at': at(text), 'imported': imported,
                 'replied_at': (dt.datetime.fromisoformat(at(text)) + dt.timedelta(minutes=3)).isoformat(),
                 'history': [{'status': 'applied', 'at': at(text)}]}
                for index, (text, imported) in enumerate(entries)]
        seed(rows)
        before = (folder / 'data/jobs.json').read_bytes()
        result = analytics.compute(ANALYTICS_TODAY)
        reply = result['kpis']['reply_rate']
        assert (reply['k'], reply['n'], reply['value'], reply['baseline']) == (4, 4, 100, 100), reply
        assert set(reply['evidence']) == {'971000000', '971000001', '971000007', '971000008'}, reply
        assert (folder / 'data/jobs.json').read_bytes() == before
        no_ledger = result['kpis']['value_per_100_connects']
        assert no_ledger['state'] == 'missing' and no_ledger['value'] is None and no_ledger['reason'], no_ledger
        assert result['north_star']['hourly_billed'] is None
        assert any(row['source'] == 'connects' and row['state'] == 'missing' for row in analytics.coverage_sources(result['coverage']))
        assert any(row['source'] == 'earnings' and row['state'] == 'missing' for row in analytics.coverage_sources(result['coverage']))
    with fixture('analytics-pooled') as folder:
        analytics_sync_marker(folder)
        rows = []
        for week, count, success in ((0, 100, 10), (1, 10, 10)):
            day = dt.date(2026, 9, 22) + dt.timedelta(weeks=week)
            for index in range(count):
                row = {'id': str(972000000 + len(rows)), 'status': 'applied', 'source': 'outbound',
                       'applied_at': analytics_stamp(day), 'found_at': analytics_stamp(day)}
                if index < success:
                    row['replied_at'] = analytics_stamp(day, 10, 3)
                rows.append(row)
        seed(rows)
        rate = analytics.compute(ANALYTICS_TODAY)['kpis']['reply_rate']
        assert (rate['k'], rate['n']) == (20, 110) and abs(rate['value'] - 2000 / 110) < .01, rate
    with fixture('analytics-working-hours') as folder:
        analytics_sync_marker(folder)
        day = dt.date(2026, 10, 8)
        rows = []
        for index, minutes in enumerate([1] * 10 + [100]):
            start = dt.datetime.fromisoformat(analytics_stamp(day))
            rows.append({'id': str(973000000 + index), 'status': 'replied', 'source': 'outbound',
                         'first_reply_s': minutes * 60,
                         'first_reply_at': (start + dt.timedelta(minutes=minutes)).isoformat()})
        rows += [{'id': '973000011', 'status': 'replied', 'first_reply_s': 3600,
                  'first_reply_at': analytics_stamp(dt.date(2026, 10, 10), 11)},
                 {'id': '973000012', 'status': 'replied', 'first_reply_s': 300,
                  'first_reply_at': analytics_stamp(day, 9, 4)},
                 {'id': '973000013', 'status': 'replied', 'first_reply_s': 3600,
                  'first_reply_at': analytics_stamp(day, 20)},
                 {'id': '973000014', 'status': 'replied', 'first_reply_s': 0,
                  'first_reply_at': analytics_stamp(day, 18)}]
        seed(rows)
        first = analytics.compute(ANALYTICS_TODAY)['kpis']['first_reply']
        assert first['n'] == 11 and first['value'] == 1 and first['state'] == 'pass', first
        assert first['p75'] == 1, first

def analytics_member():
    import analytics
    with fixture('analytics-eight-weeks') as folder:
        rows = analytics_rows()
        hourly = {'id': '979999999', 'status': 'won', 'source': 'direct_offer', 'imported': True,
                  'contract_id': 'synthetic-hourly', 'history': [{'status': 'won', 'at': analytics_stamp(dt.date(2026, 8, 1))}],
                  'won_value': {'type': 'hourly', 'amount': 9999, 'currency': 'USD', 'start_date': '2026-08-01'}}
        run('sync.py', 'apply', '--file', '-', value={
            'earnings': [{'week_start': (dt.date(2026, 8, 24) + dt.timedelta(weeks=index)).isoformat(),
                          'contract_id': 'synthetic-hourly', 'billed': 200, 'currency': 'USD'} for index in range(8)],
            'connects': [{'at': row['applied_at'], 'amount': -16, 'reason': 'Application submitted', 'job_id': row['id']}
                         for row in rows if row.get('applied_at')] +
                        [{'at': analytics_stamp(dt.date(2026, 10, 1)), 'amount': 100, 'reason': 'Receipt', 'job_id': None}]})
        seed(rows + [hourly])
        run('pipeline.py', 'note', rows[-80]['id'], 'analytics job_fit: ' + json.dumps({'state': 'pass', 'reason': 'Fits the member lane'}))
        before = (folder / 'data/jobs.json').read_bytes()
        result = json.loads(run('analytics.py', 'compute', '--today', ANALYTICS_TODAY).stdout)
        assert len(result['kpis']) == 24
        expected = analytics_rate_oracle(rows, ANALYTICS_TODAY)
        baseline = analytics_rate_oracle(rows, ANALYTICS_TODAY, baseline=True)
        for key, (k, n, target) in expected.items():
            row = result['kpis'][key]
            rungs = {'reply_rate': [11, 15, 20], 'reply_to_call': [30, 40, 50],
                     'booked_to_held': [70, 80, 90], 'held_to_proposal': [70, 80, 90],
                     'proposal_to_won': [20, 25, 30], 'invite_to_call': [30, 40, 50],
                     'offer_to_contract': [60, 70, 80]}.get(key, [target])  # Frozen §13.1 supplies these rungs.
            target = next((rung for rung in rungs if 100 * k / n < rung), rungs[-1])
            assert (row['k'], row['n'], row['target'], row['state']) == (k, n, target, analytics_rate_state(k, n, target)), (key, row)
            assert row['rungs'] == rungs and row['baseline_phase'] is False, (key, row)
            assert abs(row['value'] - 100 * k / n) < .01, (key, row)
            bk, bn, _ = baseline[key]
            assert abs(row['baseline'] - 100 * bk / bn) < .01, (key, row)
            assert row['delta_pp'] == row['delta'] == 0, (key, row)
            assert row['history'] == [None] * 7 + [row['value']], (key, row)
            low, high = analytics_interval(k, n)
            assert abs(row['low'] - low) < .01 and abs(row['high'] - high) < .01
            exact_low, exact_high = analytics_exact_interval(k, n)
            assert abs(row['exact_low'] - exact_low) < .01 and abs(row['exact_high'] - exact_high) < .01, (key, row)
        other = {
            'won_value': (44, 44, 'undecided', 4400),
            'value_per_100_connects': (176, 2560, 'undecided', 515.625),
            'weekly_volume': (36, 25, 'pass', 36),
            'speed_10min': (32, 36, 'pass', 3200 / 36),
            'first_reply': (32, 32, 'pass', 3),
            'follow_ups_on_time': (36, 40, 'fail', 90),
            'proposal_on_time': (21, 22, 'pass', 2100 / 22),
            'job_fit': (36, 40, 'fail', 90),
            'application_review': (None, None, 'undecided', None),
            'conversation_review': (None, None, 'undecided', None),
            'call_review': (None, None, 'undecided', None),
            'proposal_review': (None, None, 'undecided', None),
            'segments': (0, 25, 'observed', 0),
            'behaviour': (0, 3, 'observed', 0),
            'lost_reasons': (0, 0, 'undecided', {'stated': 0, 'observed': 0, 'unknown': 0}),
            'goal_effect': (0, 0, 'undecided', None),
            'goal_done': (0, 0, 'undecided', None),
        }
        for key, values in other.items():
            row = result['kpis'][key]
            assert (row['k'], row['n'], row['state']) == values[:3], (key, row, values)
            if isinstance(values[3], (int, float)):
                assert row['baseline'] is not None, (key, row, values)
                assert abs(row['baseline'] - values[3]) < .001, (key, row, values)
            else:
                assert row['baseline'] == values[3], (key, row, values)
        assert result['kpis']['won_value']['value'] == 4400
        assert abs(result['kpis']['value_per_100_connects']['value'] - 687.5) < .001
        assert result['kpis']['speed_10min']['proposals_under_5'] == {'k': 30, 'n': 36}
        assert result['kpis']['first_reply']['p75'] == 3
        assert result['north_star']['value'] == 4400 and result['north_star']['fixed_value'] == 4400
        assert result['north_star']['hourly_billed'] == 200 and result['north_star']['wins'] == 44
        assert result['north_star']['baseline'] == 4400
        assert result['periods']['activity'] == result['periods']['outcome'] == {'start': '2026-10-07', 'end': '2026-10-13'}
        assert result['periods']['cohort'] == result['window'] == {'start': '2026-09-16', 'end': '2026-10-13'}
        assert set(row['source'] for row in analytics.coverage_sources(result['coverage'])) == {'recorder', 'upwork', 'tracking', 'loom', 'earnings', 'connects'}
        assert result['verdict']['kpi'] == 'follow_ups_on_time' and result['verdict']['state'] == 'levers'
        assert result['findings'] == []
        assert result['community_card']['applications'] == 36, result['community_card']
        assert all(set(row) == ({'stage', 'count', 'known_value', 'oldest_days', 'stalled', 'proposals_out'} |
                    ({'booked', 'held', 'unknown_call'} if row['stage'] == 'call' else set()))
                   for strand in result['pipeline'].values() for row in strand)
        assert sum(row['count'] for row in result['pipeline']['outbound']) == 8 * 22
        assert sum(row['count'] for row in result['pipeline']['inbound']) == 8 * 14
        assert (folder / 'data/jobs.json').read_bytes() == before
        analytics_storage(result, folder, rows)

def analytics_storage(snapshot, folder, rows):
    import analytics
    value=analytics_payload(snapshot,agree=False)
    goal_input={'week':value['week'],'goals':[dict(goal,start='2026-10-14') for goal in value['goals_next']]}
    def rejected(payload):
        try:analytics.record_snapshot(payload)
        except ValueError:pass
        else:raise AssertionError('Invalid persisted snapshot accepted')
    rejected(value)
    assert not (folder/'data/goals.jsonl').exists() and not (folder/'data/analytics-history.jsonl').exists()
    agreed=analytics.add_goals(goal_input)
    assert analytics.read_lines('goals.jsonl')==[agreed]
    changed=json.loads(json.dumps(value));changed['goals_next'][0]['action']='Unagreed changed action'
    rejected(changed)
    tampered=json.loads(json.dumps(value));tampered['kpis']['reply_rate']['value']=99
    rejected(tampered)
    stored=analytics.record_snapshot(value)
    readback=analytics.last()
    assert readback==analytics.read_lines('analytics-history.jsonl')[-1]==stored
    assert analytics.due(ANALYTICS_TODAY+dt.timedelta(days=7))
    for surface in (json.dumps(stored['community_card']),analytics.public_onepager_html(stored['community_card'])):
        assert all(secret not in surface for secret in ('SYNTHETIC PRIVATE CLIENT NAME','SYNTHETIC PRIVATE CLIENT WORDS','Operations dashboard and audit automation'))
    assert stored['reviews']['application']['example']=='I can offer Tuesday at ten.'
    previous = analytics_payload(analytics.compute(ANALYTICS_TODAY - dt.timedelta(days=7)),agree=False)
    keys = ('booked_to_held', 'first_reply', 'follow_ups_on_time')
    previous_goals = {'week': previous['week'], 'goals': [dict(previous['goals_next'][index],
                      kpi=key, stage=snapshot['kpis'][key]['label'], start='2026-10-07')
                      for index, key in enumerate(keys)]}
    analytics.add_goals(previous_goals)
    reviewed = analytics_payload(analytics.compute(ANALYTICS_TODAY))
    assert [goal['effect'] for goal in reviewed['goals_review']] == ['undecided', 'not', 'not'], reviewed['goals_review']
    assert (reviewed['goals_review'][0]['before_k'], reviewed['goals_review'][0]['before_n']) == (88, 96)  # Frozen §13.7: full28days before start.
    assert abs(reviewed['goals_review'][0]['before'] - 2200 / 24) < .001 and reviewed['goals_review'][0]['after'] is None
    assert [(goal['before'], goal['after']) for goal in reviewed['goals_review'][1:]] == [(3, 3), (90, 90)]
    evidence = [row['id'] for row in rows[-80:-76]]
    for index, goal in enumerate(reviewed['goals_review']):
        goal['evidence_lead_ids'] = evidence[:index + 2]
        goal['done_lead_ids'] = evidence[:2] if index < 2 else []
        goal['decision'] = ('adjust', 'keep', 'stop')[index]
    reviewed = analytics.prepare_snapshot(reviewed, ANALYTICS_TODAY)
    analytics.record_snapshot(reviewed,replace=True)
    stored=analytics.last()
    assert [(goal['done_k'], goal['done_n']) for goal in stored['goals_review']] == [(2, 2), (2, 3), (0, 4)]
    assert [goal['effect'] for goal in stored['goals_review']] == ['undecided', 'not', 'not']
    assert stored['kpis']['goal_effect']['k'] == 0 and stored['kpis']['goal_effect']['n'] == 3
    assert (stored['kpis']['goal_done']['k'], stored['kpis']['goal_done']['n'], stored['kpis']['goal_done']['state']) == (4, 9, 'fail')
    for key in ('application_review', 'conversation_review', 'call_review', 'proposal_review'):
        assert (stored['kpis'][key]['k'], stored['kpis'][key]['n'], stored['kpis'][key]['state'], stored['kpis'][key]['baseline']) == (0, 1, 'undecided', None)


def analytics_levers_and_imports():
    import analytics
    import cockpit
    with fixture('analytics-levers') as folder:
        analytics_sync_marker(folder)
        (folder / 'context/me.md').write_text('## Bars\nreply_rate: 25\nfirst_reply: 2\nfirst_reply_p75: 10\nweekly_volume: 30\nVolume: 8\nProposal: 33\nreply_to_call: 101\nunknown: 50\n## Weekly goal\n12\n## Working hours\n09:00-18:00 Mon-Fri Europe/Berlin\n')
        assert analytics.bars()['reply_rate'] == 25 and analytics.bars()['reply_to_call'] == 50
        assert analytics.bars()['first_reply'] == 2 and analytics.bars()['weekly_volume'] == 30
        assert cockpit.bars()['Volume'] == 8 and cockpit.bars()['Proposal'] == 33
        path = folder / 'context/me.md'
        path.write_text(path.read_text().replace('weekly_volume: 30\n', ''))
        assert analytics.bars()['weekly_volume'] == 12
        start = dt.datetime.fromisoformat(analytics_stamp(dt.date(2026, 10, 9), 17, 55))
        end = dt.datetime.fromisoformat(analytics_stamp(dt.date(2026, 10, 12), 9, 10))
        assert analytics.working_reply({'first_reply_at': end.isoformat(), 'first_reply_s': (end - start).total_seconds()}) == 15
        rows = [
            {'id': '975000001', 'status': 'applied', 'source': 'outbound', 'found_at': analytics_stamp(dt.date(2026, 10, 1)),
             'status_updated_at': analytics_stamp(dt.date(2026, 10, 1)), 'last_activity_at': analytics_stamp(dt.date(2026, 10, 13)),
             'details': {'price_estimate': 500}, 'next_follow_up': '2026-10-08', 'follow_up_plan': {'lane': 'silent'},
             'follow_up_history': [{'action': 'sent', 'lane': 'silent', 'due_on': '2026-10-09', 'on': '2026-10-09'},
                                   {'action': 'sent', 'lane': 'silent', 'due_on': '2026-10-09', 'on': '2026-10-09'},
                                   {'action': 'sent', 'lane': 'silent', 'due_on': '2026-10-12', 'on': '2026-10-13'}]},
            {'id': '975000002', 'status': 'offer', 'source': 'direct_offer', 'imported': True,
             'found_at': analytics_stamp(dt.date(2026, 10, 2)), 'status_updated_at': analytics_stamp(dt.date(2026, 10, 2)),
             'last_activity_at': analytics_stamp(dt.date(2026, 10, 2)), 'details': {'bid_amount': 700}},
            {'id': '975000003', 'status': 'won', 'source': 'outbound', 'imported': True,
             'applied_at': analytics_stamp(dt.date(2026, 9, 20)), 'replied_at': analytics_stamp(dt.date(2026, 9, 21)),
             'won_value': {'type': 'fixed', 'amount': 700, 'currency': 'USD', 'start_date': '2026-10-08'},
             'history': [{'status': 'won', 'at': analytics_stamp(dt.date(2026, 10, 8))}]},
            {'id': '975000004', 'status': 'won', 'source': 'outbound', 'imported': True,
             'won_value': {'type': 'fixed', 'amount': 400, 'currency': 'USD', 'start_date': '2026-09-10'},
             'history': [{'status': 'won', 'at': analytics_stamp(dt.date(2026, 9, 10))}]},
            {'id': '975000005', 'status': 'lost', 'status_updated_at': analytics_stamp(dt.date(2026, 10, 8))}]
        seed(rows)
        run('pipeline.py', 'note', '975000005', 'analytics lost_reason: ' + json.dumps({'kind': 'stated', 'reason': 'Timing changed'}))
        (folder / 'data/earnings.jsonl').write_text('')
        value = analytics.compute(ANALYTICS_TODAY)
        assert value['north_star']['value'] == value['north_star']['fixed_value'] == 700
        assert value['north_star']['wins'] == 1 and value['north_star']['baseline'] == 100
        assert value['kpis']['reply_rate']['n'] == 0
        assert (value['kpis']['follow_ups_on_time']['k'], value['kpis']['follow_ups_on_time']['n']) == (1, 3)
        assert value['kpis']['lost_reasons']['value'] == {'stated': 1, 'observed': 0, 'unknown': 0}
        applied = next(row for row in value['pipeline']['outbound'] if row['stage'] == 'applied')
        offer = next(row for row in value['pipeline']['inbound'] if row['stage'] == 'offer')
        assert applied == {'stage': 'applied', 'count': 1, 'known_value': 500, 'oldest_days': 13, 'stalled': 0, 'proposals_out': 0}
        assert offer == {'stage': 'offer', 'count': 1, 'known_value': 700, 'oldest_days': 12, 'stalled': 1, 'proposals_out': 0}
        (folder / 'data/connects.jsonl').write_text(json.dumps({'at': analytics_stamp(dt.date(2026, 10, 8)),
            'amount': -100, 'reason': 'Application spend', 'job_id': '975000003'}) + '\n')
        path.write_text(path.read_text().replace('## Bars\n', '## Bars\nwon_value: 650\nvalue_per_100_connects: 800\n'))
        monetary = analytics.compute(ANALYTICS_TODAY)
        assert monetary['kpis']['won_value']['target'] == 650 and monetary['kpis']['won_value']['state'] == 'pass'
        assert monetary['kpis']['value_per_100_connects']['value'] == 700 and monetary['kpis']['value_per_100_connects']['target'] == 800
        assert monetary['kpis']['value_per_100_connects']['state'] == 'fail'
        live_missing = analytics.prepare_snapshot({'coverage': [{'source': 'upwork', 'state': 'missing', 'fix': 'Reconnect the connector'}]}, ANALYTICS_TODAY)
        assert live_missing['kpis']['reply_rate']['state'] == 'missing' and live_missing['north_star']['value'] is None
    needed = analytics.cases_needed(5, 18, 30)
    assert isinstance(needed, int) and needed > 0
    assert analytics_rate_state(round(5 / 18 * (18 + needed)), 18 + needed, 30) != 'undecided'
    assert analytics.cases_needed(3, 10, 30) is None

def analytics_source_and_timezone():
    import analytics
    with fixture('analytics-source-timezone') as folder:
        analytics_sync_marker(folder)
        (folder / 'data/earnings.jsonl').write_text('')
        seed([{'id': '976000001', 'status': 'applied', 'found_at': analytics_stamp(dt.date(2026, 10, 12)),
               'applied_at': analytics_stamp(dt.date(2026, 10, 12))}])
        optional = analytics.compute(ANALYTICS_TODAY)
        assert optional['kpis']['application_review']['state'] == 'undecided'
        assert optional['kpis']['proposal_review']['state'] == 'undecided'
        assert next(row for row in analytics.coverage_sources(optional['coverage']) if row['source'] == 'tracking')['affects'] == []
        jobdir = folder / 'jobs/976000001'
        jobdir.mkdir()
        (jobdir / 'application.sent.md').write_text('Member wording: please see https://www.loom.com/share/synthetic')
        required = analytics.compute(ANALYTICS_TODAY)
        assert required['kpis']['application_review']['state'] == 'missing'
        (jobdir / 'loom.md').write_text('SYNTHETIC recorded member words')
        present = analytics.compute(ANALYTICS_TODAY)
        assert present['kpis']['application_review']['state'] == 'undecided'
        (folder / 'context/me.md').write_text('## Timezone\nAmerica/New_York\n## Working hours\n09:00-18:00 Mon-Fri\n')
        assert str(analytics.local_zone()) == 'America/New_York'
        assert analytics.working_reply({'first_reply_at': '2026-10-08T18:30:00+00:00', 'first_reply_s': 300}) == 5
        local = analytics.compute(ANALYTICS_TODAY)
        assert dt.datetime.fromisoformat(local['generated_at']).utcoffset() == dt.timedelta(hours=-4)


def outcome_badge_interval():
    import analytics
    with fixture('outcome-badge-interval') as folder:
        analytics_sync_marker(folder)
        date = ANALYTICS_TODAY - dt.timedelta(days=14)
        rows = [dict(id=str(963000000+i), source='outbound', applied_at=analytics_stamp(date),
                     replied_at=analytics_stamp(date,10,1)) for i in range(20)]
        rows.append(dict(id='963999999', source='outbound', applied_at=analytics_stamp(ANALYTICS_TODAY-dt.timedelta(weeks=10))))
        low, _ = analytics_exact_interval(20,20)
        tiers = dict(Bronze=11, Silver=15, Gold=20, Platinum=25, Legend=30)
        awards = [row for row in analytics.compute(ANALYTICS_TODAY,jobs=rows)['badges'] if row['badge']=='Harbour Master']
        assert awards and all(low >= tiers[row['tier']] for row in awards)
        assert not any(row['badge']=='Harbour Master' and row['tier']=='Legend' for row in analytics.compute(ANALYTICS_TODAY,jobs=[rows[0],rows[-1]])['badges'])


def analytics_privacy_and_badge_replace():
    import analytics
    import pipeline
    with fixture('privacy-call') as folder:
        analytics_sync_marker(folder)
        seed([{'id': '962000001', 'source': 'outbound', 'status': 'call',
               'client': 'SYNTHETICSTRINGCLIENT', 'found_at': analytics_stamp(ANALYTICS_TODAY)}])
        jobdir = folder / 'jobs/962000001'
        jobdir.mkdir()
        (jobdir / 'call.md').write_text('Member: Alex\nAlex: I can offer Tuesday at ten.\n'
            'SYNTHETICCALLCLIENT: SYNTHETIC private spoken client sentence.\n')
        payload = analytics_payload(analytics.compute(ANALYTICS_TODAY))
        for secret in ('SYNTHETICSTRINGCLIENT', 'SYNTHETICCALLCLIENT', 'SYNTHETIC private spoken client sentence.'):
            invalid = json.loads(json.dumps(payload))
            invalid['report'] = secret
            assert run('analytics.py', 'record', '--file', '-', value=invalid, success=False).returncode != 0, secret
        invalid = json.loads(json.dumps(payload))
        invalid['reviews']['call']['example'] = 'SYNTHETIC private spoken client sentence.'
        assert run('analytics.py', 'record', '--file', '-', value=invalid, success=False).returncode != 0
        run('analytics.py', 'record', '--file', '-', value=payload)
        assert json.loads(run('analytics.py', 'last').stdout)['reviews']['call']['example'] == 'I can offer Tuesday at ten.'
    with fixture('badge-same-week-replace') as folder:
        analytics_sync_marker(folder)
        date = ANALYTICS_TODAY - dt.timedelta(days=2)
        seed([{'id': '961000001', 'source': 'outbound', 'status': 'applied',
               'applied_at': analytics_stamp(date), 'speed_to_lead_s': 120,
               'applied_observation': {'verified': True, 'source': 'upwork-proposal'},
               'job_fit': {'state': 'pass', 'reason': 'Verified lane and rate fit'},
               'application_review': {'state': 'pass', 'reason': 'Submitted copy fits the agreed problem and offer'},
               'application_facts': {'source': 'outbound', 'posted_age_band': '<10m'}}])
        payload = analytics_payload(analytics.compute(ANALYTICS_TODAY))
        run('analytics.py', 'record', '--file', '-', value=payload)
        pipeline.save([])
        replacement = analytics_payload(analytics.compute(ANALYTICS_TODAY))
        assert any(row['badge'] == 'Swift Sail' and row['tier'] == 'Bronze'
                   for row in replacement['badges']), replacement['badges']
        run('analytics.py', 'record', '--replace', '--file', '-', value=replacement)
        stored = json.loads(run('analytics.py', 'last').stdout)
        assert any(row['badge'] == 'Swift Sail' and row['tier'] == 'Bronze' for row in stored['badges'])

def obligations_finance_and_atomic_goals():
    import analytics
    import concurrent.futures
    today = dt.date(2026, 10, 14)
    now = '2026-10-14T15:00:00+02:00'
    def ts(date, hour=10, minute=0): return analytics_stamp(date, hour, minute)
    def marker(folder):
        (folder / 'data/sync.json').write_text(json.dumps({'synced_at': now}))
        (folder / 'data/earnings.jsonl').write_text('')
        (folder / 'data/connects.jsonl').write_text('')
    def goal(key='reply_rate', start='2026-09-01'):
        return {'kpi': key, 'stage': analytics.LABELS[key], 'change': 'Offer two concrete call times',
                'start': start, 'primary': True, 'cue': 'When clients reply', 'action': 'Offer two call times',
                'fallback': 'Offer one time', 'review_on': (dt.date.fromisoformat(start) + dt.timedelta(days=7)).isoformat()}
    with fixture('audit-analytics') as folder:
        marker(folder)
        cleared={'id':'920000007','follow_up_history':[{'lane':'silent','due_on':'2026-10-08','cancelled_at':'2026-10-09T12:00:00+02:00'},
                  {'lane':'silent','due_on':'2026-10-10','cancelled_at':'2026-10-09T12:00:00+02:00'}]}
        compliance=analytics.calculate([cleared],today,now=now)[0]['follow_ups_on_time']
        assert (compliance['k'],compliance['n'])==(0,1)
        obligations={'id':'920000077','follow_up_history':[
            {'obligation_id':'first','lane':'silent','due_on':'2026-10-08','on':'2026-10-08','action':'sent'},
            {'obligation_id':'first','lane':'silent','due_on':'2026-10-08','cancelled_at':'2026-10-09T12:00:00+02:00'},
            {'obligation_id':'second','lane':'silent','due_on':'2026-10-08'}]}
        obligations_result=analytics.calculate([obligations],today,now=now)[0]['follow_ups_on_time']
        assert (obligations_result['k'],obligations_result['n'])==(1,2)

        fixed={'id':'920000010','won_at':ts(today-dt.timedelta(days=1)), 'won_value':{'type':'fixed','amount':200,'currency':'USD','start_date':'2026-10-13'}}
        old={'id':'920000011','won_value':{'type':'fixed','amount':100,'currency':'EUR','start_date':'2026-10-06'}}
        hourly={'id':'920000012','won_value':{'type':'hourly','amount':50,'weekly_hours':10,'currency':'USD','start_date':'2026-10-12'}}
        bills=[{'contract_id':'old','week_start':'2026-10-12','currency':'EUR','billed':100}, {'contract_id':'old','week_start':'2026-10-12','currency':'EUR','billed':250}]
        finance=analytics.financial([fixed,old,hourly],bills,analytics.span(today,7))
        assert finance['value']==2200 and finance['hourly_billed']==250 and finance['currency']=='USD'
        unknown=analytics.financial([dict(fixed,id='920000013',won_value=None)],[],analytics.span(today,7))
        assert unknown['value'] is None and unknown['value_unknown_n']==1 and unknown['known_subtotal']==0
        before=analytics.rate_metric('reply_rate',[{'id':str(i)} for i in range(1)],lambda row:False,20)
        after=analytics.rate_metric('reply_rate',[{'id':str(i)} for i in range(1)],lambda row:True,20)
        lo,hi=analytics.difference_bounds(before,after)
        assert lo<0<hi
        (folder/'context/me.md').write_text('## Bars\nreply_rate: 30\n')
        entry=today-dt.timedelta(days=35)
        flow=[]
        for index in range(100):
            row={'id':str(930000000+index),'source':'outbound','applied_at':ts(entry)}
            if index<20: row['replied_at']=ts(entry+dt.timedelta(days=1))
            if index<5: row.update(won_at=ts(entry+dt.timedelta(days=5)),won_value={'type':'fixed','amount':1000,'currency':'USD','start_date':(entry+dt.timedelta(days=5)).isoformat()})
            flow.append(row)
        losses=analytics.calculate(flow,today,now=now)[0]
        assert losses['reply_rate']['downstream_to_won']==.25
        assert losses['reply_rate']['lost_revenue']==2500
        terminal=[]
        for index in range(100):
            row={'id':str(930100000+index),'source':'outbound','proposal_sent_at':ts(entry)}
            if index<20:row.update(won_at=ts(entry+dt.timedelta(days=5)),won_value={'type':'fixed','amount':1000,'currency':'USD','start_date':(entry+dt.timedelta(days=5)).isoformat()})
            terminal.append(row)
        loss=analytics.calculate(terminal,today,now=now)[0]['proposal_to_won']
        assert loss['downstream_to_won']==1 and abs(loss['lost_revenue']-10000)<.01
        (folder/'context/me.md').write_text('# Synthetic member\n')

        atomic_input={'week':'2026-W43','goals':[goal('weekly_volume','2026-10-19')]}
        def add_once(_):
            try:analytics.add_goals(atomic_input);return True
            except ValueError:return False
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            assert sum(pool.map(add_once,range(2)))==1
        previous_bytes=(folder/'data/goals.jsonl').read_bytes()
        with mock.patch.object(analytics.os,'replace',side_effect=OSError('synthetic interruption')):
            try:analytics.atomic_lines('goals.jsonl',[])
            except OSError:pass
        assert (folder/'data/goals.jsonl').read_bytes()==previous_bytes
        assert not list((folder/'data').glob('*analytics*.lock')) and not list((folder/'data').glob('*goals*.lock'))

def goal_effect_execution_forecast_and_record_races():
    import analytics
    import copy
    import concurrent.futures
    today=dt.date(2026,10,14);now='2026-10-14T15:00:00+02:00'
    def setup(folder):
        (folder/'data/sync.json').write_text(json.dumps({'synced_at':now}))
        (folder/'data/earnings.jsonl').write_text('');(folder/'data/connects.jsonl').write_text('')
    def commitment(key,start='2026-09-01'):
        return {'kpi':key,'goal_library_id':{'reply_rate':'reply-proof','first_reply':'first-answer','weekly_volume':'volume-sessions'}[key],'stage':analytics.LABELS[key],'change':'Review applications once','start':start,
                'primary':True,'cue':'When reviewing the week','action':'Review applications once',
                'fallback':'Review one application','review_on':(dt.date.fromisoformat(start)+dt.timedelta(days=7)).isoformat()}
    with fixture('audit-real-effects') as folder:
        setup(folder)
        for before_min,after_min,expected in ((1,3,'not'),(10,6,'worked'),(3,3,'not')):  # Frozen §13.7: unchanged is no effect.
            rows=[]
            for phase,value in ((0,before_min),(1,after_min)):
                date=dt.date(2026,8,28) if phase==0 else dt.date(2026,9,3)
                for index in range(100):
                    rows.append({'id':str(931000000+phase*1000+index),'first_reply_at':analytics_stamp(date,10,value),'first_reply_s':value*60})
            analytics.atomic_lines('goals.jsonl',[{'week':'2026-W36','goals':[commitment('first_reply')]}])
            review=analytics.goal_reviews(rows,today,now=now)[0]
            assert review['effect']==expected,(before_min,after_min,review)
            assert (review['before'],review['after'])==(before_min,after_min)
        for bk,bn,ak,an,expected in ((0,200,40,200,'worked'),(20,20,16,20,'not')):  # Frozen §13.7: after Wilson wholly below before rate.
            rows=[]
            for phase,k,n in ((0,bk,bn),(1,ak,an)):
                date=dt.date(2026,8,28) if phase==0 else dt.date(2026,9,3)
                for index in range(n):
                    row={'id':str(932000000+phase*1000+index),'source':'outbound','applied_at':analytics_stamp(date)}
                    if index<k:row['replied_at']=analytics_stamp(date+dt.timedelta(days=1))
                    rows.append(row)
            analytics.atomic_lines('goals.jsonl',[{'week':'2026-W36','goals':[commitment('reply_rate')]}])
            review=analytics.goal_reviews(rows,today,now=now)[0]
            assert review['effect']==expected,(bk,bn,ak,an,review)
            if bk==20:assert review['effect']!='worked'
    with fixture('audit-partial-execution') as folder:
        setup(folder)
        rows=[{'id':str(933000000+index),'title':'Automate client onboarding in Airtable'} for index in range(27)]
        seed(rows)
        analytics.add_goals({'week':'2026-W36','goals':[commitment('reply_rate')]})
        for done,eligible,state in ((22,27,'partial'),(0,27,'undone'),(0,0,'no opportunity')):
            value=analytics.compute(today,now=now)
            review=value['goals_review'][0]
            review['evidence_lead_ids']=[row['id'] for row in rows[:eligible]]
            review['done_lead_ids']=[row['id'] for row in rows[:done]]
            prepared=analytics.prepare_snapshot(value,today,now=now)
            execution=prepared['kpis']['goal_done']
            assert (execution['k'],execution['n'])==(done,eligible)
            assert prepared['goals_review'][0]['execution_state']==state
            public=prepared['community_card']['goals'][0]
            assert (public['k'],public['n'],public['state'])==(done,eligible,state)
            if not eligible:assert execution['state']=='undecided'
    with fixture('audit-badges-forecast') as folder:
        setup(folder)
        rows=[]
        for index in range(10):
            date=today-dt.timedelta(days=2)
            rows.append({'id':str(934000000+index),'source':'outbound','call_held_at':analytics_stamp(date,10),
                         'call_ended_at':analytics_stamp(date,11),'proposal_sent_at':analytics_stamp(date,11,5) if index<9 else analytics_stamp(date,12),
                         'proposal_review':{'state':'pass','reason':'Reviewed relevant scope and next step'}})
        snapshot=analytics.compute(today,jobs=rows,now=now)
        snapshot['kpis']['call_review']['state']='pass'  # Unit input: validated review; source gating has a separate negative case.
        snapshot['reviews']['call']['rubric']=[{'lead_id':rows[0]['id'],'reviewable':True,
          'points':[{'point':point,'state':'not needed' if point==6 else 'met','reason':'No separate objection occurred' if point==6 else ''} for point in range(1,10)]}]
        badges=analytics.badge_results(snapshot,rows,[],today)
        assert any(badge['badge']=='Quick Draw' and badge['tier']=='Bronze' for badge in badges) and not any(badge['badge']=='Quick Draw' and badge['tier']=='Silver' for badge in badges)
        assert any(badge['badge']=='True North' and badge['tier']=='Bronze' for badge in badges) and not any(badge['badge']=='True North' and badge['tier']=='Silver' for badge in badges)
        poor={'id':'934000020','source':'outbound','applied_at':analytics_stamp(today-dt.timedelta(days=1)),
              'speed_to_lead_s':60,'job_fit':{'state':'fail','reason':'Wrong lane'}}
        snapshot=analytics.compute(today,jobs=[poor],now=now)
        assert not any(badge['badge']=='Swift Sail' for badge in snapshot['badges'])
        past=[]
        for index in range(100):
            date=today-dt.timedelta(days=35)
            row={'id':str(934100000+index),'source':'outbound','applied_at':analytics_stamp(date),'status':'won' if index<20 else 'lost'}
            if index<20:row.update(won_at=analytics_stamp(date+dt.timedelta(days=2)),won_value={'type':'fixed','amount':1000,'currency':'USD','start_date':(date+dt.timedelta(days=2)).isoformat()})
            past.append(row)
        opens=[{'id':str(934200000+index),'source':'outbound','status':'applied','price_estimate':9999} for index in range(10)]
        forecast=analytics.explore_fields(past+opens,today,[])['forecast']['by_stage'][0]
        assert forecast['own_rate']==.2 and forecast['average_won_value']==1000 and forecast['expected']==2000
        tiny=analytics.explore_fields(past[:1]+opens,today,[])['forecast']['by_stage'][0]
        assert tiny['own_rate'] is None and tiny['expected'] is None
    with fixture('audit-record-race') as folder:
        setup(folder)
        goal=commitment('weekly_volume','2026-10-14')
        analytics.add_goals({'week':'2026-W42','goals':[goal]})
        value=analytics.compute(today,now=now)
        value['goals_next']=[goal];value['report']='Weekly measured review.'
        value['community_card']['next_focus']=analytics.LABELS['weekly_volume'];value['community_card']['question_id']=analytics.PUBLIC_QUESTIONS[0]
        prepared=analytics.prepare_snapshot(value,today,now=now)
        payload=json.dumps(prepared)
        commands=[sys.executable,str(CODE/'analytics.py'),'record','--file','-']
        workers=[subprocess.Popen(commands,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for _ in range(2)]
        results=[worker.communicate(payload) for worker in workers]
        assert sorted(worker.returncode for worker in workers)==[0,1],results
        ledger=folder/'data/analytics-history.jsonl'
        assert len(ledger.read_text().splitlines())==1
        before=ledger.read_bytes()
        with mock.patch.object(analytics.os,'replace',side_effect=OSError('synthetic interrupted record')):
            try:analytics.record_snapshot(prepared,replace=True)
            except OSError:pass
        assert ledger.read_bytes()==before
        legacy={'week':'2026-W41','generated_at':'2026-10-07T12:00:00+02:00','kpis':{},'north_star':{}}
        analytics.atomic_lines('analytics-history.jsonl',[legacy])
        migrated=analytics.compute(today,now=now)
        assert migrated['north_star']['history'][-2] is None and migrated['verdict_history'][0]['stage'] is None
        assert 'community_card' in migrated and 'call_to_won' in migrated and 'forecast' in migrated
        migrated['goals_next']=[goal]; migrated['report']='Corrected weekly measured review.'
        migrated['community_card']['next_focus']=analytics.LABELS['weekly_volume']
        migrated['community_card']['question_id']=analytics.PUBLIC_QUESTIONS[0]
        corrected=analytics.prepare_snapshot(migrated,today,now=now)
        analytics.record_snapshot(corrected)
        replace_commands=commands + ['--replace']
        workers=[subprocess.Popen(replace_commands,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for _ in range(2)]
        results=[worker.communicate(json.dumps(corrected)) for worker in workers]
        assert all(worker.returncode==0 for worker in workers),results
        complete_history=[json.loads(line) for line in ledger.read_text().splitlines()]
        assert [row['week'] for row in complete_history]==['2026-W41','2026-W42']
        assert complete_history[0]==legacy and complete_history[1]['report']==corrected['report']

def pipeline_progression_and_jobfit_coverage():
    import analytics
    import copy
    today=dt.date(2026,10,14);now='2026-10-14T15:00:00+02:00'
    with fixture('audit-producer-followup') as folder:
        (folder/'data/sync.json').write_text(json.dumps({'synced_at':now}))
        (folder/'data/earnings.jsonl').write_text('');(folder/'data/connects.jsonl').write_text('')
        rows=[{'id':'937000001','source':'outbound','status':'call','call_booked_at':'2026-10-12T10:00:00+02:00','call_scheduled_at':'2026-10-20T10:00:00+02:00'},
              {'id':'937000002','source':'outbound','status':'call','call_held_at':'2026-10-12T10:00:00+02:00','proposal_sent_at':'2026-10-12T11:00:00+02:00'},
              {'id':'937000003','source':'outbound','status':'call'},
              {'id':'937000004','source':'outbound','status':'offer','proposal_sent_at':'2026-10-11T11:00:00+02:00'},
              {'id':'937000005','source':'invite','status':'call','call_held_at':'2026-10-12T10:00:00+02:00'}]
        counts=analytics.pipeline_counts(rows,today)
        call=next(row for row in counts['outbound'] if row['stage']=='call')
        offer=next(row for row in counts['outbound'] if row['stage']=='offer')
        inbound=next(row for row in counts['inbound'] if row['stage']=='call')
        assert (call['count'],call['booked'],call['held'],call['unknown_call'],call['proposals_out'])==(3,1,1,1,1)
        assert call['booked']+call['held']+call['unknown_call']==call['count']
        assert offer['proposals_out']==1 and inbound['held']==1
        assert sum(row['count'] for row in counts['outbound'])==4
        entry=today-dt.timedelta(days=20)
        direct={'id':'937000010','source':'outbound','replied_at':analytics_stamp(entry),
                'offered_at':analytics_stamp(entry+dt.timedelta(days=1))}
        actual={'id':'937000011','source':'outbound','replied_at':analytics_stamp(entry),
                'call_held_at':analytics_stamp(entry+dt.timedelta(days=1))}
        invitation=dict(direct,id='937000012',source='invite',invited_at=analytics_stamp(entry))
        result=analytics.compute(today,jobs=[direct,actual,invitation],now=now)
        row=result['kpis']['reply_to_call']
        assert (row['k'],row['n'])==(2,2)
        assert row['label']=='Call rate'
        assert row['outcome_label']=='Reply → booked call, held call, offer or contract within 14 days'
        assert row['progression']=={'booked_calls':0,'held_calls':1,'offer_or_contract_without_call':1}
        invite=result['kpis']['invite_to_call']
        assert (invite['k'],invite['n'])==(1,1) and invite['progression']['offer_or_contract_without_call']==1
        public=result['community_card']['reply_to_call']
        assert public['outcome_label']==row['outcome_label'] and public['progression']=={'booked_calls':0,'held_calls':0,'offer_or_contract_without_call':0}
        analytics.validate_community_card(result['community_card'],[direct,actual,invitation])
        poisoned=copy.deepcopy(result['community_card']);poisoned['reply_to_call']['outcome_label']='Private client text'
        try:analytics.validate_community_card(poisoned,[])
        except ValueError:pass
        else:raise AssertionError('Public fixed definition was overwritten')
        fitrows=[{'id':str(937001000+index),'source':'outbound','applied_at':'2026-10-12T10:00:00+02:00',
                  **({'job_fit':{'state':'pass','reason':'Member lane'}} if index==0 else {})} for index in range(10)]
        fit=analytics.calculate(fitrows,today,now=now)[0]['job_fit']
        assert (fit['k'],fit['n'],fit['coverage_low'],fit['coverage_high'],fit['known_n'])==(1,10,10,100,1)
        assert fit['state']=='undecided' and fit['value'] is None
        for row in fitrows:row['job_fit']={'state':'pass','reason':'Member lane'}
        assert analytics.calculate(fitrows,today,now=now)[0]['job_fit']['state']=='pass'
        for row in fitrows:row.pop('job_fit')
        assert analytics.calculate(fitrows,today,now=now)[0]['job_fit']['state']=='missing'

def uma_source_rubric_coverage():
    import analytics
    import copy
    today=dt.date(2026,10,14);now='2026-10-14T15:00:00+02:00'
    with fixture('audit-uma-review') as folder:
        (folder/'data/sync.json').write_text(json.dumps({'synced_at':now}))
        (folder/'data/earnings.jsonl').write_text('');(folder/'data/connects.jsonl').write_text('')
        jid='938000001'
        seed([{'id':jid,'title':'Automate client onboarding in Airtable','status':'applied','source':'outbound'}])
        record(jid,{'application_modality':'uma','application_sent_verified':True})
        path=folder/'jobs'/jid
        path.mkdir(exist_ok=True)
        sent=path/'application.sent.md';sent.write_text('SYNTHETIC submitted interview answers and video evidence')
        value=analytics.compute(today,now=now)
        value['reviews']['application'].update(fix='Keep specific evidence in answers',example='I implemented this workflow.',evidence_lead_ids=[jid],
            rubric=[{'lead_id':jid,'reviewable':True,'points':[{'point':point,'state':'met'} for point in range(1,4)]}])
        reviewed=analytics.prepare_snapshot(value,today,now=now)
        assert reviewed['kpis']['application_review']['state']=='pass'
        coverage=[row for row in reviewed['reviews']['application']['coverage'] if row.get('modality')=='uma']
        assert [row['point'] for row in coverage]==[1,2,3]
        assert all(row['n']==row['met']==1 for row in coverage)
        assert all(not row['n'] for row in reviewed['reviews']['application']['coverage'] if row.get('modality')!='uma')
        bad=copy.deepcopy(value)
        bad['reviews']['application']['rubric'][0]['points']=[{'point':point,'state':'met'} for point in range(1,7)]
        try:analytics.prepare_snapshot(bad,today,now=now)
        except ValueError:pass
        else:raise AssertionError('Uma accepted cover-letter rubric')
        sent.unlink()
        missing=analytics.prepare_snapshot(value,today,now=now)
        assert missing['kpis']['application_review']['state']=='missing'
        assert all(not row['n'] for row in missing['reviews']['application']['coverage'])

def complete_call_source_badge_gate():
    import analytics
    today=dt.date(2026,10,14);now='2026-10-14T15:00:00+02:00'
    with fixture('audit-call-badge-evidence') as folder:
        (folder/'data/sync.json').write_text(json.dumps({'synced_at':now}))
        (folder/'data/earnings.jsonl').write_text('');(folder/'data/connects.jsonl').write_text('')
        jid='938100001'
        seed([{'id':jid,'title':'Automate client onboarding in Airtable','source':'outbound','status':'call',
               'call_held_at':'2026-10-12T10:00:00+02:00'}])
        path=folder/'jobs'/jid;path.mkdir(exist_ok=True)
        transcript=path/'call.md'
        text='Language: English\nMember: Alex\nAlex: Which workflow is slow?\nClient: The intake takes time.\nAlex: What outcome matters?\n'
        transcript.write_text('Complete: no\n'+text)
        value=analytics.compute(today,now=now)
        value['reviews']['call'].update(fix='Clarify the outcome once',example='What outcome matters?',evidence_lead_ids=[jid],
            rubric=[{'lead_id':jid,'reviewable':True,'points':[{'point':point,'state':'met'} for point in range(1,10)]}])
        try:analytics.prepare_snapshot(value,today,now=now)
        except ValueError:pass
        else:raise AssertionError('Incomplete transcript accepted as reviewed.')
        unavailable=__import__('copy').deepcopy(value)
        unavailable['reviews']['call']['rubric'][0].update(reviewable=False,points=[])
        incomplete=analytics.prepare_snapshot(unavailable,today,now=now)
        assert incomplete['kpis']['call_review']['state']=='missing'
        assert not any(badge['badge']=='True North' for badge in incomplete['badges'])
        transcript.write_text('Complete: yes\n'+text)
        complete=analytics.prepare_snapshot(value,today,now=now)
        assert complete['kpis']['call_review']['state']=='pass'
        assert any(badge['badge']=='True North' and badge['tier']=='Bronze' for badge in complete['badges']) and not any(badge['badge']=='True North' and badge['tier']=='Silver' for badge in complete['badges'])
        degraded=analytics.prepare_snapshot(dict(value,coverage=[{'source':'recorder','state':'missing','fix':'Recorder source unavailable'}]),today,now=now)
        assert degraded['kpis']['call_review']['state']=='missing'
        assert not any(badge['badge']=='True North' for badge in degraded['badges'])

def analytics_final_numerical():
    """Independent final §13 boundary/interval/cohort checks; no live recording."""
    import analytics
    today = dt.date(2026, 10, 14)
    now = '2026-10-14T15:00:00+02:00'
    with fixture('final-numerical') as folder:
        analytics_sync_marker(folder)
        (folder / 'data/connects.jsonl').write_text('')
        (folder / 'data/earnings.jsonl').write_text('')
        expected_rungs = {'reply_rate': (11, 15, 20), 'reply_to_call': (30, 40, 50),
            'booked_to_held': (70, 80, 90), 'held_to_proposal': (70, 80, 90),
            'proposal_to_won': (20, 25, 30), 'invite_to_call': (30, 40, 50),
            'offer_to_contract': (60, 70, 80)}
        assert analytics.RUNGS == expected_rungs
        rows = [dict(id=str(940000000+i), source='outbound',
                     applied_at=analytics_stamp(today-dt.timedelta(days=35)),
                     replied_at=analytics_stamp(today-dt.timedelta(days=34))) for i in range(100)]
        top = analytics.compute(today, jobs=rows, now=now)['kpis']['reply_rate']
        assert top['target'] == 20 and top['rung_reached'] == 3, top
        assert top['ladder_mode'] == 'maintain', top
        for k, n, target in ((0, 20, 11), (5, 20, 11), (17, 40, 50), (20, 20, 90)):
            lo, hi = analytics_interval(k, n)
            expected = 'pass' if lo >= target else 'fail' if hi < target else 'undecided'
            assert analytics.rate_state(k, n, target) == expected, (k, n, target)
            measured = analytics.rate_metric('reply_rate', [{'id':str(i)} for i in range(n)],
                lambda row: int(row['id']) < k, target)
            exact_lo, exact_hi = analytics_exact_interval(k, n)
            assert abs(measured['exact_low'] - exact_lo) < .01 and abs(measured['exact_high'] - exact_hi) < .01
            assert abs(measured['low'] - lo) < .01 and abs(measured['high'] - hi) < .01
            assert abs(measured['performance_low'] - lo) < .01 and abs(measured['performance_high'] - hi) < .01
        booked = [{'id':'940100001', 'source':'outbound',
                   'call_booked_at':analytics_stamp(today-dt.timedelta(days=50)),
                   'call_scheduled_at':analytics_stamp(today-dt.timedelta(days=3)),
                   'call_held_at':analytics_stamp(today-dt.timedelta(days=3))},
                  {'id':'940100002','source':'outbound',
                   'call_booked_at':analytics_stamp(today-dt.timedelta(days=5)),
                   'call_scheduled_at':analytics_stamp(today+dt.timedelta(days=3))},
                  {'id':'940100003','source':'outbound',
                   'call_booked_at':analytics_stamp(today-dt.timedelta(days=50)),
                   'call_scheduled_at':analytics_stamp(today-dt.timedelta(days=1))}]
        attendance = analytics.calculate(booked, today, now=now)[0]['booked_to_held']
        assert (attendance['k'],attendance['n']) == (1,1), attendance
        assert attendance['evidence'] == ['940100001']
        callrows = []
        for offset, win_day in ((29,28),(29,29),(27,1),(57,1)):
            held = today-dt.timedelta(days=offset)
            callrows.append({'id':str(940200000+len(callrows)), 'source':'outbound',
                             'call_held_at':analytics_stamp(held),
                             'won_at':analytics_stamp(held+dt.timedelta(days=win_day))})
        call = analytics.call_to_won(callrows,today)
        assert (call['k'],call['n'],call['horizon_days']) == (1,2,28), call
        assert analytics.lever_shortfall({'direction':'up','value':80,'target':100}) == .2
        assert analytics.lever_shortfall({'direction':'down','value':6,'target':5}) == .2
        goal={'kpi':'reply_rate','stage':analytics.LABELS['reply_rate'],'change':'Make the next step explicit',
              'start':'2026-09-01','primary':True,'cue':'When applying','action':'Make the next step explicit',
              'fallback':'Ask one question','review_on':'2026-09-08'}
        analytics.atomic_lines('goals.jsonl',[{'week':'2026-W36','goals':[goal]}])
        effectrows=[]
        for entry,replied,count in ((dt.date(2026,8,15),False,40),(dt.date(2026,8,2),True,40),
                                   (dt.date(2026,9,3),True,40),(dt.date(2026,10,9),False,40)):
            for i in range(count):
                row={'id':str(940250000+len(effectrows)),'source':'outbound','applied_at':analytics_stamp(entry)}
                if replied:row['replied_at']=analytics_stamp(entry+dt.timedelta(days=1))
                effectrows.append(row)
        reviewed=analytics.goal_reviews(effectrows,today,now=now)[0]
        assert (reviewed['before_k'],reviewed['before_n'],reviewed['after_k'],reviewed['after_n'],reviewed['effect']) == (0,40,40,40,'worked'),reviewed
        assert reviewed['before_period']=={'start':'2026-08-04','end':'2026-08-31'}
        assert reviewed['after_period']=={'start':'2026-09-01','end':'2026-09-15'}
        assert reviewed['after_entry_period']=={'start':'2026-09-01','end':'2026-09-07'}
        empty = analytics.compute(today,jobs=[],now=now)
        assert empty['kpis']['value_per_100_connects']['state'] == 'not measurable'
        assert empty['kpis']['value_per_100_connects']['value'] is None
        for key in ('first_reply','follow_ups_on_time','proposal_on_time','speed_10min','job_fit'):
            assert empty['kpis'][key]['state'] == 'no opportunities', (key,empty['kpis'][key])
        response = [{'id':str(940300000+i),'first_reply_at':analytics_stamp(today-dt.timedelta(days=1),10,5),
                     'first_reply_s':300} for i in range(10)]
        first = analytics.calculate(response,today,now=now)[0]['first_reply']
        assert (first['n'],first['value'],first['p75'],first['state']) == (10,5,5,'pass')
        assert analytics.calculate(response[:9],today,now=now)[0]['first_reply']['state'] == 'undecided'
        for row in response[-3:]: row['first_reply_s'] = 16*60
        assert analytics.calculate(response,today,now=now)[0]['first_reply']['state'] == 'fail'
        for row in response[-3:]: row['first_reply_s'] = 15*60
        assert analytics.calculate(response,today,now=now)[0]['first_reply']['state'] == 'pass'
        pending = response+[{'id':'940399999','first_client_message_at':analytics_stamp(today-dt.timedelta(days=1),10)}]
        first = analytics.calculate(pending,today,now=now)[0]['first_reply']
        assert first['n'] == 11 and first['open_n'] == 1
        wins = [{'id':str(940400000+i),'source':'outbound','won_at':analytics_stamp(today-dt.timedelta(days=2)),
                 'won_value':{'type':'fixed','amount':amount,'currency':currency,'start_date':(today-dt.timedelta(days=2)).isoformat()}}
                for i,(currency,amount) in enumerate((('EUR',100),('EUR',200),('EUR',300),('USD',9000)))]
        wins.append({'id':'940499999','source':'outbound','won_at':analytics_stamp(today-dt.timedelta(days=1))})
        star = analytics.compute(today,jobs=wins,now=now)['north_star']
        assert star['currency'] == 'EUR' and star['value'] == 600, star
        assert star['value_unknown_n'] == 1 and 'unknown' in star['hourly_note'].casefold(), star
        assert any(row['currency'] == 'USD' and row['value'] == 9000 for row in star['other_totals']), star



def analytics_public_onepager_contract():
    import analytics
    import copy
    import struct
    today=dt.date(2026,10,14);now='2026-10-14T15:00:00+02:00'
    with fixture('final-public-onepager') as folder:
        analytics_sync_marker(folder)
        snapshot=analytics.compute(today,jobs=[],now=now)
        card=copy.deepcopy(snapshot['community_card'])
        card['next_focus']=analytics.LABELS['weekly_volume']
        card['question_id']='weekly_volume-1'
        assert analytics.validate_community_card(card,[])['question_id'] == card['question_id']
        windows=[card[key]['entry_period'] for key in ('reply_rate','reply_to_call','call_to_won')]
        assert windows[0] == windows[1] == windows[2]
        assert (dt.date.fromisoformat(windows[0]['end'])-dt.date.fromisoformat(windows[0]['start'])).days == 27
        start,end=(dt.date.fromisoformat(card['reply_rate']['entry_period'][key]) for key in ('start','end'))
        (folder/'context/me.md').write_text('## Working hours\n09:00-18:00 Mon-Sun\n')
        population=[]
        for index,(entry,minutes) in enumerate(((start,2),(end,8),(start-dt.timedelta(days=1),50),(end+dt.timedelta(days=1),58))):
            population.append({'id':str(942500000+index),'source':'outbound','job_fit':{'state':'pass','reason':'Fits'},
                'applied_at':analytics_stamp(entry,9),'replied_at':analytics_stamp(entry,9,minutes),
                'first_client_message_at':analytics_stamp(entry,9),'first_reply_at':analytics_stamp(entry,9,minutes),'first_reply_s':minutes*60,
                'call_booked_at':analytics_stamp(entry,10),'call_scheduled_at':analytics_stamp(entry,10),
                'call_held_at':analytics_stamp(entry,11),'proposal_sent_at':analytics_stamp(entry,12),'won_at':analytics_stamp(entry,13)})
        boundary=analytics.compute(today,jobs=population,now=now)['community_card']
        for key in ('reply_rate','reply_to_call','call_to_won','booked_to_held','proposal_to_won'):
            assert boundary[key]['entry_period']=={'start':start.isoformat(),'end':end.isoformat()},(key,boundary[key])
            assert (boundary[key]['k'],boundary[key]['n'],boundary[key]['value'])==(2,2,100),(key,boundary[key])
        assert boundary['first_reply_median_min']==5,boundary
        assert boundary['stage_counts']=={'applications':2,'replies':2,'calls_booked':2,'calls_held':2,'proposals':2,'won':2,'pending_proposals':0},boundary
        delayed=[{'id':'942599901','source':'outbound','call_booked_at':analytics_stamp(start-dt.timedelta(days=8)),
                  'call_scheduled_at':analytics_stamp(start,10),'call_held_at':analytics_stamp(start+dt.timedelta(days=1),10)},
                 {'id':'942599902','source':'outbound','call_booked_at':analytics_stamp(end-dt.timedelta(days=8)),
                  'call_scheduled_at':analytics_stamp(end,10),'call_held_at':analytics_stamp(end+dt.timedelta(days=2),10)},
                 {'id':'942599903','source':'outbound','call_booked_at':analytics_stamp(end-dt.timedelta(days=8)),
                  'call_scheduled_at':analytics_stamp(end,10),'call_held_at':analytics_stamp(end+dt.timedelta(days=2),10,1)}]
        public_attendance=analytics.compute(today,jobs=delayed,now=now)['community_card']['booked_to_held']
        assert (public_attendance['k'],public_attendance['n'])==(2,3),public_attendance
        sources=[{'title':'Secret Tender Redtail','details':{'client':{'name':'Private Rowan'}},
                  'description':'Confidential workflow replaces manual invoice reconciliation'}]
        for question in ('What did Private Rowan request?', 'Could Secret Tender Redtail be improved?',
                         'Who uses manual invoice reconciliation?', ' '.join(['word']*15),
                         'Contact me at private@example.test'):
            candidate=copy.deepcopy(card);candidate['question_id']=question
            assert analytics.validate_community_card(candidate,sources)['question_id'] is None,question
        improvement=copy.deepcopy(card)
        improvement['biggest_improvement']={'kpi':'reply_rate','from':10,'to':20}
        assert analytics.validate_community_card(improvement,[])['biggest_improvement']=={'kpi':'reply_rate','from':10,'to':20}
        improvement['biggest_improvement']['reason']='Private Rowan liked the application'
        try:analytics.validate_community_card(improvement,sources)
        except ValueError:pass
        else:raise AssertionError('Improvement free text accepted')
        improvement['biggest_improvement']['reason']=' '.join(['word']*15)
        try:analytics.validate_community_card(improvement,[])
        except ValueError:pass
        else:raise AssertionError('Oversized improvement free text accepted')
        for mutation in ({'client_name':'Private Rowan'},{'report':'Private source'},{'unknown':0}):
            invalid=dict(card,**mutation)
            try: analytics.validate_community_card(invalid,[])
            except ValueError: pass
            else: raise AssertionError('Unknown public root field accepted')
        (folder/'context/me.md').write_text('**Name and location:** Alex Rowan, Berlin\n')
        named=analytics.compute(today,jobs=[],now=now)['community_card']
        assert named['member_name']=='Alex R.' and 'Alex R.' in analytics.public_onepager_html(named)
        forged=copy.deepcopy(named);forged['member_name']='Client Person'
        try:analytics.validate_community_card(forged,[])
        except ValueError:pass
        else:raise AssertionError('Caller-supplied public name accepted')
        badge={'badge':'Swift Sail','tier':'Gold','earned_week':'2026-W42','new':False,'progress_to_next':'All tiers earned'}
        named['top_badges']=[badge]
        assert 'Swift Sail' not in analytics.public_onepager_html(named), 'Public card renders only newly earned tiers.'
        named['new_badge']=dict(badge,tier='Silver',new=True)
        html=analytics.public_onepager_html(named)
        assert html.count('Swift Sail')==1 and '<small>Silver</small>' in html
        invalid=copy.deepcopy(card);invalid['reply_rate']['target']=99
        try:analytics.validate_community_card(invalid,[])
        except ValueError:pass
        else:raise AssertionError('Variable public target accepted')
        invalid=copy.deepcopy(card);invalid['call_to_won']['horizon_days']=21
        try:analytics.validate_community_card(invalid,[])
        except ValueError:pass
        else:raise AssertionError('Superseded public horizon accepted')
        private_canaries=['PRIVATE_FULL_SNAPSHOT_CANARY','CLIENT_QUOTATION_NEVER_PUBLIC','PRIVATE_ROWAN_SENTENCE']
        snapshot.update(report=private_canaries[0],call_cards=[{'quote':private_canaries[1]}],
                        reviews={'call':{'example':private_canaries[2]}})
        snapshot['community_card']=card
        html=analytics.public_onepager_html(analytics.snapshot_public_card(snapshot, sources))
        assert all(value not in html for value in private_canaries)
        snapshot['community_card']['won_value']=987654
        hidden=analytics.public_onepager_html(analytics.snapshot_public_card(snapshot, sources))
        assert '987,654' not in hidden
        (folder/'context/me.md').write_text('## Share money\nyes\n')
        shared=analytics.public_onepager_html(analytics.snapshot_public_card(snapshot, sources))
        assert '987,654' in shared
        assert not (folder/'data/analytics-history.jsonl').exists() and not (folder/'data/badges.jsonl').exists()

def analytics_private_call_cards_contract():
    import analytics
    import copy
    today=dt.date(2026,10,14);now='2026-10-14T15:00:00+02:00'
    with fixture('final-private-call-cards') as folder:
        analytics_sync_marker(folder)
        (folder/'data/earnings.jsonl').write_text('');(folder/'data/connects.jsonl').write_text('')
        jid='943000001'
        seed([{'id':jid,'source':'outbound','status':'call','call_held_at':analytics_stamp(today-dt.timedelta(days=2)),
               'title':'Private call card client title'}])
        path=folder/'jobs'/jid;path.mkdir(exist_ok=True)
        quote='PRIVATE_CLIENT_QUOTATION_CANARY costs three hours weekly.'
        own='What outcome would make this worthwhile?'
        (path/'call.md').write_text('Member: Alex\nComplete: yes\nLanguage: English\nAlex: '+own+'\nClient: '+quote+'\nAlex: Let us agree the next step.\n')
        value=analytics.compute(today,now=now)
        item={'lead_id':jid,'reviewable':True,
              'points':[{'point':point,'state':'not needed' if point==6 else 'met','reason':'No separate objection occurred' if point==6 else '','quote':quote} for point in range(1,10)],
              'moments':[{'quote':quote,'better_wording':'Clarify the measured cost and desired outcome'} for _ in range(3)],
              'fix':'Clarify the outcome once','example':own,'next_step':'Client reviews scope on Friday'}
        value['reviews']['call'].update(fix=item['fix'],example=own,evidence_lead_ids=[jid],rubric=[item])
        prepared=analytics.prepare_snapshot(value,today,now=now)
        assert prepared['kpis']['call_review']['state']=='pass'
        assert len(prepared['call_cards'])==1
        card=prepared['call_cards'][0]
        assert card['lead_id']==jid and [point['point'] for point in card['points']]==list(range(1,10))
        assert all(point['quote']==quote for point in card['points']) and card['points'][5]['state']=='not needed'
        assert len(card['moments'])==3 and all(moment['better_wording'] for moment in card['moments'])
        assert (card['fix'],card['example'],card['next_step'])==(item['fix'],own,item['next_step'])
        assert {'label','date','duration_minutes','talk_share','questions','reviewable'}<=card.keys()
        assert all(point['quote_state']=='supported' for point in card['points'])
        unreviewed=copy.deepcopy(value);unreviewed['reviews']['call']['rubric'][0].update(reviewable=False,points=[],moments=[])
        unavailable=analytics.prepare_snapshot(unreviewed,today,now=now)['call_cards'][0]
        assert unavailable['reviewable'] is False and unavailable['reason'] and unavailable['points']==[]
        legacy=copy.deepcopy(value)
        for point in legacy['reviews']['call']['rubric'][0]['points']:point.pop('quote')
        oldcard=analytics.prepare_snapshot(legacy,today,now=now)['call_cards'][0]
        assert all(point.get('quote') is None and point['quote_state']=='unknown' for point in oldcard['points'])
        assert quote not in json.dumps(prepared['community_card'])
        assert quote not in analytics.public_onepager_html(prepared['community_card'])
        analytics.privacy(prepared)
        invalid=copy.deepcopy(value);invalid['reviews']['call']['rubric'][0]['points'][0]['quote']='Invented unsupported quotation'
        try:analytics.prepare_snapshot(invalid,today,now=now)
        except ValueError:pass
        else:raise AssertionError('Unsupported call quotation accepted')
        invalid=copy.deepcopy(value);invalid['reviews']['call']['rubric'][0]['points'][0]['quote']='Complete: yes'
        try:analytics.prepare_snapshot(invalid,today,now=now)
        except ValueError:pass
        else:raise AssertionError('Transcript metadata accepted as supporting speech')
        invalid=copy.deepcopy(value);invalid['reviews']['call']['rubric'][0]['moments'].append({'quote':quote,'better_wording':own})
        try:analytics.prepare_snapshot(invalid,today,now=now)
        except ValueError:pass
        else:raise AssertionError('More than three call moments accepted')

def explicit_goal_action_execution():
    import analytics
    today=ANALYTICS_TODAY; earlier=analytics_stamp(today-dt.timedelta(days=1))
    with fixture('goal-action-execution'):
        seed([dict(id=jid, source='outbound', replied_at=analytics_stamp(today,0)) for jid in ('944000000','944000001')])
        goal={'kpi':'reply_to_call','change':'Offer two concrete times','start':today.isoformat()}
        identity=analytics.goal_id(goal,'2026-W42');goal['goal_id']=identity
        action={'goal_id':identity,'kpi':'reply_to_call','at':analytics_stamp(today,1),'evidence':'Member confirmed two times offered'}
        run('pipeline.py','note','944000000','analytics goal_action: '+json.dumps(action))
        run('pipeline.py','note','944000000','analytics goal_action: '+json.dumps(action))
        for bad in (dict(action,goal_id='wrong-goal'),dict(action,kpi='reply_rate'),dict(action,at=earlier),dict(action,evidence='')):
            run('pipeline.py','note','944000001','analytics goal_action: '+json.dumps(bad))
        quest=analytics.quest_progress({'week':'2026-W42','goals_next':[goal]},list(records().values()),today)[0]
        assert (quest['goal_id'],quest['done_k'],quest['done_n'],quest['execution_state'])==(identity,1,2,'partial'),quest
        unknown=analytics.quest_progress({'week':'2026-W42','goals_next':[dict(goal,goal_id='unknown-goal')]},list(records().values()),today)[0]
        assert unknown['done_k'] is None and unknown['done_n']==2 and unknown['execution_state']=='unverified' and unknown['note']

def analytics_fix_round():
    import analytics
    for successes, target in ((6, 11), (12, 11)):
        with fixture(f'ladder-{successes}') as folder:
            analytics_sync_marker(folder)
            day = ANALYTICS_TODAY - dt.timedelta(days=14)
            rows = [{'id': str(968000000 + index), 'source': 'outbound', 'status': 'applied',
                     'applied_at': analytics_stamp(day), 'found_at': analytics_stamp(day),
                     'application_facts': {'source': 'outbound', 'posted_age_band': '<10m'}}
                    for index in range(100)]
            for row in rows[:successes]:
                row['replied_at'] = analytics_stamp(day, 10, 3)
            rows.append({'id': '968999999', 'source': 'outbound', 'status': 'applied',
                         'applied_at': analytics_stamp(ANALYTICS_TODAY - dt.timedelta(weeks=10))})
            seed(rows)
            value = analytics.compute(ANALYTICS_TODAY)
            assert value['kpis']['reply_rate']['target'] == target, value['kpis']['reply_rate']
            assert value['kpis']['reply_rate']['baseline_phase'] is False
    with fixture('baseline-four-weeks') as folder:
        analytics_sync_marker(folder)
        start = ANALYTICS_TODAY - dt.timedelta(weeks=3)
        seed([{'id': '967000001', 'source': 'outbound', 'status': 'applied', 'applied_at': analytics_stamp(start)}])
        for week in range(4):
            value = analytics.compute(start + dt.timedelta(weeks=week))
            for key in analytics.FUNNEL:
                assert value['kpis'][key]['baseline_phase'] is True, (week, key, value['kpis'][key])
                assert value['kpis'][key]['state'] not in ('pass', 'fail'), (week, key, value['kpis'][key])
            assert value['verdict']['kpi'] not in analytics.FUNNEL, value['verdict']
            assert value['kpis']['weekly_volume']['target'] == 25
            assert value['kpis']['speed_10min']['target'] == 80
            assert value['kpis']['first_reply']['target'] == 5
            assert value['kpis']['follow_ups_on_time']['target'] == 100
            assert value['kpis']['proposal_on_time']['target'] == 90
    with fixture('feeding-levers'):
        value = analytics.compute(ANALYTICS_TODAY)
        for outcome, levers in {'reply_rate': ('speed_10min',),
                                'reply_to_call': ('first_reply', 'follow_ups_on_time'),
                                'held_to_proposal': ('proposal_on_time',)}.items():
            for lever in levers:
                kpis = json.loads(json.dumps(value['kpis']))
                for key in analytics.FUNNEL:
                    kpis[key].update(state='pass', baseline_phase=False)
                for key in ('speed_10min', 'first_reply', 'follow_ups_on_time', 'proposal_on_time'):
                    kpis[key].update(state='pass')
                kpis[outcome].update(state='fail', k=0, n=100, value=0)
                kpis[lever].update(state='fail')
                verdict = analytics.verdict(kpis)
                assert verdict['kpi'] == lever and verdict['state'] == 'levers', (outcome, lever, verdict)
    with fixture('todos-bars-forecast') as folder:
        analytics_sync_marker(folder)
        (folder / 'context/me.md').write_text('## Bars\nreply_rate: 25\nreply_to_call: 60\nproposal_to_won: 40\nfirst_reply: 2\n')
        seed([{'id': str(966000000 + index), 'source': 'outbound', 'status': 'replied',
               'found_at': analytics_stamp(ANALYTICS_TODAY - dt.timedelta(days=20)),
               'last_activity_at': analytics_stamp(ANALYTICS_TODAY - dt.timedelta(days=1)),
               'next_follow_up': (ANALYTICS_TODAY - dt.timedelta(days=10 - index)).isoformat(),
               'follow_up_plan': {'lane': 'silent'}, 'details': {'price_estimate': 500}}
              for index in range(10)])
        value = analytics.compute(ANALYTICS_TODAY)
        assert len(value['todos']) == 7 and all(row['kind'] == 'follow_up' for row in value['todos']), value['todos']
        assert value['todos'][0]['due'] == (ANALYTICS_TODAY - dt.timedelta(days=10)).isoformat()
        assert value['kpis']['reply_rate']['rungs'][-1] == 25
        assert value['community_card']['won_value'] is None
        assert all(row['own_rate'] is None and row['expected'] is None for row in value['forecast']['by_stage'])
        assert value['forecast']['next_30_days'] is None
        payload = analytics_payload(value)
        payload['findings'] = [{'sentence': 'Due follow-ups need a clear next step',
            'action': 'Complete the oldest due follow-up', 'kpi': 'follow_ups_on_time',
            'observed': 0, 'expected': None, 'n': 10, 'strength': 'emerging', 'status': 'emerging'}]
        payload = analytics.prepare_snapshot(payload, ANALYTICS_TODAY)
        for path, change in (('insight', ' '.join(['word'] * 13)), ('market_line', 'Unverified market source')):
            invalid = json.loads(json.dumps(payload))
            invalid['kpis']['reply_rate'][path] = change
            assert run('analytics.py', 'record', '--file', '-', value=invalid, success=False).returncode != 0
        invalid = json.loads(json.dumps(payload))
        invalid['community_card']['question_id'] = ' '.join(['word'] * 15)
        assert analytics.prepare_snapshot(invalid, ANALYTICS_TODAY)['community_card']['question_id'] is None
        invalid = json.loads(json.dumps(payload))
        invalid['insights_top'][0]['text'] = ' '.join(['word'] * 13)
        assert run('analytics.py', 'record', '--file', '-', value=invalid, success=False).returncode != 0
        for field in ('cohorts', 'daily_applications', 'reply_time_hist', 'speed_curve', 'segments',
                      'forecast', 'call_rubric_weeks', 'badges', 'todos'):
            invalid = json.loads(json.dumps(payload))
            invalid[field] = {'tampered': True}
            assert run('analytics.py', 'record', '--file', '-', value=invalid, success=False).returncode != 0, field
        invalid = json.loads(json.dumps(payload))
        invalid['kpis']['reply_rate']['external_reference'] = {'value': 11, 'population': 'fabricated',
            'definition': 'fabricated', 'source': 'https://unverified.example', 'date': '2026-10-14'}
        invalid['kpis']['reply_rate']['market_line'] = 'Market11 percent unverified source'
        assert run('analytics.py', 'record', '--file', '-', value=invalid, success=False).returncode != 0
        invalid = json.loads(json.dumps(payload))
        invalid['findings'] = [{'sentence': 'Unstructured private claim'}]
        assert run('analytics.py', 'record', '--file', '-', value=invalid, success=False).returncode != 0
        run('analytics.py', 'record', '--file', '-', value=payload)
        stored = json.loads(run('analytics.py', 'last').stdout)
        assert stored['community_card']['next_focus'] == payload['community_card']['next_focus']
        assert stored['community_card']['question_id'] == payload['community_card']['question_id']
        assert stored['insights_top'] == payload['insights_top']
        assert stored['findings'] == payload['findings']
        assert stored['kpis']['reply_rate']['insight'] == payload['kpis']['reply_rate']['insight']

def run_checks(checks):
    import argparse
    import traceback
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--focus', help='Comma-separated check names; omitted runs this file only.')
    args = parser.parse_args()
    selected = args.focus.split(',') if args.focus else [check.__name__ for check in checks]
    available = {check.__name__: check for check in checks}
    assert set(selected) <= available.keys(), ('Unknown check', set(selected)-available.keys())
    failures = []
    for name in selected:
        started = time.monotonic()
        try:
            available[name]()
            print(f'PASS {name} ({time.monotonic()-started:.3f}s)', flush=True)
        except Exception:
            failures.append(name + ':\n' + traceback.format_exc())
            print(f'FAIL {name} ({time.monotonic()-started:.3f}s)', flush=True)
    current = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
               for path in (ROOT/'data').rglob('*') if path.is_file()}
    assert current == REAL_DATA_HASHES, 'Repository data changed'
    assert not failures, '\n\n'.join(failures)


def badge_event_persistence():
    import badges
    with fixture('badge-event-persistence') as folder:
        rows=[dict(id='941000001',source='outbound',won_at=analytics_stamp(ANALYTICS_TODAY))]
        awards=badges.check(jobs=rows,now=analytics_stamp(ANALYTICS_TODAY,15))
        assert {row['badge'] for row in awards} == {'First Doubloon'}
        assert badges.check(jobs=rows,now=analytics_stamp(ANALYTICS_TODAY,15)) == []
        assert badges.read_ledger() == awards
        assert not (folder/'data/jobs.json').exists() and not (folder/'data/analytics-history.jsonl').exists()

CHECKS = (badge_event_persistence,analytics_decisions, analytics_boundaries, analytics_member, analytics_levers_and_imports, analytics_source_and_timezone, outcome_badge_interval, analytics_privacy_and_badge_replace, obligations_finance_and_atomic_goals, goal_effect_execution_forecast_and_record_races, pipeline_progression_and_jobfit_coverage, uma_source_rubric_coverage, complete_call_source_badge_gate, analytics_final_numerical, analytics_public_onepager_contract, analytics_private_call_cards_contract, explicit_goal_action_execution, analytics_fix_round,)

if __name__ == "__main__":
    run_checks(CHECKS)
