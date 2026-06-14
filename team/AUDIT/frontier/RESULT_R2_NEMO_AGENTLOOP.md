# RESULT — R2: Wire a11oy Restraint into SZL-Nemo + ReAct Agent Loop

**Agent:** Restraint Dev R2 (SZL Holdings)
**Date:** 2026-06-14
**Status:** ✅ SHIPPED & LIVE-VERIFIED (restraint integration PENDING-degraded honestly until R1's `a11oy_restraint.py` goes live — by design, no rework needed when it lands)

---

## What shipped (additive, front + back)

### 1. SZL-Nemo code path (`a11oy_nemo_core.py`, `/nemo`)
- Before emitting CODE, the intended diff is routed through the restraint ladder via
  `_restraint_evaluate(task, intensity, lang, sign_fn)` — 3-tier resolution:
  (a) in-process import of R1's `a11oy_restraint` (preferred), (b) HTTP loopback to
  `POST /api/a11oy/v1/restraint/evaluate` (env override `A11OY_RESTRAINT_URL`),
  (c) **honest PENDING** degrade if neither is reachable.
- New `nemo_code(query,intent,intensity,lang,sign_fn)` builds a governed code-emission
  plan; chosen rung + **signed restraint receipt** are nested inside the Nemo response receipt.
- `infer()` attaches the restraint block whenever the primary routed expert is `code`.
- New route `POST/GET /api/a11oy/v1/nemo/code` (base + `/a11oy` alias). `nemo/_diag` and
  the model-card sources now expose a `restraint` section (module-importable flag, HTTP
  fallback endpoint, Ponytail MIT provenance).
- `/nemo` page (`web/nemo.html`): **"Restraint applied" indicator** — input + button,
  rung, lines-saved, `restraint:` ceilings, signed-receipt verify. PENDING maps to the
  ROADMAP canonical badge + literal "PENDING" text (never fabricates a rung/number/signature).

### 2. ReAct agent loop (`a11oy_react_core.py`, `/agent-loop`)
- Added `write_code` / `code_patch` / `emit_code` tools (`_CODE_TOOLS`); `_plan_action()`
  routes code-writing goals to `write_code`.
- The **ACTION node** is gated: when `tool in _CODE_TOOLS`, `_drive()` calls
  `_restraint_evaluate(...)` and stores the verdict in the node's **signed receipt body**.
- `react/_diag` exposes a `restraint` section (gated code tools, Ponytail MIT provenance).
- **`/agent-loop` page now served from THIS module** (additive `Route`s at position 0,
  beating the SPA catch-all): the committed `web/agent-loop.html` trace UI (restraint-verdict
  column) was never routed by `serve.py` (no `add_api_route`, no Dockerfile COPY), so it fell
  through to the orchestration SPA and the restraint column was not user-visible. R2 serves it
  from `a11oy_react_core.register()` reading on-disk paths with a **byte-identical embedded
  base64 fallback**, so it renders without touching `serve.py` or the Dockerfile (avoids
  clobbering concurrent sibling lanes). `/agent-loop` + `/a11oy/agent-loop` both wired.
- `web/agent-loop.html`: added **restraint column** to the trace table + `restraintCell()`
  (rung / lines-saved / Λ / ceiling badges; LIVE vs ROADMAP+PENDING); default goal switched
  to a code goal to exercise the path; explanatory note cites Ponytail (MIT).

### 3. Honest labels & provenance
- `window.SZLLabels`: MEASURED only if measured, else SAMPLE / ROADMAP; PENDING surfaced
  literally while R1 not live. **No savings numbers fabricated.**
- Ponytail cited as MIT upstream throughout: `https://github.com/DietrichGebert/ponytail`
  (license MIT, relation "adopted + governed"). No internal codenames; no 550B/Nemotron-Ultra
  leaks (only honest negations in the SZL-Nemo disclaimer).

---

## Shas

| Target | Sha |
|---|---|
| GitHub `szl-holdings/a11oy` @ main — restraint back+front (nemo+react+tabs) | `3a8305e24d8ef39cc29cdf16cc74b9cbc26026dd` |
| GitHub `szl-holdings/a11oy` @ main — /agent-loop trace UI served from react_core | `7bbae212d89fed02b42f587b83163d93e033a153` |
| HF Space `SZLHOLDINGS/a11oy` — front-end commit (nemo+agent-loop html) | `5ea238fd346ef9841408133ef4dcbc9abcff91c8` |
| HF Space `SZLHOLDINGS/a11oy` — react_core (/agent-loop route + embed) | `a610f4cd09334a75457ddcea4951c205554c7aca` |

All pushes: GitHub Git Data API (blobs→tree→commit→ref) with **fresh HEAD immediately before
ref update**, additive overlay of **only R2's 4 files** onto fresh remote tree (siblings'
concurrent edits untouched), 25× conflict retries, 8× HTTP-000 retries. HF via NDJSON commit
API + `restart?factory=true`. **No key ever committed.** `.py` files `ast.parse` OK; `<script>`
blocks `node --check` OK before each push.

