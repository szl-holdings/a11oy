// Strict RFC 8785 (JSON Canonicalization Scheme) serializer.
//
// Why this exists next to canonicalJson() in index.ts: canonicalJson() builds an
// intermediate object and lets JSON.stringify enumerate it. ECMAScript enumerates
// integer-like keys ("1", "2", "10") in ascending numeric order BEFORE all other
// keys, so for such keys the bytes differ from RFC 8785 (which sorts by UTF-16
// code units: "10" < "2"). The bytes are still deterministic inside this
// implementation, but a Go/Python/Rust verifier following RFC 8785 computes a
// different hash. This module writes the text directly in the sorted order.
//
// It is additive: nothing in the receipt hash path calls it yet. Switching the
// hash path changes the hash of any stored receipt that has an integer-like key,
// so it needs a schema_version bump and Stephen's approval (see README).
//
// Differences from canonicalJson(): no NFC normalisation, no skipping of
// `undefined`, and only JSON data is accepted (plain objects, arrays, strings,
// finite numbers, booleans, null).

const LONE_SURROGATE = /[\uD800-\uDBFF](?![\uDC00-\uDFFF])|(?<![\uD800-\uDBFF])[\uDC00-\uDFFF]/;

function serializeString(text: string): string {
  if (LONE_SURROGATE.test(text)) throw new Error("jcs: lone surrogate is not valid I-JSON (RFC 8785 3.2.2.2)");
  // JSON.stringify of a well-formed string is exactly RFC 8785 3.2.2.2
  // (ECMA-262 QuoteJSONString: \b \t \n \f \r, lowercase \u00xx for other
  // controls, no escaping of U+007F or U+2028/2029).
  return JSON.stringify(text);
}

function isPlainObject(value: object): boolean {
  const proto = Object.getPrototypeOf(value);
  return proto === Object.prototype || proto === null;
}

export function jcsCanonicalize(value: unknown): string {
  if (value === null) return "null";
  switch (typeof value) {
    case "string":
      return serializeString(value);
    case "boolean":
      return value ? "true" : "false";
    case "number":
      if (!Number.isFinite(value)) throw new Error("jcs: NaN and Infinity are not permitted (RFC 8785 3.2.2.3)");
      // ECMA-262 Number::toString, which RFC 8785 3.2.2.3 mandates ("-0" -> "0").
      return JSON.stringify(value);
    case "object": {
      if (Array.isArray(value)) return `[${value.map(jcsCanonicalize).join(",")}]`;
      if (!isPlainObject(value)) throw new Error("jcs: only plain JSON objects are accepted");
      const obj = value as Record<string, unknown>;
      // Default sort() compares UTF-16 code units, as RFC 8785 3.2.3 requires.
      const members = Object.keys(obj)
        .sort()
        .map((key) => `${serializeString(key)}:${jcsCanonicalize(obj[key])}`);
      return `{${members.join(",")}}`;
    }
    default:
      throw new Error(`jcs: unsupported ${typeof value} value`);
  }
}

export function jcsBytes(value: unknown): Buffer {
  return Buffer.from(jcsCanonicalize(value), "utf8");
}
