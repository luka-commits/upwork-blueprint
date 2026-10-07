'use client';
// The contract every cockpit component builds on. components/Cockpit.tsx provides
// it; nothing else talks to the server directly. The cockpit only reads.
import { createContext, useContext } from 'react';

export type Job = any;
export type State = any;

export type CockpitApi = {
  token: string;
  state: State | null;                  // /api/state: generated_at, jobs, sync, tracker, funnel
  load: () => Promise<void>;
  api: (path: string) => Promise<{ ok: boolean; data: any }>;
  toast: (message: string) => void;
  drawerId: string | null;
  openDrawer: (id: string) => void;
  closeDrawer: () => void;
};

export const CockpitContext = createContext<CockpitApi | null>(null);

export function useCockpit(): CockpitApi {
  const ctx = useContext(CockpitContext);
  if (!ctx) throw new Error('useCockpit needs <CockpitProvider>');
  return ctx;
}
