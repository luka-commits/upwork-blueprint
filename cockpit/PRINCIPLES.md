# The cockpit: what it is for and how it is built

Read this before changing anything in `cockpit/`. Every review and every build measures against it.
The product goal lives in [`../VISION.md`](../VISION.md); this file applies it to the interface.

## The vision

One place where a freelancer runs their Upwork business from first search to finished client: find, pitch, apply, talk, win, deliver. A member opens it and knows in ten seconds what to do next. The buttons start the same commands they could type in Claude Code, and nothing leaves their account without their yes.

## The principles

1. **Next move first.** Every screen, row and panel leads with the one decision it exists for. One primary button per surface; everything else is secondary and quieter.
2. **Three depths, never more.** A row shows enough to choose. The side panel shows enough to act. The full page shows everything. Within a panel, detail sits in collapsible sections with a one-line summary.
3. **Native desktop materials.** Keep the useful Sqanit list mechanics, not a frozen palette. Use the platform font, dark ink and blue actions. Glass belongs to floating navigation, controls and the inspector; reading surfaces stay quiet and opaque. Soft gradients, fine edge highlights and restrained shadows establish layers without movement or decoration behind text. Labeled stages use slate, blue, teal, amber, green and red. Honor reduced motion, reduced transparency and increased contrast.
4. **Same thing, same place, same word.** The stage select, due chip, score badge, task list and file rows look and behave the same wherever they appear. The stages are always Not applied, Applied, In conversation, Offer, Won, Lost, Skipped.
5. **Every click answers.** A change shows a short confirmation and the list updates. A run is visible from start to finish in the runs dock, with what it made. A missing command is hidden; a useful action blocked by an unfinished prerequisite stays visible and disabled with the exact prerequisite beside it.
6. **Nothing leaves without a yes.** The cockpit sends only one thing: the exact reply text the member approved with that click. Proposals remain manual on Upwork, and every sending surface says what will happen before the click.
7. **Plain words.** No IDs, no jargon, no raw data. Dates in words, numbers with their unit.
8. **Honest empty states.** An empty place says why it is empty and gives the one next step.
9. **Desktop first, keyboard complete.** Every action works by keyboard and the desktop workspace is the release target. Smaller screens stay usable, but phone optimization is not a release gate.
10. **The workspace follows the stage.** Not applied opens preparation; Applied opens waiting and reply checks; In conversation and Offer open chat with call/proposal support; Won opens delivery tasks and project files; Lost and Skipped open history. Earlier materials remain accessible without competing with the current job. Changing views must preserve unfinished edits and keep keyboard focus visible.
