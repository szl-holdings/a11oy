# Doctrine pre-check (local, advisory)

A fast local mirror of the org doctrine guard's highest-value honesty invariants,
so overclaims are caught **before push** instead of failing CI on a PR.

> The authoritative gate is the reusable CI workflow `.github/workflows/doctrine-check.yml`.
> This local check is advisory and intentionally simpler (it has a smaller exemption set).
> If a local hit is a false positive, the CI guard has the full exemption logic.

## What it checks
- **Λ = Conjecture 1** — flags Λ described as a "theorem" without a conjecture/conditional/Theorem-U qualifier.
- **SLSA L3 banned** — any L3 claim not scoped as roadmap/not-achieved.
- **SLSA L2 evidence-gated** — on non-verified repos, a bare L2 claim must be scoped (roadmap) or reference verified product images (a11oy/killinchu).
- **No positive compliance claims** — Iron Bank / FedRAMP High|Moderate / CMMC L2-5 / SWFT / Mission Owner without a roadmap/negation scope.
- **Kernel commit** — locked-kernel claims must stay `c7c0ba17`.

## Use
```bash
make doctrine                 # scan the repo (advisory)
make doctrine-hook            # install the git pre-commit hook
# or directly:
bash .github/scripts/doctrine_precommit.sh
bash .github/scripts/install-doctrine-hook.sh
DOCTRINE_SKIP=1 git commit …  # bypass the hook once
```

Honesty doctrine v11: locked-proven = 8 `{F1,F4,F7,F11,F12,F18,F19,F22}` (see
`.github/data/lean_numbers.json` → `locked_formula_count`); Λ = Conjecture 1;
Khipu = Conjecture 2; SLSA L1 honest; kernel `c7c0ba17`.
