# sentra — Developer Onboarding

> **Doctrine v11 LOCKED** · 749 declarations · 14 axioms · 163 sorries · Λ = Conjecture 1 · SLSA L1 honest

This is the entry point for a new developer joining sentra.

---

## 1. What sentra actually is

sentra is the **8-gate deny-by-default immune system** for the SZL mesh. Every
incoming action is evaluated through 8 gates in sequence; any gate failure = deny.
Verdicts are signed with DSSE, traced with W3C traceparent (Wire B), and chained
into a Khipu receipt DAG.

It is **not** a general-purpose API gateway. Its only job is immune evaluation.

---

## 2. Architecture diagram

```
  HF Space: SZLHOLDINGS/sentra  (port 7860)
  ┌─────────────────────────────────────────────────────┐
  │  serve.py (FastAPI)                                 │
  │  ├── /                    Vessels-DNA landing       │
  │  ├── /console/*           Replit SPA console        │
  │  ├── /api/sentra/v1/verdict   POST — immune eval    │
  │  ├── /api/sentra/v1/inspect   POST — full-signal    │
  │  ├── /api/sentra/v1/gates     GET — 8 gate list     │
  │  ├── /api/sentra/v1/audit-log GET — verdict history │
  │  ├── /api/sentra/v1/forecast  GET/POST — Mādhava    │
  │  └── /api/sentra/v1/honest    GET — doctrine check  │
  │                                                     │
  │  Core immune modules:                               │
  │  sentra_immune_v2.py   8-gate engine (deny-default) │
  │  sentra_v4_threat.py   threat-intel corpus (STIX)   │
  │  szl_wire.py           Wire B/D traceparent wiring  │
  │  szl_dsse.py           DSSE receipt signing         │
  │  szl_khipu.py / szl_khipu_consensus.py  DAG store   │
  │  szl_be_hardening.py   Rate-limit, structured logs  │
  └─────────────────────────────────────────────────────┘
         ▲ Wire B (verdicts upstream to a11oy)
         │
       a11oy (orchestrator / root of trust)
```

---

## 3. The 8 immune gates (deny-by-default — ALL must pass)

| Gate | Name | What it checks |
|---|---|---|
| G1 | Size guard | Payload ≤ MAX_PACKET_BYTES (500 KB) |
| G2 | Structural integrity | JSON schema / depth / key count |
| G3 | Recursive pattern scan | Threat signatures across all string fields |
| G4 | Base64 decode-and-rescan | Detect encoded bypass attempts |
| G5 | Entropy check | High-entropy strings flagged as potential exfil |
| G6 | Action schema validation | Action must be in known vocab |
| G7 | Payload digest verification | Content-addressed integrity when digest present |
| G8 | Auth claim + replay protection | Nonce window, rate-limit |

Implementation: `sentra_immune_v2.py`. Each gate returns `(passed, reason, score)`.
The public API is `sentra_inspect_v2(payload)` → full verdict dict with Khipu receipt.

---

## 4. Running locally

### Fastest: Docker

```bash
docker run --rm -p 7860:7860 ghcr.io/szl-holdings/sentra:uds-v0.2.0
curl -X POST http://localhost:7860/api/sentra/v1/verdict \
  -H "Content-Type: application/json" \
  -d '{"action":"read","payload":{"key":"value"}}'
```

### Manual

```bash
# FULL clone (never --depth 1)
git clone https://github.com/szl-holdings/sentra.git && cd sentra

pip install fastapi uvicorn httpx cryptography pydantic
PORT=7860 uvicorn serve:app --host 0.0.0.0 --port 7860 --reload
```

---

## 5. Endpoint map

```
GET  /                              Vessels-DNA landing (SPA)
GET  /console/*                     Replit SPA console
GET  /api/sentra/healthz            Liveness
POST /api/sentra/v1/verdict         Full immune verdict (Wire B)
POST /api/sentra/v1/inspect         Full-signal inspect (no short-circuit)
GET  /api/sentra/v1/gates           List all 8 immune gates
GET  /api/sentra/v1/gates/{id}      Per-gate detail
POST /api/sentra/v1/gates/{id}/test Per-gate test with sample input
GET  /api/sentra/v1/audit-log       Recent verdict history
GET  /api/sentra/v1/threats         Threat-signature corpus
GET/POST /api/sentra/v1/forecast    Witnessed forecasting (Mādhava error envelope)
GET  /api/sentra/v1/honest          Live doctrine posture (749/14/163, Λ=Conjecture)
```

---

## 6. Wire B — the a11oy↔sentra connection

Wire B is the verdict pipeline from sentra back to a11oy. The verdict response
carries provenance fields that are LOCKED (do not rename or remove):

```json
{
  "verdict": "ALLOW|DENY",
  "receipt_hash": "...",
  "actionId": "...",
  "gates_fired": ["G1","G2",...],
  "traceparent": "00-...",
  "doctrine": "v11"
}
```

These fields are checked by a11oy on the receiving end. Changing them silently
breaks the Wire B contract.

---

## 7. HF Space deploy (same caveats as a11oy)

The `hf-sync` workflow syncs only `README.md`. Python code does not
auto-sync. See `KNOWN_GOTCHAS.md` for the full picture. The Space is at
`SZLHOLDINGS/sentra` (https://szlholdings-sentra.hf.space).

---

## 8. Doctrine constants (LOCKED)

Same as the platform: 749/14/163, kernel `c7c0ba17`, Λ = Conjecture 1.
The `/v1/honest` endpoint is authoritative.

---

## 9. Running tests

```bash
pip install pytest && pytest tests/ -v
pnpm install && pnpm -F @szl-holdings/sentra test
bash scripts/smoke-from-public-url.sh
```

---

## 10. Key module index

| Module | Purpose |
|---|---|
| `serve.py` | FastAPI app, route registration |
| `sentra_immune_v2.py` | 8-gate immune engine (start here) |
| `sentra_v4_threat.py` | Threat-intel corpus (STIX/TAXII) |
| `szl_wire.py` | Wire B/D/E/F cross-pod wiring |
| `szl_dsse.py` | DSSE receipt signing |
| `szl_khipu_consensus.py` | Multi-organ consensus DAG |
| `szl_be_hardening.py` | Backend hardening (rate-limit, logs, SQLite) |
| `szl_hm_lambda_score.py` | Lambda score helper (H/M aggregation) |

---

*Authored by Perplexity Computer Agent on behalf of Yachay (CTO).*
*Doctrine v11 LOCKED · 749/14/163 · Λ = Conjecture 1.*
*Signed-off-by: stephenlutar2-hash <stephenlutar2@gmail.com>*
