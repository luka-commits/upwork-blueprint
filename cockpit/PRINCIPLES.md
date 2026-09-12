# The cockpit: what it is for and how it is built

Read this before changing anything in `cockpit/`. Every review and every build measures against it.
The product goal lives in [`../VISION.md`](../VISION.md); this file applies it to the interface.

## The vision

One place where a freelancer runs their Upwork business from first search to finished client: find, pitch, apply, talk, win, deliver. A member opens it and knows in ten seconds what to do next. The buttons start the same commands they could type in Claude Code, and nothing leaves their account without their yes.

## The principles

1. **Next move first.** Every screen, row and panel leads with the one decision it exists for. One primary button per surface; everything else is secondary and quieter.
2. **Three depths, never more.** A row shows enough to choose. The side panel shows enough to act. The full page shows everything. Within a panel, detail sits in collapsible sections with a one-line summary.
3. **Quiet chrome.** Indigo only for action and selection. Red means due or overdue, amber means soon or stale, green means done. No decorative boxes, thin lines, small labels. The Sqanit master list is the reference for look and list mechanics.
4. **Same thing, same place, same word.** The stage select, due chip, score badge, task list and file rows look and behave the same wherever they appear. The stages are always Not applied, Applied, In conversation, Offer, Won, Lost, Skipped.
5. **Every click answers.** A change shows a short confirmation and the list updates. A run is visible from start to finish in the runs dock, with what it made. A button that cannot work is hidden, not left there to fail.
6. **Nothing leaves without a yes.** The cockpit never sends. Where sending happens, it says so in one line.
7. **Plain words.** No IDs, no jargon, no raw data. Dates in words, numbers with their unit.
8. **Honest empty states.** An empty place says why it is empty and gives the one next step.
9. **Works everywhere.** Every action by keyboard, every screen at phone width.
10. **Leads and clients are different jobs.** A lead screen is about winning (pitch, application, follow-up). A client screen is about delivering (tasks, check-ins, files, conversation).
