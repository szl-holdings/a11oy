# Sentra receipt-verifier current-main successor

- `workcell_id`: `A11OY-SENTRA-VERIFIER-CURRENT-MAIN-20260905`
- `source_base`: `94e129d016a7e82e0b22f11c00ea877b5cc430f5`
- `supersedes_candidate`: `#1981` / `45f12bcd0dca42a44d289b1462d6b5ef79d39ad6`
- `state`: `OPEN_REPAIR`

## Objective

Port only the reviewed Sentra receipt-verifier semantic correction from #1981 onto current protected main without replacing newer Terra/runtime/publisher work already present in the shared generator.

## Required semantic delta

- Sentra upstream becomes the read-only `/api/a11oy/v1/verify/receipt` manifest.
- Evidence language and schematic become receipt/signature/digest/chain/verdict oriented rather than cyber-feed/admission oriented.
- Remove unsupported admission claims; endpoint availability must not be represented as a receipt verdict.
- Preserve every unrelated current-main change in `scripts/hf_publish_vertical_flagships_v4_impl.py` and its tests.
- Port/update the focused Sentra regression coverage from #1981.

## Acceptance

Fresh exact-head hosted matrix including HF module-drift guard, focused Sentra tests, no unresolved Codex findings, and no provider/source/security boundary weakening. No direct provider mutation is authorized by this workcell.
