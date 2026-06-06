// SPDX-License-Identifier: Apache-2.0
// Author: Lutar, Stephen P. | ORCID 0009-0001-0110-4173 | SZL Holdings
// Module: vsp-otel  runtime/src/otlp/exporter.ts
// Real OpenTelemetry SpanExporter emitting OTLP/HTTP-JSON (ExportTraceServiceRequest).
// Operationalizes MASTER_ARCHITECTURE F4. Doctrine v11 LOCKED (749/14/163) preserved.
//
// HONESTY BOUNDARY (declared, never faked):
//   * This module produces a spec-shaped OTLP/HTTP-JSON ExportTraceServiceRequest
//     (resourceSpans -> scopeSpans -> spans, nanosecond string timestamps) that any
//     standard OpenTelemetry collector can ingest. The SZL anchor-formula attributes
//     (szl.anchor_formula.id, szl.lean_theorem_ref, szl.lean_commit_sha) are preserved.
//   * Network transport is INJECTABLE. In CI no socket is opened: the default
//     transport captures the request in-process. A real fetch()-based transport is
//     provided but is only used when an endpoint is supplied (env VSP_OTLP_ENDPOINT
//     or constructor arg). This keeps tests hermetic and avoids faking a green network.
//   * The DSSE envelope + Lambda streaming state land in feat/dsse-welford (F3/F5/F13),
//     intentionally kept separable from the wire-format exporter.

import { type OtelSpan } from "../exporter.js";

// ---------------------------------------------------------------------------
// OTLP/HTTP-JSON minimal type surface
// (subset of opentelemetry-proto trace/v1, JSON encoding)
// ---------------------------------------------------------------------------

export interface OtlpKeyValue {
  key: string;
  value:
    | { stringValue: string }
    | { boolValue: boolean }
    | { intValue: string }
    | { doubleValue: number };
}

export interface OtlpSpan {
  traceId: string;
  spanId: string;
  name: string;
  kind: number;
  startTimeUnixNano: string;
  endTimeUnixNano: string;
  attributes: OtlpKeyValue[];
  status: { code: number; message?: string };
}

export interface OtlpScopeSpans {
  scope: { name: string; version: string };
  spans: OtlpSpan[];
}

export interface OtlpResourceSpans {
  resource: { attributes: OtlpKeyValue[] };
  scopeSpans: OtlpScopeSpans[];
}

export interface ExportTraceServiceRequest {
  resourceSpans: OtlpResourceSpans[];
}

// OTLP status_code enum: 0=UNSET, 1=OK, 2=ERROR
const STATUS_CODE: Record<OtelSpan["status"], number> = {
  UNSET: 0,
  OK: 1,
  ERROR: 2,
};

// SZL instrumentation scope identity (stable across the mesh).
const SCOPE = { name: "@szl/vsp-otel", version: "0.1.0" };

// ---------------------------------------------------------------------------
// Attribute encoding (OTel AnyValue JSON form)
// ---------------------------------------------------------------------------

export function toOtlpAttributes(
  attrs: Record<string, string | number | boolean>,
): OtlpKeyValue[] {
  const out: OtlpKeyValue[] = [];
  for (const [key, v] of Object.entries(attrs)) {
    if (typeof v === "string") {
      out.push({ key, value: { stringValue: v } });
    } else if (typeof v === "boolean") {
      out.push({ key, value: { boolValue: v } });
    } else if (Number.isInteger(v)) {
      // OTLP-JSON encodes 64-bit ints as strings.
      out.push({ key, value: { intValue: String(v) } });
    } else {
      out.push({ key, value: { doubleValue: v } });
    }
  }
  return out;
}

export function fromOtlpAttributes(
  kvs: OtlpKeyValue[],
): Record<string, string | number | boolean> {
  const out: Record<string, string | number | boolean> = {};
  for (const kv of kvs) {
    const val = kv.value as Record<string, unknown>;
    if ("stringValue" in val) out[kv.key] = val.stringValue as string;
    else if ("boolValue" in val) out[kv.key] = val.boolValue as boolean;
    else if ("intValue" in val) out[kv.key] = Number(val.intValue as string);
    else if ("doubleValue" in val) out[kv.key] = val.doubleValue as number;
  }
  return out;
}

