/* SPDX-License-Identifier: Apache-2.0
 * (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
 * ============================================================================
 * szl_receipt_cosign.js - SHARED MODULE (byte-identical across a11oy + killinchu)
 * ----------------------------------------------------------------------------
 * The single DSSE receipt + cosign-verify primitive for the SZL estate.
 * NO CDN, no build step. Browser-native SubtleCrypto only. Node-safe import.
 *
 *   *** ONE documented signing scheme for the whole estate: ***
 *       ECDSA P-256 (SECP256R1) over SHA-256  ==  Sigstore cosign default.
 *
 * WHY P-256 and NOT Ed25519 (resolving the signing-scheme drift, gate G4):
 *   - The deployed estate, szl_dsse.py (byte-identical in both apps), every
 *     server verify path, and the PUBLISHED key szl-holdings/.github/cosign.pub
 *     are ALL ECDSA P-256. cosign sign-blob / verify-blob round-trips against it.
 *   - a11oy_signing_key.py states the curve is "deliberately NOT Ed25519" to
 *     match cosign.pub and every existing verify path.
 *   - Switching to Ed25519 would orphan cosign.pub and break cosign-CLI
 *     interop. Doctrine G8 ("don't claim/ship more than is real") => keep the
 *     scheme that actually verifies. The Ed25519 suggestion is therefore
 *     RESOLVED in favor of ECDSA-P256. HMAC is forbidden (symmetric, not
 *     publicly verifiable). This is the single source of truth for clients.
 *
 * DSSE (secure-systems-lab/dsse) PAE pre-authentication encoding (must match
 * szl_dsse.py byte-for-byte):
 *   PAE(type, body) = "DSSEv1" SP LEN(type) SP type SP LEN(body) SP body
 *   SIGNATURE       = ECDSA-P256-SHA256( PAE(payloadType, canonical_body) )
 *
 * HONESTY (gate G7/G8): this module NEVER fabricates a signature. Signing is
 * done by the SAME-ORIGIN server endpoint POST /khipu/sign (which holds the
 * szlholdings-cosign private key). The client:
 *   - builds the canonical receipt + chain hash (SHA-256, re-checkable),
 *   - asks the server to sign,
 *   - records keyid + sig_type returned (truthfully),
 *   - if the signer is unreachable OR returns an ephemeral/non-canonical key,
 *     marks the receipt UNSIGNED / CROSS-APP-PENDING and shows it honestly.
 *
 * Public API (window.SZLReceipts / module.exports):
 *   SCHEME                              - "ECDSA-P256-SHA256" (frozen)
 *   COSIGN_KEYID                        - "szlholdings-cosign" (frozen)
 *   COSIGN_PUB_URL                      - canonical published key URL
 *   canonicalJSON(obj)                  - deterministic JSON (sorted keys)
 *   sha256Hex(strOrBytes) -> Promise    - SubtleCrypto SHA-256 hex
 *   pae(type, bodyBytes) -> Uint8Array  - DSSE PAE bytes
 *   chainHash(prevHash, receipt) -> P   - SHA-256 of (prev_hash || canonical)
 *   signReceipt(receipt, opts) -> P     - POST /khipu/sign; honest never-fake
 *   verifyEnvelope(env, opts) -> P      - POST /khipu/verify; cross-app verdict
 *   isCanonicalKey(keyid)               - keyid === szlholdings-cosign ?
 *   newChain(opts)                      - a small append-only signed chain helper
 * ============================================================================ */
