import Lake
open Lake DSL

package «lutar» where
  -- Lean 4 + Mathlib package for the Lutar Invariant uniqueness theorem.

require mathlib from git
  "https://github.com/leanprover-community/mathlib4.git" @ "v4.13.0"

@[default_target]
lean_lib «Lutar» where
  -- Library root: Lutar/

lean_lib «RefVectors» where
  -- Top-level module imported by MainRef; declared as its own lean_lib so
  -- `lake exe ref_vectors` can resolve `import RefVectors`.
  roots := #[`RefVectors]

@[default_target]
lean_exe «check» where
  root := `Main

lean_exe «ref_vectors» where
  root := `MainRef
  -- Reads reference-vectors.json (TS-generated) and asserts Λ₉ parity
  -- between the Lean-side Float implementation and the production TS
  -- runtime. CI invokes:  lake exe ref_vectors <path-to-json>
