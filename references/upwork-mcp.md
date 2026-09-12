# What the Upwork connector can and cannot do

The technical picture. **What you are allowed to do sits next door in [upwork-rules.md](upwork-rules.md).** Both questions come up in the same moment ("can I automate this?") but they are different ones: this file says what the tool gives you, that one says what you may do with it. Technically possible is not the same as permitted.

Read by every command that talks to Upwork. **They link here instead of restating it.**

Everything under "Measured" was called against a real account and produced the response described, with its date. The rest is marked untested on purpose: a capability nobody has exercised is a guess, and a guess in this file would be worse than a gap.

## The short version

**Reading gives you a lot. Writing gives you almost nothing.** That pattern is behind nearly every disappointment with this API. Before planning any automation, check whether the writing half exists at all.

## Measured 14 August 2026: reading a profile

- **`get_profile` action `get`, no key:** your own profile. Title, full overview text, skills, languages and proficiency, education, employment history, hourly rate, `profileAggregates` (earnings, job counts, feedback count), location, availability, profile URL.
- **`get_profile` action `get` with a `profile_key`** (starts with `~`): another freelancer's public profile. Used to analyse three top earners. **Measured again 12 September 2026:** the fields sit under `data.talentProfileByProfileKey` instead of `data`, and `profileAggregates` adds the badge (`top_rated`), the earnings bucket ("$100K+") and `totalFeedback`. The key comes from any public profile URL, `upwork.com/freelancers/~0...`, which a web search for the profession returns without touching Upwork.
- **`get_profile` action `list_highlights`:** portfolio projects (id and title) and certificates. Titles only, no contents.
- **`get_profile` actions `transactions` and `connects_balance`:** present, untested.

**Not in the profile response** (the public profile page is the only source): Job Success Score, client review texts, billed hours, portfolio contents, **intro video** (there is no field for one, which says nothing about whether a video exists). The review **count** is there: `profileAggregates.totalFeedback`.

**Measured 12 September 2026:** `get_freelancer_dashboard` and `list_contracts` action `search` carry no Job Success Score either. The dashboard does show Connects spending line by line, which is how a recurring "Paid invitation badge" charge of one Connect every twelve hours became visible.

## Writing a profile: the limit moved

**14 August 2026, measured:** `update_profile` wrote only availability, employment, languages, education and other experience.

**12 September 2026, from Upwork's own tool description (not yet exercised):** `update_profile` now also has `update_title` (70 characters at most), `update_overview` (5,000 characters at most) and `set_skills` (the complete set, 20 at most, names resolved to Upwork's skill list, custom skills rejected). **Still not writable: hourly rate, portfolio, video.** Every write returns a preview first and runs only through `confirm_preview` after an explicit yes. The first real run moves this section to measured.

## Profile boosters, from the tool description 12 September 2026

`boost_profile` action `get_status` reads the Availability Badge (the "Available Now" badge, a recurring weekly Connects charge that shows up as "Paid invitation badge" in the Connects history) and any profile boost ad. `toggle_availability_badge` with `enabled: false` switches the badge off; switching it on or starting ads is only possible on upwork.com.

## Proposals, from the tool description 12 September 2026

