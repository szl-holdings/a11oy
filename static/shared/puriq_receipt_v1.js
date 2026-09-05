/* SPDX-License-Identifier: Apache-2.0
 * (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
 *
 * PurIQ receipt v1 canonical serializer and client-side session verifier.
 * Browser-native Web Crypto; the same module is consumable from Node tests.
 *
 * Hash material is the exact object containing receipt_version through gate.
 * payload_hash and signature are deliberately outside that material. Signed
 * receipts require a server verification callback because signing key material
 * never enters the browser. Honest UNSIGNED receipts require key_id === null.
 * Canonical encoding uses ECMAScript JSON number/string spelling and UTF-16
 * code-unit key ordering. Lone surrogates are rejected; Unicode is not normalized.
 */
(function (root, factory) {
  var api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  }
  if (root) {
    root.PurIQReceiptV1 = api;
  }
})(
  typeof self !== "undefined"
    ? self
    : typeof window !== "undefined"
      ? window
      : null,
  function () {
    "use strict";

    var TOP_LEVEL_KEYS = [
      "gate",
      "issued_at",
      "payload_hash",
      "prev_receipt_hash",
      "ranking_inputs",
      "receipt_id",
      "receipt_version",
      "sequence",
      "session_id",
      "signature",
      "subject"
    ];
    var MATERIAL_KEYS = [
      "gate",
      "issued_at",
      "prev_receipt_hash",
      "ranking_inputs",
      "receipt_id",
      "receipt_version",
      "sequence",
      "session_id",
      "subject"
    ];
    var SHA256_HEX = /^[0-9a-f]{64}$/;
    var UUID_V4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
    var RFC3339_UTC = /^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]+)?Z$/;
    var SEMVER = /^(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)(?:-(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)(?:\.(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*))*)?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$/;

    function _validUnicode(value) {
      for (var i = 0; i < value.length; i += 1) {
        var code = value.charCodeAt(i);
        if (code >= 0xd800 && code <= 0xdbff) {
          var next = value.charCodeAt(i + 1);
          if (!(next >= 0xdc00 && next <= 0xdfff)) return false;
          i += 1;
        } else if (code >= 0xdc00 && code <= 0xdfff) {
          return false;
        }
      }
      return true;
    }

    function _validTimestamp(value) {
      if (typeof value !== "string" || !RFC3339_UTC.test(value)) return false;
      var year = Number(value.slice(0, 4));
      var month = Number(value.slice(5, 7));
      var day = Number(value.slice(8, 10));
      var hour = Number(value.slice(11, 13));
      var minute = Number(value.slice(14, 16));
      var second = Number(value.slice(17, 19));
      var leap = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
      var days = [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
      return month >= 1 && month <= 12 && day >= 1 && day <= days[month - 1] &&
        hour <= 23 && minute <= 59 &&
        (second <= 59 || (second === 60 && hour === 23 && minute === 59));
    }

    function _isPlainObject(value) {
      if (value === null || typeof value !== "object" || Array.isArray(value)) {
        return false;
      }
      var proto = Object.getPrototypeOf(value);
      return proto === Object.prototype || proto === null;
    }

    function _canonical(value, seen) {
      if (typeof value === "string" && !_validUnicode(value)) {
        throw new TypeError("canonical JSON rejects lone Unicode surrogates");
      }
      if (value === null || typeof value === "boolean" || typeof value === "string") {
        return JSON.stringify(value);
      }
      if (typeof value === "number") {
        if (!Number.isFinite(value)) {
          throw new TypeError("canonical JSON rejects non-finite numbers");
        }
        return JSON.stringify(value);
      }
      if (typeof value !== "object") {
        throw new TypeError("canonical JSON accepts JSON values only");
      }
      if (seen.indexOf(value) !== -1) {
        throw new TypeError("canonical JSON rejects circular structures");
      }
      seen.push(value);
      var result;
      if (Array.isArray(value)) {
        var items = [];
        for (var i = 0; i < value.length; i += 1) {
          items.push(_canonical(value[i], seen));
        }
        result = "[" + items.join(",") + "]";
      } else {
        if (!_isPlainObject(value)) {
          throw new TypeError("canonical JSON accepts plain objects only");
        }
        var keys = Object.keys(value).sort();
        var parts = [];
        for (var j = 0; j < keys.length; j += 1) {
          var key = keys[j];
          if (!_validUnicode(key)) {
            throw new TypeError("canonical JSON rejects lone Unicode surrogates");
          }
          parts.push(JSON.stringify(key) + ":" + _canonical(value[key], seen));
        }
        result = "{" + parts.join(",") + "}";
      }
      seen.pop();
      return result;
    }

    function canonicalJSON(value) {
      return _canonical(value, []);
    }

    function _subtle() {
      var cryptoObject =
        typeof globalThis !== "undefined" && globalThis.crypto
          ? globalThis.crypto
          : null;
      return cryptoObject && cryptoObject.subtle ? cryptoObject.subtle : null;
    }

    function _utf8(value) {
      if (typeof TextEncoder === "undefined") {
        throw new Error("TextEncoder unavailable");
      }
      return new TextEncoder().encode(value);
    }

    function _hex(buffer) {
      var bytes = new Uint8Array(buffer);
      var output = "";
      for (var i = 0; i < bytes.length; i += 1) {
        output += bytes[i].toString(16).padStart(2, "0");
      }
      return output;
    }

    function sha256Hex(value) {
      var subtle = _subtle();
      if (!subtle) {
        return Promise.reject(
          new Error("Web Crypto SubtleCrypto unavailable; use a secure browser context")
        );
      }
      return subtle.digest("SHA-256", _utf8(String(value))).then(_hex);
    }

    function _sameKeys(value, expected) {
      if (!_isPlainObject(value)) {
        return false;
      }
      var actual = Object.keys(value).sort();
      if (actual.length !== expected.length) {
        return false;
      }
      for (var i = 0; i < expected.length; i += 1) {
        if (actual[i] !== expected[i]) {
          return false;
        }
      }
      return true;
    }

    function _allStrings(value) {
      if (!Array.isArray(value)) {
        return false;
      }
      for (var i = 0; i < value.length; i += 1) {
        if (typeof value[i] !== "string") {
          return false;
        }
      }
      return true;
    }

    function _receiptErrors(receipt) {
      var errors = [];
      if (!_sameKeys(receipt, TOP_LEVEL_KEYS)) {
        return ["receipt_shape"];
      }
      if (receipt.receipt_version !== 1) errors.push("receipt_version");
      if (typeof receipt.receipt_id !== "string" || !UUID_V4.test(receipt.receipt_id)) {
        errors.push("receipt_id");
      }
      if (!_validTimestamp(receipt.issued_at)) {
        errors.push("issued_at");
      }
      if (typeof receipt.session_id !== "string" || !UUID_V4.test(receipt.session_id)) {
        errors.push("session_id");
      }
      if (!Number.isSafeInteger(receipt.sequence) || receipt.sequence < 0) {
        errors.push("sequence");
      }
      if (
        receipt.prev_receipt_hash !== "GENESIS" &&
        (typeof receipt.prev_receipt_hash !== "string" ||
          !SHA256_HEX.test(receipt.prev_receipt_hash))
      ) {
        errors.push("prev_receipt_hash");
      }

      if (!_sameKeys(receipt.subject, [
        "normalized_record_hash",
        "parser_version",
        "source_record_id"
      ])) {
        errors.push("subject_shape");
      } else {
        if (typeof receipt.subject.normalized_record_hash !== "string" ||
            !SHA256_HEX.test(receipt.subject.normalized_record_hash)) {
          errors.push("normalized_record_hash");
        }
        if (typeof receipt.subject.source_record_id !== "string") {
          errors.push("source_record_id");
        }
        if (
          typeof receipt.subject.parser_version !== "string" ||
          !SEMVER.test(receipt.subject.parser_version)
        ) {
          errors.push("parser_version");
        }
      }

      if (!_sameKeys(receipt.ranking_inputs, [
        "caveats",
        "confidence",
        "reasons",
        "source_path"
      ])) {
        errors.push("ranking_inputs_shape");
      } else {
        if (!_allStrings(receipt.ranking_inputs.source_path)) errors.push("source_path");
        if (!_allStrings(receipt.ranking_inputs.caveats)) errors.push("caveats");
        if (!Array.isArray(receipt.ranking_inputs.reasons)) {
          errors.push("reasons");
        } else {
          for (var reasonIndex = 0; reasonIndex < receipt.ranking_inputs.reasons.length; reasonIndex += 1) {
            var reason = receipt.ranking_inputs.reasons[reasonIndex];
            if (!_sameKeys(reason, ["code", "detail", "direction", "weight"])) {
              errors.push("reason_shape");
              break;
            }
            if (
              typeof reason.code !== "string" ||
              (reason.direction !== "up" && reason.direction !== "down") ||
              typeof reason.weight !== "number" ||
              !Number.isFinite(reason.weight) ||
              typeof reason.detail !== "string"
            ) {
              errors.push("reason_value");
              break;
            }
          }
        }
        var confidence = receipt.ranking_inputs.confidence;
        if (!_sameKeys(confidence, ["high", "low"])) {
          errors.push("confidence_shape");
        } else if (
          typeof confidence.low !== "number" ||
          !Number.isFinite(confidence.low) ||
          confidence.low < 0 ||
          confidence.low > 1 ||
          typeof confidence.high !== "number" ||
          !Number.isFinite(confidence.high) ||
          confidence.high < 0 ||
          confidence.high > 1 ||
          confidence.low > confidence.high
        ) {
          errors.push("confidence");
        }
      }

      if (!_sameKeys(receipt.gate, ["failures", "name", "result"])) {
        errors.push("gate_shape");
      } else {
        if (receipt.gate.name !== "yuyay-13") errors.push("gate_name");
        if (receipt.gate.result !== "pass" && receipt.gate.result !== "fail") {
          errors.push("gate_result");
        }
        if (!_allStrings(receipt.gate.failures)) errors.push("gate_failures");
        if (Array.isArray(receipt.gate.failures) && receipt.gate.result === "pass" && receipt.gate.failures.length !== 0) {
          errors.push("gate_failures_on_pass");
        }
        if (Array.isArray(receipt.gate.failures) && receipt.gate.result === "fail" && receipt.gate.failures.length === 0) {
          errors.push("gate_failures_on_fail");
        }
      }

      if (typeof receipt.payload_hash !== "string" || !SHA256_HEX.test(receipt.payload_hash)) {
        errors.push("payload_hash");
      }
      if (!_sameKeys(receipt.signature, ["algorithm", "key_id", "value"])) {
        errors.push("signature_shape");
      } else {
        if (receipt.signature.algorithm !== "HMAC-SHA256") errors.push("signature_algorithm");
        if (receipt.signature.value === "UNSIGNED") {
          if (receipt.signature.key_id !== null) errors.push("unsigned_key_id");
        } else {
          if (typeof receipt.signature.value !== "string" || !SHA256_HEX.test(receipt.signature.value)) errors.push("signature_value");
          if (typeof receipt.signature.key_id !== "string" || receipt.signature.key_id.length === 0) {
            errors.push("signature_key_id");
          }
        }
      }
      return errors;
    }

    function payloadMaterial(receipt) {
      if (!_sameKeys(receipt, TOP_LEVEL_KEYS)) {
        throw new TypeError("receipt must contain exactly the PurIQ v1 fields");
      }
      var material = {};
      for (var i = 0; i < MATERIAL_KEYS.length; i += 1) {
        var key = MATERIAL_KEYS[i];
        material[key] = receipt[key];
      }
      return material;
    }

    function computePayloadHash(receipt) {
      var errors = _receiptErrors(receipt);
      if (errors.length !== 0) {
        return Promise.reject(new TypeError("invalid PurIQ v1 receipt: " + errors.join(",")));
      }
      return sha256Hex(canonicalJSON(payloadMaterial(receipt)));
    }

    async function verifySession(receipts, options) {
      options = options || {};
      if (!Array.isArray(receipts)) {
        throw new TypeError("receipts must be an array");
      }
      var signatureVerifier = options.verifySignature;
      var expectedSessionId = receipts.length > 0 && _isPlainObject(receipts[0])
        ? receipts[0].session_id : null;
      var results = [];
      var firstFailureReceiptId = null;
      var firstFailureIndex = null;
      var upstreamInvalid = false;

      for (var index = 0; index < receipts.length; index += 1) {
        var receipt = receipts[index];
        var errors = _receiptErrors(receipt);
        var expectedHash = null;
        var payloadHashValid = false;
        var sequenceValid = false;
        var linkValid = false;
        var signatureValid = false;
        var signatureState = "INVALID";

        if (upstreamInvalid) errors.push("upstream_invalid");
        if (_isPlainObject(receipt)) {
          sequenceValid = receipt.sequence === index;
          if (!sequenceValid) errors.push("sequence_not_contiguous");
          if (receipt.session_id !== expectedSessionId) errors.push("session_id_mismatch");
          var priorReceipt = index === 0 ? null : receipts[index - 1];
          var expectedPrevious =
            index === 0
              ? "GENESIS"
              : _isPlainObject(priorReceipt)
                ? priorReceipt.payload_hash
                : null;
          linkValid = receipt.prev_receipt_hash === expectedPrevious;
          if (!linkValid) errors.push("prev_receipt_hash_mismatch");
          if (receipt.gate && receipt.gate.result !== "pass") errors.push("gate_failed_receipt");
        }

        if (errors.indexOf("receipt_shape") === -1) {
          try {
            expectedHash = await sha256Hex(canonicalJSON(payloadMaterial(receipt)));
            payloadHashValid = receipt.payload_hash === expectedHash;
            if (!payloadHashValid) errors.push("payload_hash_mismatch");
          } catch (error) {
            errors.push("payload_hash_uncomputable");
          }
        }

        if (_isPlainObject(receipt) && _isPlainObject(receipt.signature)) {
          if (receipt.signature.value === "UNSIGNED" && receipt.signature.key_id === null) {
            signatureValid = null;
            signatureState = receipt.signature.algorithm === "HMAC-SHA256" ? "UNSIGNED" : "INVALID";
          } else if (
            SHA256_HEX.test(receipt.signature.value || "") &&
            typeof receipt.signature.key_id === "string" &&
            receipt.signature.key_id.length > 0
          ) {
            if (typeof signatureVerifier !== "function") {
              signatureState = "UNVERIFIED";
              errors.push("signed_receipt_unverified");
            } else {
              try {
                signatureValid =
                  (await signatureVerifier({
                    receipt_id: receipt.receipt_id,
                    payload_hash: receipt.payload_hash,
                    key_id: receipt.signature.key_id,
                    signature: receipt.signature.value
                  })) === true;
                signatureState = signatureValid ? "VERIFIED" : "INVALID";
                if (!signatureValid) errors.push("signature_invalid");
              } catch (error) {
                errors.push("signature_verification_error");
              }
            }
          }
        }

        errors = Array.from(new Set(errors));
        var valid = errors.length === 0;
        if (!valid && firstFailureIndex === null) {
          firstFailureIndex = index;
          firstFailureReceiptId =
            _isPlainObject(receipt) && typeof receipt.receipt_id === "string"
              ? receipt.receipt_id
              : null;
        }
        if (!valid) upstreamInvalid = true;
        results.push({
          receipt_id:
            _isPlainObject(receipt) && typeof receipt.receipt_id === "string"
              ? receipt.receipt_id
              : null,
          sequence: _isPlainObject(receipt) ? receipt.sequence : null,
          valid: valid,
          payload_hash_valid: payloadHashValid,
          sequence_valid: sequenceValid,
          link_valid: linkValid,
          signature_valid: signatureValid,
          signature_state: signatureState,
          expected_payload_hash: expectedHash,
          errors: errors
        });
      }

      return {
        valid: results.every(function (result) { return result.valid; }),
        receipt_count: receipts.length,
        first_failure_receipt_id: firstFailureReceiptId,
        first_failure_index: firstFailureIndex,
        results: results
      };
    }

    return Object.freeze({
      VERSION: 1,
      canonicalJSON: canonicalJSON,
      sha256Hex: sha256Hex,
      payloadMaterial: payloadMaterial,
      computePayloadHash: computePayloadHash,
      validateReceipt: function (receipt) {
        return _receiptErrors(receipt).slice();
      },
      verifySession: verifySession
    });
  }
);
