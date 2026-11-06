# Shared alert relay Worker

This Worker restores `ntfy.a11oy.net` as the receiving edge for the shared
receipt-failure channel. It forwards to the real `ntfy.sh` provider while
keeping the managed secret's opaque path at the controlled edge. A deterministic
240-bit SHA-256 prefix converts that path into an ntfy-safe topic; query behavior
is preserved, and the same mapping supports JSON, SSE, raw, and WebSocket
subscriptions through the custom domain.

The relay has no secret binding and its own code never logs the inbound path.
Platform logging is a separate setting: since commit `042f5f54` (2026-10-10)
`wrangler.jsonc` enables persisted Workers invocation logs at a sampling rate
of 1, matching the live Worker. Cloudflare's Workers Logs record each fetch
invocation as `<method> <URL>`, and `redact_query_string` redacts only the query,
so the opaque path is retained in the account's Workers Logs for their
retention window. Native ntfy request bodies stream through unchanged.
Slack-compatible JSON with a non-empty `text` field is bounded to 64 KiB and
translated to `text/plain`, which keeps the older receipt and health workflows
compatible with the ntfy channel.

Safety properties:

- upstream origin is fixed to `https://ntfy.sh` and redirects are not followed;
- arbitrary legacy paths become one provider-safe, non-reversible topic;
- cookies and Cloudflare forwarding metadata are not sent upstream;
- write requests require a topic path;
- malformed or oversized JSON fails before delivery;
- the real upstream response status and body are preserved;
- transport errors return HTTP 502, never a synthetic 2xx;
- one reserved read-only path, `GET /.well-known/szl-worker-revision`, answers
  `{"worker": "szl-alert-relay", "source_revision": "<40-hex or null>"}` from
  the `SOURCE_REVISION` var; it is never relayed and any other method on it is
  405, so it cannot answer a publish with a 2xx.

## Deployed copy vs source (read back 2026-11-06)

