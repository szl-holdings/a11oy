# Controlled email credential repair

This manual procedure repairs only the `API_SECRET` binding on
`szl-email-sender` at
`https://szl-email-sender.stephenlutar2.workers.dev`.
It sends no email, creates no recipient payload, and changes no routes, DNS,
Access policy, publisher, or other binding.

The motivating diagnostic was the canonical deployment
[44001119761](https://github.com/szl-holdings/a11oy/actions/runs/44001119761):
the Worker reported its expected source, all three non-secret readiness checks
passed, and `secret_requirement_met` was false. This predicate does not
distinguish an absent, non-string, or insufficient-length runtime secret. Named
secret metadata alone does not prove the value is usable.

## Custody and admission

Use the protected `cloudflare-production` environment secret
`EMAIL_SENDER_API_SECRET_V2`. Its value must be exactly 64 URL-safe ASCII
characters, generated from 48 random bytes by the separately reviewed custody
procedure. Do not paste it into a workflow input, command argument, issue, log,
artifact, or repository file. The repair consumes the environment secret in
memory and never retrieves the previous value or records a value hash or length.

The initial incident's separately observed deployment identities were:

| Field | Observed identity |
| --- | --- |
| Served source | `d64a597e6ded40eee71efbc58cb14eaf6f1fd2e0` |
| Canonical Cloudflare version | `21f0205b-6363-4f2b-851b-ccbdb8b657e0` |
| Canonical run / job | `44001119761 / 133765370492` |
| Worker origin | `https://szl-email-sender.stephenlutar2.workers.dev` |

These are incident evidence, not permanent defaults. Before any execution, obtain
the exact current revision and version from the reviewed canonical deployment
record. A changed version, split deployment, or unknown origin is a stop condition.

The workflow is `.github/workflows/email-sender-secret-repair.yml`.
It accepts only `workflow_dispatch` on `main`, uses the protected
environment, and shares the existing `deploy-szl-email-sender` job
concurrency group with normal email deployments. It does not change or trigger
the existing email or alert-relay deployment path filters. The concurrency group
serializes cooperating GitHub jobs; it does not lock the Cloudflare dashboard or
other API clients.

The workflow needs the existing Cloudflare API token with Worker metadata read
and secret-write permissions, and a read-only GitHub token for protected-main
and immutable source checks. A configured 32-hex account ID is accepted;
otherwise exactly one account must be returned by a single bounded discovery
request. The authenticated account's Workers subdomain must match the fixed host.

## Reviewed execution sequence

1. Merge the reviewed four-file patch through normal repository checks. Complete
   the separately reviewed one-time custody seeding procedure without exposing
   the replacement value.
2. Dispatch the workflow on current `main` with
   `expected_deployed_revision`, `expected_version_id`, and
   `execute=false`. Inspect its value-free report. This mode performs no
   secret update. If the Worker is already ready it can make the same empty-body
   authentication probe described below; it never attempts mail delivery.
3. Review the current canonical source/version and the admission report, then
   dispatch one authorized execution with `execute=true`. The execution
   repeats all live checks; the earlier report is not reusable authorization or
   a cached precondition. A rerun of an existing execution
   (`GITHUB_RUN_ATTEMPT > 1`) is refused before any network request.
4. Read `receipt.jsonl` and `report.json` in the workflow
   artifact. Treat a persisted `PUT_INTENT` without a conclusive outcome
   as a possible submission. Do not retry the update to resolve uncertainty.

The helper distinguishes the workflow's current protected control commit from
the deployed Worker revision. It verifies the four reviewed Worker/configuration
files byte-for-byte against the immutable deployed GitHub revision. It requires
the complete binding set (`API_SECRET`, `MAIL_FROM`,
`SOURCE_REVISION`, `SEND_EMAIL`), their expected types and
non-secret values, compatible settings, named-secret metadata, the exact origin,
and the expected public revision.

The active deployment must contain exactly one 100% version. That version and
the latest uploaded version must both match the explicit expected version ID.
This refuses an undeployed newer version. Before writing, a second complete
observation must match the first, and protected `main` must still equal
the executing control commit. One original five-second window covers that final
observation, the source recheck, the intent flush/fsync, and request dispatch.
Slow reads or filesystem work do not renew the deadline.

Only then can the helper submit one
`PUT /accounts/{account}/workers/scripts/szl-email-sender/secrets`
with `name=API_SECRET`, `type=secret_text`, and the replacement
value. Proxies, redirects, automatic retries, alternate targets, and additional
mutation attempts are refused. Response bodies are bounded and validated;
untrusted response strings and exception text are never exported.

Cloudflare documents this secret update as creating a new version, and the
ordinary secret-put operation deploys immediately. The endpoint does not offer
a documented conditional version/CAS parameter. The observed version and
five-second dispatch bound therefore do **not** provide atomic exclusion against
another external writer or prove the exact instant of provider execution.
The prior deployment/version IDs are retained as recovery metadata. They are
not a promise that rolling back either ID restores the previous secret, and the
helper performs no rollback or separate deployment.

## What the outcomes mean

| Outcome | Meaning and next action |
| --- | --- |
| `READY_FOR_EXECUTION` | Read-only admission passed and only the secret predicate failed; no update was attempted. A later execution must repeat all checks. |
| `ALREADY_REPAIRED` | The Worker was already ready and authenticated the same protected replacement credential. No update was attempted. |
| `VERIFIED` | One update was acknowledged; one readiness GET matched the expected source and all four predicates; the controlled authentication probe passed. This is not delivery evidence. |
| `BLOCKED` | A precondition or local evidence operation failed before a network mutation attempt. Review the fixed diagnostic code and any intent record. |
| `WRITE_OUTCOME_UNCERTAIN` | A mutation attempt began but no valid acknowledgment was established. Stop; retain the receipt and inspect provider/runtime state separately. Do not repeat or replace the credential automatically. |
| `ACKNOWLEDGED_NOT_VERIFIED` | Cloudflare acknowledged the update, but a readback, authentication, or evidence step failed. Stop without another update; propagation delay can also produce this state. |

After a valid acknowledgment there is exactly one readiness GET. Only a response
with the unchanged expected source and all four true predicates admits the auth
probe: an empty `POST /send`, bearer replacement credential, and
`Content-Type: application/octet-stream`. The reviewed handler checks
configuration and authentication before content type, then returns exactly
`415 {"error":"unsupported_media_type"}` before message ID creation,
body parsing, MIME construction, or `SEND_EMAIL.send`. The helper requires
that exact JSON response, not an arbitrary edge-generated 415.

The report preserves attempted, acknowledged, readiness, and authentication
flags independently. A timeout or broken response never becomes a claim that
nothing changed. The fsynced intent is also printed before submission so that a
process interruption still leaves a value-free possible-submission marker in
the GitHub log. Artifact-upload failure does not erase that uncertainty.

No existing external caller or recipient has been identified by this repair.
Future and external consumers need controlled access to the protected
replacement custody; this procedure does not establish their credential
agreement or prove end-to-end email delivery.

## Offline verification

Run from the repository root:

```text
python -B -m unittest discover -s tests -p test_email_sender_secret_repair.py -v
```

The suite uses in-memory provider fixtures and blocks real socket connections.
It exercises identity/binding drift, the exact active/latest version binding,
deadline expiry after the final main read or intent fsync, one-write enforcement,
uncertain outcomes, value-free evidence, credential separation, the controlled
probe, and workflow trigger isolation. It does not use production credentials,
Cloudflare writes, a remote collector, or an email recipient.

## Primary protocol references

- [Update Worker secret](https://developers.cloudflare.com/api/resources/workers/subresources/scripts/subresources/secrets/methods/update/): fixed secret PUT schema and new-version behavior.
- [Worker secrets](https://developers.cloudflare.com/workers/configuration/secrets/): immediate deployment for ordinary secret put, contrasted with version-only upload.
- [List deployments](https://developers.cloudflare.com/api/resources/workers/subresources/scripts/subresources/deployments/methods/list/): latest serving deployment first and percentage/version schema.
- [List versions](https://developers.cloudflare.com/api/resources/workers/subresources/scripts/subresources/versions/methods/list/): latest version first, with `result.items`.
- [Get Worker settings](https://developers.cloudflare.com/api/resources/workers/subresources/scripts/subresources/script_and_version_settings/methods/get/): settings and binding metadata.
- [Get named secret](https://developers.cloudflare.com/api/resources/workers/subresources/scripts/subresources/secrets/methods/get/): secret metadata with value omitted.
- [Get account Workers subdomain](https://developers.cloudflare.com/api/resources/workers/subresources/subdomains/methods/get/): authenticated account-to-origin binding.
