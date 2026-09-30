#!/usr/bin/env node
// SPDX-License-Identifier: Apache-2.0
// (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"use strict";

import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const receiptV1 = require("../static/shared/puriq_receipt_v1.js");
const here = path.dirname(fileURLToPath(import.meta.url));
const repositoryRoot = path.resolve(here, "..");
const vectorPath = path.join(
  repositoryRoot,
  "tests",
  "fixtures",
  "puriq-receipt-v1-vectors.json"
);
const ZERO_HASH = "0".repeat(64);

function uuidV4FromInteger(value) {
  return `00000000-0000-4000-8000-${String(value).padStart(12, "0")}`;
}

async function normalizedRecordHash(sequence) {
  return receiptV1.sha256Hex(`official-record-${sequence}`);
}

async function makeSession(count, sessionId, receiptIdOffset) {
  const receipts = [];
  let previous = "GENESIS";
  for (let sequence = 0; sequence < count; sequence += 1) {
    const receipt = {
      receipt_version: 1,
      receipt_id: uuidV4FromInteger(receiptIdOffset + sequence),
      issued_at: new Date(Date.UTC(2026, 8, 4, 16, 0, sequence)).toISOString(),
      session_id: sessionId,
      sequence,
      prev_receipt_hash: previous,
      subject: {
        normalized_record_hash: await normalizedRecordHash(receiptIdOffset + sequence),
        source_record_id: `official-record-${receiptIdOffset + sequence}`,
        parser_version: "1.0.0"
      },
      ranking_inputs: {
        source_path: ["official-records:reference"],
        reasons: [
          {
            code: "reference-signal",
            direction: sequence % 2 === 0 ? "up" : "down",
            weight: sequence % 2 === 0 ? 1 : 0.5,
            detail: "Deterministic conformance vector"
          }
        ],
        confidence: {
          low: 0.5,
          high: 0.9
        },
        caveats: ["Reference data only"]
      },
      gate: {
        name: "yuyay-13",
        result: "pass",
        failures: []
      },
      payload_hash: ZERO_HASH,
      signature: {
        algorithm: "HMAC-SHA256",
        key_id: null,
        value: "UNSIGNED"
      }
    };
    receipt.payload_hash = await receiptV1.computePayloadHash(receipt);
    receipts.push(receipt);
    previous = receipt.payload_hash;
  }
  return receipts;
}

function expected(valid, receiptCount, firstFailureReceiptId) {
  return {
    valid,
    receipt_count: receiptCount,
    first_failure_receipt_id: firstFailureReceiptId
  };
}

async function buildVectors() {
  const single = await makeSession(
    1,
    "10000000-0000-4000-8000-000000000001",
    1
  );
  const hundred = await makeSession(
    100,
    "20000000-0000-4000-8000-000000000002",
    1000
  );
  const broken = await makeSession(
    3,
    "30000000-0000-4000-8000-000000000003",
    2000
  );
  broken[1].prev_receipt_hash = ZERO_HASH;
  const unsigned = await makeSession(
    2,
    "40000000-0000-4000-8000-000000000004",
    3000
  );
  const interoperable = await makeSession(
    1,
    "50000000-0000-4000-8000-000000000005",
    4000
  );
  interoperable[0].ranking_inputs.reasons[0].weight = 1e-7;
  interoperable[0].ranking_inputs.reasons[0].detail = "Unicode: café, 😀, \uE000; no normalization";
  interoperable[0].ranking_inputs.confidence = { low: 1e-6, high: 1 };
  interoperable[0].payload_hash = await receiptV1.computePayloadHash(interoperable[0]);
  const canonicalValue = {
    "\uE000": "private-use",
    "\u{1F600}": "astral",
    values: [-0, 1.0, 1e-7, 1e-6, 1e20, 1e21],
    unicode: "café\n\"\\\u2028"
  };
  const canonical = receiptV1.canonicalJSON(canonicalValue);

  return {
    license: "SPDX-License-Identifier: Apache-2.0; (c) 2026 Lutar, Stephen P. - SZL Holdings",
    vector_version: 1,
    canonical_vectors: [{ value: canonicalValue, canonical, sha256: await receiptV1.sha256Hex(canonical) }],
    vectors: [
      {
        name: "empty_session",
        receipts: [],
        expected: expected(true, 0, null)
      },
      {
        name: "single_receipt_session",
        receipts: single,
        expected: expected(true, 1, null)
      },
      {
        name: "hundred_receipt_session",
        receipts: hundred,
        expected: expected(true, 100, null)
      },
      {
        name: "chain_broken_session",
        receipts: broken,
        expected: expected(false, 3, broken[1].receipt_id)
      },
      {
        name: "unsigned_session",
        receipts: unsigned,
        expected: expected(true, 2, null)
      },
      {
        name: "unicode_numeric_session",
        receipts: interoperable,
        expected: expected(true, 1, null)
      }
    ]
  };
}

async function main() {
  const rendered = `${JSON.stringify(await buildVectors(), null, 2)}\n`;
  if (process.argv.includes("--check")) {
    if (!fs.existsSync(vectorPath)) {
      throw new Error(`missing generated vector file: ${vectorPath}`);
    }
    const current = fs.readFileSync(vectorPath, "utf8");
    if (current !== rendered) {
      throw new Error(
        "PurIQ v1 vectors are stale; run generate_puriq_receipt_v1_vectors.mjs --write"
      );
    }
    process.stdout.write("PurIQ v1 vectors are current\n");
    return;
  }
  if (process.argv.includes("--write")) {
    fs.mkdirSync(path.dirname(vectorPath), { recursive: true });
    fs.writeFileSync(vectorPath, rendered, "utf8");
    process.stdout.write(`wrote ${vectorPath}\n`);
    return;
  }
  process.stdout.write(rendered);
}

main().catch((error) => {
  process.stderr.write(`${error.stack || error.message}\n`);
  process.exitCode = 1;
});
