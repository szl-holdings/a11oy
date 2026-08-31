# payloads/round-10-estate — SZL Full Estate Convergence (Round 10)

One self-contained, additive module. Nothing here overwrites the existing
`tools/lexicon_gate.py` or `tools/release_gate.py` (round-5, already in CI).
This module adds what does not yet exist in the estate:

| New here | Why it is load-bearing | Path |
|---|---|---|
| `a11oy/` core | TypedPolicyEngine · SegmentedFlightRecorder · receipts (Ed25519, honest demo fallback) · OfflineVerifier | `payloads/round-10-estate/a11oy/` |
| Proof-surface demo | 12-step deny→approve→tamper→INCOMPLETE→PENDING_SYNC→replay→Art.12 sequence; every verdict asserted in code | `payloads/round-10-estate/demo/proof_surface_demo.py` |
| `raise_gate.py` | 24 commercial facts under the SAME CI law as technical claims; all UNKNOWN, all block a raise | `payloads/round-10-estate/tools_raise_gate.py` |
| Ledgers | claims / contradictions / commercial, Zero-Bandaid enforced | `payloads/round-10-estate/ledgers/` |
| Article 12 profile | machine-readable, one resolver per statutory row | `payloads/round-10-estate/conformance/ARTICLE12_PROFILE.yaml` |
| Live audit artifacts | GitHub org (100 repos, 12 PRs classified), HF org (43/29/45/18), domains | `payloads/round-10-estate/audits/` |
| Master bootstrap | runs the whole stack, emits a signed pass receipt | `payloads/round-10-estate/payloads/master_bootstrap.py` |

## Run it

```bash
python3 payloads/round-10-estate/demo/proof_surface_demo.py     # 12/12 must PASS
python3 payloads/round-10-estate/tools_raise_gate.py .          # exit 1 by design (the checklist)
python3 payloads/round-10-estate/payloads/master_bootstrap.py --run
```

## What this module deliberately does NOT do
- Does not touch the round-5 gates at `tools/lexicon_gate.py` / `tools/release_gate.py`.
- Does not commit any signing key (demo keypairs are runtime-generated and `.gitignore`d).
- Does not merge, close, or modify any PR — it classifies. Merge decisions stay human.

## Relationship to open PR #1534
`a11oy#1534` (feat(governance): round-10 truth gates) is Codex's in-flight
implementation of this same round. This module is the audited reference
build to compare PR #1534 against. Keep #1534 HUMAN_REQUIRED.
