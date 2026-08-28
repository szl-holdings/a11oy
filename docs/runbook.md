# SZL Holdings — On-Call Runbook

<!-- RETIRED-ORGANS-NOTICE -->
> **⚠️ Retired organs notice.** `amaru`, `sentra`, and `rosie` have been retired and consolidated into the **[a11oy](https://github.com/szl-holdings/a11oy)** flagship (Memory, Sentinel, and Operator verticals). Their standalone `szl-holdings/{amaru,sentra,rosie}` GitHub repositories and `szlholdings-{amaru,sentra,rosie}.hf.space` Hugging Face Spaces **no longer exist**; only the signed GHCR images persist, for supply-chain verification. Any amaru/sentra/rosie Space URLs, repo links, or endpoints referenced below are **historical and not live** — use a11oy instead.
**Doctrine v11 LOCKED 749/14/163 | SLSA L1 honest · L2 build-attested (Rekor) · L3+ roadmap | Generated: 2026-06-03**

## Quick Reference

| Flagship | Space URL | Lambda | Honest | Critical Endpoint |
|----------|-----------|--------|--------|-------------------|
| a11oy | https://szlholdings-a11oy.hf.space | /v1/lambda | /v1/honest | /api/a11oy/v4/fleet |
| sentra | https://szlholdings-sentra.hf.space | /api/sentra/v1/lambda | /api/sentra/v1/honest | /api/sentra/v1/verdict |
| amaru | https://szlholdings-amaru.hf.space | /api/amaru/v1/lambda | /api/amaru/v1/honest | /api/amaru/v1/brain |
| rosie | https://szlholdings-rosie.hf.space | /api/rosie/v1/lambda | /api/rosie/v1/honest | /api/rosie/v1/brain |
| killinchu | https://szlholdings-killinchu.hf.space | /api/killinchu/v1/lambda | /api/killinchu/v1/honest | /api/killinchu/v1/lambda |

## Incident Playbooks

### INC-01: HF Space is DOWN (not RUNNING)

**Symptoms:** Space stage = `BUILD_ERROR` or `STOPPED` or `APP_STARTING` for >5 min

**Diagnosis:**
```bash
curl -s https://huggingface.co/api/spaces/SZLHOLDINGS/<flagship>/runtime | python3 -c "import json,sys; print(json.load(sys.stdin))"
```

**Resolution steps:**
1. Check HF Space logs via https://huggingface.co/spaces/SZLHOLDINGS/<flagship>/logs
2. If BUILD_ERROR: Check recent commits for Dockerfile issues. Look for broken COPY lines.
3. If the error is `cache miss: [N/N] COPY --chown=user <file>`: file listed in Dockerfile does not exist in Space. Remove that COPY line.
4. Push a minimal fix commit via `huggingface_hub` (NOT the NDJSON API which is unreliable)
5. Wait 2-3 min for rebuild; verify `stage: RUNNING`
6. Run smoke test: `curl https://szlholdings-<flagship>.hf.space/api/<flagship>/v1/lambda`
7. If still failing after 2 rebuild attempts, file GitHub Issue with `incident` label

**Rollback:**
```bash
# Get previous good commit SHA from HF commit log
curl -s https://huggingface.co/api/spaces/SZLHOLDINGS/<flagship>/commits/main?limit=10
# Revert to good SHA via huggingface_hub
```

---

### INC-02: Endpoint returns 404 (regression)

**Symptoms:** Lambda, honest, or other CTO-signed endpoint returns 404

**Diagnosis:**
```bash
curl -sv https://szlholdings-<flagship>.hf.space/api/<flagship>/v1/lambda 2>&1 | tail -20
```

**Common causes:**
1. **HF race condition**: Multiple commits to same Space within 5 minutes caused file corruption
   - Check: `curl -s https://huggingface.co/api/spaces/SZLHOLDINGS/<flagship>/commits/main?limit=5`
   - Fix: Push the correct file content via `huggingface_hub.upload_file()`
2. **Import failure**: Module used by route fails to import, route never registers
   - Fix: Add try/except around import; check that module is COPY'd in Dockerfile
3. **Mount ordering**: Starlette `/api/<flagship>` mount shadows explicit routes
   - Fix: Register explicit routes BEFORE calling `app.mount("/api/<flagship>", ...)`

---

### INC-03: Doctrine violation in live response

**Symptoms:** `doctrine` field ≠ `v11`, `declarations` ≠ 749, or `sorries_total` ≠ 163

**Diagnosis:**
```bash
curl -s https://szlholdings-<flagship>.hf.space/api/<flagship>/v1/lambda | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('doctrine'), d.get('declarations'), d.get('sorries_total'))"
```

**Resolution:**
1. Identify the commit that introduced the violation via HF commit log
2. Check: is `DOCTRINE = "v10"` or any other non-v11 value in serve.py/app.py?
3. Fix: Update DOCTRINE constant; commit with DCO trailers
4. Push via GitHub → HF sync or `huggingface_hub.upload_file()`
5. CRITICAL: Never change `749/14/163` — these are LOCKED

---

### INC-04: GitHub Actions CI failing

**Symptoms:** Red check on main branch

**Diagnosis:**
```bash
gh run list --repo szl-holdings/<flagship> --limit 5
gh run view <run-id> --repo szl-holdings/<flagship> --log-failed
```

**Common CI failures:**
- `gitleaks`: Secret detected → do NOT push fix to public; rotate credential immediately
- `trivy/grype`: HIGH/CRITICAL CVE in base image → update base image pinning
- `dco`: Commit missing `Signed-off-by:` → rebase + amend with `-s`
- `doctrine-grep`: Doctrine violation pattern detected → fix inline

---

## Escalation Matrix

| Severity | Condition | Escalate To | SLA |
|----------|-----------|-------------|-----|
| Critical | Doctrine violation in live response | Founder immediately | 15 min |
| Critical | Secret leaked in response/logs | Founder + rotate credentials | 30 min |
| High | 2+ flagships down simultaneously | On-call team | 1 hour |
| High | Build failing for >30 min | On-call team | 2 hours |
| Medium | Single flagship 404 on CTO endpoint | On-call team | 4 hours |
| Low | CI failing but prod OK | Team | Next business day |

---

### INC-05: public identity hosts (DNS / Cloudflare — not an app deploy)

Locked architecture (do not merge the two hosts):

- `a-11-oy.com` = product command center (this app; HF Space behind Cloudflare)
- `a11oy.net` = public proof/registry (GitHub Pages repo `szl-holdings/a11oy-net`, separate failure domain)
- Public name is **a11oy**. Do not stamp or 301 toward the unhyphenated third-party furniture host.

#### Wiring map (KALLPA 2026-08-28 17:05 UTC — do not invent LIVE)

| What a visitor sees | What it actually is | Honest label |
|---|---|---|
| Apex `a-11-oy.com` GET `/` HTTP 200, HSTS `max-age=31536000; includeSubDomains`, `x-szl-space: a11oy` | Cloudflare A `104.21.27.230` / `172.67.169.206` in front of Space `SZLHOLDINGS/a11oy` | Product origin **reachable via Cloudflare**. Not Hugging Face custom-domain READY. |
| Hugging Face `runtime.domains` | `szlholdings-a11oy.hf.space` **READY**; `a-11-oy.com` **PENDING** | HF custom domain **PENDING** (or **UNAVAILABLE**). Do not stamp LIVE. |
| `x-szl-wire-d: LIVE` | DSSE Wire D provenance header from `szl_provenance.py` | Provenance hop, **not** domain LIVE. Do not conflate. |
| `www.a-11-oy.com` | NXDOMAIN (`curl: could not resolve`) | **UNAVAILABLE**. With HSTS `includeSubDomains`, www is a hard fail until Cloudflare has `CNAME www → a-11-oy.com`. This app cannot change CF DNS. |
| `https://a11oy.com/trust` | Unrelated WordPress/Cloudways furniture shop; GET 301s to a hanging-egg-chair product | **Not ours.** Canonical MUST be `https://a-11-oy.com/trust`. |
| Canonical receipt RECORD | Lasting public copy on **a11oy.net** | Registry origin. `/verify` on `a-11-oy.com` is the interactive checker only. |
| `HEAD` vs `GET` on the apex | GET 200 / HEAD 200 on `/` and `/verify`; GET 200 / HEAD 405 on `/console`, `/trust`, `/assurance`, `/robots.txt` (pre-fix, Space SHA not this PR) | Document routes now declare GET+HEAD. FastAPI `@app.get` FileResponse had no HEAD; StaticFiles already covered `/` and `/verify`. |
| killinchu | Hub `https://huggingface.co/spaces/SZLHOLDINGS/killinchu` HTTP 200; `https://szlholdings-killinchu.hf.space/` timed out | Runtime **UNAVAILABLE**. Do not imply live on the inference landing. |
| Observability DAG depth 0 / IDLE | Empty process-local ring, not a measured live graph | **UNAVAILABLE**, not invented numbers. |
| Promote path | `hf-sync.yml` publishes GitHub `main` → Space `SZLHOLDINGS/a11oy` | Staging Space `szlholdings-a11oy.hf.space` ≠ prod DNS `a-11-oy.com`. Space READY is not prod-DNS verified. |
| QHAPAQ S1–S12 HEAD (MEASURED 2026-08-28 13:05–13:12 ET) | GET 200 / HEAD 405 on `/console` `/trust` `/assurance` `/robots.txt` `/healthz` `/readyz` `/api/health`; GET 200 / HEAD 404 on `/api/a11oy/healthz` and `/api/a11oy/v1/health` | Document **and** health JSON now declare GET+HEAD. `/` and `/verify` were already HEAD 200. |
| Signer enum | `/api/a11oy/healthz` rollup.signer.status=`DSSE-LIVE` (scheme DSSEv1 / ECDSA-P256, fingerprint `9926bf69…`) when the live key is present. `/healthz`, `/api/health`, `/api/a11oy/v1/health` had **no** signer field. | Only the rollup may stamp **DSSE-LIVE**. Other health JSON is **ABSENT** / **UNAVAILABLE**. Never copy LIVE. |
| ISS `GET /api/a11oy/v1/live/iss` | source Where-the-ISS-at, mode live, bare `data.latitude` numbers | Field **units** (degrees, km, km/h) or **UNAVAILABLE**. |
| `GET /v1/live-fetch/status` | `{status:NOT_FOUND, reason:undeclared path refused SPA fallback}` | Honest **404**. Do not invent the endpoint. Rebind a tab or mark ROADMAP. |

**www.a-11-oy.com is NXDOMAIN** while apex sends `Strict-Transport-Security: max-age=31536000; includeSubDomains`. Browsers that have seen the apex will refuse `http://www.a-11-oy.com` and have nothing to connect to on HTTPS. DNS is Cloudflare/ops (Stephen). This app cannot create the `www` record.

**HTTP `Link: rel="canonical"`** to `https://huggingface.co/spaces/SZLHOLDINGS/a11oy` was MEASURED on every probed apex path (box, 2026-08-28 13:05–13:13 ET). Hugging Face may still inject that header at the Space proxy. This app now stamps `Link: <https://a-11-oy.com{path}>; rel="canonical"` on public product GET/HEAD/OPTIONS and drops a Space or furniture-shop canonical from its own response. Do not make `huggingface.co/spaces` or `a11oy.com` the product canonical. If the HF proxy still appends a second Link after origin, that remaining conflict is provider-side; HF custom domain stays **PENDING** (`_huggingface.a-11-oy.com` NXDOMAIN, www NXDOMAIN — Stephen/DNS).

**HEAD 405 is the app, not Cloudflare.** Same 405 on `https://szlholdings-a11oy.hf.space/trust` and `/console` (`Server: szl`). `/sitemap.xml` was GET 200 / HEAD 405 — now GET+HEAD. OPTIONS `/` and `/console` now send `Allow` and `Access-Control-Allow-Methods`.

**Do not** 301 `a11oy.net` onto `a-11-oy.com` from this app (the old sunset middleware was a landmine if `.net` DNS ever pointed at the Space).

**Hugging Face custom domain is PENDING, not verified.** MEASURED 2026-08-28 via `GET https://huggingface.co/api/spaces/SZLHOLDINGS/a11oy`: `runtime.domains` is `szlholdings-a11oy.hf.space` READY and `a-11-oy.com` PENDING. The same day, `GET https://a-11-oy.com/` returned HTTP 200 through Cloudflare (`x-szl-space: a11oy`, `x-proxied-replica` present). Apex serving is not the same as Hugging Face provider verification.

- Treat HF `PENDING` as an open identity defect owned by **KALLPA / Stephen (DNS)**. Completing or removing the Hugging Face custom-domain binding is an external operator action (`docs/SPACES_HEALTH_OPERATIONS.md`).
- **Do not** claim the custom domain is verified in HTML, badges, or PR copy.
- **Do not** paper over PENDING by moving `<link rel="canonical">` / `og:url` onto `*.hf.space`. Product HTML canonicals stay `https://a-11-oy.com`.
- **Do not** fight Cloudflare (CNAME flattening, orange-cloud, or nameserver changes) just to make Hugging Face report READY if that would take the public origin down. Public 200 on the apex beats a green HF domain row.

This PR does **not** merge PR 1363 (HOLD). Chrome/nav IA belongs to PR 1391 (ÑAWI); this work is wiring/honesty only and keeps house tokens.

---

## Required DCO on All Fix Commits

```
Signed-off-by: Yachay <yachay@szlholdings.ai>
Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
```

**Signed-off-by: Yachay <yachay@szlholdings.ai>**  
**Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>**
