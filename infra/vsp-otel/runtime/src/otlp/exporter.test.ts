// SPDX-License-Identifier: Apache-2.0
// Author: Lutar, Stephen P. | ORCID 0009-0001-0110-4173 | SZL Holdings
// Tests: vsp-otel real OTLP/HTTP-JSON exporter + collector round-trip (F4).

import { describe, it, expect } from "vitest";
import {
  VspOtlpExporter,
  ExportResultCode,
  toOtlpJson,
  toOtlpAttributes,
  fromOtlpAttributes,
  type ExportResult,
  type ExportTraceServiceRequest,
} from "./exporter.js";
import { parseOtlpJson } from "./collector.js";
import { injectAnchorFormula, type OtelSpan } from "../exporter.js";

function makeSpan(overrides: Partial<OtelSpan> = {}): OtelSpan {
  return {
    spanId: "00f067aa0ba902b7",
    traceId: "4bf92f3577b34da6a3ce929d0e0e4736",
    name: "sentra.gate.decision",
    startTime: 1_700_000_000_000,
    endTime: 1_700_000_000_250,
    attributes: { "lambda.moral_grounding": 0.96, "decision": "allow", "retries": 2 },
    status: "OK",
    ...overrides,
  };
}

describe("OTLP attribute encoding", () => {
  it("encodes string/bool/int/double with correct AnyValue keys", () => {
    const kvs = toOtlpAttributes({ s: "x", b: true, i: 7, d: 0.5 });
    const byKey = Object.fromEntries(kvs.map((k) => [k.key, k.value]));
    expect(byKey.s).toEqual({ stringValue: "x" });
    expect(byKey.b).toEqual({ boolValue: true });
    expect(byKey.i).toEqual({ intValue: "7" }); // 64-bit ints are strings in OTLP-JSON
    expect(byKey.d).toEqual({ doubleValue: 0.5 });
  });

  it("round-trips attributes encode->decode", () => {
    const attrs = { name: "rosie", weight: 0.9, count: 3, ok: false };
    expect(fromOtlpAttributes(toOtlpAttributes(attrs))).toEqual(attrs);
  });
});

describe("toOtlpJson shape", () => {
  it("produces spec-shaped resourceSpans/scopeSpans/spans", () => {
    const req = toOtlpJson([makeSpan()]);
    expect(Array.isArray(req.resourceSpans)).toBe(true);
    const rs = req.resourceSpans[0];
    expect(rs.scopeSpans[0].scope.name).toBe("@szl/vsp-otel");
    const sp = rs.scopeSpans[0].spans[0];
    expect(sp.spanId).toBe("00f067aa0ba902b7");
    // nanosecond timestamps are strings
    expect(typeof sp.startTimeUnixNano).toBe("string");
    expect(sp.startTimeUnixNano).toBe("1700000000000000000");
    expect(sp.status.code).toBe(1); // OK
  });
});

describe("collector round-trip", () => {
  it("parseOtlpJson(toOtlpJson(spans)) reproduces the spans", () => {
    const span = makeSpan();
    const { spans, rejected } = parseOtlpJson(toOtlpJson([span]));
    expect(rejected).toBe(0);
    expect(spans).toHaveLength(1);
    const got = spans[0];
    expect(got.spanId).toBe(span.spanId);
    expect(got.traceId).toBe(span.traceId);
    expect(got.name).toBe(span.name);
    expect(got.startTime).toBe(span.startTime);
    expect(got.endTime).toBe(span.endTime);
    expect(got.status).toBe("OK");
    expect(got.attributes.decision).toBe("allow");
    expect(got.attributes.retries).toBe(2);
  });

  it("preserves SZL anchor-formula attributes across the round-trip", () => {
    const span = makeSpan();
    injectAnchorFormula(span, {
      formula_id: "madhava_bound",
      lean_theorem_ref: "Lutar.PACBayes.MadhavaBound.madhava_alt_series_bound",
      lean_commit_sha: "c7c0ba17c2eaec60ad38ea9172b4a0d9ca0b582f",
    });
    const { spans } = parseOtlpJson(toOtlpJson([span]));
    expect(spans[0].attributes["szl.anchor_formula.id"]).toBe("madhava_bound");
    expect(spans[0].attributes["szl.lean_theorem_ref"]).toBe(
      "Lutar.PACBayes.MadhavaBound.madhava_alt_series_bound",
    );
    expect(spans[0].attributes["szl.lean_commit_sha"]).toBe(
      "c7c0ba17c2eaec60ad38ea9172b4a0d9ca0b582f",
    );
  });

  it("rejects malformed payloads honestly", () => {
    const bad = { resourceSpans: [{ scopeSpans: [{ spans: [{ name: "x" }] }] }] } as unknown;
    const { spans, rejected, reasons } = parseOtlpJson(bad);
    expect(spans).toHaveLength(0);
    expect(rejected).toBe(1);
    expect(reasons[0]).toContain("malformed span");
  });

  it("reports missing resourceSpans", () => {
    expect(parseOtlpJson({}).rejected).toBe(1);
  });
});

describe("VspOtlpExporter", () => {
  it("default in-process transport opens no socket and captures the request", async () => {
    const exp = new VspOtlpExporter();
    let result: ExportResult | undefined;
    await exp.export([makeSpan()], (r) => (result = r));
    expect(result?.code).toBe(ExportResultCode.SUCCESS);
    expect(exp.lastRequest?.resourceSpans[0].scopeSpans[0].spans).toHaveLength(1);
  });

  it("invokes an injected transport and reports SUCCESS", async () => {
    let captured: ExportTraceServiceRequest | null = null;
    const exp = new VspOtlpExporter({ transport: (req) => { captured = req; } });
    let result: ExportResult | undefined;
    await exp.export([makeSpan(), makeSpan({ spanId: "bb" })], (r) => (result = r));
    expect(result?.code).toBe(ExportResultCode.SUCCESS);
    expect(captured!.resourceSpans[0].scopeSpans[0].spans).toHaveLength(2);
  });

  it("reports FAILED when the transport throws (no fake green)", async () => {
    const exp = new VspOtlpExporter({
      transport: () => { throw new Error("network down"); },
    });
    let result: ExportResult | undefined;
    await exp.export([makeSpan()], (r) => (result = r));
    expect(result?.code).toBe(ExportResultCode.FAILED);
    expect(result?.error?.message).toBe("network down");
  });
});
