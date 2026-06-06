import { describe, it, expect } from 'vitest';
import { dsseV1Pae, base64ToBytes, dsseV1PaeFromBase64Body } from '../src/lib/dsse-pae.ts';
import { canonicalJson, canonicalJsonBytes } from '../src/lib/canonical-json.ts';
import { createSubstrate, loadEd25519Signer, sha256Hex } from '../src/lib/receipt-substrate.ts';

describe('canonical DSSE v1 PAE', () => {
  it('matches the frozen DSSE spec test vector', () => {
    // protocol.md: type "http://example.com/HelloWorld", body "hello world"
    // → "DSSEv1 29 http://example.com/HelloWorld 11 hello world"
    const pae = dsseV1Pae('http://example.com/HelloWorld', new TextEncoder().encode('hello world'));
    expect(new TextDecoder().decode(pae)).toBe('DSSEv1 29 http://example.com/HelloWorld 11 hello world');
  });

  it('decodes base64 and base64url tolerantly', () => {
    expect(new TextDecoder().decode(base64ToBytes('aGVsbG8'))).toBe('hello');
    expect(new TextDecoder().decode(base64ToBytes('aGVsbG8='))).toBe('hello');
  });

  it('computes PAE from a base64 body identically to raw', () => {
    const raw = new TextEncoder().encode('hello world');
    const b64 = Buffer.from(raw).toString('base64');
    const a = dsseV1Pae('t', raw);
    const b = dsseV1PaeFromBase64Body('t', b64);
    expect(Buffer.from(a).equals(Buffer.from(b))).toBe(true);
  });
});

describe('canonical JSON', () => {
  it('sorts keys deterministically', () => {
    expect(canonicalJson({ b: 1, a: 2 })).toBe('{"a":2,"b":1}');
  });
  it('drops undefined and rejects non-finite numbers', () => {
    expect(canonicalJson({ a: undefined, b: 1 })).toBe('{"b":1}');
    expect(() => canonicalJson({ a: Infinity })).toThrow();
  });
  it('returns UTF-8 bytes', () => {
    expect(new TextDecoder().decode(canonicalJsonBytes({ a: 1 }))).toBe('{"a":1}');
  });
});

describe('receipt substrate degraded mode', () => {
  it('emits an unsigned receipt when no key is loaded', () => {
    const signer = loadEd25519Signer(undefined, 'k-degraded');
    expect(signer.publicKey()).toBeNull();
    const sub = createSubstrate(signer);
    const r = sub.emit({ kind: 'test' }, null, 0);
    expect(r.signatures[0].sig).toBe('UNSIGNED-DEGRADED-NO-KEY');
    const verdict = sub.verify(r);
    expect(verdict.verified).toBe(false);
    expect(verdict.errors.join(' ')).toContain('unsigned');
  });

  it('chains via sha256Hex', () => {
    expect(sha256Hex('a')).toHaveLength(64);
    expect(sha256Hex('a')).not.toBe(sha256Hex('b'));
  });

  it('flags a bad payloadType on verify', () => {
    const signer = loadEd25519Signer(undefined, 'k');
    const sub = createSubstrate(signer);
    const verdict = sub.verify({
      payload: 'e30=',
      payloadType: 'application/wrong',
      signatures: [{ keyid: 'k', sig: 'x', alg: 'ed25519' }],
      chain: { prev_hash: 'GENESIS', index: 0, ts: new Date().toISOString() },
    });
    expect(verdict.verified).toBe(false);
    expect(verdict.errors.join(' ')).toContain('payloadType');
  });
});
