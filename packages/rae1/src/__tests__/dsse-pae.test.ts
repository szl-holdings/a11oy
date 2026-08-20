/**
 * @file packages/rae1/src/__tests__/dsse-pae.test.ts
 * @description Byte-for-byte freeze of the canonical DSSE v1 PAE.
 *
 * Source of truth: https://github.com/secure-systems-lab/dsse/blob/master/protocol.md
 *   PAE = "DSSEv1" SP LEN(type) SP type SP LEN(body) SP body
 *   SP  = ASCII space [0x20]
 *   LEN = ASCII decimal byte-length, no leading zeros
 *
 * The spec's own test vector (protocol.md "Test vectors" section) is reproduced
 * here as the cross-checked reference; if this test ever drifts from the spec
 * string, the module — not the test — is wrong.
 */

import { describe, it, expect } from "vitest";
import {
  dsseV1Pae,
  dsseV1PaeFromBase64Body,
  base64ToBytes,
} from "../dsse-pae";

const td = new TextDecoder();

describe("dsseV1Pae — canonical DSSE v1 PAE", () => {
  it("empty body produces 'DSSEv1 15 application/x.t 0 ' with a trailing SP and 0 body bytes", () => {
    // NOTE: "application/x.t" is 15 UTF-8 bytes (verified), so LEN(type)=15.
    // The DSSE-unification brief's "13" was an arithmetic slip; the spec's
    // LEN rule (ASCII decimal byte length) yields 15. Empty body ⇒ LEN(body)=0
    // followed by SP and zero body bytes (the string ends with a trailing space).
    const pae = dsseV1Pae("application/x.t", new Uint8Array(0));
    expect(td.decode(pae)).toBe("DSSEv1 15 application/x.t 0 ");
    // The last byte is the separator SP (0x20); there are no body bytes after it.
    expect(pae[pae.length - 1]).toBe(0x20);
  });

  it("matches the DSSE spec test vector exactly (HelloWorld)", () => {
    // From github.com/secure-systems-lab/dsse/blob/master/protocol.md:
    //   payloadType = "http://example.com/HelloWorld", body = "hello world"
    //   PAE = "DSSEv1 29 http://example.com/HelloWorld 11 hello world"
    const type = "http://example.com/HelloWorld";
    const body = new TextEncoder().encode("hello world");
    const pae = dsseV1Pae(type, body);
    expect(td.decode(pae)).toBe(
      "DSSEv1 29 http://example.com/HelloWorld 11 hello world"
    );
  });

  it("uses ASCII decimal lengths with no leading zeros", () => {
    const body = new TextEncoder().encode("x".repeat(100));
    const pae = td.decode(dsseV1Pae("a", body));
    expect(pae).toBe("DSSEv1 1 a 100 " + "x".repeat(100));
  });

  it("SP separator is exactly 0x20 (single space), never LF", () => {
    const pae = dsseV1Pae("a", new TextEncoder().encode("bc"));
    expect(Array.from(pae)).not.toContain(0x0a); // no LF anywhere
    // Layout: 'D''S''S''E''v''1' 0x20 '1' 0x20 'a' 0x20 '2' 0x20 'b''c'
    const decoded = td.decode(pae);
    expect(decoded).toBe("DSSEv1 1 a 2 bc");
  });

  it("counts BYTE length, not character length (multi-byte UTF-8 body)", () => {
    // "é" is 2 UTF-8 bytes; "€" is 3.
    const body = new TextEncoder().encode("é€"); // 5 bytes
    const pae = dsseV1Pae("t", body);
    const prefix = td.decode(pae.slice(0, pae.indexOf(0x20, 7) + 1));
    // LEN(body) must be 5, not 2.
    expect(td.decode(pae).startsWith("DSSEv1 1 t 5 ")).toBe(true);
    expect(prefix).toBeDefined();
  });

  it("multi-byte type counts BYTE length too", () => {
    const type = "t€"; // 1 + 3 = 4 bytes
    const pae = td.decode(dsseV1Pae(type, new Uint8Array(0)));
    expect(pae).toBe("DSSEv1 4 t€ 0 ");
  });
});

describe("dsseV1PaeFromBase64Body — PAE over RAW decoded body", () => {
  it("decodes base64 first, then computes PAE over raw bytes (NOT over the base64 string)", () => {
    const body = "hello world";
    const b64 = Buffer.from(body, "utf8").toString("base64"); // "aGVsbG8gd29ybGQ="
    const fromB64 = dsseV1PaeFromBase64Body("http://example.com/HelloWorld", b64);
    const fromRaw = dsseV1Pae(
      "http://example.com/HelloWorld",
      new TextEncoder().encode(body)
    );
    expect(Array.from(fromB64)).toEqual(Array.from(fromRaw));
    expect(td.decode(fromB64)).toBe(
      "DSSEv1 29 http://example.com/HelloWorld 11 hello world"
    );
  });

  it("accepts base64url (URL-safe) input", () => {
    const raw = new Uint8Array([0xff, 0xfe, 0xfd]); // encodes with + and / in std b64
    const b64url = Buffer.from(raw)
      .toString("base64")
      .replace(/\+/g, "-")
      .replace(/\//g, "_")
      .replace(/=+$/, "");
    const decoded = base64ToBytes(b64url);
    expect(Array.from(decoded)).toEqual([0xff, 0xfe, 0xfd]);
  });
});
