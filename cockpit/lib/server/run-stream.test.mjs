import assert from 'node:assert/strict';
import test from 'node:test';

import { followRunStream } from '../run-stream.mjs';

const encoder = new TextEncoder();

function frame(event) {
  return `data: ${JSON.stringify(event)}\n\n`;
}

function response(events) {
  return new Response(new ReadableStream({
    start(controller) {
      events.forEach(event => {
        controller.enqueue(encoder.encode(typeof event === 'string' ? event : frame(event)));
      });
      controller.close();
    },
  }), { status: 200, headers: { 'content-type': 'text/event-stream' } });
}

function unavailable() {
  return new Response('', { status: 503 });
}

function dropsAfter(event) {
  let delivered = false;
  return new Response(new ReadableStream({
    pull(controller) {
      if (!delivered) {
        delivered = true;
        controller.enqueue(encoder.encode(frame(event)));
      } else {
        controller.error(new Error('stream dropped'));
      }
    },
  }), { status: 200, headers: { 'content-type': 'text/event-stream' } });
}

const noWait = async () => true;

test('a transient fetch failure reconnects to the same run', async () => {
  let opens = 0;
  let reconnects = 0;
  const events = [];
  const result = await followRunStream({
    openStream: async () => ++opens === 1 ? unavailable() : response([{ kind: 'done', text: 'Finished.' }]),
    inspectRun: async () => true,
    onEvent: async event => events.push(event),
    onReconnect: () => { reconnects += 1; },
    wait: noWait,
  });
  assert.equal(result, 'done');
  assert.equal(opens, 2);
  assert.equal(reconnects, 1);
  assert.deepEqual(events.map(event => event.kind), ['done']);
});

test('a dropped SSE replay does not duplicate events', async () => {
  let opens = 0;
  const seen = [];
  const events = [{ kind: 'text', text: 'Working.' }, { kind: 'done', text: 'Finished.' }];
  const result = await followRunStream({
    openStream: async () => ++opens === 1 ? dropsAfter(events[0]) : response(events),
    inspectRun: async () => true,
    onEvent: async event => seen.push(event.kind),
    wait: noWait,
  });
  assert.equal(result, 'done');
  assert.deepEqual(seen, ['text', 'done']);
});

test('EOF before done reconnects and resumes after consumed frames', async () => {
  let opens = 0;
  const seen = [];
  const events = [{ kind: 'status', text: 'thinking' }, { kind: 'done', text: 'Finished.' }];
  await followRunStream({
    openStream: async () => ++opens === 1 ? response(events.slice(0, 1)) : response(events),
    inspectRun: async () => true,
    onEvent: async event => seen.push(event.kind),
    wait: noWait,
  });
  assert.equal(opens, 2);
  assert.deepEqual(seen, ['status', 'done']);
});

test('a transient summary error remains unknown and retries', async () => {
  let opens = 0;
  let inspections = 0;
  let lost = 0;
  const result = await followRunStream({
    openStream: async () => ++opens === 1 ? unavailable() : response([{ kind: 'done' }]),
    inspectRun: async () => { inspections += 1; throw new Error('summary unavailable'); },
    onEvent: async () => {},
    onLost: () => { lost += 1; },
    wait: noWait,
  });
  assert.equal(result, 'done');
  assert.equal(inspections, 1);
  assert.equal(lost, 0);
});

test('an unknown server handle ends as tracking lost without claiming completion', async () => {
  let lost = 0;
  let completed = 0;
  const result = await followRunStream({
    openStream: async () => unavailable(),
    inspectRun: async () => false,
    onEvent: async event => { if (event.kind === 'done') completed += 1; },
    onLost: () => { lost += 1; },
    wait: noWait,
  });
  assert.equal(result, 'lost');
  assert.equal(lost, 1);
  assert.equal(completed, 0);
});

test('dismissal aborts retry without losing or completing the run', async () => {
  const controller = new AbortController();
  let opens = 0;
  let lost = 0;
  const result = await followRunStream({
    signal: controller.signal,
    openStream: async () => { opens += 1; return unavailable(); },
    inspectRun: async () => true,
    onEvent: async () => {},
    onLost: () => { lost += 1; },
    wait: async () => { controller.abort(); return false; },
  });
  assert.equal(result, 'aborted');
  assert.equal(opens, 1);
  assert.equal(lost, 0);
});

test('completion is delivered exactly once after malformed and replayed frames', async () => {
  let opens = 0;
  let completed = 0;
  const malformed = 'data: {bad json}\n\n';
  const events = [malformed, { kind: 'text', text: 'Working.' }];
  const result = await followRunStream({
    openStream: async () => ++opens === 1
      ? response(events)
      : response([...events, { kind: 'done', text: 'Finished.' }]),
    inspectRun: async () => true,
    onEvent: async event => { if (event.kind === 'done') completed += 1; },
    wait: noWait,
  });
  assert.equal(result, 'done');
  assert.equal(completed, 1);
});
