# Upwork: the connector, operationally

What a command needs to call Upwork correctly. Background, policy sources and reasoning live in `RESEARCH.md`.

Every claim carries its measurement date. **MEASURED** means called against a real account. **DOCUMENTED BUT UNTESTED** means read from the connector's tool description and never exercised; a command may not rely on it without saying so.

## Hard constraints

1. A human starts every Upwork call. No timer, no background job, no hosted agent.
2. A message goes out only on the member's explicit yes, one message at a time,
   with the exact text in front of them and nothing else in the same question.
   Proposals and offers stay theirs to submit: one spends Connects, the other is
   a contract.
3. Never buy Connects. Say what an application costs and what is left.
4. `python3 code/pipeline.py prune` after every run. Upwork content is cached 24 hours, saved chats 90 days (`KEEP_CHAT_HOURS`); the member's own work stays.
5. No login leaves this machine.
6. Every run ends with `Upwork calls: N`, counted rather than estimated. No fixed
   ceiling on the total: a pipeline with twenty open leads legitimately costs more than one
   with three; `/find-jobs` alone caps itself at 25 search pages and 15 opened jobs. What is never allowed is a loop that keeps asking, which is the
   pattern Upwork's policy names, not the total.
7. Full job details (`find_jobs get`) one job at a time, when a job is opened or before applying, never for a list.
   `include_full_details` on a search is not that: it is a search parameter Upwork documents to
   save the `get` per result, and adds no call.
   Every Upwork call waits for the answer to the one before: never two at once, never spread
   across subagents, never a sweep of terms beyond the run's own searches. MEASURED 8 October
   2026: about 45 title searches in two minutes, partly parallel, from five subagents, got the
   account's search "restricted due to violations of our Terms of Service", far below the
   published 300 a minute. The pattern triggers it, not the count.
8. No contact information before the contract starts, given or asked for (checked 12 September 2026). A link to your work is allowed, so every page this repo publishes for a client carries no email, phone, WhatsApp, booking link, contact form or social profile, and says "reply here on Upwork" instead. Meetings run on Upwork's own video calls. Exception: Enterprise plan on either side.
9. Pipeline state is written only through `python3 code/pipeline.py`.

## Call routes

Use fresh local state first: a cached response under 24 hours old answers the same question without a call. State the planned call budget before calling.

- Job discovery: `find_jobs search` or `smart_search`; page only until the stated time window or enough candidates are covered.
- Full job facts: `find_jobs get`, one opened or shortlisted job, never a list.
- Profile: `get_profile`; `list_highlights` only when portfolio or certificates matter.
- Pipeline state: proposal, offer and contract list calls once per required first page. `get_room` only for pipeline jobs that can have a client reply.
- Messages: `list_rooms` once for waiting state, then `list_messages` only for the rooms being reviewed.

Stop when the requested fact is known; never broaden a search to make an empty result look productive. Every write needs approval for the exact action and content: profile previews stay unconfirmed until the member says yes, proposal previews are never confirmed here at all.

## Profile

**MEASURED 14 August 2026, `get_profile` action `get` without a key** (your own profile): title, full overview text, skills, languages and proficiency, education, employment history, hourly rate, `profileAggregates` (earnings, job counts, feedback count), location, availability, profile URL.

**MEASURED 12 September 2026, `get_profile` action `get` with a `profile_key`** (starts with `~`, from any public profile URL): another freelancer's public profile, with the badge, the earnings bucket and the review count. Response shape in `RESEARCH.md`.

`get_profile` action `list_highlights`: portfolio projects (id and title) and certificates, titles only, no contents. Actions `transactions` and `connects_balance` exist, untested.

**Not in any profile response**, only on the public profile page: Job Success Score, client review texts, billed hours, portfolio contents, intro video (no field exists, which says nothing about whether one exists). The review *count* is there, as `profileAggregates.totalFeedback`.

**MEASURED 12 September 2026:** `get_freelancer_dashboard` and `list_contracts` action `search` carry no Job Success Score either. The dashboard does show Connects spending line by line.

