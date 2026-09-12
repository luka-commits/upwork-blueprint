'use client';

import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';
import { useCockpit, type Run, type RunLine } from '@/lib/context';
import { parseRunResult } from '@/lib/run-result.mjs';
import RunResult from './RunResult';
import './commands.css';

type Command = {
  name: string;
  description: string;
  hint: string;
  button: boolean;
  needsJob: boolean;
};

type HistoryRun = {
  id: string;
  command: string;
  job: string | null;
  started: number;
  ended: number | null;
  done: boolean;
  error: boolean;
  stopped: boolean;
  result: string;
  log: Array<{ kind: 'text' | 'tool' | 'error'; text: string }>;
};

type DisplayRun = {
  id: string;
  command: string;
  job: string | null;
  started: number;
  ended: number | null;
  done: boolean;
  error: boolean;
  stopped: boolean;
  result: string;
  summary: string;
  log: RunLine[];
};

const DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

function startedAt(seconds: number) {
  const date = new Date(seconds * 1000);
  const time = `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`;
  return `${DAYS[date.getDay()]} ${date.getDate()} ${MONTHS[date.getMonth()]}, ${time}`;
}

function duration(started: number, ended: number) {
  const seconds = Math.max(0, Math.round(ended - started));
  if (seconds < 1) return '<1s';
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ${seconds % 60}s`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h ${minutes % 60}m`;
}

