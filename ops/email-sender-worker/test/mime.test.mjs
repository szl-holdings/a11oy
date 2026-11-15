// SPDX-License-Identifier: Apache-2.0
// (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173

import assert from "node:assert/strict";
import test from "node:test";

import {
  MAX_BODY_BYTES,
  MAX_SUBJECT_CHARS,
  MessageInputError,
  assertAddress,
  buildMimeMessage,
  encodeHeaderText,
  formatDate,
} from "../src/mime.mjs";

const BASE = {
  from: "betterwithage@a-11-oy.com",
  to: "owner@example.org",
  subject: "Receipt guard failed",
  body: "line one\nline two",
  date: new Date(Date.UTC(2026, 10, 6, 16, 20, 0)),
  messageId: "6f1d1c2e-1111-4a4a-9b9b-0123456789ab",
};

// A deliberately small RFC 5322 reader: unfolds headers and decodes the
// "B" encoded-words and base64 body this builder emits.
function parse(raw) {
  const split = raw.indexOf("\r\n\r\n");
  assert.notEqual(split, -1, "header/body separator missing");
  const head = raw.slice(0, split);
  const headers = new Map();
  for (const line of head.replace(/\r\n /g, " ").split("\r\n")) {
    const colon = line.indexOf(":");
    assert.ok(colon > 0, `malformed header line ${JSON.stringify(line)}`);
    const name = line.slice(0, colon).toLowerCase();
    assert.equal(headers.has(name), false, `duplicate header ${name}`);
    headers.set(name, line.slice(colon + 1).trim());
  }
  const body = Buffer.from(raw.slice(split + 4).replace(/\r\n/g, ""), "base64").toString("utf8");
  return { head, headers, body };
}

function decodeWords(value) {
  return value
    .split(" ")
    .map((word) => {
      const match = /^=\?UTF-8\?B\?([A-Za-z0-9+/=]+)\?=$/.exec(word);
      return match ? Buffer.from(match[1], "base64").toString("utf8") : word;
    })
    .join("");
}

function rejects(fields, code) {
  assert.throws(
    () => buildMimeMessage({ ...BASE, ...fields }),
    (error) => error instanceof MessageInputError && error.code === code,
  );
}

test("builds one RFC 5322 message whose headers match the envelope", () => {
  const raw = buildMimeMessage(BASE);
  const { headers, body } = parse(raw);
  assert.deepEqual([...headers.keys()], [
    "from",
    "to",
    "subject",
    "date",
    "message-id",
    "mime-version",
    "content-type",
    "content-transfer-encoding",
    "auto-submitted",
  ]);
  assert.equal(headers.get("from"), BASE.from);
  assert.equal(headers.get("to"), BASE.to);
  assert.equal(headers.get("subject"), BASE.subject);
  assert.equal(headers.get("date"), "Fri, 06 Nov 2026 16:20:00 +0000");
  assert.equal(headers.get("message-id"), `<${BASE.messageId}@a-11-oy.com>`);
  assert.equal(headers.get("mime-version"), "1.0");
  assert.equal(headers.get("content-type"), "text/plain; charset=utf-8");
  assert.equal(headers.get("content-transfer-encoding"), "base64");
  assert.equal(headers.get("auto-submitted"), "auto-generated");
  assert.equal(body, "line one\r\nline two");
  assert.equal(/\r(?!\n)/.test(raw), false, "bare CR anywhere");
  assert.equal(/(^|[^\r])\n/.test(raw), false, "bare LF anywhere");
  assert.ok(raw.endsWith("\r\n"));
});

test("UTF-8 subjects become RFC 2047 encoded-words split on code points", () => {
  const subject = `Alerta: recibo fallido ✅ ${"🔐".repeat(30)} – Ñandú`;
  const raw = buildMimeMessage({ ...BASE, subject, body: "Señal recibida 📡" });
  const { headers, body } = parse(raw);
  const encoded = headers.get("subject");
  for (const word of encoded.split(" ")) {
    assert.match(word, /^=\?UTF-8\?B\?[A-Za-z0-9+/=]+\?=$/);
    assert.ok(word.length <= 75, `encoded-word too long: ${word.length}`);
    const decoded = Buffer.from(word.slice(10, -2), "base64");
    // A split inside a multi-byte sequence would decode to U+FFFD.
    assert.equal(decoded.toString("utf8").includes("�"), false);
  }
  assert.equal(decodeWords(encoded), subject);
  assert.equal(body, "Señal recibida 📡");
  for (const line of raw.split("\r\n")) {
    assert.ok(line.length <= 998, "line exceeds the RFC 5322 hard limit");
  }
});

