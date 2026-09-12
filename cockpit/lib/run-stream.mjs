export const RECONNECTING_RUN = 'Reconnecting…';
export const RUN_TRACKING_LOST = 'Run tracking was lost. Check Commands before starting another run.';

function aborted(error, signal) {
  return signal?.aborted || (error && error.name === 'AbortError');
}

function waitFor(ms, signal) {
  if (signal?.aborted) return Promise.resolve(false);
  return new Promise(resolve => {
    const timer = setTimeout(() => finish(true), ms);
    const onAbort = () => finish(false);
    const finish = value => {
      clearTimeout(timer);
      signal?.removeEventListener('abort', onAbort);
      resolve(value);
    };
    signal?.addEventListener('abort', onAbort, { once: true });
  });
}

async function consumeReplay(body, cursor, onEvent, signal) {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let replayed = 0;
  const cancel = () => reader.cancel().catch(() => {});
  const onAbort = () => { void cancel(); };
  signal?.addEventListener('abort', onAbort, { once: true });
  try {
    while (!signal?.aborted) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value, { stream: !done });
      let boundary = buffer.indexOf('\n\n');
      while (boundary !== -1) {
        const frame = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        const frameIndex = replayed++;
        if (frameIndex >= cursor.frames) {
          const data = frame.startsWith('data: ') ? frame.slice(6) : '';
          if (data) {
            let event;
            try { event = JSON.parse(data); }
            catch { cursor.frames += 1; boundary = buffer.indexOf('\n\n'); continue; }
            await onEvent(event);
            cursor.frames += 1;
            if (event?.kind === 'done') {
              await cancel();
              return true;
            }
          } else {
            cursor.frames += 1;
          }
        }
        boundary = buffer.indexOf('\n\n');
      }
      if (done) return false;
    }
    return false;
  } finally {
    signal?.removeEventListener('abort', onAbort);
    reader.releaseLock();
  }
}

/** Follow a run until its terminal event, replaying safely after a dropped stream.
 * `inspectRun` returns true when the server still knows the handle, false when it
 * does not, and null when the check itself is inconclusive. */
export async function followRunStream({
  openStream,
  inspectRun,
  onEvent,
  onReconnect = () => {},
  onLost = () => {},
  signal,
  delays = [300, 750, 1500, 3000, 5000],
  wait = waitFor,
}) {
  const cursor = { frames: 0 };
  let attempt = 0;
  while (!signal?.aborted) {
    try {
      const response = await openStream(signal);
      if (!response?.ok || !response.body) throw new Error(`run stream unavailable (${response?.status || 'no response'})`);
      if (await consumeReplay(response.body, cursor, onEvent, signal)) return 'done';
    } catch (error) {
      if (aborted(error, signal)) return 'aborted';
    }
    if (signal?.aborted) return 'aborted';
    onReconnect();
    let known = null;
    try {
      known = await inspectRun(signal);
    } catch (error) {
      if (aborted(error, signal)) return 'aborted';
    }
    if (known === false) {
      onLost();
      return 'lost';
    }
    const delay = delays[Math.min(attempt++, delays.length - 1)] ?? 5000;
    if (!await wait(delay, signal)) return 'aborted';
  }
  return 'aborted';
}
