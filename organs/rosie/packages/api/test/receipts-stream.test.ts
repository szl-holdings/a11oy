import { describe, it, expect, vi } from 'vitest';
import { buildRig } from './helpers.ts';
import { encodeHeartbeat, encodeReceiptEvent, sseStream } from '../src/lib/sse.ts';
import { createSubstrate } from '../src/lib/receipt-substrate.ts';
import { testSigner } from './helpers.ts';
import type { Receipt } from '../src/types/index.ts';

describe('SSE encoding', () => {
  it('encodes a receipt event with event: receipt and a data line', () => {
    const sub = createSubstrate(testSigner());
    const r = sub.emit({ kind: 'test' }, null, 0);
    const frame = encodeReceiptEvent(r);
    expect(frame).toContain('event: receipt');
    expect(frame).toContain('data: ');
    expect(frame.endsWith('\n\n')).toBe(true);
  });

  it('encodes a heartbeat comment frame', () => {
    const hb = encodeHeartbeat();
    expect(hb.startsWith(':heartbeat')).toBe(true);
    expect(hb.endsWith('\n\n')).toBe(true);
  });
});

describe('GET /v1/receipts/stream', () => {
  it('emits heartbeats on the configured interval', async () => {
    vi.useFakeTimers();
    try {
      const dec = new TextDecoder();
      // Empty source so the stream stays open on heartbeats.
      const never: AsyncIterable<Receipt> = {
        async *[Symbol.asyncIterator]() {
          await new Promise(() => {}); // never resolves
        },
      };
      const stream = sseStream(never, { heartbeatMs: 30_000 });
      const reader = stream.getReader();

      // Advance 30s → one heartbeat.
      await vi.advanceTimersByTimeAsync(30_000);
      const first = await reader.read();
      expect(dec.decode(first.value)).toContain(':heartbeat');

      // Advance another 30s → another heartbeat.
      await vi.advanceTimersByTimeAsync(30_000);
      const second = await reader.read();
      expect(dec.decode(second.value)).toContain(':heartbeat');

      await reader.cancel();
    } finally {
      vi.useRealTimers();
    }
  });

  it('streams existing receipts then a heartbeat, behind operator auth', async () => {
    const { app, token, store, signer } = await buildRig();
    const sub = createSubstrate(signer);
    store.append(sub.emit({ kind: 'ask', app: 'a11oy' }, null, 0));
    const jwt = await token({ groups: ['szl-operators'] });
    const res = await app.request('/v1/receipts/stream?heartbeat_ms=30000', {
      headers: { authorization: `Bearer ${jwt}` },
    });
    expect(res.status).toBe(200);
    expect(res.headers.get('content-type')).toContain('text/event-stream');
    const reader = res.body!.getReader();
    const dec = new TextDecoder();
    const chunk = await reader.read();
    expect(dec.decode(chunk.value)).toContain('event: receipt');
    await reader.cancel();
  });

  it('rejects the stream without operator auth (401)', async () => {
    const { app } = await buildRig();
    const res = await app.request('/v1/receipts/stream');
    expect(res.status).toBe(401);
  });
});