- The live script (`last_deployed_from: quick_editor`, modified
  2026-10-10T13:46:22Z) is byte-for-byte the `src/index.mjs` of commit
  `b3f15605` (#1561, 2026-08-30). It forwards the inbound path unchanged, so it
  lacks the provider-safe topic derivation from #1851 (2026-09-04).
- The live observability settings already equal `wrangler.jsonc` here; the
  only deployed setting the source lacked was `compatibility_date`
  `2026-08-31` (source said `2026-08-30`). The source now declares `2026-08-31`
  so the next deploy changes code, not runtime semantics.
- CI never deployed this Worker: every push run of `alert-relay-worker.yml`
  since 2026-09-02 failed in its deploy job, first with "No Cloudflare API
  token is configured", and from 2026-10-03 with the zone-lookup account
  preflight returning HTTP 403 (the token cannot read zones). The workflow now
  takes the account ID from the `CLOUDFLARE_ACCOUNT_ID` secret and reads no zone.

Deploying the current source changes the upstream topic for a given inbound
path from the raw path to `szl_<first 60 hex of SHA-256(path)>`. Publishers
using `https://ntfy.a11oy.net/<path>` need no change. A subscriber that reads
`ntfy.sh/<raw path>` directly will stop receiving; subscribe through the relay
instead (`https://ntfy.a11oy.net/<same path>/json`, `/sse`, `/raw`, or `/ws`
map to the same derived topic) or to the derived `ntfy.sh/szl_...` topic.

## Validate

```shell
cd ops/alert-relay-worker
npm ci --ignore-scripts
npm test         # node --test, 8 tests
npm run build    # wrangler deploy --dry-run with the locked Wrangler 4.150.0
```

The workflow also runs the Python contracts from the repository root:
`pytest tests/test_alert_channel_canary.py tests/test_alert_channel_static_registry_contract.py
tests/test_managed_alert_endpoint.py tests/test_managed_alert_transport_workflows.py
tests/test_verify_worker_revision.py tests/test_workers_compute_observability.py -q`.

## Deploy (GitOps)

`.github/workflows/alert-relay-worker.yml` deploys only from `main`, after the
test job, inside the `cloudflare-production` environment:

1. checks out exactly `github.sha` and installs Wrangler 4.150.0 from
   `package-lock.json` (Wrangler 4.128.0 dropped the declared
   `observability.issues` setting with a warning; 4.150.0 accepts it);
2. deploys with `cloudflare/wrangler-action` pinned to commit
   `9acf94ace14e7dc412b076f2c5c20b8ce93c79cd` (v3.15.0), injecting the full
   40-character SHA as `SOURCE_REVISION` and as the version message;
3. fails unless `https://ntfy.a11oy.net/.well-known/szl-worker-revision`
   reports that exact SHA (`scripts/verify_worker_revision.py`, which names an
   x402 `402` or a bot-management `403` challenge explicitly);
4. runs one protected `--send` canary through the managed endpoint and uploads
   its secret-free evidence. The canary's exit status fails the job.

Source tests and CI do not constitute delivery evidence; only the workflow's
bounded POST returning 2xx may record `HEALTHY` and close issue 541.

## Owner actions (the agent that wrote this has no Cloudflare credentials)

1. GitHub → `szl-holdings/a11oy` → Settings → Environments → create
   `cloudflare-production` with required reviewers and deployment branches
   limited to `main`. (The previous job used the `production` environment; its
   `CLOUDFLARE_API_TOKEN` lacked zone read access and is no longer used here.)
2. Environment secrets:
   - `CLOUDFLARE_ACCOUNT_ID`: the 32-hex account ID.
   - `CLOUDFLARE_API_TOKEN`: custom token with **Account → Workers Scripts →
     Edit** and **Account → Account Settings → Read**, limited to this account,
     with no zone or user permissions. Cloudflare's published API schema lists
     Workers Scripts Write as the permission for attaching Worker Custom
     Domains; Wrangler uses the script-scoped variant of that endpoint, which is
     not in the published schema (unverified). If the deploy step fails at the
     custom-domain stage with an authentication error, add only **Zone →
     Workers Routes → Edit** scoped to `a11oy.net`.
   - `SLACK_WEBHOOK_URL` stays the existing repository secret used by every
     alert workflow; no change.
3. Add the WAF skip rule below, otherwise GitHub-hosted runners (curl and
   Python clients with datacenter IPs) receive a Super Bot Fight Mode managed
   challenge (`403`, `cf-mitigated: challenge`) and both the readback and every
   alert POST fail. Keep `ntfy.a11oy.net` out of every Monetization Gateway
   rule (as of the coordinator's 2026-11-06 17:00Z change, the a11oy.net
   verified-bot rules are disabled and the URL scanner saw `200` here).

### WAF skip rule for `a11oy.net` (not applied by this change)

Security → WAF → Custom rules → Create rule, zone `a11oy.net`:

- Name: `Skip bot challenge: alert relay machine clients (opaque topic path is the credential)`
- Expression:

  ```text
  (http.host eq "ntfy.a11oy.net" and http.request.uri.path ne "/" and http.request.method in {"GET" "HEAD" "POST" "PUT"})
  ```

- Action: **Skip** → *All Super Bot Fight Mode rules*, *Browser Integrity
  Check*, *Security Level*. Leave *All remaining custom rules* and managed
  rules unticked so the existing scanner-probe block rule and the managed
  rulesets still apply.
- API form (same parameters as the existing HQ Vigil skip rule on
  `a-11-oy.com`):
  `{"action": "skip", "action_parameters": {"phases": ["http_request_sbfm"], "products": ["bic", "securityLevel"]}, "expression": "<above>", "enabled": true}`

Machine clients this covers, from code. Sixteen other workflows consume
`SLACK_WEBHOOK_URL`, which `scripts/managed_alert_env.sh` normalizes to
`https://ntfy.a11oy.net/<opaque path>`: fifteen POST Slack-compatible JSON with
`curl -X POST -H 'Content-Type: application/json'` (directly or through
`scripts/weight_guard_alert.sh`), and `alert-channel-watch.yml` runs
`scripts/alert_channel_canary.py` (`User-Agent: szl-alert-channel-canary/2`),
as does this workflow's post-deploy canary. The deploy readback sends
`GET /.well-known/szl-worker-revision` with `User-Agent:
szl-worker-revision-readback/1`. `GET /` (ntfy's web page) stays challenged.
