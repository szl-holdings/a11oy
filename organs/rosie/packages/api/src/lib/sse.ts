/**
 * @file packages/api/src/lib/sse.ts
 * @description Server-Sent Events encoder utility for /v1/receipts/stream.
 *
 * Emits `event: receipt` + `data: <json>` frames and a `:heartbeat` comment
 * every 30s to keep the connection alive through UDS authservice + ingress
 * proxies. Pure functions for encoding so they are unit-testable without a
 * socket.
 */

import type { Receipt } from '../types/index.ts';

export const HEARTBEAT_INTERVAL_MS = 30_000;

/** Encode a single receipt as an SSE `event: receipt` frame. */
export function encodeReceiptEvent(receipt: Receipt, id?: string): string {
  const lines: string[] = [];
  if (id) lines.push(`id: ${id}`);
  lines.push('event: receipt');
  lines.push(`data: ${JSON.stringify(receipt)}`);
  lines.push('', ''); // blank line terminates the event
  return lines.join('\n');
}

/** Encode an SSE heartbeat comment frame. */
export function encodeHeartbeat(): string {
  return `:heartbeat ${new Date().toISOString()}\n\n`;
}

/**
 * Build a ReadableStream of SSE frames from an async iterable of receipts plus
 * a periodic heartbeat. Used by the /v1/receipts/stream route.
 */
export function sseStream(
  source: AsyncIterable<Receipt>,
  opts: { heartbeatMs?: number; signal?: AbortSignal } = {}
): ReadableStream<Uint8Array> {
  const enc = new TextEncoder();
  const heartbeatMs = opts.heartbeatMs ?? HEARTBEAT_INTERVAL_MS;
  let timer: ReturnType<typeof setInterval> | undefined;

  return new ReadableStream<Uint8Array>({
    async start(controller) {
      timer = setInterval(() => {
        try {
          controller.enqueue(enc.encode(encodeHeartbeat()));
        } catch {
          /* controller closed */
        }
      }, heartbeatMs);

      try {
        for await (const receipt of source) {
          if (opts.signal?.aborted) break;
          controller.enqueue(enc.encode(encodeReceiptEvent(receipt, receipt.chain?.prev_hash)));
        }
      } catch (e) {
        controller.enqueue(enc.encode(`event: error\ndata: ${JSON.stringify({ message: (e as Error).message })}\n\n`));
      } finally {
        if (timer) clearInterval(timer);
        controller.close();
      }
    },
    cancel() {
      if (timer) clearInterval(timer);
    },
  });
}

/** The SSE response headers. */
export const SSE_HEADERS: Record<string, string> = {
  'Content-Type': 'text/event-stream',
  'Cache-Control': 'no-cache, no-transform',
  Connection: 'keep-alive',
  'X-Accel-Buffering': 'no',
};
