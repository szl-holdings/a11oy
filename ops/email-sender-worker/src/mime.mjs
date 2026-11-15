// SPDX-License-Identifier: Apache-2.0
// (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
//
// RFC 5322 / RFC 2045 / RFC 2047 construction for one plain-text message.
//
// Every value that reaches a header is validated first: addresses must be a
// single bare ASCII addr-spec and the subject must not contain CR, LF or any
// other control character, so a caller cannot add headers (header injection)
// or recipients. The body is UTF-8, CRLF-normalized and base64-encoded, so
// every body line is short, has no bare CR or LF, and never starts with a dot.

const CRLF = "\r\n";
const BASE64_LINE = 76;
// "=?UTF-8?B?" + "?=" is 12 characters; 45 bytes encode to 60 base64
// characters, so every encoded-word stays within RFC 2047's 75-character cap.
const ENCODED_WORD_BYTES = 45;

export const MAX_ADDRESS_LENGTH = 254;
export const MAX_SUBJECT_CHARS = 200;
export const MAX_BODY_BYTES = 32 * 1024;

const LOCAL_PART = /^[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+)*$/;
const DOMAIN_LABEL = /^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$/;
// C0 controls, DEL and the C1 range never belong in a header value.
const HEADER_CONTROL = /[\u0000-\u001f\u007f-\u009f]/;
const PRINTABLE_ASCII = /^[ -~]*$/;

export class MessageInputError extends Error {
  constructor(code) {
    super(code);
    this.name = "MessageInputError";
    this.code = code;
  }
}

/** Returns the lower-cased domain of a validated bare addr-spec, else throws. */
export function assertAddress(value, code = "invalid_address") {
  if (typeof value !== "string" || value.length === 0 || value.length > MAX_ADDRESS_LENGTH) {
    throw new MessageInputError(code);
  }
  const at = value.lastIndexOf("@");
  if (at <= 0 || at !== value.indexOf("@")) {
    throw new MessageInputError(code);
  }
  const local = value.slice(0, at);
  const domain = value.slice(at + 1);
  if (local.length > 64 || !LOCAL_PART.test(local)) {
    throw new MessageInputError(code);
  }
  const labels = domain.split(".");
  if (domain.length > 253 || labels.length < 2 || !labels.every((label) => DOMAIN_LABEL.test(label))) {
    throw new MessageInputError(code);
  }
  if (/^[0-9]+$/.test(labels[labels.length - 1])) {
    throw new MessageInputError(code);
  }
  return domain.toLowerCase();
}

export function assertSubject(value) {
  if (typeof value !== "string" || value.trim() === "" || !value.isWellFormed()) {
    throw new MessageInputError("invalid_subject");
  }
  if ([...value].length > MAX_SUBJECT_CHARS || HEADER_CONTROL.test(value)) {
    throw new MessageInputError("invalid_subject");
  }
  return value;
}

export function assertBody(value) {
  if (typeof value !== "string" || value.trim() === "" || !value.isWellFormed()) {
    throw new MessageInputError("invalid_body");
  }
  if (value.includes("\u0000") || new TextEncoder().encode(value).byteLength > MAX_BODY_BYTES) {
    throw new MessageInputError("invalid_body");
  }
  return value;
}

function bytesToBase64(bytes) {
  let binary = "";
  for (let offset = 0; offset < bytes.length; offset += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(offset, offset + 0x8000));
  }
  return btoa(binary);
}

/** RFC 2047 "B" encoded-words, split only on code-point boundaries. */
export function encodeHeaderText(text) {
  if (PRINTABLE_ASCII.test(text) && !text.includes("=?")) {
    return text;
  }
  const encoder = new TextEncoder();
  const words = [];
  let chunk = [];
  let chunkBytes = 0;
  for (const character of text) {
    const size = encoder.encode(character).byteLength;
    if (chunkBytes + size > ENCODED_WORD_BYTES) {
      words.push(chunk.join(""));
      chunk = [];
      chunkBytes = 0;
    }
    chunk.push(character);
    chunkBytes += size;
  }
  if (chunk.length > 0) {
    words.push(chunk.join(""));
  }
  return words
    .map((word) => `=?UTF-8?B?${bytesToBase64(encoder.encode(word))}?=`)
    .join(`${CRLF} `);
}

export function encodeBody(text) {
  const normalized = text.replace(/\r\n?/g, "\n").split("\n").join(CRLF);
  const encoded = bytesToBase64(new TextEncoder().encode(normalized));
  const lines = [];
  for (let offset = 0; offset < encoded.length; offset += BASE64_LINE) {
    lines.push(encoded.slice(offset, offset + BASE64_LINE));
  }
  return lines.join(CRLF);
}

/** RFC 5322 date-time in UTC, e.g. "Fri, 06 Nov 2026 16:20:00 +0000". */
export function formatDate(date) {
  if (!(date instanceof Date) || Number.isNaN(date.getTime())) {
    throw new MessageInputError("invalid_date");
  }
  return date.toUTCString().replace(/ GMT$/, " +0000");
}

/**
 * Build the raw message handed to `new EmailMessage(from, to, raw)`.
 * The envelope sender and recipient must equal the From and To headers.
 */
export function buildMimeMessage({ from, to, subject, body, date, messageId }) {
  const senderDomain = assertAddress(from, "invalid_from");
  assertAddress(to, "invalid_to");
  assertSubject(subject);
  assertBody(body);
  if (typeof messageId !== "string" || !/^[A-Za-z0-9-]{1,64}$/.test(messageId)) {
    throw new MessageInputError("invalid_message_id");
  }
  const headers = [
    `From: ${from}`,
    `To: ${to}`,
    `Subject: ${encodeHeaderText(subject)}`,
    `Date: ${formatDate(date)}`,
    `Message-ID: <${messageId}@${senderDomain}>`,
    "MIME-Version: 1.0",
    "Content-Type: text/plain; charset=utf-8",
    "Content-Transfer-Encoding: base64",
    "Auto-Submitted: auto-generated",
  ];
  return `${headers.join(CRLF)}${CRLF}${CRLF}${encodeBody(body)}${CRLF}`;
}
