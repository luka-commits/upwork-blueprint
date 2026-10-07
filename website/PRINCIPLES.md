# The cockpit: what it is for and how it is built

Read this before changing anything in `website/`. Every review and every build measures against it.
The product goal lives in [`../VISION.md`](../VISION.md); this file applies it to the interface.

## The vision

The cockpit shows the member's Upwork pipeline and Claude Code does the work. A member opens it and knows in ten seconds whether a job is worth it and which command to run next. It runs no command, sends nothing and writes nothing.

## The principles

1. **Show, never run.** Every next step is a command to copy into Claude Code or a sentence for the member's own hands. No button starts Claude, calls Upwork or spends money.
2. **Read-only.** Stages change through `/brief` or when the member tells Claude Code. Skipping a lead and giving feedback happen in Claude Code too, where `/find-jobs skip <id> <reason>` keeps the reason the next search learns from. Generated HTML is served sandboxed and never gains `allow-same-origin`, and the file route serves a job's own public artifacts only, never the internal receipts (`thread.json`, `replies.json`).
3. **Worth it at a glance.** The list holds the leads still to decide on. Score, flags, client and competition sit in the row; the side panel adds the full details, the pitch page, the application and the reply drafts. There is no full page.
4. **Same thing, same place, same word.** The stages are always Not applied, Applied, In conversation, Call, Offer, Won, Lost, Skipped, and `website/lib/stages.mjs` owns that list. The board carries only the stages where a conversation is alive: In conversation, Call, Offer, Won. The list holds Not applied and Applied. Lost and Skipped are counted in the funnel and shown on neither surface, because nothing about them needs deciding again. The numbers tracked are today's applications, the funnel from application to won, applications per week, and three median timings. A rate shows only from 50 leads behind it and a median from 20; below that the count stands alone.
5. **Native desktop materials.** Use the platform font, dark ink and blue actions. Reading surfaces stay opaque. Use 6px control, 10px panel and 12px floating-surface corners, not pill-shaped buttons. Pointer feedback stays within 120-180ms; keyboard actions are immediate. Honor reduced motion, reduced transparency and increased contrast. Every text colour clears 4.5:1 against every surface it can sit on, including the soft semantic backgrounds and each stop of the primary gradient, so changing a colour token means re-checking that. Backdrop blur stays under 20px and lives on the control layer only, and no rule animates `all`.
6. **One fact once.** No IDs, jargon or repeated status strips. A row shows the job in one sentence; the panel splits it into what they want, key work and must-haves, with the posting folded away. Dates in words, numbers with units.
7. **Honest empty states.** An empty place says why it is empty and gives the one next step.
8. **Desktop first, keyboard complete.** Every row, card and copy button works by keyboard. Smaller screens stay usable, but phone optimization is not a release gate.
