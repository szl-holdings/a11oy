<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# A11oy Anatomy v6 evidence view

Scope: an additive, read-only A11oy product view at `/anatomy-v6`, backed by
the Python `szl_anatomy_brainloop` service. It does not replace
`szl-holdings/anatomy` or the creator-profile `betterwithage/anatomy` companion,
which already documents its own v6/v7 layers. Existing `/anatomy-v5` and
Wire-D's version/authorization claims are unchanged.

## Read contract

`GET /api/a11oy/v1/anatomy/evidence` returns `szl.anatomy.evidence/v6` with
`MODELED`, `READ_ONLY`, `SUMMARY_ONLY` and explicit `NONE` authority. It replays
the local overlay already available to this runtime, exposing counts only.
No query, private note text, node identifiers, graph harvest, model inference,
gradient training, file creation, receipt signing or provider request occurs.
An unreadable overlay is HTTP 503 `UNAVAILABLE`, not fabricated zero counts.
Only a missing file (including a missing parent directory) represents an empty
overlay. A directory, another nonregular target, an inaccessible parent, or an
invalid parent component is an unavailable replay, including after a previous
empty result was cached. Reads create neither an overlay nor its parent.

For writes without `SZL_BRAIN_OVERLAY`, the existing local-then-temporary-directory
selection uses an actual append probe on the authorized write path. An existing
read-only local log therefore does not block a usable temporary fallback. The
pulse replays the selected target before constructing its receipt, then appends
and consolidates against that same target. Subsequent readers in that process
follow the selected target without repeating the probe. The two logs are never
copied or merged. An explicit `SZL_BRAIN_OVERLAY` remains authoritative; a failure
there is reported rather than redirected to another log.

The existing self-audit route and indirect loop-health reader now preview
demotions without applying them. The compatibility `demotions` list is a list
of proposals; `demotions_applied=false` is explicit. Applying proposals through
a separately authorized, receipted write path is **ROADMAP**. In particular,
reading an audit does not repair a broken receipt chain. A later locally matching
link cannot restore an invalid prefix. Hash consistency is not signature
verification, external signer trust, semantic correctness or authorization.

`POST /api/{namespace}/v1/anatomy/pulse` retains the existing pulse behavior but
now requires the established operator Bearer principal before the body is read,
inference attempted, or an overlay write is reached. Missing, wrong or
unconfigured credentials and resolver failures are denied. The shared
`szl_operator_auth` implementation is reused without altering its byte-pinned
source. This credential gate does not qualify the existing pulse's scientific
outputs or confer two-person approval.

The existing second brain remains retrieval context, external to model weights.
The v6 view links to the existing `/brain` and same-origin second-brain alias;
it does not introduce an external retriever, silently ingest a corpus, convert
a retrieved note to a system instruction, or grant memory execution authority.

## Evidence lanes and publication

Source, runtime, model evaluation and authorization are separate lanes. Local
synthetic software tests establish only the behavior they exercise. They do not
qualify Khipu abstention, Named-N, medical devices or clinical results. A source
merge is not a Hugging Face publication, deployment witness or live domain.
The existing canonical `hf-sync.yml` remains the only automatic Space writer;
its current inspection/recovery holds are not changed by this feature.

The existing Dockerfile already copies `szl_anatomy_brainloop.py`,
`a11oy_ecosystem_atlas.py`, and the complete `pages/` directory. Registration
uses these owning modules ahead of the application fallbacks. New routes are
added to the demo-critical regression list; no existing gate is relaxed.

## Research lineage, not a performance claim

Separating memory records from authority and preserving unsupported claims
draws inspiration from [Zep temporal memory](https://arxiv.org/abs/2501.13956),
[LongMemEval](https://arxiv.org/abs/2410.10813), and
[ALCE citation evaluation](https://arxiv.org/abs/2305.14627). This change is an
original bounded SZL integration; no third-party implementation, managed-service
benchmark or first-ever scientific claim is adopted. Bitemporal claim storage,
human-reviewed contradiction queues and held-out grounded-answer benchmarks
are separate **ROADMAP** work, not implemented by this summary view.

Validation commands for the source slice:

```text
python -m pytest -q tests/test_anatomy_read_boundary.py tests/test_anatomy_v6_page_contract.py
python -m pytest -q tests/test_anatomy_v5_contract.py
python test_anatomy_loop.py
python -m pytest -q tests/test_demo_critical_routes.py
python -m ruff check --select E9,F szl_anatomy_brainloop.py a11oy_ecosystem_atlas.py tests/test_anatomy_read_boundary.py
git diff --check
```

Run results and exact source/CI/publication observations belong in the PR's
release evidence. Commands listed here are not a claim that every command ran.
