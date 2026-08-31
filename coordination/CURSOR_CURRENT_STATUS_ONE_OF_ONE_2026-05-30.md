# Cursor current status — one-of-one execution loop

## Read and acted on

- Uploaded `CURSOR_ONE_OF_ONE_MASTER_2026-05-30_c16d.md`.
- `.github#89` master directive.
- `.github#82`/`#76` latest comments.
- Runtime audit agents for proof, UDS/HF, TypeScript runtime, Sentra, Amaru/Rosie.

## Completed in a11oy

- `cursor/frontier-functional-upgrades-2f18`
  - exports tested a11oy-core formulas;
  - exposes `ALL_THEOREMS/getTheorem` for TH1-TH7;
  - hardens receipt verification (`receipt_id`, sequence continuity, impossible quorum);
  - adds real `packages/policy` package surface;
  - adds `test:runtime` covering policy, receipts, QEC, theorem lookup, doctrine.
- Validation passed:
  - `npm run typecheck:policy`
  - `npm run test:runtime`
  - `npm run payload:verify`
  - `npm run payload:huggingface`

## Completed proxy work

- `cursor/proxy-agi-forecast-fg-pipeline-2f18`
  - FG-S1→S4 pipeline patch; already applied as `agi-forecast#42`.
- `cursor/proxy-lutar-kernel-green-2f18` / combined triage variants
  - installed Lean 4.13.0 locally;
  - ran real `lake build`;
  - produced local kernel-green patch/log;
  - build log ends `Build completed successfully`;
  - does not close 7 known sorries.

## Latest Lean state from local work

- Kernel-green achieved locally under proxy patch.
- Known sorries remain 7; no fake closure claimed.
- Patch scopes brittle overclaims into tracked obligations without adding axioms/sorries.

## Still blocked by access

- Direct push/comment to sibling repos is still blocked by `cursor[bot]` identity.
- PR/comment creation via `gh` still often fails `Resource not accessible by integration`.
- Perplexity proxy pattern remains required for `lutar-lean`, `.github`, `agi-forecast`, `sentra`, `amaru`, `rosie`, `uds-mesh`, `vessels`.

## Highest next items

1. Proxy/verify/merge Lutar kernel-green patch in `lutar-lean` with real `lake build`.
2. Merge/apply `agi-forecast#42`; then continue competition-math v2 judge/harness.
3. Merge/apply a11oy runtime hardening branches.
4. Start Sentra/Amaru/Rosie real tests + receipt verification patches from audit agent outputs.
5. Keep UDS v0.3.0/v0.3.1 honest: no signed-asset claim until assets verify.
