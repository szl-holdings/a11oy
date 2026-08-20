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

## Required DCO on All Fix Commits

```
Signed-off-by: Yachay <yachay@szlholdings.ai>
Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
```

**Signed-off-by: Yachay <yachay@szlholdings.ai>**  
**Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>**