- `manage_proposals` action `create` prepares a proposal and returns a **preview, not a submission**: Connects price and balance, competing bid stats (Freelancer Plus), the client's screening questions, unmet preferred qualifications, and a boost block with the real competing boost bids. `confirm_preview` with type `proposal` submits it.
- **Blueprint boundary:** this repository never calls `confirm_preview` for a proposal. It shows the prepared fields and preview in the cockpit, then the member reviews and submits on Upwork. The connector preview does not populate Upwork's browser form, so the cockpit provides copy controls instead of pretending that handoff is automatic.
- **Boost bids live only in that preview,** never in `find_jobs get`. The `boost` block: `available` (false means do not offer it, `reason` says why), `current_top_bids` (the real competing bids, highest first, empty when nobody boosted; `current_top_bids_available` false means unknown, not zero), `recommended_connects` (the smallest bid that secures a top slot), `max_boost_connects` (balance minus the application's own price), `note` (how many paid slots this job has), `recommendation` (`skip` when boosting makes no sense). A boost is a bid, charged only if you land in the paid slots or the client engages before the auction closes. It cannot be edited or withdrawn once submitted.
- **Only one pending preview per action type.** A new `create` replaces the last unconfirmed one.
- **Mandatory before `create`:** `list_freelancer_proposals` action `invitations` (an invited job takes `accept_invitation` instead) and action `list` (an existing proposal makes `create` fail).
- **Before submitting, always ask** about attachments and which portfolio projects or certificates to highlight.
- **Keeping up with Upwork (read only, tool descriptions 12 September 2026):** `list_freelancer_proposals` action `list` takes a `status` (`Accepted` means submitted, `Offered`, `Hired`, `Declined`, `Withdrawn`), 10 per page; action `get_room` gives the thread of one proposal once the client wrote. `get_messages` action `list_rooms` carries `awaiting_reply_from` (you or them) per room, `list_messages` reads newest first. `list_offers` action `list_mine` shows offers as `awaiting_your_acceptance` or `contract_started`; `list_contracts` action `search` with `contract_statuses`. `/sync` uses exactly these.
- **Measured 12 September 2026, the `status` filter on `list` does not filter.** `Accepted`, `Offered`, `Pending` and `Activated` came back empty with "no submitted proposals yet". `Hired`, `Declined` and `Withdrawn` each returned the same mixed list (submitted, hired and declined proposals together, totals 44 to 56). So `/sync` takes each proposal's own `status` field and never trusts the filter it asked for, and an empty list proves nothing.
- **A freelancer cannot message a client first on a proposal.** No room exists until the client writes. A "follow-up" on an application therefore means re-checking it, not messaging.

## Measured 12 September 2026: finding other freelancers

`get_tool_help` for `find_freelancers` returns a full tool description, so the server knows it, even though it does not appear in a freelancer account's default tool list. **Whether a freelancer account may call it is untested.** Its actions:

- **`search`:** filters `query` (the role, short), `skills` (structured, ANDed), `title`, `earnings_min` and `earnings_max`, `job_success_min` (0 to 100), `top_rated`, `top_rated_plus`, `rising_talent`, `total_jobs_min`, `hours_billed_min`, `rate_min` and `rate_max`, location and language filters. Up to 10 results per call, paged with `offset`. Each result carries `profile_key` (for `get_profile`) and `personId` (for invitations, never interchange them).
- **`get_profile`:** skills, employment, education, job aggregates, portfolio when readable, and **`work_history`: each contract's title, dates, status, amount earned and the client's review.** An absent section is not evidence of no contracts; check `work_history_available`.
- **Boosted results are paid ad placements,** not merit. A benchmark skips them.
- Earnings in search results are bucketed for display ("$50K+"), never exact.

## Measured 14 August 2026: jobs

`find_jobs` action `search` returns only a truncated `description_snippet`; the full text requires action `get`.

**Ten results per call, and no way to ask for more in one go.** `limit` is capped at 10. **There is also no date filter**, so "only the last two days" can only be applied to results after they arrive.

More results come from **paging**: repeat the identical filters with `cursor` set to the previous response's `pageInfo.endCursor`, while `pageInfo.hasNextPage` is true. On a dense search, ten newest results cover only a few hours (measured: 8 to 16 hours per page), so a single page once a day misses most of what was posted, and misses it invisibly.

**Filters that exist:** `title` (job title only, words ANDed), `query` (whole posting, semantic), `skills`, `category`, `proposals_max` and `proposals_min`, `client_hires_min` and `max`, `budget_min` and `max` (fixed price), `rate_min` and `rate_max` (hourly), `experience_level`, `workload`, `timezone`, `location`, `previous_clients_only`, `job_type`. A client's `preferred_qualifications` are **not** in search results, only in `get`.

**Measured 12 September 2026, and it changes three things from August:**

- **Every result now carries `url`,** a working job link. The old workaround (a search page with the job title) is gone.
- **`title` filters on the job title only,** words ANDed. Cleaner than `query`, which matches the whole posting semantically. It cannot be combined with `query` or `sort` relevance.
- **`smart_search`** reads Upwork's own recommendation feeds for your profile. `mode` `most_recent` is the only search with a real date filter (`days_posted`, `from_date`, `to_date`); `best_match` ranks by fit and ignores dates. Its results carry `connect_price` and `applied` but a proposals tier instead of a count.
- Search results carry `proposal_count`, `applied`, `featured` and the client's `total_posted_jobs`, but no hire count; the hire record comes only from `get` (`client_record`).

### What `find_jobs get` adds beyond search

- **`connects_cost`:** what applying costs. Nothing else tells you the price of a click.
- **`activityStat.applicationsBidStats`:** average, minimum and maximum rate bid by the competition. A price anchor, not a guess.
- **`activityStat.jobActivity`:** invites sent, hired, invited to interview, offered, unanswered invites. Is this still a real opening?
- **`preferred_qualifications`:** minimum Job Success Score, earnings, hours, English level, rising talent, portfolio, contractor type. Whether you clear the client's own bar at all.
- **`client_work_history`:** the client's recent contracts with feedback both ways. Do they actually hire, and how do they rate?
- **`clientCompanyPublic`:** city, country, timezone.
- **`contractTerms`:** experience level, engagement type, hourly budget, persons to hire.
- **`can_apply`:** whether the application path is even open.

Two cautions. **These come only from `get`, one call per job.** Pulling them for a whole list is exactly the request pattern Upwork flags as scraping, so fetch them when a job is opened or before applying, never in bulk. And the full description regularly carries a screening instruction the fields never show, such as a demand that the application begin with certain words. Read the description before writing a proposal.

## Measured since 14 August 2026, reading only

`get_freelancer_dashboard` action `check` (one call returns contracts, Connects, invitations, unread rooms, offers and Upwork's own match feed), `list_freelancer_proposals` (every proposal with its creation time and job id, the basis for a daily count), `get_messages` (rooms and full threads, **but no author field on any message**, so only `numUnread` reliably says "the client wrote"), `list_contracts`, `get_account`, `set_tool_permission` action `get`.

## Measured 12 September 2026: sending a reply

- **`send_message` action `send` sends immediately.** There is no preview and no second confirmation tool. It needs the account `org_uid`, an existing `room_id` and the exact message text.
- **A room is the gate.** A proposal has no room until the client writes, so a freelancer still cannot message first. The cockpit hides Send when `thread.json` has no `room_id`.
- **The safe cockpit path uses three calls:** `list_accounts` once for `org_uid`, `send_message` once, then `get_messages` action `list_messages` once for the same room. The first real run returned the new freelancer message immediately and its text matched the server-written outbox character for character.
- **Confirmation is mechanical.** `code/threads.py confirm` refuses to update `thread.json` unless the refreshed room contains a freelancer message exactly equal to `jobs/<id>/outbox.json`. The browser then marks that draft sent and confirmed.

## Present but untested

- **`manage_proposals`:** creating and submitting a proposal. Never exercised, so nobody knows yet whether the draft-then-confirm pattern holds here.
- **`find_jobs` action `smart_search`:** new since the first measurement.
- Contracts and milestones beyond listing, attachments, `save_job`, `boost_profile`, `get_agency`, `set_tool_mode` (switching it is a write and needs a yes).

## Keeping this current

**Whoever hits one of these limits in real use writes it down here,** with the actual call and the actual response, not the assumption about it. Each limit in this file was found once by a real run; written down, it never has to be found again.
