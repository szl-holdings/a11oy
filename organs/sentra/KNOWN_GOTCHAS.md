# KNOWN_GOTCHAS.md — sentra

> Things that have burned developers before. Doctrine v11 LOCKED · 749/14/163.

---

## 1. GitHub ↔ HF Space drift

Same issue as a11oy: `hf-sync.yml` only syncs `README.md`. Python code
changes need a GHCR image rebuild to reach the live Space.
Space: `SZLHOLDINGS/sentra` (https://szlholdings-sentra.hf.space).

---

## 2. Dockerfile per-file COPY discipline

Every Python module imported in `serve.py` needs a corresponding `COPY` line in
the Dockerfile. Missing module = try/except at import time swallows the error,
and the route silently serves the SPA catch-all instead of JSON.

Check for silent failures: look for `[sentra] ... NOT registered:` in Space logs.

---

## 3. Wire B provenance fields are LOCKED

The verdict response fields `receipt_hash`, `actionId`, `gates_fired`,
`traceparent`, and `doctrine` are consumed by a11oy's Wire B handler. If you
rename, remove, or reorder them, the a11oy side breaks silently (no error — it
just misses the provenance fields). Do not change them.

---

## 4. 8 gates canonical — do not add/remove silently

The canonical gate count is 8 (G1–G8, in `sentra_immune_v2.py`). The `/v1/gates`
endpoint and the doctrine posture both report 8 gates. Adding a gate silently
breaks the Wire B contract (a11oy expects 8 named gates). Any gate change must be
coordinated with a11oy and bumped through the doctrine version process.

---

## 5. `from __future__ import annotations` FastAPI gotcha

Same as a11oy: do not use this import in files defining FastAPI route handlers or
Pydantic models with complex generics. It makes type hints lazy strings, which
breaks FastAPI/Pydantic model introspection at runtime.

---

## 6. Mādhava forecast has 2 open sorries — "partial" label is correct

The `sentra_v4_threat.py` forecast endpoint reports `lean_status: "partial"`.
This is honest: `MadhavaBound.lean` still carries 2 tracked sorries (included in
the 163 total). Do not upgrade it to "proven" — the CI doctrine-grep workflow will
flag it.

---

## 7. Shallow clone risk

Always `git clone` (full, no `--depth`). Verify after: `git ls-files | wc -l`
should be ~822 for sentra. If it's < 50, you have a partial checkout.

---

## 8. SLSA level — L1 honest (cosign-signed; L2 attestation roadmap via Wire D, not yet earned; not L3)

Do not upgrade the badge to L2 until `cosign verify-attestation --type slsaprovenance`
actually returns the attestation on the deployed image (today it returns "no matching
attestations"). Do not upgrade to L3 without an isolated hardened build pipeline. The
`/v1/honest` endpoint is authoritative.

---

*Signed-off-by: stephenlutar2-hash <stephenlutar2@gmail.com>*
*Doctrine v11 LOCKED · 749/14/163.*
