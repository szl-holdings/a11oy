# RESULT_RESTRAINT.md — a11oy Restraint (Ponytail, adopted + governed)

> **Lane:** Frontier / Code-agent capability.
> **What this is:** an honest after-action record of ingesting the open-source
> **Ponytail** coding-agent skill (`github.com/DietrichGebert/ponytail`, MIT, 4.6k★)
> and evolving it into a **GOVERNED + MEASURED** capability inside a11oy-Code called
> **a11oy Restraint**. Adopted, not invented — see *Provenance & citation* below.
>
> **Doctrine v11 contract upheld:** locked=8 @ kernel `c7c0ba17`; Λ = Conjecture 1
> (**OPEN**, advisory floor < 1.0, never described as a closed theorem); SLSA L1 honest
> / L2–L3 roadmap; 0 runtime application-logic CDN; 0 visible codenames; signed receipts
> on every decision; benchmark numbers never fabricated; additive-only changes.
> *"The half-state is the only unacceptable outcome"* — shipped end-to-end and verified live.

---

## 0. TL;DR

a11oy Restraint is a frugality gate wired into the a11oy-Code agent path. Before the
agent emits a diff it descends a **6-rung ladder** and stops at the first rung that
holds, marking deliberate simplifications with `restraint:` ceiling comments that name
the upgrade path. Every decision becomes a **signed DSSE receipt** (in-image ECDSA-P256)
plus an **advisory Λ score** (< 1.0). A two-arm benchmark (no-skill baseline vs
a11oy-restraint) is ported from Ponytail's promptfoo methodology and labelled honestly
(**SAMPLE / ROADMAP** until a model run is actually wired, never MEASURED-by-default).
An energy tie-in models tokens→joules saved, labelled `MODELED` / joules `sample`.
A live UI panel renders at `/restraint`.

**All endpoints live and verified on the running Space** (see §6).

---

## 1. Provenance & citation (honest)

a11oy Restraint **adopts** the 6-rung ladder and the `lite / full / ultra` intensity
levels from the open-source **Ponytail** coding-agent skill
(<https://github.com/DietrichGebert/ponytail>, MIT, © 2026 DietrichGebert, 4.6k★).
The idea and the ladder are **Ponytail's**. a11oy's additions — the *differentiators* —
are:

1. a **signed DSSE receipt per decision** (host in-image ECDSA-P256 signer);
2. an **advisory Λ trust score** per decision;
3. **measured-on-our-stack** benchmarks (honest SAMPLE/ROADMAP→MEASURED gate);
4. a **J/token energy tie-in** (sovereign thesis: less code → fewer tokens → fewer joules).

This is recorded in-product: `/api/a11oy/v1/restraint/info` returns
`relation: "adopted + governed (NOT invented here). Idea & ladder are Ponytail's."`
and every signed receipt carries
`provenance: {adopted_from: "Ponytail", repo, license: "MIT", relation: "adopted + governed"}`.

Ponytail's **published** benchmark figures (80–94% less code, 47–77% cheaper, 3–6× faster,
median across Haiku/Sonnet/Opus) are surfaced **only** as
`label: "CITED (Ponytail's numbers, not ours)"` with source
<https://github.com/DietrichGebert/ponytail/tree/main/benchmarks>. They are **never**
repeated as a11oy's own measurements.

---

## 2. The ladder (implementation)

Module: **`szl_restraint.py`** (~655 lines; self-test + Starlette TestClient integration
test pass). Registered into the live ASGI app via the standard a11oy module pattern
(`register(app, ns="a11oy", sign_fn=_a11oy_sign_receipt, ...)`, routes inserted at
position 0 to beat the SPA catch-all).

The pre-write gate descends the ladder and **stops at the first rung that holds**:

| Rung | Key        | Question                                            |
|------|------------|-----------------------------------------------------|
| 1    | `yagni`    | Does this need to exist at all? (YAGNI)             |
| 2    | `stdlib`   | Stdlib does it?                                     |
| 3    | `native`   | Native platform feature covers it?                  |
| 4    | `installed`| Already-installed dependency solves it?             |
| 5    | `oneline`  | Can it be one line?                                 |
| 6    | `minimal`  | Only then: the minimum code that works.             |

**Intensity** (adopted from Ponytail):
- `lite` — build what's asked, name the lazier alternative in one line.
- `full` — ladder enforced, stdlib/native first, shortest diff (default).
- `ultra` — YAGNI-extremist: deletion before addition; rung 1 fires on speculation.

**Ceiling comments** are emitted in the honest rename of Ponytail's `ponytail:` marker.
Example (live, `"add a cache…"`, intensity `full`):

