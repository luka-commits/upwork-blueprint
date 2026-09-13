# Pocket CEO audit contract

The report answers three questions in this order:

1. **Get found:** a 25-point Local Maps grid for one verified generic service
   search, plus the businesses that lead that grid.
2. **Build trust:** the exact public Google Business Profile, including reviews,
   owner replies, categories, services, updates, photos, hours and booking data
   when available.
3. **Win enquiries:** the rendered website, its applicable enquiry elements,
   reachable pages and the official mobile Lighthouse categories.

The first view contains the business name, one overall conclusion, one overall
score and up to four evidenced quick fixes. The three audit sections start
closed and open in place. Each closed section shows its score, evidence source
and one business consequence. Supporting method and source limits sit in one
disclosure at the end.

Use the warm paper, ink and amber Pocket CEO report palette. Cards contain
measured objects, not paragraphs. Keep headings short and owner-facing. The
report ends with `Reply here on Upwork` and has no outbound link.

Scoring is reconstructible:

- Get found: checked grid points in the first three results divided by all
  checked points.
- Build trust: good profile checks count 1, warnings 0.5 and failed checks 0.
- Win enquiries: applicable website elements found divided by applicable
  elements checked.
- Overall: the arithmetic mean of only the sections that were measured.

A missing input has no score. A completed check that finds nothing is zero.
The local report includes the pull date and states that rankings are a snapshot,
traffic estimates are not first-party analytics, and the website check covers
what a visitor can see rather than what happens after an enquiry.

Thresholds and their limits live in `measurement-benchmarks.md`. Report copy
must label them as Pocket CEO operating heuristics, never Google requirements
or causal proof.

## Source snapshot

The research programs in `code/` and `scripts/` are a self-contained snapshot
of Pocket CEO's measured engine from 13 September 2026. They were copied from
`method/blueprint/code` and the `instantly-proposal-response-v2` managed-agent
bundle. This repository owns its snapshot so another freelancer never needs
the original operator's filesystem or Pocket CEO's database.
