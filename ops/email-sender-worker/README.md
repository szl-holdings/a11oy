<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# szl-email-sender Worker

`szl-email-sender` is one authenticated, server-to-server endpoint that sends a
single plain-text message from `betterwithage@a-11-oy.com` through the Cloudflare
Email Routing `send_email` binding. This directory is now its source of record;
before 2026-11-06 the Worker existed only in the Cloudflare account.

## Why it was rewritten

The copy deployed on 2026-11-05 (read back 2026-11-06, no source in GitHub) could
not send mail and had two auth defects:

| Deployed behaviour | Problem | This source |
|---|---|---|
| `new EmailMessage(from, to, subject)` then `msg.append(body)` | `EmailMessage` was never imported from `cloudflare:email`, and the runtime constructor is `new EmailMessage(from, to, raw)` where `raw` is a complete RFC 5322 message; there is no `append`. | `src/index.mjs` imports the class; `src/mime.mjs` builds the raw message. |
| `authHeader !== 'Bearer ' + env.API_SECRET` | Timing-dependent comparison; with the secret unset it accepts `Bearer undefined`. | SHA-256 digests compared in constant time; a missing or short (< 32 characters) secret fails closed with 503. |
| `Access-Control-Allow-Origin: *` | Invites browser callers, which would have to hold the bearer secret. | No CORS headers at all; `OPTIONS` is 405. |
| `subject`/`to` passed through unchecked | Header injection (`\r\nBcc:`) and multi-recipient strings. | Strict validation; CR, LF and all control characters rejected. |

No caller of this Worker was found: on 2026-11-06 the 154 `szl-holdings`
repository clones and the Hugging Face Space cards were searched for
`szl-email-sender`, `email-sender`, `workers.dev`, `SEND_EMAIL`, and
`cloudflare:email`, and only unrelated UI category labels matched. Space
application code that is not mirrored in a GitHub repository was not
searchable. CORS therefore stays off.

## API

`POST /send` (the deployed root path `POST /` is kept as an alias)

```http
POST /send HTTP/1.1
Authorization: Bearer <API_SECRET>
Content-Type: application/json

{"to": "owner@example.org", "subject": "Receipt guard failed", "body": "Details..."}
```

| Status | Body |
|---|---|
| 200 | `{"success": true, "to": "...", "message_id": "<uuid@a-11-oy.com>"}` |
| 400 | `{"error": "invalid_json" \| "invalid_encoding" \| "unknown_field" \| "missing_field" \| "invalid_to" \| "invalid_subject" \| "invalid_body"}` |
| 401 | `{"error": "unauthorized"}` (with `WWW-Authenticate: Bearer`) |
| 404 / 405 | `{"error": "not_found"}` / `{"error": "method_not_allowed"}` (with `Allow`) |
| 413 / 415 | `{"error": "payload_too_large"}` / `{"error": "unsupported_media_type"}` |
| 502 | `{"error": "send_failed"}` — the binding refused or failed; nothing claims delivery |
| 503 | `{"error": "not_configured"}` — secret, binding, or sender unusable |

`GET /.well-known/szl-worker-revision` (no auth, no secret material):
`{"worker": "szl-email-sender", "source_revision": "<40-hex or null>", "ready": true|false}`.
The deploy workflow reads this back.

Limits: the request body is at most 64 KiB; `to` is one bare ASCII addr-spec
(no display name, no list, no quoted local part, no IP literal, at most 254
characters); `subject` is 1-200 characters with no control characters; `body`
is 1 byte to 32 KiB of well-formed UTF-8 text.

## Message construction (`src/mime.mjs`)

Headers, in order, CRLF line endings: `From` (the configured sender, equal to the
envelope sender), `To` (equal to the envelope recipient), `Subject` (verbatim
when printable ASCII, otherwise RFC 2047 `=?UTF-8?B?...?=` words of at most 75
characters split on code-point boundaries and folded), `Date` (RFC 5322, UTC),
`Message-ID` (`<uuid@a-11-oy.com>`), `MIME-Version: 1.0`,
`Content-Type: text/plain; charset=utf-8`, `Content-Transfer-Encoding: base64`,
`Auto-Submitted: auto-generated`. The body is CRLF-normalized UTF-8 in
76-character base64 lines.

