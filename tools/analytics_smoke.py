#!/usr/bin/env python3
"""One hydrated browser smoke on a disposable local Next copy and shared source fixture."""
import json
import os
import pathlib
import re
import shutil
import signal
import socket
import subprocess
import tempfile
import time
import urllib.request
from analytics_fixture import ROOT, ANALYTICS_TODAY, fixture, analytics_sync_marker, analytics_payload
from analytics_audit_regressions import review_fixture_jobs
import analytics

FORBIDDEN_TERMS = ('not supplied', 'undecided', 'eligible', "Writer's", 'cohort', 'SYNTHETIC',
    'saved review', 'Execution and effect apart', 'stage starts', 'Possible range',
    'Too few finished cases to decide against the next rung', 'rung')
PATTERNS = (r'\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b',
    r'(?<![\w.])[-+]?\d+\.\d{3,}(?:[eE][-+]?\d+)?(?![\w.])', r'(?<![\w.])\d+\.\d+\s*%')

def browser_smoke():
    from playwright.sync_api import sync_playwright
    failures, observations, console, pageerrors = [], [], [], []
    def check(condition, message):
        if not condition and message not in failures: failures.append(message)
    with fixture('browser-smoke') as folder:
        analytics_sync_marker(folder)
        jobs = review_fixture_jobs(folder)
        snapshot = analytics_payload(analytics.compute(ANALYTICS_TODAY, jobs=[{k:v for k,v in job.items() if not k.endswith('_review')} for i,job in enumerate(jobs)]))
        projection = dict(snapshot, reviews={})
        projection['call_cards'] = analytics.call_cards(projection,jobs)
        snapshot['conversations'] = analytics.conversations_fields(projection,jobs)
        state = {'jobs': [dict(job, status=('applied','won','skipped','replied')[i], artifacts=[]) for i,job in enumerate(jobs)],
                 'analytics': {'latest': snapshot, 'history': []}}
        selected = [str(jobs[0]['id']),str(jobs[1]['id'])]
        snapshot['presentation']['scorecard'][0]['evidence']=selected
        snapshot['presentation']['scorecard'][0]['next_action']={'lead_filter':{'lead_ids':selected}}
        website = folder/'website'
        shutil.copytree(ROOT/'website', website, ignore=shutil.ignore_patterns('node_modules','.next','.git','tsconfig.tsbuildinfo'))
        (website/'node_modules').symlink_to(ROOT/'website/node_modules', target_is_directory=True)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0)); port = sock.getsockname()[1]
        origin = f'http://127.0.0.1:{port}'
        logpath = folder/'next.log'
        with logpath.open('w') as log:
            server = subprocess.Popen(['node','node_modules/next/dist/bin/next','dev','-H','127.0.0.1','-p',str(port)],
                cwd=website, env=dict(os.environ, NEXT_TELEMETRY_DISABLED='1', BLUEPRINT_ROOT=str(folder)),
                stdout=log, stderr=log, start_new_session=True)
            try:
                deadline = time.monotonic()+120
                while True:
                    assert server.poll() is None, logpath.read_text()[-3000:]
                    try:
                        urllib.request.urlopen(origin+'/analytics', timeout=2).close(); break
                    except Exception:
                        assert time.monotonic()<deadline, logpath.read_text()[-3000:]
                        time.sleep(.3)
                with sync_playwright() as pw:
                    browser = pw.chromium.launch()
                    context = browser.new_context(viewport={'width':1280,'height':900}, permissions=['clipboard-read','clipboard-write'])
                    page = context.new_page()
                    page.on('console', lambda message: console.append(message.text) if message.type in ('error','warning') else None)
                    page.on('pageerror', lambda error: pageerrors.append(str(error)))
                    def route(request):
                        url = request.request.url
                        if not url.startswith(origin+'/'): request.abort(); return
                        if '/api/state' in url: request.fulfill(json=state); return
                        if '/api/' in url:
                            check(request.request.method=='GET', 'Unexpected mutating API request: '+url)
                            request.fulfill(json={}); return
                        request.continue_()
                    page.route('**/*', route)
                    def guard(label):
                        opened = page.locator('[role="dialog"]:visible, [aria-modal="true"]:visible, .drawer.open:visible, .an-drawer:visible, .selection-drawer:visible').count()
                        check(opened==0, label+': drawer/dialog/aria-modal opened')
                    def scan(label):
                        text = page.locator('body').inner_text()
                        for term in FORBIDDEN_TERMS:
                            check(term.casefold() not in text.casefold(), label+': forbidden '+term)
                        for pattern in PATTERNS:
                            matches = sorted(set(re.findall(pattern,text,re.I)))
                            check(not matches, label+': raw values '+repr(matches))
                        guard(label)
                        if page.viewport_size['width']==390:
                            sizes = page.evaluate('({width:innerWidth, scroll:document.documentElement.scrollWidth})')
                            check(sizes['scroll']<=sizes['width'], label+': horizontal overflow '+repr(sizes))
                    def tab(index):
                        page.goto(origin+'/analytics'); page.get_by_role('tab').nth(index).click()
                        page.locator(f'#analytics-panel-{index}').wait_for(state='visible')
                    def open_details(label):
                        # Click real summary controls, including nested disclosures revealed by parents.
                        for _ in range(page.locator('.an-shell details').count()+1):
                            closed = page.locator('.an-shell details:not([open]) > summary:visible')
                            if not closed.count(): break
                            closed.first.click();scan(label+' disclosure')
                        check(not page.locator('.an-shell details:not([open]) > summary:visible').count(),label+': unopened details')
                        controls = page.locator('.an-shell button[aria-controls^="scorecard-"]:visible')
                        for index in range(controls.count()):
                            control = controls.nth(index)
                            if control.get_attribute('aria-expanded')!='true': control.click()
                            check(control.get_attribute('aria-expanded')=='true',label+': scorecard detail stayed closed')
                            scan(label+' '+str(control.get_attribute('aria-controls')))
                        for _ in range(page.locator('.an-shell details').count()+1):
                            closed = page.locator('.an-shell details:not([open]) > summary:visible')
                            if not closed.count(): break
                            closed.first.click();scan(label+' nested disclosure')
                        scan(label)
                        observations.append({'surface':label,'scorecard_details':controls.count(),
                            'open_details':page.locator('.an-shell details[open]:visible').count()})
                    for width in (1280,390):
                        page.set_viewport_size({'width':width,'height':900})
                        for index in range(3):
                            tab(index); label=f'tab{index}/{width}'
                            if index==1:
                                sections=page.locator('.an-review-section')
                                check(sections.count()==2,label+': chat and call sections missing')
                                check(page.locator('.an-review-section a[href*="upwork.com/jobs"], .an-review-section [data-lead-id]').count()==0,label+': lead links in conversations')
                                for section in sections.all():
                                    check(section.locator('.an-criteria').count()==1,label+': criteria missing')
                                    check(section.locator('.an-criterion-bar').count()>0,label+': criteria chart missing')
                            open_details(label)
                    # Exercise every reachable analytics button variant and local state transitions.
                    page.set_viewport_size({'width':390,'height':900})
                    tab(0);open_details('filtered navigation')
                    source_row=snapshot['presentation']['scorecard'][0]
                    nav=page.locator('[id='+json.dumps('scorecard-'+source_row['key'])+'] .sc-open-leads')
                    nav.scroll_into_view_if_needed();return_scroll=page.evaluate('scrollY')
                    nav.click();page.wait_for_url(origin+'/?**')
                    from urllib.parse import urlparse,parse_qs
                    check(json.loads(parse_qs(urlparse(page.url).query)['analytics_leads'][0])==selected,'selected navigation URL IDs')
                    page.locator('[data-analytics-leads]').wait_for()
                    actual=page.locator('[data-lead-id]').evaluate_all('(xs)=>xs.map(x=>x.dataset.leadId)')
                    check(sorted(actual)==sorted(selected),'selected navigation rendered IDs across statuses')
                    page.go_back();page.wait_for_url(origin+'/analytics');page.locator('#analytics-panel-0').wait_for(state='visible')
                    try:page.wait_for_function('(y)=>Math.abs(scrollY-y)<3',arg=return_scroll,timeout=3000)
                    except Exception:check(False,'selected navigation Back scroll restoration')
                    guard('selected navigation Back')
                    visited=set()
                    for index in range(3):
                        tab(index)
                        for select in page.locator('.an-shell select:visible').all():
                            for value in select.locator('option').evaluate_all('(xs)=>xs.map(x=>x.value)'):
                                select.select_option(value); guard('select '+value)
                        open_details(f'interaction/tab{index}')
                        for _ in range(180):
                            if not page.locator('.an-shell').count():break
                            candidates=page.locator('.an-shell button:visible:not([disabled]):not([role="tab"]):not([aria-controls^="scorecard-"])')
                            target=None
                            for button in candidates.all():
                                signature=button.evaluate('(b)=>[b.closest("tr[id],section[id],details[id]")?.id,b.closest("article")?.querySelector("summary strong")?.textContent,b.className,b.textContent,b.getAttribute("aria-pressed"),b.getAttribute("aria-label"),b.getAttribute("aria-controls")].join("|")')
                                if (index,signature) not in visited:
                                    target=button;visited.add((index,signature));break
                            if target is None: break
                            scope_id=target.evaluate('(b)=>b.closest("tr[id],section[id],details[id]")?.id')
                            scope=page.locator('[id='+json.dumps(scope_id)+']') if scope_id else page.locator('.an-shell')
                            title=target.evaluate('(b)=>b.closest("article")?.querySelector("summary strong")?.textContent')
                            if title:scope=scope.locator('article').filter(has=page.locator('summary strong',has_text=title))
                            target=scope.get_by_role('button',name=target.get_attribute('aria-label') or target.inner_text(),exact=True).first
                            target.scroll_into_view_if_needed(timeout=5000)
                            before_scroll=page.evaluate('scrollY')
                            assert target.is_visible() and target.is_enabled()
                            target.evaluate('(b)=>b.click()');page.wait_for_timeout(150);guard('button '+signature)
                            if not page.url.startswith(origin+'/analytics'):
                                from urllib.parse import urlparse,parse_qs
                                expected=json.loads(parse_qs(urlparse(page.url).query)['analytics_leads'][0])
                                page.locator('[data-analytics-leads]').wait_for()
                                actual=page.locator('[data-lead-id]').evaluate_all('(xs)=>xs.map(x=>x.dataset.leadId)')
                                check(sorted(actual)==sorted(expected),'filtered lead IDs '+repr((expected,actual)))
                                page.go_back();page.locator(f'#analytics-panel-{index}').wait_for(state='visible')
                                try:page.wait_for_function('(y)=>Math.abs(scrollY-y)<3',arg=before_scroll,timeout=3000)
                                except Exception:check(False,'Back scroll not restored '+repr((before_scroll,page.evaluate('scrollY'))))
                                guard('Back restoration')
                            elif page.locator(f'#analytics-panel-{index}').get_attribute('hidden') is not None:
                                page.get_by_role('tab').nth(index).click()
                            if target.count() and target.evaluate('(b)=>!!b.closest(".an-criteria-heading")'):scan('criteria table/chart '+signature)
                        else: check(False,f'tab{index}: interaction traversal exhausted')
                        open_details(f'final interaction/tab{index}')
                    check(not console,'console warning/error: '+repr(console))
                    check(not pageerrors,'pageerror: '+repr(pageerrors))
                    print(json.dumps({'observations':observations[:6], 'button_variants_exercised':len(visited),'filtered_fixture_statuses':{job['id']:job['status'] for job in state['jobs'] if str(job['id']) in selected},
                        'console':console,'pageerrors':pageerrors,'failures':failures},indent=2))
                    browser.close()
            finally:
                os.killpg(server.pid,signal.SIGTERM) if server.poll() is None else None
                try: server.wait(timeout=10)
                except subprocess.TimeoutExpired: os.killpg(server.pid,signal.SIGKILL);server.wait()
                print('Owned temporary Next process stopped:',server.pid,server.returncode,flush=True)
                print('Smoke findings:',json.dumps(failures),flush=True)
        assert not failures, '\n'.join(failures)

if __name__=='__main__':
    browser_smoke()
