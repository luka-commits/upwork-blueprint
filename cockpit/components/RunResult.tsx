'use client';

import { parseRunResult } from '@/lib/run-result.mjs';
import './run-result.css';

function Text({ value }: { value: string }) {
  const lines = String(value || '').split('\n').map(line => line.replace(/^[-*]\s+/, '').trim()).filter(Boolean);
  if (lines.length > 1) return <ul>{lines.map((line, index) => <li key={index}>{line}</li>)}</ul>;
  return <p>{lines[0] || ''}</p>;
}

function Block({ label, value }: { label: string; value: string }) {
  if (!value) return null;
  return <section className="result-block"><h4>{label}</h4><Text value={value} /></section>;
}

export default function RunResult({ result, error = false, stopped = false }: {
  result: string;
  error?: boolean;
  stopped?: boolean;
}) {
  const outcome = parseRunResult(result);
  const verdict = stopped ? 'STOPPED' : error ? 'FAILED' : outcome.verdict || 'DONE';
  const cls = stopped ? 'stopped' : error ? 'failed' : outcome.verdict === 'DRAFT / HELD' || outcome.verdict === 'BLOCKED' ? 'held' : 'complete';
  return <div className={`run-result ${cls}`}>
    <div className="result-lead">
      <span className="result-verdict">{verdict}</span>
      <p>{outcome.headline}</p>
    </div>
    {outcome.findings.length ? <section className="result-findings">
      <h4>Key findings</h4>
      <ul>{outcome.findings.map((finding: string, index: number) => <li key={index}>{finding}</li>)}</ul>
    </section> : null}
    <div className="result-sections">
      <Block label="Created" value={outcome.built} />
      <Block label="Checked" value={outcome.checked} />
      <Block label="Next" value={outcome.next} />
    </div>
    {outcome.stillNeeded && outcome.stillNeeded !== outcome.next ? <Block label="Still needed" value={outcome.stillNeeded} /> : null}
    {outcome.quality || outcome.calls ? <div className="result-meta">
      {outcome.quality ? <span><b>Quality</b> {outcome.quality}</span> : null}
      {outcome.calls ? <span><b>Upwork calls</b> {outcome.calls}</span> : null}
    </div> : null}
  </div>;
}
