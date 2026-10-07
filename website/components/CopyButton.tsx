'use client';

import type { MouseEvent } from 'react';
import { useCockpit } from '@/lib/context';

/** Copies a command for Claude Code, or a text for Upwork. The cockpit never runs it. */
export default function CopyButton({ text, label, compact = false }: { text: string; label: string; compact?: boolean }) {
  const { toast } = useCockpit();
  const copy = (event: MouseEvent) => {
    event.stopPropagation();
    navigator.clipboard.writeText(text).then(
      () => toast(text.startsWith('/') ? 'Copied. Paste it into Claude Code.' : 'Copied.'),
      () => toast('Copy was blocked. Select the text and copy it by hand.'),
    );
  };
  return <button className={`copy-button${compact ? ' compact' : ''}`} onClick={copy} title={`Copy ${text}`}>{label}</button>;
}