// vsp-otel's OtelSpan carries startTime/endTime as epoch milliseconds.
// OTLP-JSON requires nanosecond timestamps encoded as strings.
function msToUnixNano(ms: number): string {
  // Use BigInt to avoid float precision loss at nanosecond scale.
  return (BigInt(Math.round(ms)) * 1_000_000n).toString();
}

function unixNanoToMs(nano: string): number {
  return Number(BigInt(nano) / 1_000_000n);
}

// ---------------------------------------------------------------------------
// Encode: OtelSpan[] -> ExportTraceServiceRequest (OTLP/HTTP-JSON)
// ---------------------------------------------------------------------------

export function toOtlpJson(
  spans: OtelSpan[],
  resourceAttrs: Record<string, string | number | boolean> = {
    "service.name": "szl-vsp-otel",
  },
): ExportTraceServiceRequest {
  const otlpSpans: OtlpSpan[] = spans.map((s) => ({
    traceId: s.traceId,
    spanId: s.spanId,
    name: s.name,
    kind: 1, // SPAN_KIND_INTERNAL
    startTimeUnixNano: msToUnixNano(s.startTime),
    endTimeUnixNano: msToUnixNano(s.endTime),
    attributes: toOtlpAttributes(s.attributes),
    status: { code: STATUS_CODE[s.status] },
  }));
  return {
    resourceSpans: [
      {
        resource: { attributes: toOtlpAttributes(resourceAttrs) },
        scopeSpans: [{ scope: SCOPE, spans: otlpSpans }],
      },
    ],
  };
}

// ---------------------------------------------------------------------------
// SpanExporter (OTel-compatible) with injectable transport
// ---------------------------------------------------------------------------

export enum ExportResultCode {
  SUCCESS = 0,
  FAILED = 1,
}

export interface ExportResult {
  code: ExportResultCode;
  error?: Error;
}

/** Transport sends the OTLP request; default captures in-process (no socket). */
export type OtlpTransport = (
  req: ExportTraceServiceRequest,
) => Promise<void> | void;

export interface VspOtlpExporterOpts {
  /** If set, the real fetch transport POSTs OTLP-JSON here. */
  endpoint?: string;
  /** Override transport entirely (used by tests). */
  transport?: OtlpTransport;
  resourceAttrs?: Record<string, string | number | boolean>;
}

export class VspOtlpExporter {
  private readonly transport: OtlpTransport;
  private readonly resourceAttrs: Record<string, string | number | boolean>;
  /** Last request captured by the default in-process transport (test aid). */
  public lastRequest: ExportTraceServiceRequest | null = null;

  constructor(opts: VspOtlpExporterOpts = {}) {
    this.resourceAttrs = opts.resourceAttrs ?? { "service.name": "szl-vsp-otel" };
    if (opts.transport) {
      this.transport = opts.transport;
    } else if (opts.endpoint ?? process.env.VSP_OTLP_ENDPOINT) {
      const url = opts.endpoint ?? (process.env.VSP_OTLP_ENDPOINT as string);
      this.transport = async (req) => {
        const res = await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(req),
        });
        if (!res.ok) throw new Error(`OTLP export HTTP ${res.status}`);
      };
    } else {
      // Hermetic default: capture, do not open a socket.
      this.transport = (req) => {
        this.lastRequest = req;
      };
    }
  }

  /** OTel SpanExporter.export signature. */
  async export(
    spans: OtelSpan[],
    resultCallback: (result: ExportResult) => void,
  ): Promise<void> {
    try {
      const req = toOtlpJson(spans, this.resourceAttrs);
      this.lastRequest = req;
      await this.transport(req);
      resultCallback({ code: ExportResultCode.SUCCESS });
    } catch (e) {
      resultCallback({
        code: ExportResultCode.FAILED,
        error: e instanceof Error ? e : new Error(String(e)),
      });
    }
  }

  async shutdown(): Promise<void> {
    // No persistent resources held by the default/in-proc transport.
  }
}

export { unixNanoToMs };
