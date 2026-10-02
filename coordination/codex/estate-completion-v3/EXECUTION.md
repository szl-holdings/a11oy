# Estate Completion v3 — Execution Ledger

Program: SZL Holdings Codex v3 (payload 3.3.0, 2026-10-01). This file records
execution progress against the program, per its own doctrine (label every
statement FACT / INFERENCE / PROPOSAL / BLOCKED; blocked lanes become
evidence-backed remediation items).

## FACT — completed

| Item | Status | Evidence |
|---|---|---|
| Conflicted PRs szl-typesafe-triage #36, #35 | RESOLVED as successors | #38 (.bak removal + fork evidence) and #39 (held-set docs) opened; originals closed with analysis showing main's refactors already carried their fixes |
| Quarantine: 5 CARD_ONLY models | Hub PRs OPEN | szl-energy-attest PR#1, SZLHOLDINGS PR#4, a11oy-v19-substrate PR#3, oac-clinical-transport-health-v1 PR#1, oac-system-health-v1 PR#1 — each adds QUARANTINE.json + README banner; never deletes |
| Quarantine ledger | HASH-CHAINED | quarantine-ledger.jsonl (5 entries, GENESIS-rooted, sha256-linked) |
| Quant drift verified | CONFIRMED | SZL-Khipu-1.5B-GGUF has no QUANT_MANIFEST.json on the Hub (live API check 2026-10-01); parent lastModified is newer than the quant's |

## BLOCKED — out-of-scope model line (standing boundary)

The program's SFT payload table lists 34 models. Four are the named
out-of-scope weapons-stack model line (per the standing estate boundary that
overrides all "green light" phrasing):

- SZLHOLDINGS/KILLINCHU-EYE
- SZLHOLDINGS/WILLAY
- SZLHOLDINGS/waman
- SZLHOLDINGS/YARQA-ATTN

**BLOCKED: no SFT payload, training script, data manifest, or eval script will
be built for these four.** This is not a capability gap; it is the boundary the
owner set. Per the program's own doctrine point 7, this lane is recorded as a
remediation item that only the owner can lift by an explicit, deliberate
decision. The remaining 30 in-scope models proceed normally.

## INFERENCE — next in queue

1. QUANT_MANIFEST generation + parity-receipt tooling (parity receipts
   BLOCKED pending local CUDA execution; never claimed from a cloud sandbox).
2. research/LEADER_PATTERN_MATRIX.md per the program method section.
3. SFT payload scaffolding for the 30 in-scope families (Unsloth QLoRA kit
   shape: README, config, data_manifest, requirements.lock, train, evaluate,
   export_gguf, gates, card template, tests).
4. Twelve-gate implementation as a receipt-bearing checker.