```
# restraint: stdlib — lru_cache(maxsize=...); a hand-rolled TTL cache only when a profiler demands it
```

**`never_simplify` floor** (rungs never apply to): input validation at trust boundaries,
data-loss error handling, security measures, accessibility basics, and anything explicitly
requested. Rung detectors are deterministic rule advisories (labelled **HEURISTIC**),
not a proof — the human stays on the loop.

---

## 3. GOVERNED — signed receipts + Λ

**Signed DSSE receipt per decision.** Each `evaluate` response carries `signed_receipt`
produced by the real in-image signer (`_a11oy_sign_receipt`):
`payloadType: application/vnd.szl.receipt+json`, DSSE PAE, ECDSA-P256-SHA256,
`keyid: a11oy-inimage-ecdsa-p256`, `signed: true`. The key is generated at server boot,
resets on rebuild, and is verifiable in-browser against `/cosign.pub`. If the key is
absent the receipt is honestly marked UNSIGNED rather than faked.

**Cryptographic verification performed live (this audit):** a fresh receipt from the
running Space verified **VALID** (DER signature) against the live `/cosign.pub`
(P-256 public key, 178 bytes), and the receipt's `_pae_sha256`
(`ed73be00…bba983`) matched the locally recomputed DSSE-PAE digest exactly. This is a
real, tamper-evident signature — not a placeholder.

**Λ score (advisory).** Each decision carries `lambda_score`: a geometric mean of bounded
axis scores (detector_confidence, task_clarity, intensity_calibration), zero-pinned, kept
strictly **< 1.0** with `advisory_floor: 1.0`, `below_floor: true`. The receipt records
`lambda` and `lambda_below_floor`. The response explicitly states:
*"Conjecture 1 (Λ uniqueness) is **OPEN** — NOT a closed theorem. Λ here is an advisory
trust signal kept strictly < 1.0."* No overclaim.

---

## 4. MEASURED — two-arm benchmark with honest labels

Endpoint `/api/a11oy/v1/restraint/bench` runs two arms — **baseline (no skill)** vs
**a11oy-restraint** — over the same five everyday tasks as Ponytail's promptfoo suite,
reporting the **median**. Methodology ported from Ponytail (MIT).

**Honesty gate (the key discipline):**
- Per-row `label: "SAMPLE"` and `overall_label: "ROADMAP"` **because no model is wired on
  the running Space** — these are ladder-model fixtures, transparently disclosed.
- The response states numbers are OUR-stack-MEASURED **only when** `overall_label == MEASURED`
  (a real model run), which flips via
  `npx promptfoo@latest eval -c benchmarks/restraint/promptfooconfig.yaml --repeat 10`
  (config shipped at `benchmarks/restraint/promptfooconfig.yaml`).
- Ponytail's published numbers are carried separately, labelled `CITED (Ponytail's numbers,
  not ours)`.

So at this moment the honest status is: **SAMPLE / ROADMAP** (fixtures), **not MEASURED**.
Wiring a code model on the Space is the single step that flips ROADMAP→MEASURED.

`lines_saved_estimate` on `evaluate` is likewise labelled **MODELED** ("OUR transparent
model … MODELED, not MEASURED").

---

## 5. ENERGY tie-in (modeled, honestly labelled)

`evaluate.energy_tiein` models `tokens_saved → joules_saved` from
`lines_saved × tokens/LOC × J/token` (sovereign thesis: less code = fewer tokens = fewer
joules on our GPU). It is labelled **MODELED**, and `joules_label: "sample"` because no
on-box NVML exporter sample is wired (it lazily imports `szl_joules_truth.joules_label`,
which only returns `"measured"` with a fresh on-box sample). The J/token figure is
explicitly disclosed as a modeled estimate, not a live meter reading. Flipping this to
`measured` is the same sovereign-box energy wiring tracked in
`team/AUDIT/elevate/FORGE_BOX_ENERGY.md`.

---

## 6. Live verification (on the running Space)

Space `SZLHOLDINGS/a11oy` — runtime **stage RUNNING**, domain `szlholdings-a11oy.hf.space`
**READY**, serving HF commit `714d76da115b58bc0ef8a85eed3074bef7836391`. All checks below
were run live against `https://szlholdings-a11oy.hf.space` (with HTTP-000 retry logic):

