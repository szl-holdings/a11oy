# Formula authority

`formula-registry.v1.json` is a **legacy transport filename** retained because the
existing A11oy container publisher copies that exact path. Its payload is
`szl.formula-authority.v2`; the former locked-five dispute crosswalk is
superseded.

## Authority chain

```text
szl-holdings/lutar-lean
  @ c497b4ed402249f23da7f290426f0e21c70ab926
    ├─ Lutar/Wave8/AxiomDisclosure.lean
    │    └─ locked_count_eight
    ├─ Lutar/Puriq/Formulas/ProvedFormulas.lean
    │    └─ F1 F4 F7 F11 F12 F18 F19 F22
    └─ Lutar/Round13/Lambda_Uniqueness.lean
         └─ F23 remains Conjecture 1 advisory
```

The exact locked-proven set is:

```text
F1, F4, F7, F11, F12, F18, F19, F22
```

Each source is bound by repository, full commit, path, and Git blob SHA. The
registry payload has a deterministic SHA-256 digest. It is honestly `UNSIGNED`;
a digest and Git pin prove integrity/lineage, not signer identity.

## Namespace and action boundaries

`szl-holdings/szl-formulas` exposes 21 callable software functions. The formal
F-number corpus and those callable names are separate namespaces. Their mapping
is `UNKNOWN_NOT_ASSERTED` until a proved binding artifact exists.

A locked formula can constrain execution only after an explicit, evidence-bound
applicability decision. No formula independently authorizes a consequential
action. A11oy remains the action-admission authority, and F23/Lambda can never be
the sole basis for `ALLOW`.

## Historical snapshots

The following files remain historical/reference inputs, not runtime formula
authority:

- `static/thesis.json`
- `corpus/formulas/lutar-lean__PROVEN_FORMULAS.md`
- `proofs/lutar-lean/**`
- `knowledge.json`

Training may teach the model how to apply formulas and abstain, but every runtime
request must re-bind formula identity, maturity, source commit, applicability,
and evidence to the v2 authority digest.
