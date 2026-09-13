'use client';

import { useEffect, useId, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useCockpit } from '@/lib/context';

export function DisqualifyDialog({ job, returnTo, onClose }: { job: any; returnTo: HTMLElement; onClose: () => void }) {
  const { move } = useCockpit();
  const dialog = useRef<HTMLDialogElement>(null);
  const returnFocus = useRef(returnTo);
  const saving = useRef(false);
  const titleId = useId();
  const reasonId = useId();
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    const element = dialog.current;
    element?.showModal();
    return () => {
      element?.close();
      if (returnFocus.current instanceof HTMLElement && returnFocus.current.isConnected) returnFocus.current.focus();
    };
  }, []);

  return createPortal(<dialog ref={dialog} className="decision-dialog" aria-labelledby={titleId}
    onClick={e => e.stopPropagation()} onKeyDown={e => e.stopPropagation()}
    onCancel={e => { e.preventDefault(); if (!saving.current) onClose(); }}>
    <form onSubmit={async e => {
      e.preventDefault();
      if (saving.current) return;
      saving.current = true;
      setBusy(true);
      setError('');
      try {
        const note = reason.trim() ? `not a fit: ${reason.trim()}` : 'not a fit';
        if (await move(job.id, 'skipped', null, note)) onClose();
        else setError('Could not save. Your reason is still here.');
      } catch {
        setError('Could not save. Your reason is still here.');
      } finally {
        saving.current = false;
        setBusy(false);
      }
    }}>
      <h2 id={titleId}>Not a fit</h2>
      <p className="decision-job">{job.title}</p>
      <label htmlFor={reasonId}>Reason <span className="hint">(optional)</span></label>
      <textarea id={reasonId} autoFocus rows={3} maxLength={500} value={reason} disabled={busy}
        placeholder="Budget, scope, wrong tools…" onChange={e => setReason(e.target.value)} />
      <p className="hint">Helps the next job search.</p>
      {error ? <p role="alert">{error}</p> : null}
      <div className="decision-actions">
        <button type="button" disabled={busy} onClick={onClose}>Cancel</button>
        <button type="submit" className="primary" disabled={busy}>{busy ? 'Saving…' : 'Disqualify'}</button>
      </div>
    </form>
  </dialog>, document.body);
}

export function DisqualifyButton({ job, compact = false }: { job: any; compact?: boolean }) {
  const [opener, setOpener] = useState<HTMLButtonElement | null>(null);
  return <>
    <button className={compact ? 'row-open row-disqualify' : undefined}
      aria-label={`Not a fit: ${job.title}`} title="Not a fit" onClick={e => { e.stopPropagation(); setOpener(e.currentTarget); }}>
      {compact ? <span aria-hidden="true">×</span> : 'Disqualify'}
    </button>
    {opener ? <DisqualifyDialog job={job} returnTo={opener} onClose={() => setOpener(null)} /> : null}
  </>;
}