test("ASCII text that looks like an encoded-word is itself encoded", () => {
  assert.equal(encodeHeaderText("plain subject"), "plain subject");
  const tricky = "=?UTF-8?B?Zm9v?= literal";
  const encoded = encodeHeaderText(tricky);
  assert.notEqual(encoded, tricky);
  assert.equal(decodeWords(encoded.replace(/\r\n /g, " ")), tricky);
});

test("body line endings are normalized to CRLF and wrapped at 76 base64 characters", () => {
  const body = `a\rb\nc\r\nd\n.\n.dot line\n${"x".repeat(3000)}`;
  const raw = buildMimeMessage({ ...BASE, body });
  const encodedLines = raw.slice(raw.indexOf("\r\n\r\n") + 4).split("\r\n").filter(Boolean);
  for (const line of encodedLines) {
    assert.match(line, /^[A-Za-z0-9+/=]{1,76}$/);
  }
  assert.equal(parse(raw).body, `a\r\nb\r\nc\r\nd\r\n.\r\n.dot line\r\n${"x".repeat(3000)}`);
});

test("header injection through the recipient is impossible", () => {
  for (const to of [
    "owner@example.org\r\nBcc: attacker@example.net",
    "owner@example.org\nBcc: attacker@example.net",
    "owner@example.org\rBcc: attacker@example.net",
    "owner@example.org, attacker@example.net",
    "owner@example.org;attacker@example.net",
    "Owner <owner@example.org>",
    "\"quoted\"@example.org",
    "owner@example.org ",
    " owner@example.org",
    "owner@@example.org",
    "owner@example",
    "owner@[127.0.0.1]",
    "owner@127.0.0.1",
    ".owner@example.org",
    "owner.@example.org",
    "own..er@example.org",
    "owner@-example.org",
    "owner@example-.org",
    "ówner@example.org",
    `${"a".repeat(65)}@example.org`,
    `owner@${"a".repeat(250)}.org`,
    "",
    42,
    null,
  ]) {
    rejects({ to }, "invalid_to");
  }
});

test("header injection through the subject is impossible", () => {
  for (const subject of [
    "hello\r\nBcc: attacker@example.net",
    "hello\nBcc: attacker@example.net",
    "hello\rBcc: attacker@example.net",
    "tab\tinside",
    "nul\u0000inside",
    "del\u007finside",
    "c1\u0085inside",
    "lone \ud800 surrogate",
    "   ",
    "",
    "x".repeat(MAX_SUBJECT_CHARS + 1),
    ["array"],
  ]) {
    rejects({ subject }, "invalid_subject");
  }
  assert.doesNotThrow(() => buildMimeMessage({ ...BASE, subject: "é".repeat(MAX_SUBJECT_CHARS) }));
});

test("body limits and malformed text are rejected", () => {
  for (const body of ["", "  \n ", "nul\u0000byte", "lone \udc00 surrogate", "x".repeat(MAX_BODY_BYTES + 1), {}]) {
    rejects({ body }, "invalid_body");
  }
  assert.doesNotThrow(() => buildMimeMessage({ ...BASE, body: "x".repeat(MAX_BODY_BYTES) }));
});

test("sender, date and message identifier are validated", () => {
  rejects({ from: "Name <betterwithage@a-11-oy.com>" }, "invalid_from");
  rejects({ messageId: "id with space" }, "invalid_message_id");
  rejects({ messageId: "x>\r\nBcc: attacker@example.net" }, "invalid_message_id");
  assert.throws(() => formatDate(new Date(Number.NaN)), MessageInputError);
  assert.equal(assertAddress("Ops.Team+alerts@Example.ORG"), "example.org");
});