function lastMeaningfulLine(text: string) {
  const lines = String(text || '').split('\n')
    .map(line => line.replace(/^[#>*\-\s|]+|[*_`|]+$/g, '').trim())
    .filter(line => /[\p{L}\p{N}]/u.test(line));
  return lines.at(-1) || '';
}

function liveResult(run: Run) {
  const text = run.log.filter(line => line.kind === 'text' || line.kind === 'error' || line.kind === 'done')
    .map(line => line.text.trim()).filter(Boolean).join('\n\n');
  return text || run.status;
}

function stateWord(run: Pick<DisplayRun, 'done' | 'stopped' | 'error'>) {
  if (!run.done) return 'Running';
  return run.stopped ? 'Stopped' : run.error ? 'Failed' : 'Done';
}

function runClass(run: Pick<DisplayRun, 'done' | 'stopped' | 'error'>) {
  if (!run.done) return 'running';
  return run.stopped ? 'stopped' : run.error ? 'failed' : 'finished';
}

function RunRow({ run, jobTitle, now }: { run: DisplayRun; jobTitle?: string; now: number }) {
  const summary = run.summary || (!run.done
    ? 'Waiting for the first update.'
    : run.stopped ? 'Stopped before a result was saved.'
      : run.error ? 'No failure detail was saved.' : 'No result was saved.');
  return (
    <details className={`command-run ${runClass(run)}${run.job && jobTitle ? ' has-job' : ''}`}>
      <summary className="command-run-summary">
        <span className="command-run-state">{stateWord(run)}</span>
        <code className="command-run-name">/{run.command}</code>
        <span className="command-run-result" title={summary}>{summary}</span>
        <span className="command-run-job">
          {run.job && jobTitle ? (
            <Link href={`/job/${encodeURIComponent(run.job)}`} onClick={event => event.stopPropagation()}>{jobTitle}</Link>
          ) : null}
        </span>
        <time className="command-run-start" dateTime={new Date(run.started * 1000).toISOString()}>{startedAt(run.started)}</time>
        <span className="command-run-duration">{duration(run.started, run.ended || now)}</span>
        <span className="command-run-chevron" aria-hidden="true">›</span>
      </summary>
      <div className="command-run-detail">
        <RunResult result={run.result || summary} error={run.error} stopped={run.stopped} />
        <details className="command-run-steps">
          <summary>Steps <span>{run.log.length}</span></summary>
          {run.log.length ? (
            <div className="command-run-log">
              {run.log.map((line, index) => (
                <div className={`command-run-log-line kind-${line.kind}`} key={index}>{line.text}</div>
              ))}
            </div>
          ) : <p className="note-sm">No steps were recorded.</p>}
        </details>
      </div>
    </details>
  );
}

export default function CommandsPage() {
  const { api, runs, runCommand, state, toast } = useCockpit();
  const [commands, setCommands] = useState<Command[]>([]);
  const [history, setHistory] = useState<HistoryRun[]>([]);
  const [commandsState, setCommandsState] = useState<'loading' | 'ready' | 'error'>('loading');
  const [historyState, setHistoryState] = useState<'loading' | 'ready' | 'error'>('loading');
  const [now, setNow] = useState(() => Date.now() / 1000);

  const finishedRunKey = runs.filter(run => run.done).map(run => run.id).sort().join('|');

  useEffect(() => {
    let active = true;
    void api('/api/commands').then(result => {
      if (!active) return;
      if (!result.ok || !Array.isArray(result.data)) {
        setCommandsState('error');
        return;
      }
      setCommands(result.data);
      setCommandsState('ready');
    });
    return () => { active = false; };
  }, [api]);

  // A completion writes its durable history entry just before the context marks it done.
  useEffect(() => {
    let active = true;
    void api('/api/history').then(result => {
      if (!active) return;
      if (!result.ok || !Array.isArray(result.data)) {
        setHistoryState('error');
        return;
      }
      setHistory(result.data);
      setHistoryState('ready');
    });
    return () => { active = false; };
  }, [api, finishedRunKey]);

  const liveRuns = useMemo<DisplayRun[]>(() => [...runs].reverse().filter(run => !run.done).map(run => {
    const result = liveResult(run);
    return {
      id: run.id,
      command: run.command,
      job: run.job,
      started: run.t0 / 1000,
      ended: null,
      done: false,
      error: !!run.error,
      stopped: !!run.stopped,
      result,
      summary: lastMeaningfulLine(run.status || result),
      log: run.log,
    };
  }), [runs]);

  useEffect(() => {
    if (!liveRuns.length) return;
    const timer = window.setInterval(() => setNow(Date.now() / 1000), 1000);
    return () => window.clearInterval(timer);
  }, [liveRuns.length]);

  const historyRuns = useMemo<DisplayRun[]>(() => history.map(run => ({
    ...run,
    summary: run.result ? parseRunResult(run.result).headline : '',
  })), [history]);

  const jobTitles = useMemo(() => new Map<string, string>((state?.jobs || []).map((job: any) => [job.id, job.title])), [state]);
  const firstRunnable = commands.find(command => command.button && !command.needsJob);
  const commandGroups = useMemo(() => [
    {
      title: 'Run here',
      hint: 'Starts now and stays visible in Recent runs.',
      commands: commands.filter(command => command.button && !command.needsJob),
    },
    {
      title: 'Run from a job',
      hint: 'Choose a lead first so the command has the right context.',
      commands: commands.filter(command => command.needsJob),
    },
    {
      title: 'Copy to Claude Code',
      hint: 'These commands continue in a Claude Code conversation.',
      commands: commands.filter(command => !command.button && !command.needsJob),
    },
  ].filter(group => group.commands.length), [commands]);

  const copyCommand = async (name: string) => {
    try {
      await navigator.clipboard.writeText(`/${name}`);
      toast('Copied. Paste it into Claude Code.');
    } catch {
      toast('Copy was blocked. Select the command instead.');
    }
  };

  return (
    <div className="commands-page">
      <div className="commands-intro">
        <h1>Commands</h1>
        <p className="note-sm">Buttons start the same commands you could type. Nothing is sent to a client from here.</p>
      </div>

      <section className="panel commands-panel" aria-label="Commands">
        {commandsState === 'loading' ? <p className="empty">Loading commands.</p> : null}
        {commandsState === 'error' ? <p className="empty">Could not load commands. Reload the page to try again.</p> : null}
        {commandsState === 'ready' && !commands.length ? <p className="empty">No commands are available yet.</p> : null}
        {commandGroups.map(group => (
          <div className="command-group" key={group.title}>
            <div className="command-group-heading">
              <h2>{group.title}</h2>
              <p className="note-sm">{group.hint}</p>
            </div>
            {group.commands.map(command => (
              <div className="command-row" key={command.name}>
                <code className="command-name">/{command.name}</code>
                <span className="command-description" title={command.description}>{command.description || 'No description yet.'}</span>
                <div className="command-action">
                  {command.button && !command.needsJob ? (
                    <button onClick={() => runCommand(command.name)}>Run</button>
                  ) : command.needsJob ? (
                    <Link className="btn" href="/">Choose job</Link>
                  ) : (
                    <button className="link command-copy" onClick={() => void copyCommand(command.name)}>Copy</button>
                  )}
                </div>
              </div>
            ))}
          </div>
        ))}
      </section>

      <h2 className="commands-section-title">Recent runs</h2>
      <section className="panel command-runs-panel" aria-label="Recent runs">
        {liveRuns.map(run => <RunRow run={run} jobTitle={run.job ? jobTitles.get(run.job) : undefined} now={now} key={`live-${run.id}`} />)}
        {historyRuns.map(run => <RunRow run={run} jobTitle={run.job ? jobTitles.get(run.job) : undefined} now={now} key={`history-${run.id}`} />)}
        {!liveRuns.length && historyState === 'loading' ? <p className="empty">Loading recent runs.</p> : null}
        {historyState === 'error' ? <p className="empty">Could not load recent runs. Reload the page to try again.</p> : null}
        {!liveRuns.length && historyState === 'ready' && !historyRuns.length && commandsState === 'ready' ? (
          firstRunnable ? <div className="command-empty">
            <p>No runs yet. Start the first one here.</p>
            <button onClick={() => runCommand(firstRunnable.name)}>Run /{firstRunnable.name}</button>
          </div> : <p className="empty">No runs yet. No command can run from this page.</p>
        ) : null}
      </section>
    </div>
  );
}
