<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# BOb reference audit and SZL Observer implementation boundary

Historical prototype status (2026-10-01): not registered, published, or deployed. Base:
`e6d1a43e3ef90d9267243b6b79076b2edc826ee7`. Client date: 2026-10-01,
America/New_York. Public reads and local tests are not operational qualification.

## Public evidence and limits

Reference: <https://bob.bzzzbx.com/dashboard.html>. A certificate-verified,
unauthenticated HTTP GET returned 200, text/html UTF-8, 836,478 bytes, SHA-256
`2017c7fe8e20c211874444bb4dc9988ed56e8b1539785ff408450528e967a2ab`.
This is the public HTML response, not a pinned upstream source release.

The visible document contains industry/channel configuration, dashboard metrics,
anomaly/alert/action panels, simulation controls, and AI explanation/chat panels.
Its client generates some counts with random numbers and requests generated
business data through `/api/ai`. Displayed activity is therefore not uniformly
observed telemetry. AI backend responses and action endpoints were not invoked.

Public source findings, not exploit or backend-test results:

- Model-returned strings enter HTML interpolation sinks. An SZL implementation
  must render untrusted text as text, validate structured responses, and preserve
  the simulation/observation boundary. Upstream server sanitization is unknown.
- The sampled response had HSTS but no enforced CSP, X-Frame-Options, or
  Referrer-Policy headers. Do not inherit this security posture.
- The document references external fonts; A11oy must use its local KANCHAY assets.
- The large single HTML document warrants mobile and performance measurement;
  no visual, accessibility, layout, latency, or device benchmark was completed.
- No code/asset reuse license or upstream repository was verified. No BOb code,
  branding, assets, trained model, or copied UI was included in this prototype.
- Authentication, tenant separation, persistence, connector accuracy, action
  governance, and scientific/model validation remain NOT_VERIFIED.

## Independent design and implemented slice

Use a shared evidence observer, not one universal confidence score. Observed
signals, synthetic scenarios, rankings, empirical intervals, review dispositions,
and policy decisions have different meanings and must remain separate fields.

`szl_observer_kernel.py` belongs to services/provenance. It is pure and bounded:
no HTTP, storage, model training, receipt minting, or action execution. Its seven
domain profiles are contracts, not working live connectors. It implements exact
SHA-256 payload binding; strict JSON/numeric/scope validation; independent-clock
freshness; immutable inputs; separate simulation labels; median/MAD descriptive
ranking; and a bracket that retains unresolved adjudications. Hash consistency
does not establish source authenticity, scientific correctness, or qualification.

Local focused result after review repairs: 58 tests passed. Existing production
readiness and the other estate repositories were not qualified by those tests.
No workflow runs this new suite yet. No route imports the kernel, and no
Dockerfile, protected controller, live workflow, or deployment writer was changed.

## Vertical plan (integration remains ROADMAP)

| Vertical | First independently evidence-bound workflow | Non-claim |
|---|---|---|
| Cyber | Detection, control, incident, recovery timeline | No autonomous containment or certification |
| Finance | Data vintage, backtest, model and scenario comparison | No investment, trading, or credit approval |
| Data governance | Dataset lineage, access/consent/retention exceptions | No compliance approval from a score |
| Enterprise | Service dependencies, SLOs and recovery evidence | Reachable is not operationally ready |
| Real estate | Dated records plus spatially scoped hazard exposure | No building-specific structural safety verdict |
| Law | Source version, jurisdiction, effective date and disposition | Provenance is not legal correctness |
| Seismic | Catalogue, station/waveform evidence and blind review | No earthquake prediction or safety alert |

Existing A11oy modules supply useful interfaces, not universal qualification:
`szl_provenance` on authorized writes only; `szl_operator_auth` with explicit new
route coverage; `szl_decision_uncertainty` for separately evaluated empirical
baselines. `szl_brainuncertainty` is retrieval-shape assessment and
`szl_semantic_entropy` contains modeled examples, not a validated hallucination
detector. `a11oy_seismic` uses generic California aftershock parameters and needs
bounded numeric/sequence qualification before any new forecasting product.

The existing `szl-seismic-review` pilot should be repaired, not duplicated. Its
current public GitHub main was observed at signed
`701bb069ca92ca2a75dcb97b0a049f335a11ce89`; the preserved local checkout is older
and has dirty `app.py`. Neither its current implementation nor HF publication
was fully verified here. Preserve that dirty work. Blind reviewer identity and
waveform binding must be server-side and tested before any review write is exposed.

## Integration and release acceptance

1. Finish source review and reconstruct on then-current protected main; preserve
   the separate OAC handoff and receipt-verifier lanes.
2. Add the dedicated hosted tests and explicit bounded, authenticated adapters.
   Avoid candidate-controlled authority, on-read signing, or a second HF writer.
3. Register routes before the proxy/catch-all, deny unsupported methods, add
   Dockerfile payload coverage, and test the assembled topology.
4. Build a native KANCHAY view: evidence drawer, aged/unknown state, review queue,
   source-to-claim trace, and a separate scenario namespace. Prove mobile geometry
   and keyboard behavior in a browser; code inspection alone is insufficient.
