'use client';
// The contract every cockpit component builds on. components/Cockpit.tsx provides
// it; nothing else talks to the server directly.
import { createContext, useContext } from 'react';

export type Job = any;
export type State = any;

export type RunLine = { kind: 'text' | 'tool' | 'error' | 'done'; text: string };
export type Made = { label: string; href?: string; open?: string };
export type Run = {
  id: string; command: string; job: string | null;
  t0: number; t1?: number;              // ms since epoch
  status: string;                       // the one line the dock shows
  log: RunLine[];
  result?: string;                      // final report, rendered as a result card
  done: boolean; error?: boolean; stopped?: boolean;
  replay: boolean;                      // attached after the fact: no toast, no deliverables
  made: Made[];                         // what it produced, shown once it is done
  showLog?: boolean; showResult?: boolean;
};

export type CockpitApi = {
  token: string;
  state: State | null;                  // /api/state: jobs, tracker, insights, me, commands, generated_at
  load: () => Promise<void>;
  api: (path: string, body?: object) => Promise<{ ok: boolean; data: any }>;
  post: (path: string, body: object) => Promise<boolean>;   // api, toast its message, then load
  move: (id: string, status: string, follow?: string | null, note?: string | null) => Promise<boolean>;
  toast: (message: string) => void;
  drawerId: string | null;
  openDrawer: (id: string) => void;
  closeDrawer: () => void;
  runCommand: (command: string, job?: string | null) => void;
  sendReply: (job: string, text: string, draft: number, draftSet: string) => void;
  runs: Run[];                          // oldest first
  stopRun: (id: string) => void;
  dismissRun: (id: string) => void;
  toggleRunLog: (id: string) => void;
  toggleRunResult: (id: string) => void;
};

export const CockpitContext = createContext<CockpitApi | null>(null);

export function useCockpit(): CockpitApi {
  const ctx = useContext(CockpitContext);
  if (!ctx) throw new Error('useCockpit needs <CockpitProvider>');
  return ctx;
}
