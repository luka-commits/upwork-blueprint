function count(n, singular, plural = `${singular}s`) {
  return `${n} ${n === 1 ? singular : plural}`;
}

export function replyDelay(hours) {
  if (typeof hours !== 'number' || !Number.isFinite(hours) || hours < 0) return null;
  if (hours < 1 / 60) return 'Under a minute';
  if (hours < 1) return `${Math.round(hours * 60)} min`;
  if (hours < 48) return `${Math.round(hours * 10) / 10} hr`;
  return `${Math.round(hours / 24 * 10) / 10} days`;
}

export function analyticsTiles(ins = {}) {
  const applied = ins.applied_total ?? 0;
  const replied = ins.replied_total ?? 0;
  const pairs = ins.reply_time_sample ?? 0;
  const missingPairs = ins.reply_time_missing ?? 0;
  const missingDates = ins.application_dates_unknown ?? 0;
  const volumeComplete = ins.applications_28d_complete === true;
  return [
    {
      label: 'Reached conversation',
      value: ins.reply_rate == null ? null : `${ins.reply_rate}%`,
      empty: 'Small sample',
      hint: `${replied} of ${count(applied, 'applied lead')} reached a conversation or later stage. All saved leads, not a dated comparison.`,
    },
    {
      label: 'Median reply delay',
      value: replyDelay(ins.reply_hours),
      empty: 'Timing not verified',
      hint: pairs
        ? `${count(pairs, 'verified pair')} of submission and first-reply times. ${count(missingPairs, 'conversation')} without verified timing.`
        : 'Needs verified submission times and complete conversation history. Sync detection times are not used.',
    },
    {
      label: 'Applications in 28 days',
      value: volumeComplete ? ins.applications_28d ?? null : null,
      empty: 'Dates missing',
      hint: volumeComplete
        ? 'Saved applications with known submission dates. This is not an account-wide total.'
        : `${count(ins.applications_28d_known ?? 0, 'dated application')} in this period. ${count(missingDates, 'application')} with a missing or invalid date.`,
    },
  ];
}
