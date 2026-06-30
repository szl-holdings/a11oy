# spaces/sda — provenance (reverse-imported for governance)

**What:** the source of the standalone HuggingFace Space `SZLHOLDINGS/sda`
("SZL SDA — Sovereign Domain Superiority"), reverse-imported here so GitHub is its
source of truth. Previously the Space had **no GitHub source** = ungoverned drift risk.

**Why reverse-import (not redirect-to-a11oy):** the a11oy-served route
`/sda` ("SDA — Space / Domain Awareness (Counter-UAS)") is a **different, narrower**
surface. This Space is a distinct, richer investor demo (Common Operating Picture canvas,
sensor-fusion convergence, verify-receipt widget, honest synthetic baseline metrics) that
the a11oy route does **not** render. Redirecting it would lose content, so the honest fill
is to govern it from GitHub, not supersede it.

**Deploy model:** the Space `Dockerfile` is whole-context (`COPY . /app`, `python -m
http.server 7860`). It is **pure static** (no backing API of its own; it reads other live
endpoints — killinchu `/api/killinchu/v1/mosaic/cop`, `a11oy.net /v1/compute-pool` — when
reachable, else labelled demo/snapshot data). Because it is whole-context, the org
reusable per-file-`COPY` deployer deliberately **skips** it; this folder is the governed
source and the Space is rebuilt from its own contents. A tree-hash drift-check (compare
this folder vs the live Space `resolve/main`) is the appropriate guard.

**Imported from:** `https://huggingface.co/spaces/SZLHOLDINGS/sda` @ `main` on 2026-06-30.
Files are faithful copies (real content, no LFS pointers). `three.module.min.js` is the
vendored MIT Three.js r160 (see `assets/THREE_LICENSE.txt`).
