<!-- SCAFFOLD: design document only — no runnable code; not counted as an executable recipe -->
# 06 — UNIFICATION WITH EXISTING CHAKRAS
## Which Chakras Need Codex Sibling Rewrites

---

## Principle

Every chakra that currently holds schema definitions or instance constants *inline* in its main module code needs a `codex.py` sibling extracted. The rewrite is:
1. Extract all frozen schema definitions and instance registries from the chakra's current code
2. Move them to `codex.py` (auto-generated at build time from the daemon schema)
3. Replace inline definitions in the chakra code with imports from `codex`
4. Register the chakra's entity types in the QILLQA daemon's SchemaStore so future builds regenerate the codex correctly

This is a refactor, not a rewrite. Domain logic stays in the chakra. Frozen ontology moves to `codex.py`.

---

## Chakra-by-Chakra Assessment

### CHAKANA
**Status: HIGH PRIORITY — rewrite required**  
CHAKANA carries the rigidity graph (Maxwell M criterion). Its entity types (RigidNode, ConstraintBar, ChakanaGraph) and the fundamental rigidity constants are currently embedded inline.

Rewrite scope:
- Extract: `RigidNode`, `ConstraintBar`, rigidity formula constants, and the Maxwell pre-check invariant (`M_MINIMUM = 0`)
- Bake into `codex.py`: the initial chakra topology (8 entity types, 24+ constraint bars confirming M ≥ 0)
- Import in chakra: `from .codex import RigidNode, ConstraintBar, MAXWELL_M_FLOOR`

Maxwell check for CHAKANA's own schema (self-referential validation):
- j = 2 entity types (RigidNode, ConstraintBar)
- b = minimum 3 typed relations required (RigidNode→ConstraintBar, ConstraintBar→RigidNode×2)
- b = 3, j = 2: M = 3 − 6 + 6 = 3. **PASSES** (over-constrained, correct for a definitional schema)

---

### PIRWA
**Status: HIGH PRIORITY — rewrite required**  
PIRWA carries the Gibson-Ashby triangulation logic (feature dictionary, stretch/bend discrimination, n=1/n=2 material behavior mapping).

Rewrite scope:
- Extract: `PIRWAFeatureClass`, `StretchMode` (n=1), `BendMode` (n=2), `TriangulationEdge`
- Bake into `codex.py`: the PIRWA feature dictionary as frozen instances (all registered material-behavior mappings from the codex priors)
- Import in chakra: `from .codex import PIRWAFeatureClass, FEATURE_REGISTRY`

Gibson-Ashby check for PIRWA schema:
- Each `PIRWAFeatureClass` must have ≥ 3 typed relations (to `StretchMode`, `BendMode`, and at least one `TriangulationEdge`)
- Flat `PIRWAFeatureClass` → `StretchMode` only (2 relations) is rejected at build time

---

### SENTRA
**Status: MEDIUM PRIORITY — partial rewrite**  
SENTRA's inspection logic is procedural (not schema-heavy), but it carries the 10 HUKLLA tripwire definitions. These tripwire definitions are schema — they describe what constitutes a violation.

Rewrite scope:
- Extract: `HUKLLATripwire` class with `tripwire_id`, `description`, `shacl_shape_ref`
- Bake into `codex.py`: all 10 HUKLLA tripwire definitions as frozen instances
- Keep in chakra: the `evaluate()` logic (procedural, calls pySHACL)
- Import in chakra: `from .codex import HUKLLA_TRIPWIRES, HUKLLATripwire`

The SHACL shape file (`huklla_shapes.ttl`) referenced by tripwires is a separate build artifact — it is generated from the daemon schema alongside the codex.py.

---

### RUWAY
**Status: MEDIUM PRIORITY — light rewrite**  
RUWAY is primarily procedural (write gate). Schema content is minimal: `YAWARPacket` type definition and the list of permitted operations.

Rewrite scope:
- Extract: `YAWARPacket` dataclass, `PERMITTED_OPERATIONS` tuple
- Bake into `codex.py`: the frozen list of permitted operation types and their validation schemas
- Keep in chakra: commit logic, label-advance logic, receipt emission

---

### HUKLLA
**Status: HIGH PRIORITY — rewrite required**  
HUKLLA is the sovereignty layer. If any chakra needs a `codex.py` deeply, it is HUKLLA — its 10 tripwires are the core ontological constraints of the entire system.

Rewrite scope:
- Extract: full tripwire taxonomy (all 10 tripwires with their semantics, thresholds, and SHACL shape references)
- Bake into `codex.py`: frozen tripwire registry with version hash
- Import everywhere that needs tripwire definitions: `from chakra.HUKLLA.codex import HUKLLA_TRIPWIRES`

Note: HUKLLA's codex is the only one that is imported *cross-chakra*. This is intentional — it is the constitutional layer.

---

### YAWAR
**Status: MEDIUM PRIORITY — rewrite required**  
YAWAR carries the packet type definitions. These are schema.

Rewrite scope:
- Extract: `YAWARPacket`, `YAWARReceipt`, `YAWAROperationType` enum
- Bake into `codex.py`: frozen packet schema with version hash
- Keep in chakra: packet routing, serialization, transport logic

---

### QILLQA (root/orchestrator)
**Status: LOW PRIORITY — coordination layer**  
QILLQA orchestrates the other chakras. It may carry some top-level schema declarations (the meta-ontology: what a "chakra" is, what a "schema version" is).

Rewrite scope:
- Extract: `ChakraDescriptor`, `SchemaVersion`, `ContinuumHashReceipt`
- Bake into `codex.py`: the top-level QILLQA meta-schema

---

### CONTINUUM
**Status: LOW PRIORITY — hash utility**  
CONTINUUM primarily carries the `continuum_hash` function. No heavy schema. The only schema it needs is the `HashReceipt` type.

Rewrite scope:
- Extract: `HashReceipt` dataclass
- Bake into `codex.py`: `HashReceipt` frozen schema

---

## Rewrite Priority Matrix

| Chakra | Schema Weight | Cross-chakra imports | Priority | Maxwell check self-pass |
|--------|--------------|----------------------|----------|------------------------|
| HUKLLA | High (10 tripwires) | Yes — imported by all | 1 | Required |
| CHAKANA | High (rigidity graph) | No | 2 | Required (self-referential) |
| PIRWA | High (feature dict) | No | 3 | Required |
| RUWAY | Medium (packet schema) | Low | 4 | Optional |
| SENTRA | Medium (tripwire refs) | Imports HUKLLA | 5 | Optional |
| YAWAR | Medium (packet types) | Imports RUWAY | 6 | Optional |
| QILLQA | Low (meta-schema) | All | 7 | Optional |
| CONTINUUM | Low (HashReceipt) | None | 8 | Optional |

---

## Rewrite Procedure Per Chakra

1. **Audit:** List all class definitions, enums, and module-level constants that are *data definitions* (not behavior)
2. **Extract:** Move extracted definitions to a `codex_source.yaml` (LinkML schema)
3. **Register:** Add the LinkML schema to the QILLQA daemon's SchemaStore
4. **Build:** Run `gen-python` and `codex_freeze.py` to produce `codex.py`
5. **Replace:** In the original chakra file, replace extracted definitions with imports from `codex`
6. **Test:** Run existing chakra tests — behavior unchanged, schema now sourced from codex

---

## Anti-Pattern to Avoid

Do NOT create a single monolithic `codex.py` at the repo root covering all chakras. This violates D-CODEX-IN-KERNEL: each chakra must own its schema locally. The HUKLLA codex is the one exception where cross-chakra import is intentional and documented.
