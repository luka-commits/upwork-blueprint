import type { GanttBar, GanttPlan } from "./types";

/** When a row happens, for the package on screen.
 *
 *  Three components draw the same build plan and each used to work the weeks
 *  out for itself: the chart, the board and the detail panel. They disagreed
 *  the moment a row stopped being a plain span - Growth builds the website
 *  after the keyword map, the two trainings are two days rather than five
 *  weeks - so the arithmetic lives here once and all three read it. */
export function barWeeks(
  bar: GanttBar,
  pick: string,
  packages: GanttPlan["packages"],
): { from: number; to: number; spots?: number[] } {
  const inPlan = bar.packages.includes(pick);
  // A row the chosen package does not carry is measured against the package
  // that does, so a Scale-only card never reads "weeks 6 to 6" on Growth.
  const owner = inPlan
    ? packages.find((p) => p.name === pick)?.weeks
    : packages.find((p) => p.name === bar.packages[0])?.weeks;
  const ownerWeeks = owner ?? bar.to;

  if (bar.lastWeeks) {
    return { from: Math.max(1, ownerWeeks - bar.lastWeeks + 1), to: ownerWeeks };
  }

  if (bar.atWeeks) {
    const spots = bar.alsoAtLastWeek ? [...bar.atWeeks, ownerWeeks] : bar.atWeeks;
    return { from: Math.min(...spots), to: Math.max(...spots), spots };
  }

  const scheduleOwner = inPlan ? pick : bar.packages[0];
  const shifted = scheduleOwner ? bar.weeksByPackage?.[scheduleOwner] : undefined;
  return { from: shifted?.[0] ?? bar.from, to: shifted?.[1] ?? bar.to };
}

/** The human label for those weeks: "Week 2", "Weeks 3 to 6", "Weeks 2 and 6". */
export function weeksLabel(
  bar: GanttBar,
  pick: string,
  packages: GanttPlan["packages"],
): string {
  const { from, to, spots } = barWeeks(bar, pick, packages);
  if (spots) return `Weeks ${spots.join(" and ")}`;
  return to > from ? `Weeks ${from} to ${to}` : `Week ${from}`;
}
