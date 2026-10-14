# Badges: canonical names and weekly criteria

Frozen calibration, 14 October 2026. Code computes recognition from dated evidence and saved reviews.
Earned tiers are kept. Steady Hand uses the best consecutive application-commitment streak; other badges
accumulate their own qualifying weeks. A missed commitment stays visible;
pauses and weeks without eligible opportunities neither advance nor erase progress. No badge awards on 0 of 0.
At most two distinct badges are awarded in a member's first week.

## Tiers

| Tier | Name | Qualifying weeks (best streak for Steady Hand) |
|---|---|---|
| I | Bronze | 1 |
| II | Silver | 3 |
| III | Gold | 6 |
| IV | Platinum | 13 |
| V | Legend | 26 |

Frame colours: Bronze #A0673A, Silver #9AA3A8, Gold #C49A2C, Platinum #7FA6A9,
Legend #8E1F1F with a gold rim. The same illustration is used for all five tiers.

## Badges

| Badge | Image | short | Weekly criterion (details only) |
|---|---|---|---|
| Harbour Master | harbour | Your applications start more conversations. | Reply rate: full mature outbound application cohort, Wilson lower bound at least 11%, after the baseline is set |
| First Mate | ship | Your conversations move towards a call. | Call rate: full mature reply cohort, including call, offer and contract progression, Wilson lower bound at least 30%, after the baseline is set |
| Treasure Hunter | treasure chest | Your calls turn into won work. | Held call to won: full mature 28-day call cohort, Wilson lower bound at least 20%, after the baseline is set |
| Swift Sail | hourglass | You send fitting applications while jobs are fresh. | At least 80% of qualified applications sent within 10 min; only fit and content checked applications count as timely successes; the full eligible denominator stays |
| Ship's Bell | ship's bell | You answer quickly and helpfully. | Useful first answer: working-hours median at most 5 min and p75 at most 15 min, with passed retained applicable conversation content checks or explicit content pass |
| Lookout | spyglass | You follow up on the agreed day. | All due silent-lane follow-ups completed on their business day; cancelled obligations before due day do not count |
| Steady Hand | anchor | You keep your application commitment. | Best consecutive weekly qualified-application commitment streak; each week's saved target applies, including agreed lower targets; completed misses reset current, preserve best; entirely off/holiday weeks skipped; incomplete week counts only once met; no anchor grace; next-tier progress uses current streak |
| Quick Draw | cannon | You send useful proposals promptly after calls. | At least 90% of fitting held calls receive a passed-content proposal within 30 min of call end; clean disqualification and offer or contract bypasses excluded |
| Message in a Bottle | bottle | You give invitations a useful answer. | All eligible invitations receive a useful passed-content response within 1 working hour |
| True North | compass | You guide calls towards a clear agreement. | A reviewed call meets at least 7/9 of applicable points; informed disqualification counts; every not needed point has a reason |
| Navigator | ship's wheel | You keep all five working habits. | All five habits meet their targets and the timeliness content checks pass, with eligible opportunities for each |
| Lighthouse Keeper | lighthouse | You review your week with evidence. | An evidenced weekly analytics review is completed; missed command runs do not erase qualifying weeks |
| First Doubloon | doubloon | You win new work. | At least one new contract is won in the completed week |
| Back on Course | ship after a storm | You return and pick things up. | Return after at least two missed full weeks; one Bronze tier, retained once earned |

Conversion badges are conversion milestones, not evidence of revenue improvement or member ability.
The complete defined mature cohort includes failures. Optional higher outcome rates do not change the fixed
weekly criterion or make a higher target compulsory. Speed alone never earns an event award. Immediate
First Doubloon and True North Bronze events can recognise their first qualifying week; the weekly writer
retains those awards and accumulates higher tiers. Back on Course keeps its owner's single-tier return rule.

## Display

- Three tabs: This week, Conversations and Achievements. Four equal progress cards include the newest badge with working-days k of n beside it, linking to Achievements.
- Newest means latest award timestamp, or a unique earned week with an explicit week-only basis. Ties without known chronology remain unknown; tier/name never decide recency.
- Achievements shows a large Funnel Score ring, current/best weekly commitment streak and all fourteen route stations using the existing art. Steady Hand reuses anchor images, including the legacy tier filenames.
- Badge faces show name, tier, short and progress; exact criteria open only in details.
- Community card shows the new badge, weekly Funnel Score with its previous value, numeric working_days {k,n} and streak_weeks. Private dates and client evidence stay private.
- Application rhythm shades qualified work against the commitment, capped at completed.
- True North point 7, Why you: proof meets the client's stated concern and distinguishes the member from other applicants.
- True North point 9, Next step on Upwork: who sends the proposal or client offer, fixed with milestones or hourly, by when, with the client's yes. Posted budget or scope counts as covered.

## Snapshot

`badges`: `[{"badge", "tier", "earned_week", "new", "progress_to_next"}]`.
`badge_qualifying`: one computed Boolean per canonical badge, retained with the weekly snapshot.
`badge_progress`: every canonical badge, including locked badges, has
`{current, target, remaining, unit: "weeks"}` computed from history, except Back on Course uses `unit: "returns"` for its single Bronze milestone; all other badges use weeks. Steady Hand's current
progress toward the next tier uses the active current streak; the best streak preserves
earned tiers. Unknown progress is null and displays once.
Historical Steady Anchor ledger/snapshot names read as Steady Hand; old earned tiers remain.
`accountability`: `{working_days: {k,n,dates,applied_dates}, application_streak: {current,best,weeks}}`.
Working dates and commitment weeks use the reported weekly-volume period, falling back to
the activity period, with Working hours minus dated Planned off days/Holidays; unknown weekdays
default to Mon-Fri. Targets come from each saved week, never today's target.
`funnel_score`: weekly, 0 to 100; never cumulative, never ranked.
Private voyage stations also retain `earned_at` from the award ledger, or null. The community `new_badge`
keeps its existing newly-earned-tier semantics; it is labelled New badge, not a claim of latest chronology.