---

## Live verification (https://szlholdings-a11oy.hf.space, Space RUNNING @ a610f4cd)

- **Nemo code path** — `POST /api/a11oy/v1/nemo/code {query:"write me a Python function that
  validates email addresses"}` → `is_code_path:true`, `restraint_required_before_emit:true`,
  `restraint.status:"PENDING"`, no fabricated rung/number/signature (honest degrade). ✅
- **`/api/a11oy/v1/nemo/_diag`** → `restraint` section present (module_importable:false, HTTP
  fallback endpoint, Ponytail MIT). HTTP 200. ✅
- **Agent loop** — `POST /api/a11oy/v1/agent/react/run {goal:"implement a function that
  validates an email address",max_steps:2}` → THOUGHT(intended_tool:write_code) →
  **ACTION(tool:write_code)** with `restraint` verdict in body (`status:PENDING`, applied:false,
  lines_saved_label:PENDING, Ponytail MIT provenance), receipt `signature_valid:true`,
  `signed:true`, `chain_intact:true`. ✅
- **`/agent-loop` page** — HTTP 200, serves the trace UI (`<title>a11oy — Agent Loop · Memory ·
  Skill Library</title>`), restraint column present, Ponytail MIT cited, **0 non-font CDN**. ✅
  (Previously served the orchestration SPA with no restraint/trace content.)
- **Regression** — `nemo/_diag` 200, `agent/react/_diag` 200, `/nemo` 200. No regression. ✅
- **0 CDN** (runtime JS/CSS): only pre-existing Google Fonts `<link>`s (already in HEAD,
  not introduced by R2). **0 visible codenames.** ✅

Screenshots captured:
`current_session_context/tool_calls/screenshot/screenshot_szlholdings-a11oy.hf.space_nemo_*.png`
`current_session_context/tool_calls/screenshot/screenshot_szlholdings-a11oy.hf.space_agent-loop_*.png`

---

## Doctrine compliance
locked=8 @ c7c0ba17 untouched · Λ = Conjecture 1 (advisory, <1.0) · trust < 100% · 0 CDN ·
0 visible codenames · signed receipts on every node · savings never fabricated (PENDING when
not measured) · **additive-only** (edited only `a11oy_nemo_core.py`, `a11oy_react_core.py`,
`web/nemo.html`, `web/agent-loop.html`; pushed only those 4; no shared-module/Dockerfile/serve.py
bytes touched; `a11oy_restraint.py` left to R1).

## Handoff note for R1
When `a11oy_restraint.py` is importable (or `/api/a11oy/v1/restraint/evaluate` returns 200),
both surfaces auto-populate the chosen rung + signed restraint receipt + lines-saved with **no
R2 rework** — the 3-tier `_restraint_evaluate` (in-process import → HTTP loopback → PENDING)
flips from PENDING to LIVE automatically.
