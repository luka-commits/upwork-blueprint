"use client";
// Which package we are talking about, held in one place.
//
// On the call the package is not a footnote, it is the conversation: the plan
// gets longer, the price changes, and the deliverables list grows. Before this,
// the Gantt kept that choice to itself, so switching tier redrew the chart and
// left the price cards behind - two answers to the same question on one screen.
// One provider, every section reads it, and the whole document moves together.
import { createContext, useContext, useState, type ReactNode } from "react";

type Ctx = { pick: string; setPick: (name: string) => void; names: string[] };

const PackageCtx = createContext<Ctx | null>(null);

export function PackageProvider({
  names,
  initial,
  children,
}: {
  names: string[];
  initial?: string;
  children: ReactNode;
}) {
  const [pick, setPick] = useState(initial ?? names[0] ?? "");
  return <PackageCtx.Provider value={{ pick, setPick, names }}>{children}</PackageCtx.Provider>;
}

/** Null outside a provider, which is how the proposal and agreement pages keep
 * their own single-track behaviour without a second code path. */
export function usePackage(): Ctx | null {
  return useContext(PackageCtx);
}
