# SZL FINAL FRONTIER CONVERGENCE PAYLOAD

        Canonical sentence:
        **SZL Holdings builds a11oy: AI that can demonstrate its work through governed execution and offline-verifiable receipts.**

        ## One-shot Python payload

        ```python
        import pathlib
        import subprocess

        ROOT = pathlib.Path(__file__).resolve().parent
        subprocess.run([sys.executable, "-I", "-B", str(ROOT / "tools" / "szl_convergence_bootstrap.py"), "--run"], check=True)
        ```

        ## Command probe status

        - `frontdoor_repair_idempotent`: PASS (return=0, duration_ms=74)
- `frontdoor_truth`: PASS (return=0, duration_ms=76)
- `github_access_audit`: PASS (return=0, duration_ms=7058)
- `hf_ecosystem_check`: PASS (return=0, duration_ms=7765)

        ## Claims ledger (seeded)

        | Claim | State | Severity | Evidence | Statement |
        | --- | --- | --- | --- | --- |
        | C-01 | MEASURED | HIGH | audit/frontier-command-probes.json#frontdoor_truth | Canonical host policy remains a-11-oy.com as user public surface; a11oy.net is redirect-only.... |
| C-02 | MEASURED | HIGH | audit/github-access-audit.json | GitHub access and entitlement evidence reflects 9 checked sibling targets and 4 write-ready repos in one authenticated s... |
| C-03 | MEASURED | HIGH | docs/huggingface-ecosystem-manifest.json | Hugging Face public snapshot is live and auditable from stephenlutar2-hash.... |
| C-04 | MEASURED | HIGH | a11oy_frontier_page.py | Domain policy and landing page claim text are reconciled with 26-space public registry semantics.... |
| C-05 | ROADMAP | MEDIUM | tools/lexicon_gate.py | Lexicon lock (five disallowed legacy names) is enforced by repository gate, not marketing copy.... |
| C-06 | UNKNOWN | HIGH | a11oy_canonical_domain.py | Domain guard status: ERROR:No module named 'a11oy_canonical_domain'... |

        ## Contradictions ledger (seeded)

        | ID | Status | Release blocker | Refutes | Statement |
        | --- | --- | --- | --- | --- |
        | B-01 | OPEN | True | C-01, C-04 | Flagship vs full-space publication claims must not mix 26-space registry with 5-space doctrine.... |
| B-02 | OPEN | True | C-03 | Stale operational counts must remain SNAPSHOT(2026-05-12) until new public evidence is re-probed.... |
| B-03 | OPEN | False | C-05 | Legacy names (e.g., discontinued product labels) must not be presented as current doctrine.... |

        ## Verification rules

        * Do not fabricate values. `UNKNOWN` is explicit debt.
        * Banned legacy names are blocked by `tools/lexicon_gate.py`.
        * `tools/release_gate.py` must pass for production release.

        ## In-toto action predicate

        This run uses `schemas/szl-governed-action-predicate.v1.schema.json`.