| Check | Result |
|-------|--------|
| `POST /api/a11oy/v1/restraint/evaluate` (`"add a cache…"`, `full`) | **200** — stopped at rung 2 (`stdlib`, `functools.lru_cache`), `restraint:` ceiling emitted, Λ=0.8258 (below_floor), `signed_receipt.signed=true` |
| Signed-receipt crypto verify vs live `/cosign.pub` | **VALID** (ECDSA-P256-SHA256 DER; PAE sha256 matches) |
| `GET /api/a11oy/v1/restraint/info` | **200** — ladder spec, intensities, provenance (Ponytail, MIT, adopted+governed), doctrine (locked=8, cdn=0, codenames=0) |
| `GET /api/a11oy/v1/restraint/bench` | **200** — two arms, rows `SAMPLE`, overall `ROADMAP`, Ponytail numbers `CITED` |
| `GET /restraint` (UI) | **200** — 23,025 bytes; ladder rendered, `window.SZLLabels` wired, scripts from `/static/` + `/vendor/` (local), 0 visible codenames |
| Regression `GET /console` | **200** |
| Regression `GET /agent-loop` | **200** |
| Regression `GET /agent` | **200** |
| Regression `GET /api/a11oy/v1/code/capabilities` | **200** |
| `GET /cosign.pub` | **200** |

No regressions detected on existing surfaces. The `/restraint` page loads fonts via the
same Google-Fonts `preconnect` pattern used by sibling pages (`web/nemo.html`,
`web/console.html`, `web/energy.html`, etc. — 35 repo files use it); all **application
logic** loads from local `/static/` and `/vendor/`, so the "0 runtime application-logic
CDN" doctrine holds.

---

## 7. Files shipped (additive-only)

| Repo path | Role |
|-----------|------|
| `szl_restraint.py` | the module (ladder + intensities + Λ + receipts + energy + 3 endpoints) |
| `web/restraint.html` | live UI panel (`/restraint`) — ladder, ceilings, signed receipts, bench, `SZLLabels` badges |
| `serve.py` *(edited, +2 inserts)* | page routes `/restraint` + `/a11oy/restraint`; module `register(...)` block |
| `Dockerfile` *(edited)* | `COPY szl_restraint.py ./` + `COPY web/restraint.html ./web/restraint.html` |
| `.github/copy-sync-lockstep.json` *(edited)* | `web/restraint.html` added to `image_only_assets` (CHECK3) |
| `benchmarks/restraint/promptfooconfig.yaml` | promptfoo two-arm config (flips ROADMAP→MEASURED when run) |
| `benchmarks/restraint/README.md` | benchmark methodology + honesty contract |

**CI guards satisfied:** `copy-sync-lockstep-guard` (CHECK1/2/3 all verified for the
additions), `dockerfile-copy-guard`, `hf-sync-backend.yml` (auto-mirrors the COPY'd `.py`),
`doctrine-grep` (0 banned tokens), `overclaim-guard` (Λ/Conjecture 1 kept OPEN throughout),
`namespace-leak-check`, codename gate (0 hits). `ast.parse` (Python) and `node --check`
(inline JS) ran clean before push.

---

## 8. Commit SHAs / identifiers

- **GitHub `main` HEAD:** `57c7029c53adce0ffe00f482b2a70f656a3d7970`
  (prior HEAD before push: `36b9c191b32b4347e9fccd3c4d6b8d0adc47125a`)
- **HF Space commit (serving):** `714d76da115b58bc0ef8a85eed3074bef7836391`
- **HF factory-rebuild sha:** `0b471373d5dd047085f1bd09e4b1e427dfca290a`
- **Space domain:** `szlholdings-a11oy.hf.space`
- **Doctrine:** v11, kernel `c7c0ba17`, locked=8

---

## 9. Honesty ledger (MEASURED vs SAMPLE/ROADMAP/MODELED)

| Claim | Honest label | Why |
|-------|--------------|-----|
| Ladder rung decision | **HEURISTIC** | deterministic rule advisory, not a proof |
| Λ score | **advisory, < 1.0; Conjecture 1 OPEN** | not a closed theorem |
| Signed receipt | **REAL** | live crypto-verified vs `/cosign.pub` this audit |
| `lines_saved` | **MODELED** | transparent baseline-LOC proxy × per-rung reduction |
| Benchmark rows / overall | **SAMPLE / ROADMAP** | no model wired; fixtures, not our measurement |
| Energy joules | **MODELED**, joules `sample` | no on-box NVML exporter wired |
| Ponytail's published numbers | **CITED (Ponytail's, not ours)** | adopted, not claimed |

Nothing in this capability is labelled MEASURED that was not actually measured. The two
flips to MEASURED (benchmark model run; sovereign energy exporter) are documented and
one-step-away, not faked.

---

*Adopted from Ponytail (MIT, © 2026 DietrichGebert) — <https://github.com/DietrichGebert/ponytail>.
Governance (signed receipts + Λ), honest measurement, and the energy tie-in are a11oy's.*
