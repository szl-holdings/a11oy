# a11oy — governed-AI command substrate (v1 slice)

## Prime directive

a11oy issues signed, offline-verifiable receipts proving what an AI agent was
authorized to do, what it actually did, and whether the required evidence
exists. (CANON section 2, verbatim.)

## Truth states

Every claim, metric, and surface in this repository carries exactly one truth
state. There is no fourth state.

- **VERIFIED** — backed by evidence linked in this repository or attached to
  a receipt.
- **UNKNOWN** — audited; no evidence exists yet. An honest state, not a blank.
- **UNAVAILABLE** — the source exists but cannot legally or technically be
  retrieved. Stated, never rendered as an empty field.

Zero-Bandaid Law: no claim without evidence; no empty states rendered as
blanks. A public claim lacking evidence auto-demotes to `UNKNOWN`. `UNKNOWN`
is an audited state; an empty field is an oversight. Applies to code output
too: no `pass`, no `NotImplementedError`, no "mock for now", no TODO stubs
shipped as done. Enforced by tools/lexicon_gate.py (docs) and
tools/release_gate.py (ledgers).

## The Laws (enforced in code)

Full wording: CANON section 3. Summary: default DENY; receipts never record
service accounts; missing evidence means INCOMPLETE, never PASS; signature is
integrity, not truth; four never-collapsed side-effect classes with
IRREVERSIBLE always requiring human approval; the Flight Recorder acknowledges
local durability only (remote sync is a visibly PENDING_SYNC state); replay is
non-mutating; `stage=RUNNING` is never evidence of a deployed revision; never
claim blanket regulatory compliance — the approved wording is "Article 12
logging conformance profile".

## Build and verify (fresh clone)

```bash
python3 tools/szl_master_bootstrap.py --run   # scaffold (idempotent)
python3 tools/lexicon_gate.py                 # docs language gate
python3 tools/release_gate.py                 # commercial truth gate
python3 tools/demo_harness.py                 # 12-step acceptance demo
```

Expected Week 1 state: bootstrap green; lexicon_gate exits 1 until the seeded
footnote in docs/positioning/AUTO_REVIEW_DELTA.md is deleted; release_gate
exits 1 while any raise-blocking COMMERCIAL_LEDGER row is not VERIFIED.
The flip procedure for both is in docs/RUNBOOK_WEEK1.md.

Dependencies: Python 3.11+, pydantic>=2.12, cryptography>=50 for the slice.
Production signing additionally needs
`pip install "in-toto-attestation>=0.9.3" "securesystemslib>=1.0"`.
YAML in this repository is the SZL-YAML-1 subset (tools/szl_miniyaml.py);
pyyaml is never assumed to be installed.