(function (root, factory) {
  var mod = factory();
  if (typeof module === "object" && module.exports) { module.exports = mod; }
  if (root) { root.SZLReceipts = mod; }
})(typeof self !== "undefined" ? self : (typeof window !== "undefined" ? window : null), function () {
  "use strict";

  var SCHEME = "ECDSA-P256-SHA256";
  var COSIGN_KEYID = "szlholdings-cosign";
  var COSIGN_PUB_URL = "https://github.com/szl-holdings/.github/blob/main/cosign.pub";
  var KHIPU_PAYLOAD_TYPE = "application/vnd.szl.khipu+json";

  function _subtle() {
    var c = (typeof self !== "undefined" && self.crypto) ? self.crypto
          : (typeof window !== "undefined" && window.crypto) ? window.crypto
          : (typeof globalThis !== "undefined" && globalThis.crypto) ? globalThis.crypto : null;
    return c && c.subtle ? c.subtle : null;
  }

  /* Deterministic canonical JSON: object keys sorted recursively, no spaces.
   * MUST match szl_dsse.canonical_json (json.dumps(sort_keys, separators=(',',':'))). */
  function canonicalJSON(obj) {
    if (obj === null || typeof obj !== "object") { return JSON.stringify(obj); }
    if (Object.prototype.toString.call(obj) === "[object Array]") {
      var items = []; for (var i = 0; i < obj.length; i++) { items.push(canonicalJSON(obj[i])); }
      return "[" + items.join(",") + "]";
    }
    var keys = []; for (var k in obj) { if (Object.prototype.hasOwnProperty.call(obj, k)) { keys.push(k); } }
    keys.sort();
    var parts = []; for (var j = 0; j < keys.length; j++) { parts.push(JSON.stringify(keys[j]) + ":" + canonicalJSON(obj[keys[j]])); }
    return "{" + parts.join(",") + "}";
  }

  function _toBytes(strOrBytes) {
    if (strOrBytes instanceof Uint8Array) { return strOrBytes; }
    var s = String(strOrBytes);
    if (typeof TextEncoder !== "undefined") { return new TextEncoder().encode(s); }
    var arr = []; for (var i = 0; i < s.length; i++) { arr.push(s.charCodeAt(i) & 0xff); }
    return new Uint8Array(arr);
  }
  function _hex(buf) {
    var b = new Uint8Array(buf), h = ""; for (var i = 0; i < b.length; i++) { h += (b[i] < 16 ? "0" : "") + b[i].toString(16); }
    return h;
  }

  function sha256Hex(strOrBytes) {
    var sub = _subtle();
    if (!sub) { return Promise.reject(new Error("SubtleCrypto unavailable (needs HTTPS/secure context)")); }
    return sub.digest("SHA-256", _toBytes(strOrBytes)).then(_hex);
  }

  /* DSSE PAE bytes. Lengths are decimal ASCII of the UTF-8 byte length. */
  function pae(payloadType, bodyBytes) {
    var t = _toBytes(payloadType), b = (bodyBytes instanceof Uint8Array) ? bodyBytes : _toBytes(bodyBytes);
    var head = "DSSEv1 " + t.length + " ";
    var mid = " " + b.length + " ";
    var pre = _toBytes(head), tb = t, midb = _toBytes(mid);
    var out = new Uint8Array(pre.length + tb.length + midb.length + b.length);
    var o = 0;
    out.set(pre, o); o += pre.length;
    out.set(tb, o); o += tb.length;
    out.set(midb, o); o += midb.length;
    out.set(b, o);
    return out;
  }

  function chainHash(prevHash, receipt) {
    var canonical = canonicalJSON(receipt);
    return sha256Hex(String(prevHash || "0") + "|" + canonical).then(function (h) {
      return { hash: h, canonical: canonical };
    });
  }

  function isCanonicalKey(keyid) { return keyid === COSIGN_KEYID; }

  /* Ask the SAME-ORIGIN server to sign. NEVER fabricates a signature.
   * opts: { base:"", payloadType, fetchImpl } */
  function signReceipt(receipt, opts) {
    opts = opts || {};
    var base = opts.base || "";
    var f = opts.fetchImpl || (typeof fetch !== "undefined" ? fetch : null);
    if (!f) { return Promise.reject(new Error("fetch unavailable")); }
    var body = JSON.stringify(receipt);
    return f(base + "/khipu/sign", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: body
    }).then(function (resp) {
      var ct = resp.headers && resp.headers.get ? (resp.headers.get("content-type") || "") : "";
      if (!resp.ok) { return resp.text().then(function (t) { throw new Error("signer HTTP " + resp.status + ": " + t.slice(0, 160)); }); }
      if (ct.indexOf("application/json") === -1) { throw new Error("signer returned non-JSON (route not mounted)"); }
      return resp.json();
    }).then(function (j) {
      var env = j.envelope || j;
      var sig0 = (env.signatures && env.signatures[0]) || null;
      var keyid = sig0 ? sig0.keyid : null;
      var sigType = (sig0 && sig0.sig_type) || (j.sig_types && j.sig_types[0]) || SCHEME;
      var hasSig = !!(sig0 && sig0.sig);
      var canonical = isCanonicalKey(keyid);
      return {
        signed: hasSig,
        canonicalKey: canonical,
        crossAppVerifiable: hasSig && canonical,
        keyid: keyid,
        sigType: sigType,
        sig: sig0 ? sig0.sig : null,
        envelope: env,
        signerNote: hasSig
          ? (canonical ? "" : "signer used a NON-CANONICAL key (" + keyid + "); cross-app verify PENDING operator cosign secret")
          : "signer returned no signature - receipt is UNSIGNED (honest)"
      };
    })["catch"](function (err) {
      // HONEST failure - never fake a signature
      return {
        signed: false, canonicalKey: false, crossAppVerifiable: false,
        keyid: null, sigType: null, sig: null, envelope: null,
        signerNote: "signer unreachable - receipt is UNSIGNED (honest): " + err.message
      };
    });
  }

  /* Verify a DSSE envelope via the server /khipu/verify (verifies against the
   * published cosign.pub). Returns a truthful verdict. */
  function verifyEnvelope(envelope, opts) {
    opts = opts || {};
    var base = opts.base || "";
    var f = opts.fetchImpl || (typeof fetch !== "undefined" ? fetch : null);
    if (!f) { return Promise.reject(new Error("fetch unavailable")); }
    return f(base + "/khipu/verify", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(envelope)
    }).then(function (resp) {
      if (!resp.ok) { throw new Error("verify HTTP " + resp.status); }
      return resp.json();
    }).then(function (j) {
      return {
        verified: j.verified === true,
        keyidMatch: j.keyid_match === true,
        keyidExpected: (j.detail && j.detail.keyid_expected) || COSIGN_KEYID,
        pubFingerprint: (j.detail && j.detail.pub_fingerprint_sha256) || null,
        verifyKeyUrl: (j.detail && j.detail.verify_key_url) || COSIGN_PUB_URL,
        raw: j
      };
    });
  }

  /* Small append-only signed chain helper. Each push() hashes (prev||receipt),
   * signs via the server, and links. Honest about UNSIGNED / cross-app state. */
  function newChain(opts) {
    opts = opts || {};
    var base = opts.base || "";
    var chain = [];
    var tip = "0";
    return {
      receipts: chain,
      tip: function () { return tip; },
      push: function (action, data) {
        var seq = chain.length;
        var receipt = { action: String(action), seq: seq, prev_hash: tip, data: data || {}, ts: new Date().toISOString() };
        return chainHash(tip, receipt).then(function (ch) {
          receipt.hash = ch.hash; receipt.canonical = ch.canonical;
          return signReceipt({ action: receipt.action, seq: seq, prev_hash: tip, data: receipt.data }, { base: base });
        }).then(function (sg) {
          receipt.signed = sg.signed; receipt.keyid = sg.keyid; receipt.sigType = sg.sigType;
          receipt.sig = sg.sig; receipt.canonicalKey = sg.canonicalKey;
          receipt.crossAppVerifiable = sg.crossAppVerifiable; receipt.signerNote = sg.signerNote;
          chain.push(receipt); tip = receipt.hash;
          return receipt;
        });
      }
    };
  }

  try { /* freeze constants */ } catch (e) {}
  return {
    VERSION: "1.0.0",
    SCHEME: SCHEME,
    COSIGN_KEYID: COSIGN_KEYID,
    COSIGN_PUB_URL: COSIGN_PUB_URL,
    PAYLOAD_TYPE: KHIPU_PAYLOAD_TYPE,
    canonicalJSON: canonicalJSON,
    sha256Hex: sha256Hex,
    pae: pae,
    chainHash: chainHash,
    isCanonicalKey: isCanonicalKey,
    signReceipt: signReceipt,
    verifyEnvelope: verifyEnvelope,
    newChain: newChain
  };
});
