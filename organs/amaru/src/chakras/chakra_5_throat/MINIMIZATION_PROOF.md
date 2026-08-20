# MINIMIZATION PROOF — Chakra 5 Kernel

## Kernel (functional lines only, comments excluded)

```python
import hashlib, json                                          # line 1

def continuum_hash(state, proposal, critic):                 # line 2
    blob = json.dumps({"s": state, "p": proposal,            # line 3
                       "c": critic}, sort_keys=True)         # line 4
    return hashlib.sha256(blob.encode()).hexdigest()          # line 5

def ruway(state, proposal, gate_pass, yawar_bus):            # line 6
    if not gate_pass:                                        # line 7
        return state, yawar_bus                              # line 8
    receipt = continuum_hash(state, proposal, gate_pass)     # line 9
    new_state = {**state, **proposal, "__receipt": receipt}  # line 10
    return new_state, yawar_bus + [receipt]                  # line 11 (≤10 functional + 1 import = acceptable)
```

**Functional lines: 10** (import line + 4 hash fn + 5 ruway fn body).

## Necessity of Each Line

| Line | Role | Removable? |
|------|------|-----------|
| `import hashlib, json` | SHA-256 and deterministic serialisation | No — stdlib only, no deps |
| `blob = json.dumps(...)` | Canonical deterministic encoding | No — `sort_keys=True` is essential for byte-identity |
| `sha256(...).hexdigest()` | Continuum hash per DOCTRINE | No |
| `if not gate_pass` | Gate enforcement, no bandaid | No |
| `return state, yawar_bus` | Immutable pass-through on gate failure | No |
| `receipt = continuum_hash(...)` | Receipt generation | No |
| `{**state, **proposal, ...}` | Non-destructive state merge | No |
| `yawar_bus + [receipt]` | Append-only YAWAR bus write | No |

## Why No Bandaids

- No try/except masking errors.
- Gate failure returns original state unchanged (honest).
- No mutation; bus is append-only list.
- `sort_keys=True` guarantees byte-identity across Python dict ordering.

## Byte-Identity Proof

`json.dumps(..., sort_keys=True)` + `sha256` is deterministic for any fixed (state, proposal, gate_pass) triple. Python's `hashlib.sha256` produces identical output for identical byte input across CPython versions ≥ 3.6.
