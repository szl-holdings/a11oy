// SPDX-License-Identifier: Apache-2.0
// Author: Lutar, Stephen P. | ORCID 0009-0001-0110-4173 | SZL Holdings
// Module: vsp-otel  runtime/src/otlp/collector.ts
// Collector-side inverse of the OTLP/HTTP-JSON encoder: parse an
// ExportTraceServiceRequest back into vsp-otel OtelSpan[] for re-verification.
// Operationalizes MASTER_ARCHITECTURE F4 (round-trip half).
//
// HONESTY BOUNDARY: this is a pure decoder. It performs no signature verification
// (that is the DSSE layer, feat/dsse-welford) and no network I/O. It validates
// only the structural shape of the OTLP-JSON payload and reports rejects honestly.

import { type OtelSpan } from "../exporter.js";
import {
  type ExportTraceServiceRequest,
  type OtlpSpan,
  fromOtlpAttributes,
  unixNanoToMs,
} from "./exporter.js";

const STATUS_FROM_CODE: Record<number, OtelSpan["status"]> = {
  0: "UNSET",
  1: "OK",
  2: "ERROR",
};

export interface ParseResult {
  spans: OtelSpan[];
  rejected: number;
  reasons: string[];
}

function decodeSpan(o: OtlpSpan): OtelSpan {
  return {
    traceId: o.traceId,
    spanId: o.spanId,
    name: o.name,
    startTime: unixNanoToMs(o.startTimeUnixNano),
    endTime: unixNanoToMs(o.endTimeUnixNano),
    attributes: fromOtlpAttributes(o.attributes ?? []),
    status: STATUS_FROM_CODE[o.status?.code ?? 0] ?? "UNSET",
  };
}

/** Parse an OTLP-JSON ExportTraceServiceRequest into OtelSpan[]. */
export function parseOtlpJson(req: unknown): ParseResult {
  const spans: OtelSpan[] = [];
  const reasons: string[] = [];
  let rejected = 0;

  const r = req as ExportTraceServiceRequest;
  if (!r || !Array.isArray(r.resourceSpans)) {
    return { spans, rejected: 1, reasons: ["missing resourceSpans[]"] };
  }
  for (const rs of r.resourceSpans) {
    if (!Array.isArray(rs.scopeSpans)) {
      rejected++;
      reasons.push("resourceSpans entry missing scopeSpans[]");
      continue;
    }
    for (const ss of rs.scopeSpans) {
      for (const sp of ss.spans ?? []) {
        if (
          typeof sp.traceId !== "string" ||
          typeof sp.spanId !== "string" ||
          typeof sp.name !== "string"
        ) {
          rejected++;
          reasons.push(`malformed span: ${JSON.stringify(sp).slice(0, 80)}`);
          continue;
        }
        spans.push(decodeSpan(sp));
      }
    }
  }
  return { spans, rejected, reasons };
}