5. Require signed exact-head review, required checks, normal protected merge,
   canonical HF publication, immutable readback, and independent runtime witness.
   Models require separate licensing, evaluation, calibration, and regional support.

## Primary references

- [W3C PROV](https://www.w3.org/TR/prov-overview/): entity/activity/agent lineage.
- [NIST AI RMF](https://airc.nist.gov/airmf-resources/airmf/5-sec-core/): documented measurement and uncertainty.
- [USGS earthquake terminology](https://www.usgs.gov/faqs/what-difference-between-earthquake-early-warning-earthquake-forecasts-earthquake-probabilities): forecasts, early warning, and prediction are distinct.
- [FDSN web services](https://www.fdsn.org/webservices/): separate waveform, station, event, and availability services.
- [Catalogue verification preprint](https://lsmeng.github.io/pdf/submitted-catalogue-verification.pdf): panel confirmability is not earthquake truth; no published performance is inherited by this kernel.
- [Licensing guidance](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository): public visibility does not establish a reuse license.

## Historical environmental hold (2026-10-01)

The host fell below 40 MB free during this work, then partially recovered to
about 392 MB, still below the safe material-build threshold. Source is preserved uncommitted;
no commit, push, PR, provider operation, CI cancellation, settings change, or
deployment was issued. Further material builds/downloads are paused pending disk
recovery. No user repository, model, backup, or evidence was deleted.

## 2026-10-02 local implementation extension

The kernel now has a bounded, exact-byte import adapter, a stdout-only command,
and a script-free HTML report in `szl_observer_contract.py` and
`scripts/review_observer_import.py`. The expanded kernel/import/CLI/report suite
passes 107 focused tests. An independent source reviewer found a Windows
redirected-stdout encoding defect; explicit UTF-8 HTML output and a cp1252-host
regression close that finding. Browser/mobile rendering remains NOT_VERIFIED.

A six-record synthetic example generated an actual SAMPLE/RANKED report at
2026-10-02T04:27:11.030703Z. It is a local dated output, not provider proof or
real telemetry. The report is `outputs/observer-synthetic-report-20261002.html`
in the parent task workspace; its SHA-256 is
`d93d6ebc8754fead9a08bdcbe3b4a28882ecfb7598a9df111bcbd6acfbe4c7bb`.
The supplied synthetic input can later become stale; do not reset its clocks
or relabel its output to make it pass. Re-evaluation uses the current clock.

The host subsequently recovered above the material-build threshold, but free
space remains volatile due to shared activity. No cleanup was performed here.
This prototype still has no route, hosted CI invocation, commit, PR, source
publication, or deployment. The managed GitHub CLI reports invalid authentication;
no credential was printed, changed, or substituted, and no unsigned API commit
was used. Preserve the source and requalify on then-current main before release.

## 2026-10-02 regression wiring and quota readback

The later pass prepared `.github/workflows/observer-contract-tests.yml` locally
and added parsed-workflow and design-token regressions. The updated suite passes
109 tests on Python 3.11.9, pytest 9.0.3, and PyYAML 6.0.3. This is a local result;
the workflow's Python 3.12 hosted target has not run. Read-only source QA found
no further material import/CLI trust defect. Browser/mobile acceptance remains
NOT_VERIFIED.

The dated synthetic input was re-evaluated without changing its timestamps. It
now returns HOLD / STALE_SOURCE and CLI exit 2, as required; the old SAMPLE
report remains a historical artifact, not a claim of current evidence.

Disk space recovered above the local-build threshold; no repository, model,
backup, evidence, or cache was deleted. The incomplete bundled Python runtime
was not modified. A small task-only hash-pinned pytest installation was used
with the existing system interpreter instead.

The prior invalid-authentication observation above is historical. The later
keyring-backed GitHub request instead reached an explicit API rate-limit 403
at 2026-10-02T22:04:17Z. Remote publication stopped; no credential substitution,
commit, push, PR, rerun, CI cancellation, HF/domain/settings mutation, or
deployment followed. The eight source-only files remain uncommitted on the
original prototype base. The dedicated workflow is prepared, not published,
and production route registration remains separate work.

## 2026-10-02 current-main reconstruction

GitHub quota recovered before the next release pass. This source-only candidate
was mechanically reconstructed on signed protected main
`606e21927a6b043dc7ed2cd4d46d17ec1acb465c`, preserving the original prototype
worktree and dated evidence. The initial signed reconstruction on `0be16b87`
was preserved unpushed as `a0001a403b12ab6989b882487b9726acc85b77e1` when main
advanced. Read-only inventory found no overlap with the earlier six open PRs;
all eight paths were independently confirmed absent at this newer exact base.
No hot assembler, existing workflow, deployment controller, Dockerfile, or
managed-payload input was changed by this source-only candidate.

The historical environmental and authentication observations above remain
dated history. This reconstruction is a source candidate, not live integration,
scientific qualification, hosted CI success, or provider publication. Observe
the exact signed head's required checks and review before release. Keep the
separate OAC, receipt, readiness, and civilian-observatory lanes disjoint.
