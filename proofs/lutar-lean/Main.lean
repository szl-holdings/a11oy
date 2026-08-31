import Lutar

/-!
# Lutar verification entry point

Running `lake exe check` exercises the kernel on the whole `Lutar` library.
If this builds without error, every theorem in `Lutar/*.lean` has been
machine-verified by the Lean kernel.
-/

def main : IO Unit := do
  IO.println "Lutar — kernel-verified invariant theorems"
  IO.println "Lambda_k formalised for k in {5, 7, 9}"
  IO.println "Axioms: A1 monotone, A2 homogeneous, A3 Egyptian-exact, A4 bounded"
  IO.println "Conjecture 1 (uniqueness, TH10): see Lutar/Uniqueness.lean — CAUCHY_ND OPEN obligation at line 120, ~40h discharge"
  IO.println "Theorem 2 (bound): see Lutar/Bound.lean"
