import RefVectors

/-!
Entry point for `lake exe ref_vectors`. Reads the reference-vectors JSON
shipped from the platform monorepo (path passed as argv[0], default
`reference-vectors.json` in CWD) and checks bit-tolerant Λ₉ parity.
-/

def main (argv : List String) : IO UInt32 := do
  let path : System.FilePath :=
    match argv with
    | p :: _ => p
    | []     => "reference-vectors.json"
  IO.println s!"Lutar RefVectors check — reading {path}"
  RefVectors.checkFile path
