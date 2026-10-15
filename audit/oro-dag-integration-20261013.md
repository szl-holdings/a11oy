<!-- SPDX-License-Identifier: Apache-2.0 -->
# ORO evidence DAG integration — local evidence, 2026-10-13

Evidence class: **MEASURED local test harness**, **DECLARED source bindings**.
Repository: `szl-holdings/a11oy`. Branch:
`feat/oro-evidence-dag-integration-20261013`, based on
`de36cfea838e23520a4b5e2850c557e2f870a439` (`origin/main` at branch creation).
PR #2731 was already merged before this follow-up work; its checks do not qualify
this candidate.

## Implemented boundary

- `oro.source_adapters.project_source_snapshots` reads at most 33 recent nodes
  from an existing Wire F Khipu DAG and projects at most 32. A missing earlier
  parent marks the window partial. The function never constructs or ticks the
  KhipuOS checkpointer and never calls a receipt writer or signer.
- Second Brain contributes at most 12 citation pointers only with an explicit
  immutable commit revision. The revision association and pointer contents
  remain **DECLARED/UNKNOWN**; lexical scores, notes, queries, and source paths
  are not projected.
- The external Anatomy observation contract contributes one source binding for
  its modeled DAG snapshot. Its topology nodes do not supply individual content
  hashes. The outer observation state, including `STALE`, stays separate from
  the modeled topology state. This adapter validates the serialized projection
  shape, including `depends_on` and `control_after`, while failed observations
  contribute no node. It does not replay Anatomy source-file hashing or raw
  effect checks.
- Hatun's local `retrieve_handles` adapter offers four literal identifiers
  without a digest or immutable revision, so it contributes zero evidence
  nodes, including on refusal. No cross-source causal edges are inferred.
- Every node in this inspection projection is `UNVERIFIED`. Projection digests
  are local SHA-256 checksums, not Khipu receipt digests, signatures, or Lean
  proof bindings. Execution, promotion, and signing authority are false.

## Local verification

| Check | Exact command or action | Result |
| --- | --- | --- |
| Focused and operational Python tests | `C:\Users\steph\AppData\Local\Programs\Python\Python311\python.exe -m pytest -q oro/test_brain_anatomy_contract.py oro/test_evidence_dag.py oro/test_source_adapters.py tests/test_oro_operational_v3.py --basetemp=.pytest-oro-20261013-run7` | **MEASURED: 52 passed**, 13 dependency/deprecation warnings; no test failures. |
| Python compilation | `C:\Users\steph\AppData\Local\Programs\Python\Python311\python.exe -m compileall -q oro tests/test_oro_operational_v3.py` | **MEASURED: passed**. |
| Doctrine banned-token scan | `C:\Users\steph\AppData\Local\Programs\Python\Python311\python.exe scripts/check_banned_tokens.py --root . --allowlist .doctrine-allowlist` | **MEASURED: 4,506 files scanned, 0 hits**. |
| Doctrine scanner negative controls | `bash scripts/check_banned_tokens.test.sh` using the installed Python interpreter as `python3` | **MEASURED: 19 passed, 0 failed**. |
| Patch whitespace | `git diff --check` and `git diff --cached --check` | **MEASURED: passed**. |

The first operational pytest attempt failed at fixture setup because the
sandbox denied the default Windows temporary directory. The rerun used a
fresh workspace-local `--basetemp` and passed. No production service was
deployed or probed. Protected PR checks, independent source replay, hosted
runtime state, and proof qualification remain **UNKNOWN** pending their own
exact-revision evidence. No merge or deployment is authorized by this report.