The sender comes from the `MAIL_FROM` var in `wrangler.toml` and must be an
address on `a-11-oy.com`, the zone whose Email Routing is enabled; anything else
leaves the Worker `not_configured`. Email Routing delivers only to destination
addresses verified on the account; add `allowed_destination_addresses` to the
`[[send_email]]` block to narrow that further.

## Validate

```shell
cd ops/email-sender-worker
npm ci --ignore-scripts
npm test              # 19 unit tests, mocked SEND_EMAIL binding
npm run build         # wrangler deploy --dry-run: bundles the exact upload
npm run test:workerd  # runs that bundle in workerd with the local send_email binding
```

`npm run check` runs all three. `test:workerd` uses Wrangler's own test harness
with this `wrangler.toml`: workerd supplies the real `cloudflare:email` class
and the local `send_email` binding parses the raw message (it rejects a missing
`Message-ID` or a `From` that differs from the envelope sender). The test then
reads the stored `.eml` and checks headers, the decoded subject, and the body.
The post-deploy readback CLI is tested from the repository root with
`python -m pytest tests/test_verify_worker_revision.py`.

## Deploy (GitOps)

`.github/workflows/email-sender-worker.yml` runs the tests above on every pull
request and push that touches this directory. On a push to `main` (or a manual
`workflow_dispatch` on `main`) the `deploy` job, gated by the
`cloudflare-production` environment:

1. checks out exactly `github.sha` and installs Wrangler 4.150.0 from the lockfile;
2. deploys with `cloudflare/wrangler-action` pinned to commit
   `9acf94ace14e7dc412b076f2c5c20b8ce93c79cd` (v3.15.0), injecting the full
   40-character SHA as the `SOURCE_REVISION` var and as the version message;
3. fails unless `https://szl-email-sender.<account>.workers.dev/.well-known/szl-worker-revision`
   reports that exact SHA with `ready: true`.

`workers_dev = true` is the only public entry point (no zone route, no custom
domain, no preview URLs). workers.dev is not behind the `a-11-oy.com` zone's
bot settings, so the readback needs no WAF change.

## Owner actions (the agent that wrote this has no Cloudflare credentials)

1. GitHub → `szl-holdings/a11oy` → Settings → Environments → create
   `cloudflare-production`; add required reviewers and limit deployment
   branches to `main`.
2. Add two environment secrets:
   - `CLOUDFLARE_ACCOUNT_ID`: the 32-hex account ID shown in the Cloudflare dashboard.
   - `CLOUDFLARE_API_TOKEN`: a custom API token with exactly **Account → Workers
     Scripts → Edit** and **Account → Account Settings → Read**, account
     resources limited to this one account, and no zone or user permissions.
3. Keep the existing Worker secret `API_SECRET`, but only if it is at least 32
   characters. A shorter value makes the new code answer 503 and the deploy
   readback fail with `NOT_READY`. To rotate, generate a value (for example
   `openssl rand -base64 48`), store it wherever a caller keeps its secrets,
   and set it from this directory with `npx wrangler secret put API_SECRET`.
4. Merge, then confirm the `Deploy szl-email-sender and read back the live
   revision` job is green.

## Proof boundary

The tests prove the request contract, header-injection resistance, constant-time
bearer comparison, fail-closed configuration, and that workerd and Wrangler's
local `send_email` simulation accept the constructed message. They do **not**
prove delivery through Cloudflare Email Routing, DKIM/DMARC alignment at a
receiving server, or inbox placement; no message has been sent to a real
mailbox from this source. Until the owner completes the actions above and a
push to `main` deploys it, the live Worker is still the broken copy described
in "Why it was rewritten".
