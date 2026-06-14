# RESULT — YUPAY governed multi-model audit harness (BUILD COMPLETE)

**Built:** 2026-06-15 (before the June 18 02:00 ET freeze)
**Author:** Perplexity Computer Agent (delegated build)
**Status:** ✅ LIVE on both apps · CI + drift guards green · byte-identical shared modules · 0 doctrine violations

---

## 5-line summary

1. **YUPAY** (Quechua *to count / to reckon / to audit*) is SZL's own governed multi-model audit harness: it adopts the **Kilo Code / André Lindenberg "We Audited the Same Codebase" methodology** ([blog.kilo.ai](https://blog.kilo.ai/p/we-audited-the-same-codebase-with), 2026-06-05) and runs it over OUR OWN governed open models, emitting **one DSSE-signed comparison receipt + a Restraint verdict** — the governed difference.
2. **No M3 weights, no M3 derivative.** MiniMax M3 is shown ONLY as a non-participating `EXCLUDED-BY-DOCTRINE` reference row (defense-license restriction + PRC sovereignty), **never run, never ingested**. SZL-Nemo is a governed **Qwen3-32B (Apache-2.0)** wrapper.
3. The **MiniMax Sparse Attention paper** ([huggingface.co/papers/2606.13392](https://huggingface.co/papers/2606.13392), Lai et al., 2026-06-12) is taken ONLY as a *published technique* to inform OUR OWN efficient-attention roadmap on the clean open base — cited as inspiration in a research note + box-gated Forge order, not implemented from M3.
4. Shipped **ADDITIVE** and **try/except-guarded** to both apps: `/yupay` tab + `/api/{ns}/v1/yupay/{doctrine,demo,compare,receipts,verify}`, registered via the proven **front-insert** pattern (beats killinchu's greedy SPA catch-all), **idempotent** via `/yupay` sentinel. All routes return **200** on a11oy AND killinchu.
5. Doctrine honored: locked = exactly **8** theorems `{F1,F4,F7,F11,F12,F18,F19,F22}` @ kernel `c7c0ba17`; Λ = Conjecture 1; Khipu = Conjecture 2; **SLSA L1 honest / L2-L3 roadmap**; trust ceiling **0.97 (<1.0)**; **0 runtime CDN**; **0 user-visible codenames**; data labeled MEASURED/MODELED/SAMPLE/EXCLUDED/ROADMAP; **honest "no key wired in HF Space → rows MODELED"** self-statement on the live tab.

---

## Live routes (verified 200, both apps)

| Route | a11oy | killinchu |
|---|---|---|
| `GET /yupay` (tab) | 200 (HTML) | 200 (HTML) |
| `GET /api/{ns}/v1/yupay/doctrine` | 200 (JSON) | 200 (JSON) |
| `GET /api/{ns}/v1/yupay/demo` | 200 (JSON) | 200 (JSON) |
| `POST /api/{ns}/v1/yupay/compare` | 200 (JSON, signed) | 200 (JSON, signed) |
| `GET /api/{ns}/v1/yupay/receipts` | 200 (JSON) | 200 (JSON) |
| `POST /api/{ns}/v1/yupay/verify` | 200 (JSON) | 200 (JSON) |

- a11oy: https://szlholdings-a11oy.hf.space/yupay
- killinchu: https://szlholdings-killinchu.hf.space/yupay

All API routes return real JSON (NOT the SPA shell) — front-insert confirmed working ahead of killinchu's catch-all. The `verify` endpoint correctly reports `verified:false` with the expected keyid + public-key URL + decoded payload because **no cosign key is wired into the HF Space runtime** — this is the doctrine-honest "trust never 100%" behavior, identical to WAQAY.

## Tab route
`/yupay` (served HTML operator tab on both apps; nav item injected idempotently into `/console` via middleware).

---

## SHAs

**GitHub HEAD (main):**
- a11oy: `5d27a0867795ec982ebcb40a68a649b9329fd90f`
- killinchu: `751f2be33be7dc444308f2e687f482509fd2970a`

**Shared module git-blob SHAs (BYTE-IDENTICAL across GitHub a11oy / GitHub killinchu / HF a11oy / HF killinchu):**
- `szl_yupay.py` → `80de6b81ee99f66551a43e7d132a78a46576a0de`
- `a11oy_yupay_nav.py` → `c4ffaee8e580aca69dfe8025026948fe818dddd4`

**Per-app files (correctly differ — namespace + per-app COPY set):**
- a11oy `serve.py` → `d410f810dfe73b15…`, `Dockerfile` → `64c5e52a006b617a…`
- killinchu `serve.py` → `d188493d17255465…`, `Dockerfile` → `af0c38807bdd6c79…`

---

## Files shipped

**a11oy** (`szl-holdings/a11oy`): `szl_yupay.py`, `a11oy_yupay_nav.py`, `serve.py` (YUPAY block after WAQAY end-marker, before `__main__`), `Dockerfile` (COPY line added after WAQAY COPY), `NOTICES.md` (YUPAY attribution section), `team/AUDIT/frontier/YUPAY_SPARSE_ATTN_RESEARCH.md`, `team/AUDIT/frontier/FORGE_YUPAY_SPARSE_ATTN.md`.

**killinchu** (`szl-holdings/killinchu`): `szl_yupay.py` (byte-identical), `a11oy_yupay_nav.py` (byte-identical), `serve.py` (re-applied onto the sibling team's FRESH WAQAY-route-ordering commit — their work fully preserved, 28 waqay refs intact), `Dockerfile` (COPY line added), `NOTICES.md` (YUPAY attribution).

**Concurrency note:** A sibling team committed killinchu WAQAY route-ordering fixes at 23:25Z. I re-fetched the FRESH killinchu `serve.py`/`Dockerfile`/`NOTICES.md` (and a11oy's too) and re-applied the YUPAY block onto the latest content right before each push — verified no WAQAY work was clobbered (waqay ref count unchanged).

---

## CI + guard status (latest HEAD)

**a11oy** — 0 failures. Green incl: Doctrine, Doctrine Overclaim Guard, Doctrine banned-token grep gate, **Shared-source drift guard** (byte-identical szl_yupay.py enforced), copy-sync lockstep guard, Dockerfile build-file guard, no-hf-mirror-guard, Tests, **Sync backend to HuggingFace Space**, **HF Space module-drift guard** (passed on re-run — original failure was a race where the guard ran ~21s before the backend sync mirrored the files; re-run after sync = success). CodeQL + GHCR container build still running (long security/publish jobs, unrelated to YUPAY correctness).

**killinchu** — 13/13 green incl: CI, Doctrine, Doctrine Overclaim Guard, Shared-source drift guard, Dockerfile build-file guard, copy-sync lockstep guard.

## HuggingFace sync
Both Spaces factory-rebuilt and `RUNNING`. `hf_sync_backend.py` parses Dockerfile COPY directives → both YUPAY .py modules auto-mirrored to both Spaces (oids confirmed byte-identical to GitHub). `szl_yupay.py` is NOT in `shared-file-drift-allow.txt`, so the drift guard ENFORCES byte-identity across both repos.

## Verification artifacts
- Route verification: all 12 endpoints (6 × 2 apps) return 200, no SPA leak.
- Playwright full-page screenshots: `team/AUDIT/frontier/shots/yupay/a11oy_yupay_tab.png`, `…/killinchu_yupay_tab.png` (titles: "a11oy · YUPAY — the governed multi-model audit harness"; M3 row visibly EXCLUDED-BY-DOCTRINE; doctrine footer present).
- Local: szl_yupay.py + a11oy_yupay_nav.py self-tests PASS; integration test confirms front-insert beats greedy catch-all + idempotency on simulated a11oy + killinchu apps; ast.parse OK on all .py.

## Attribution (in NOTICES.md, both repos)
Kilo Code / André Lindenberg audit methodology (blog.kilo.ai, 2026-06-05) + MiniMax Sparse Attention paper (huggingface.co/papers/2606.13392, 2026-06-12) cited as INSPIRATION. SZL-Nemo = governed Qwen3-32B (Apache-2.0). NO M3 weights, NO M3 derivative.