**Writing, MEASURED 14 August 2026:** `update_profile` wrote only availability, employment, languages, education and other experience. **DOCUMENTED BUT UNTESTED, tool description 12 September 2026:** `update_title` (70 characters max), `update_overview` (5,000 characters max), `set_skills` (the complete set, 20 max, names resolved to Upwork's skill list, custom skills rejected). **Not writable: hourly rate, portfolio, video.** Every write returns a preview and runs only through `confirm_preview` after an explicit yes.

## Jobs

**MEASURED 14 August 2026.** `find_jobs search` returns only a truncated `description_snippet`; the full text needs action `get`. **DOCUMENTED BUT UNTESTED, tool description 8 October 2026:** `include_full_details` true adds each result's full description to the same search answer.

- **`limit` is hard at 10** results per call, with no way to ask for more.
- **There is no date filter**, so "only the last two days" can be applied only after results arrive.
- More results come from paging: identical filters with `cursor` set to the previous `pageInfo.endCursor` while `pageInfo.hasNextPage` is true. On a dense search ten newest results cover 8 to 16 hours, so one page a day misses most of what was posted, invisibly.
- Filters that exist: `title` (job title only, words ANDed), `query` (whole posting, semantic), `skills`, `category`, `proposals_max`/`proposals_min`, `client_hires_min`/`max`, `budget_min`/`max` (fixed price), `rate_min`/`rate_max` (hourly), `experience_level`, `workload`, `timezone`, `location`, `previous_clients_only`, `job_type`. `preferred_qualifications` is **not** in search results, only in `get`.

**MEASURED 12 September 2026:** every result carries `url`, a working job link. `title` cannot be combined with `query` or with `sort` relevance. Results carry `proposal_count`, `applied`, `featured` and the client's `total_posted_jobs`, but no hire count; the hire record comes only from `get` (`client_record`).

**Never exercised from this repo:** `smart_search` reads Upwork's recommendation feeds. `/find-jobs` uses `mode` `most_recent` with `from_date` (an RFC3339 time, the start of its window); `days_posted` counts whole days only. Whatever else its description promises is unverified, so a run says what it got back rather than what it expected.

**What `find_jobs get` adds:** `connects_cost` (what applying costs), `activityStat.applicationsBidStats` (average, minimum and maximum competing rate), `activityStat.jobActivity` (invites sent, hired, invited to interview, offered, unanswered invites), `preferred_qualifications` (minimum Job Success Score, earnings, hours, English level, rising talent, portfolio, contractor type), `client_work_history` (recent contracts with feedback both ways), `clientCompanyPublic` (city, country, timezone), `contractTerms` (experience level, engagement type, hourly budget, persons to hire), `can_apply`. The full description regularly carries a screening instruction no field shows, such as a mandatory opening phrase: read it before writing a proposal.

## Proposals, rooms and pipeline

**MEASURED 12 September 2026: the `status` filter on `list_freelancer_proposals` action `list` does not filter.** Read each proposal's own `status` field, never trust the filter, and treat an empty list as proof of nothing. What each value returned is in `RESEARCH.md`.

**No room exists until the client writes**, so an applied proposal gets no draft, no follow-up and no task. `/brief` asks after 14 full days without a reply whether to set it to `lost`.

**MEASURED since 14 August 2026, reading only:** `get_freelancer_dashboard` action `check` (one call returns contracts, Connects, invitations, unread rooms, offers and Upwork's match feed), `list_freelancer_proposals` (records with creation time and job id), `get_messages`, `list_contracts`, `list_accounts` (each `org_uid`; the tool description says to call it first), `get_account`, `set_tool_permission` action `get`. Message authorship is response-shape dependent: a 14 August response had no author field, 12 September responses exposed sender information. Never infer authorship from message order.

**What `/brief` calls, all reading:** page `list_freelancer_proposals` action `list` (10 per page) only to match active leads missing IDs, then `get_room` for missing rooms. Refresh every active stored room with `get_messages` `list_messages`; `list_rooms` carries `awaiting_reply_from`. `list_offers` `list_mine`: awaiting acceptance means offer, contract started means won; declined, withdrawn and expired mean lost. Unknown states are logged. `list_contracts` `search` takes `contract_statuses`.

**Submitting is not ours to do.** `manage_proposals` action `create` builds a preview and `confirm_preview` would submit it; `accept_invitation` exists and nobody here has run it. An application spends Connects and a boost cannot be edited or withdrawn once placed, so both stay the member's own click on Upwork. That is the rule, and the rest of what those tools describe is unverified and therefore not written down here.

## Present but untested

`find_jobs` action `smart_search`, contracts and milestones beyond listing, attachments, `save_job`, `boost_profile`, `get_agency`, `set_tool_mode` (switching it is a write and needs a yes).
