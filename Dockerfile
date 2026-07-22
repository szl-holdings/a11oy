# syntax=docker/dockerfile:1
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
#
# a11oy HF Docker Space — RESET build (Brand Orchestration Layer at /).
#
# RESET 2026-05-31 (Yachay CTO): a11oy is NOT a /console/ admin panel.
# Per Replit .replit-artifact/artifact.toml: BASE_PATH="/", serve="static" from dist/public,
# rewrite /* -> /index.html (SPA history fallback). The React SPA IS the Brand
# Orchestration Layer; its HomePage (Vessels-DNA / investor-facing landing) renders at /.
#
# Serves:
#   /            — SPA front door (Brand Orchestration Layer landing)
#   /assets/*    — SPA JS/CSS chunks (vite base="/")
#   /boardroom, /investor-demo, /sovereign, /fabric, /nexus, /command, ... — SPA routes (history fallback)
#   /api/a11oy/* — a11oy serve endpoints (health, gates, reason, policy/evaluate, proxy)
#
# HF Space requirement: listen on PORT 7860.

# ---------------------------------------------------------------------------
# IMAGE-LEANNESS: multi-stage build. The CPU demo tier needs llama-cpp-python
# compiled FROM SOURCE against glibc (see the long WHY note above the runtime
# install far below). That compile pulls in a heavy build toolchain
# (build-essential/cmake/ninja/git — hundreds of MB of apt .deb churn) plus
# compile intermediates. Doing it in a THROWAWAY builder stage and copying only
# the resulting prebuilt wheel keeps all of that OUT of the published runtime
# image, shrinking the final image + its layer count (faster GHCR pulls) without
# changing what the demo tier serves.
#
# CONDITIONAL COMPILE: a constrained builder (HF Spaces cpu-basic) sets
# A11OY_REQUIRE_LOCAL_LLM=0 and must NOT pay the heavy compile (it OOM/timed-out
# -> BUILD_ERROR). Select the builder by ARG: =1 -> llama-build-1 (real source
# compile), else -> llama-build-0 (empty, no compile). BuildKit only builds the
# stage actually referenced by the `llama-build` alias, so on the constrained
# path the compile is skipped entirely. The strict GHCR build sets =1.
ARG A11OY_REQUIRE_LOCAL_LLM=0

# Real compile path (=1): build the pinned llama-cpp-python from source into a
# prebuilt glibc wheel, then assert the bundled libllama.so links glibc
# (NEEDs libc.so.6), not musl. set -eux => a bad compile fails the build LOUD.
FROM python:3.12-slim@sha256:423ed6ab25b1921a477529254bfeeabf5855151dc2c3141699a1bfc852199fbf AS llama-build-1
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends build-essential cmake ninja-build git; \
    CMAKE_ARGS="-DGGML_NATIVE=OFF" pip wheel --no-cache-dir --no-binary llama-cpp-python \
        --wheel-dir=/wheels "llama-cpp-python==0.3.19"
RUN python3 <<'GLIBCCHK'
import glob, sys, zipfile
whls = glob.glob("/wheels/llama_cpp_python-*.whl")
assert whls, "no llama_cpp_python wheel produced by the source build"
w = whls[0]
z = zipfile.ZipFile(w)
sos = [n for n in z.namelist() if n.endswith("libllama.so")]
assert sos, "libllama.so not present inside the built wheel " + w
data = z.read(sos[0])
assert b"libc.so.6" in data and b"libc.musl-x86_64.so.1" not in data, \
    "built libllama.so is not glibc-linked (would not load on python:3.12-slim): " + sos[0]
print("[a11oy] built glibc wheel OK:", w, "->", sos[0])
GLIBCCHK

# Skip path (!=1): no compile; just an empty wheel dir so the runtime
# COPY --from has a valid (empty) source on the constrained build.
FROM python:3.12-slim@sha256:423ed6ab25b1921a477529254bfeeabf5855151dc2c3141699a1bfc852199fbf AS llama-build-0
RUN mkdir -p /wheels

# Pick the builder the runtime stage actually copies from.
FROM llama-build-${A11OY_REQUIRE_LOCAL_LLM} AS llama-build

# ---------------------------------------------------------------------------
# RUNTIME IMAGE (the published a11oy Space / GHCR image).
FROM python:3.12-slim@sha256:423ed6ab25b1921a477529254bfeeabf5855151dc2c3141699a1bfc852199fbf AS runtime

# Build identity is supplied by the canonical container workflow. The runtime
# contract validates REVISION as a full SHA before exposing it; an absent or
# malformed value remains honestly UNKNOWN.
ARG VERSION=""
ARG REVISION=""
ARG BUILD_DATE=""
ENV A11OY_VERSION=${VERSION} \
    A11OY_GIT_SHA=${REVISION} \
    A11OY_BUILD_DATE=${BUILD_DATE}
LABEL org.opencontainers.image.version=${VERSION} \
      org.opencontainers.image.revision=${REVISION} \
      org.opencontainers.image.created=${BUILD_DATE}

WORKDIR /app

# Install Node 22 (for a11oy serve TypeScript runner)
# … (full rationale: docs/DOCKERFILE_NOTES.md §1)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates gnupg git && \
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    apt-get clean && rm -rf /var/lib/apt/lists/* && \
    curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
      | gpg --dearmor -o /usr/share/keyrings/githubcli-archive-keyring.gpg && \
    chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
      > /etc/apt/sources.list.d/github-cli.list && \
    apt-get update && apt-get install -y --no-install-recommends gh && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
# … (full rationale: docs/DOCKERFILE_NOTES.md §2)
RUN pip install --no-cache-dir \
    "fastapi==0.137.1" \
    "uvicorn[standard]==0.49.0" \
    "httpx==0.28.1" \
    "starlette==1.3.1" \
    "huggingface_hub==1.19.0" \
    "openai==2.43.0" \
    "python-multipart==0.0.32" \
    "cryptography==49.0.0" \
    "lmdb==2.2.1" \
    "slowapi==0.1.10" \
    "defusedxml==0.7.1" \
    "numpy==2.1.3"

# sqlite-vss removed from build: no pre-built wheel for python:3.12-slim;
# szl_khipu_lmdb.py and szl_unay.py already have honest try/except fallback
# to cosine similarity if the sqlite-vss .so cannot load. (P0 CI fix, Dev1 Rumi)

# a11oy source for the serve runtime (receipt-substrate + policy gates only).
# … (full rationale: docs/DOCKERFILE_NOTES.md §3)
COPY packages/receipt-substrate/src /app/a11oy-src/packages/receipt-substrate/src
COPY packages/policy/src/gates /app/a11oy-src/packages/policy/src/gates

# Copy the pre-built SPA (Brand Orchestration Layer) to the static root.
# index.html + assets/* are served directly at / and /assets/*; unknown GET -> index.html.
COPY console/ ./static/
# Security discovery is maintained at repository root; copy it into the static
# tree so /.well-known/security.txt resolves before the SPA fallback.
COPY .well-known/security.txt ./static/.well-known/security.txt

# Build cache-bust 2026-06-08T23:30Z (Wave23 instillation): knowledge.json was
# … (full rationale: docs/DOCKERFILE_NOTES.md §4)
COPY knowledge.json ./static/knowledge.json

# Ayllu — a11oy-native agent community. a11oy_ayllu.py is imported (guarded) by
# … (full rationale: docs/DOCKERFILE_NOTES.md §5)
COPY a11oy_ayllu.py ./
COPY ayllu/ ./ayllu/
# Canonical model-family/control-plane evidence ships with the runtime image so
# deployed status surfaces can be audited against the same release contracts.
COPY model_release/szl-forge-family.json model_release/szl-compute-plane.json model_release/szl-ayllu-binding.json model_release/szl-khipu-second-brain.json ./model_release/
COPY model_release/frontier-qualification/ ./model_release/frontier-qualification/
COPY model_release/receipt-agent/ ./model_release/receipt-agent/
# Brain-derived rows remain quarantined until this deterministic, fail-closed
# admission engine validates immutable provenance, rights, contamination, and
# split obligations. Shipping the CLI does not start training or admit rows.
COPY szl_brain_training_admission.py ./
# Waqay Security Loop wave 15: pure read-only proposal contract.  The module
# exposes zero external effectors; serve.py registers only its manifest GET.
COPY szl_waqay_security_loop.py ./
# Claim-integrity Rupture Gate / EvidenceOS Claim Compiler: external signals
# only, unsigned deterministic receipts, zero effectors.  The exact request
# schemas ship beside the module so served OpenAPI cannot drift from the
# reviewed source contracts.
COPY szl_claim_rupture_gate.py ./
COPY schemas/evidenceos/ ./schemas/evidenceos/
# Wave 38 evidence surfaces: involution probe + runtime contracts + committed quant
# benchmark receipt (read-only, validated+signature-checked at serve time).
COPY szl_involution_probe.py ./
COPY szl_runtime_contracts.py ./
COPY benchmarks/quant_live/receipts/latest.json ./benchmarks/quant_live/receipts/latest.json
# Quantum Utility Gate wave 16: pure-stdlib proposal analysis only.  No provider
# SDK, QPU call, credential path, external effector, or finance-engine coupling.
COPY szl_quantum_utility.py ./
# Wave 18 numerical-engine frontier. These are only the Apache-2.0 host contract
# … (full rationale: docs/DOCKERFILE_NOTES.md §6)
COPY szl_numerics_adapter.py ./
COPY szl_numerics_dataset.py ./
COPY szl_numerics_experiment.py ./
COPY numerics/ ./numerics/
# Wave 23 Yupaq governed computation plane.  It ships only the strict routing
# contract and delegates to already-copied engines; it installs no new runtime,
# prover, provider SDK, or proprietary dependency.
COPY szl_yupaq_compute.py ./
COPY proofs/lean-theorem-tree.json ./proofs/lean-theorem-tree.json
COPY research/formula-training-admission/admission-manifest.json ./research/formula-training-admission/admission-manifest.json
COPY data/szl-lake/evidence-manifest.json ./data/szl-lake/evidence-manifest.json
# Wave 19 formal-conjecture receipt lab. This copies only the strict contract,
# bounded ledger, and public-key receipt verifier; it installs no prover and
# exposes no command or network execution path.
COPY szl_formal_conjecture_lab.py ./
# M1 experimental model operational gate. Metadata and the status UI are
# … (full rationale: docs/DOCKERFILE_NOTES.md §7)
COPY szl_m1_model_gate.py ./
COPY szl_m1_corpus_manifest.py ./
COPY model_release/m1/ ./model_release/m1/
# Canonical release identity and public Zenodo readback receipt. The readback
# file ships in a PENDING state until a separately verified archive PR replaces
# it; the runtime never invents a DOI from the version number.
COPY szl_release_identity.py ./
COPY zenodo-readback.json ./
# Shared fail-closed provider transport. Registry adapters opt in to private
# destinations explicitly; this module performs pinned DNS validation, bounded
# redirect handling, response-size limits, and secret-safe deterministic errors.
COPY szl_provider_http.py ./
# Primary official project registry (51 records across 10 fields).  Runtime
# serves the deterministic, unranked registry; optional live metadata remains a
# bounded adapter and is not executed on anonymous public requests.
COPY research/ ./research/
# routers/ — Wave-K Dev4 serve.py decomposition (first bounded slice). serve.py
# … (full rationale: docs/DOCKERFILE_NOTES.md §8)
COPY routers/ ./routers/
# Genome registry served to the console Genome panel + /api/a11oy/v1/genome.
# Per-file COPY (this Dockerfile uses no `COPY . .`); a missing line -> the endpoint
# degrades to an honest labeled 503 (never a faked payload), the panel shows it.
COPY data/genome.json ./data/genome.json
# ---------------------------------------------------------------------------
# … (full rationale: docs/DOCKERFILE_NOTES.md §9)

# Copy serve orchestrator and gates manifest
# … (full rationale: docs/DOCKERFILE_NOTES.md §10)
COPY static/a11oy_cathedral.js ./static/a11oy_cathedral.js
# Operator organ (Dev3) — ingested 3D infra-viz, vendored-three (0 CDN)
COPY static/a11oy_operator_organ.js ./static/a11oy_operator_organ.js
# (pages/operator_organ.html is copied below via `COPY pages/ ./pages/`)
COPY static/vendor3d/three.module.min.js static/vendor3d/OrbitControls.js static/vendor3d/THREE_LICENSE.txt ./static/vendor3d/
# ADDITIVE (Dev0, 2026-06-14): SHARED szl3d 3D toolkit + holographic shell. The
# … (full rationale: docs/DOCKERFILE_NOTES.md §11)
COPY szl3d_holographic.py ./szl3d_holographic.py
# ADDITIVE (Wave-P Dev2): live cross-node mesh orchestrator backing the /holographic
# … (full rationale: docs/DOCKERFILE_NOTES.md §12)
COPY szl_mesh_orchestrator.py ./szl_mesh_orchestrator.py
# ADDITIVE (cathedral unification, GitHub-aligned): the ONE canonical genius
# … (full rationale: docs/DOCKERFILE_NOTES.md §13)
COPY cathedral_genius.html ./cathedral_genius.html
COPY static/cathedral_app.js ./static/cathedral_app.js
# ADDITIVE (holographic front-door landing, Dev1): the governed-inference-field
# … (full rationale: docs/DOCKERFILE_NOTES.md §14)
COPY a11oy_landing.html ./a11oy_landing.html
COPY static/a11oy_landing.js ./static/a11oy_landing.js
# ADDITIVE: batch-2 sovereign security data module (imported by serve.py; try/except-guarded).
# … (full rationale: docs/DOCKERFILE_NOTES.md §15)
COPY corpus/ ./corpus/
# ADDITIVE: a11oy Code IDE page (served by orchestrator GET /api/a11oy/code/ide as a
# … (full rationale: docs/DOCKERFILE_NOTES.md §16)

# ADDITIVE (Yachay / AYNI-OS, 2026-06-01): reciprocity organism + event-sourced replay
# … (full rationale: docs/DOCKERFILE_NOTES.md §17)
COPY ayni_os/ ./ayni_os/
# ayni_os_serve event-sources its ledger from the real signed-receipt corpus; it
# must be in the image or the loader honestly falls back to synthetic. Per-file
# Dockerfile (no `COPY . .`), so copy the corpus explicitly.
COPY infra/receipts-samples/ ./infra/receipts-samples/
COPY pages/ ./pages/

# Readiness contract: serve.py exposes this matrix at
# /api/a11oy/v1/readiness/tab-matrix. The endpoint previously degraded to
# available:false because this explicit-copy image never shipped the artifact.
COPY tools/readiness-harness/tabs.json ./tools/readiness-harness/tabs.json

# ADDITIVE (Live 3D Wires / PURIQ Doctrine v12, Yachay): explicit per-file COPY.
# … (full rationale: docs/DOCKERFILE_NOTES.md §18)

# ADDITIVE (Provenance Hardening / Wire D + DSSE Cosign REAL signing, 2026-06-01, Yachay):
# … (full rationale: docs/DOCKERFILE_NOTES.md §19)

ENV PORT=7860
# BE hardening (Greene) — per-file COPY (this Dockerfile uses per-file COPY).

EXPOSE 7860

# ADDITIVE (UNAY + Khipu-LMDB v2, 2026-06-01, Yachay / Perplexity Computer Agent):
# … (full rationale: docs/DOCKERFILE_NOTES.md §20)

# ADDITIVE (Anatomy 3D + live formula wiring, 2026-06-02, Yachay / Perplexity
# … (full rationale: docs/DOCKERFILE_NOTES.md §21)
COPY static-vendor/three.min.js static-vendor/chart.umd.min.js static-vendor/3d-force-graph.min.js static-vendor/echarts.min.js static-vendor/echarts-gl.min.js static-vendor/globe.gl.min.js static-vendor/cytoscape.min.js static-vendor/d3.min.js static-vendor/katex.min.js static-vendor/katex.min.css static-vendor/dagre.min.js static-vendor/cytoscape-dagre.js static-vendor/d3-sankey.min.js static-vendor/ngraph.graph.min.js static-vendor/ngraph.path.min.js static-vendor/ngraph.forcelayout.min.js static-vendor/panzoom.min.js static-vendor/vivagraph.min.js static-vendor/ngraph.events.umd.js static-vendor/a11oy-operator-widget.js static-vendor/a11oy-operator-widget.css static-vendor/uPlot.iife.min.js static-vendor/uPlot.min.css ./static-vendor/

# ADDITIVE (Graph/Viz lane + Perplexity Computer Agent, 2026-06-06): AIR-GAP
# … (full rationale: docs/DOCKERFILE_NOTES.md §22)

# ADDITIVE (V4 Fleet Panel + /api/health fix, 2026-06-02, Dev2 Inti):
# … (full rationale: docs/DOCKERFILE_NOTES.md §23)

# ADDITIVE (Frontier wave, 2026-06-08): two founder tabs served from /app/web/
# … (full rationale: docs/DOCKERFILE_NOTES.md §24)

# ADDITIVE (WALLPA): Voice / expression organ — renders governed actions into audio output.
# … (full rationale: docs/DOCKERFILE_NOTES.md §25)
COPY benchmarks/restraint/run_bench.py ./benchmarks/restraint/run_bench.py
# ADDITIVE (nonlinear-PINN frontier, 2026-07-02): szl_pinn_nonlinear.py is imported by
# … (full rationale: docs/DOCKERFILE_NOTES.md §26)
COPY benchmarks/pinn/results.json ./benchmarks/pinn/results.json
COPY benchmarks/pinn/run_bench.py ./benchmarks/pinn/run_bench.py
# ADDITIVE (Lane F1, 2026-06-14): the 3D/holographic SUBSTRATE demo page, served at
# … (full rationale: docs/DOCKERFILE_NOTES.md §27)
COPY web/formulas.html web/v4_fleet_panel.html web/operator.html web/fleet-c2.html web/living-anatomy.html web/nemo.html web/restraint.html web/restraint-bench.html web/holo.html web/constitution.html web/quant.html web/estate-hologram.html web/hologram.html web/determinacy.html web/verify-receipt.html web/sda.html web/dns.html web/m1-model.html ./web/
COPY web/signature-is-not-proof.html ./web/signature-is-not-proof.html
COPY web/defense-readiness.html ./web/defense-readiness.html
# ADDITIVE (Lane A AGENTIC CORE, Dev A, 2026-06-14; QA9 restore 2026-06): the
# … (full rationale: docs/DOCKERFILE_NOTES.md §28)
# Quant-claim provenance gate: strict schemas plus a bounded, digest-addressed,
# read-only DSSE receipt loader. It performs no benchmark, signing, GPU, or network work.
COPY szl_quant_claims.py ./
COPY szl_formula_registry.py ./
COPY schemas/quant-claims/ ./schemas/quant-claims/
COPY knowledge.json szl_parity_gaps.py compliance_crosswalk.py szl_compliance_mesh.py a11oy_warhacker_obs.py serve.py szl_governed_api.py szl_demo_tier1.py szl_assurance.py govern_showcase.html a11oy_wireA_metrics.py cathedral.html a11oy_operator_organ.py a11oy_hf_assets.py szl_b2_secdata.py gates_manifest.json a11oy_code_orchestrator.py a11oy_agent_loop.py a11oy_org_rag.py a11oy_mcp_client.py szl_rag.py a11oy_code_ide.html wayra_serve.py wayra_snapshot.json wayra_digests_7d.json szl_khipu_os_routes.py szl_spaces_proxy.py szl_spaces_surface.py szl_khipu_consensus.py szl_puriq_formulas.py ayni_os_serve.py szl_live_wires.py live_wires.html live_wires_3d.js szl_intoto.py szl_intoto_routes.py szl_scitt.py szl_dsse.py szl_content_address.py szl_provenance.py szl_be_hardening.py szl_unay.py szl_khipu_lmdb.py szl_khipu_replicate.py szl_unay_routes.py szl_warhacker_aliases.py a11oy_v4_hickok.py szl_khipu.py szl_formulas.py a11oy_v4_formulas.py szl_anatomy_3d.py szl_anatomy_routes.py _vendor_blobs.py szl_v4_fleet.py operator_shell_v4.py szl_bridge.py szl_bridge_schemas.py agent.html a11oy_bridge_cli.py szl_ken.py a11oy_formula_endpoints.py a11oy_formula_registry_guard.py a11oy_formulas_page.py a11oy_frontier_patch.py a11oy_v4_agent.py szl_brain.py szl_wire.py szl_hub.py szl_rosie_companion.py szl_receipt_substrate.py szl_alloy_embed_fabric.py szl_ayni_quorum.py szl_agentic_loop.py szl_ltc_dynamics.py szl_sgh_scheduler.py szl_formula_wiring.py szl_formula_surfaces.py a11oy_code_engine.py a11oy_code_runloop.py a11oy_code.py a11oy_seismic.py szl_warhacker_real.py szl_warhacker_demos.py NOTICE_warhacker_demos.txt szl_llm_registry.py szl_elite_console.py szl_alloy_models.py szl_scaling.py szl_allodial.py szl_entanglement.py szl_neuroplasticity.py szl_neuromorphic.py szl_kan.py szl_titans.py szl_mor.py szl_ternary.py szl_agentmem.py szl_edgefusion.py szl_hybridssm.py szl_aigov.py szl_chain_of_title.py szl_sovereign_compute.py szl_a11oy_interpretability.py a11oy_active_flux_router.py szl_energy_budget.py szl_energy_sovereign.py szl_energy_provenance.py szl_heart_blood.py szl_engine_status.py szl_backend_hardening.py revenue_endpoints.py a11oy_harvest_endpoints.py szl_energy_measured.py joule_billing.py szl_durable_ledger.py szl_energy_ledger.py szl_energy_operator.py szl_energy_projection.py szl_cheapest_watt.py szl_energy_live.py szl_orbital_topology.py szl_orbital_projection.py a11oy_orbital_page.py a11oy_frontier_page.py szl_frontier_manifest.py szl_frontier_zkinfer.py szl_frontier_fmverif.py szl_frontier_supplychain.py a11oy_code_as_action.py a11oy_governed_kernel.py szl_lambda_tripwire.py szl_provenance_receipt.py szl_khipu_verify.py szl_public_verify.py szl_attest_stack.py szl_demo_sign.py szl_sda.py szl_fabric_surface.py szl_nemo_agents.py szl_kverify.py szl_specdec.py szl_immune.py szl_quant_qbio_holo.py szl_materials.py szl_materials_predict.py a11oy_factory.py a11oy_constitution.py a11oy_nav_wireup.py szl_mbse_cosim.py szl_mbse_nav.py szl_mbse.py szl_factory.py szl_willay_gateway.py a11oy_willay_nav.py szl_waqay.py a11oy_waqay_nav.py szl_yupay.py a11oy_yupay_nav.py a11oy_uds_portability_nav.py szl_pinn_bounds.py szl_pinn_residual.py physical_bounds_certificate.json agentic_decision_trail.json physical_bounds_certificate.dsse.json szl_pinn_inverse.py szl_governed_ipinn.py szl_calphad_inverse.py szl_pnt_mesh.py quantum_sensing_limits.py pnt_resilience.py nav_coasting.py fundamental_limits.py szl_counter_uas_proxy.py szl_gpu_quant.py szl_joules_truth.py revenue_model.py szl_prod_hardening.py szl_resilience.py szl_observability.py szl_corpus_publish.py szl_lake_store.py szl_lake_ingest.py szl_e8.py szl_trajectory_sign.py szl_nemotron_ingest.py szl_nemotron_corpus.py szl_nemo_verify.py a11oy_nemo_core.py szl_restraint.py szl_sapa.py szl_sapa_patch.py szl_restraint_energy.py a11oy_react_core.py szl_org_lambda.py a11oy_canonical_domain.py a11oy_formula_tiers.py szl_physical_bounds.py szl_kc_loop_forge.py szl_kc_loop_forge_metrics.py szl_kc_atlas.py szl_eval_arena.py szl_vqc.py szl_kc_jpt.py ./

# Wave M / Dev 4: Sovereign Local Model panel — imported GUARDED by serve.py
# … (full rationale: docs/DOCKERFILE_NOTES.md §29)

# Wave P / Dev 4: three new frontier synthesis surfaces — imported GUARDED by serve.py
# … (full rationale: docs/DOCKERFILE_NOTES.md §30)

# Wave P / Dev 4: three more frontier surfaces — imported GUARDED by serve.py (GET
# … (full rationale: docs/DOCKERFILE_NOTES.md §31)

# Wave O / Dev 3: Brain-Body panel — imported GUARDED by serve.py (GET /api/a11oy/v1/
# … (full rationale: docs/DOCKERFILE_NOTES.md §32)

# FlowBrain frontier surface backend (WaveS) — imported by serve.py (guarded) for GET
# … (full rationale: docs/DOCKERFILE_NOTES.md §33)

# DEV2 Build 1: TEE/TDX attestation hook (2026-06-30) — imported by serve.py (guarded);
# … (full rationale: docs/DOCKERFILE_NOTES.md §34)
COPY brain/harvest ./brain/harvest
# BRAIN NERVOUS-SYSTEM HUB (WAVE O Dev1, 2026-07-07) — the pulse bus. serve.py imports
# … (full rationale: docs/DOCKERFILE_NOTES.md §35)
COPY brain/harvest_vault.py ./brain/harvest_vault.py
# --- buildkit max-depth fix: per-file COPYs grouped into one layer (no file dropped; every source token preserved). ---
COPY szl_qhawaq.py szl_wallpa.py szl_pinn_nonlinear.py szl_sovereign_panel.py szl_lgmi.py szl_gnqs.py szl_casta.py szl_sparsemoe.py szl_pddisagg.py szl_execverify.py szl_brainbody.py szl_flowbrain.py szl_tee_attest.py szl_attested_inference.py szl_proof_carrying_infer.py szl_eu_energy.py a11oy_brain_graph.py szl_brain_api.py szl_brainprovenance.py szl_braincontradict.py szl_governed_infer.py szl_brain_energy.py szl_brain_command.py szl_brain_hub.py ./

# DEV2: in-toto offline verifier recipe (Apache-2.0)
RUN mkdir -p /app/szl-cookbook
COPY szl-cookbook/verify-intoto-receipt.py /app/szl-cookbook/


# ADDITIVE (Cross-Harness Receipt Bridge — Hermes + OpenClaw; 2026-06-01, Yachay /
# … (full rationale: docs/DOCKERFILE_NOTES.md §36)


# ADDITIVE (SZL Ken Agent Pattern v1, CTO Yachay Convergence Cycle 1, 2026-06-03):
# … (full rationale: docs/DOCKERFILE_NOTES.md §37)


# ADDITIVE (Formulas → Ecosystem instillation, Opus 4.8, 2026-06-03):
# … (full rationale: docs/DOCKERFILE_NOTES.md §38)
COPY src/a11oy/__init__.py ./src/a11oy/__init__.py
COPY src/a11oy/formulas/__init__.py src/a11oy/formulas/pac_bayes.py src/a11oy/formulas/bls_aggregate.py src/a11oy/formulas/welford.py src/a11oy/formulas/byzantine_quorum.py src/a11oy/formulas/holevo_bound.py src/a11oy/formulas/bloom_filter.py src/a11oy/formulas/kalman.py src/a11oy/formulas/hnsw_retrieval.py src/a11oy/formulas/reidemeister.py src/a11oy/formulas/allodial.py src/a11oy/formulas/allodial_gate.py src/a11oy/formulas/entanglement.py ./src/a11oy/formulas/
# FIX (formula/* 404 repair): a11oy_formula_endpoints.py imports a11oy.formulas.{allodial,
# … (full rationale: docs/DOCKERFILE_NOTES.md §39)
COPY src/a11oy/harvest/__init__.py src/a11oy/harvest/wasted_energy_harvest.py src/a11oy/harvest/harvest_budget.py ./src/a11oy/harvest/
# ADDITIVE (Formulas SECTION page — closeout): serve.py imports a11oy_formulas_page
# … (full rationale: docs/DOCKERFILE_NOTES.md §40)

# ADDITIVE (Missing modules fix, 2026-06-04, Perplexity Computer Agent):
# … (full rationale: docs/DOCKERFILE_NOTES.md §41)

# ADDITIVE (Parity Gaps + Receipt Substrate fix, 2026-06-05, Orchestrator Squad):
# … (full rationale: docs/DOCKERFILE_NOTES.md §42)

# Governed agent loop module (RAG->tool-call->policy/trust->signed-receipt + canonical /mcp/).

# Formula-wiring module (ADDITIVE 2026-06-06): registers the kernel-verified theorem
# … (full rationale: docs/DOCKERFILE_NOTES.md §43)

# a11oy Code engine (governed chat/code/research; C20/W7-5 router; W5-3/W7-4 conformal;
# … (full rationale: docs/DOCKERFILE_NOTES.md §44)

# a11oy.code 7-tier organ->model router (TIERS + route() + tiers_payload()).
# … (full rationale: docs/DOCKERFILE_NOTES.md §45)

# a11oy Seismic forecaster (Doctrine v13): honest Reasenberg-Jones (1994) +
# … (full rationale: docs/DOCKERFILE_NOTES.md §46)

# Warhacker mission tabs backend (5 investor-facing surfaces; reuses
# … (full rationale: docs/DOCKERFILE_NOTES.md §47)

# Warhacker EXHAUSTIVE demos backend (5 full step-by-step demos: step timeline,
# … (full rationale: docs/DOCKERFILE_NOTES.md §48)

# ---------------------------------------------------------------------------
# … (full rationale: docs/DOCKERFILE_NOTES.md §49)

# LIVE CPU demo tier: install llama.cpp + fetch ONE tiny Apache-2.0 GGUF
# … (full rationale: docs/DOCKERFILE_NOTES.md §50)
ARG A11OY_REQUIRE_LOCAL_LLM=0
# The wheel is BIND-MOUNTED from the builder stage (not COPY'd) so it is
# … (full rationale: docs/DOCKERFILE_NOTES.md §51)
RUN --mount=type=bind,from=llama-build,source=/wheels,target=/wheels \
    set -eux; \
    if [ "${A11OY_REQUIRE_LOCAL_LLM}" != "1" ]; then \
      echo '[a11oy] A11OY_REQUIRE_LOCAL_LLM!=1 (constrained builder, e.g. HF cpu-basic): no llama.cpp wheel built/installed. The demo tier serves the HONEST tower-side label (szl_alloy_models.py, served_locally=False, never fake output). The strict GHCR-published image sets =1 and installs the prebuilt glibc wheel + boot-verifies real local output.'; \
    else \
      apt-get update; \
      apt-get install -y --no-install-recommends libgomp1 libstdc++6; \
      apt-get clean; \
      rm -rf /var/lib/apt/lists/*; \
      pip install --no-cache-dir /wheels/*.whl; \
      python3 -c "import llama_cpp, os, glob; base=os.path.dirname(llama_cpp.__file__); so=glob.glob(os.path.join(base,'**','libllama.so'), recursive=True); assert so, 'libllama.so not found under '+base; d=open(so[0],'rb').read(); assert b'libc.so.6' in d and b'libc.musl-x86_64.so.1' not in d, 'libllama.so is not glibc-linked: '+so[0]; print('[a11oy] llama_cpp installed from prebuilt glibc wheel OK:', so[0], getattr(llama_cpp,'__version__','?'))"; \
    fi
# GGUF weight — RELIABLY PRESENT (pinned revision + retry + integrity verify), NOT best-effort.
# … (full rationale: docs/DOCKERFILE_NOTES.md §52)
ARG A11OY_ALLOY_GGUF_REPO=Qwen/Qwen2.5-Coder-0.5B-Instruct-GGUF
ARG A11OY_ALLOY_GGUF_FILE=qwen2.5-coder-0.5b-instruct-q4_k_m.gguf
ARG A11OY_ALLOY_GGUF_REV=ebb2015119c907b064c512bf053e945850b5875f
ARG A11OY_ALLOY_GGUF_SHA256=1d9614638d18024d0fbb36575a15f1302a3adf044df10345688ec4f6e1c4ff32
ARG A11OY_ALLOY_GGUF_SIZE=491400064
ARG A11OY_REQUIRE_LOCAL_LLM=0
ENV A11OY_REQUIRE_LOCAL_LLM=${A11OY_REQUIRE_LOCAL_LLM}
RUN python3 <<'GGUFPY'
import hashlib, os, sys, time
from huggingface_hub import hf_hub_download

# RESILIENCE: on a constrained builder (A11OY_REQUIRE_LOCAL_LLM!=1, e.g. HF cpu-basic)
# … (full rationale: docs/DOCKERFILE_NOTES.md §53)
if os.environ.get("A11OY_REQUIRE_LOCAL_LLM") != "1":
    print("[a11oy] A11OY_REQUIRE_LOCAL_LLM!=1: skipping GGUF weight fetch (demo tier = honest tower-side label). App boots normally.", flush=True)
    sys.exit(0)
repo      = os.environ["A11OY_ALLOY_GGUF_REPO"]
fname     = os.environ["A11OY_ALLOY_GGUF_FILE"]
rev       = os.environ["A11OY_ALLOY_GGUF_REV"]
want_sha  = os.environ["A11OY_ALLOY_GGUF_SHA256"].lower()
want_size = int(os.environ["A11OY_ALLOY_GGUF_SIZE"])
dest      = "/app/models"
os.makedirs(dest, exist_ok=True)

def verify(p):
    if not p or not os.path.exists(p):
        return "missing"
    sz = os.path.getsize(p)
    if sz != want_size:
        return "size %d != expected %d" % (sz, want_size)
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    got = h.hexdigest()
    if got != want_sha:
        return "sha256 %s != expected %s" % (got, want_sha)
    return None

last = None
for attempt in range(1, 7):
    try:
        p = hf_hub_download(repo_id=repo, filename=fname, revision=rev, local_dir=dest)
        last = verify(p)
        if last is None:
            print("[a11oy] GGUF verified present: %s (%d bytes, sha256 ok, rev %s)"
                  % (fname, want_size, rev[:12]), flush=True)
            sys.exit(0)
        print("[a11oy] attempt %d: integrity check failed: %s" % (attempt, last), flush=True)
        try:
            os.remove(p)
        except OSError:
            pass
    except Exception as e:
        last = "%s: %s" % (type(e).__name__, str(e)[:200])
        print("[a11oy] attempt %d: download failed: %s" % (attempt, last), flush=True)
    time.sleep(min(60, 5 * attempt))

# RESILIENCE (a11oy-build-resilience): fail-loud on the strict published-image path
# (A11OY_REQUIRE_LOCAL_LLM=1 in GHCR CI), else honest skip so a constrained HF rebuild
# still boots (demo tier shows the tower-side label, never fake output).
if os.environ.get("A11OY_REQUIRE_LOCAL_LLM") == "1":
    sys.stderr.write("[a11oy] FATAL: could not obtain a verified GGUF after retries: %s\n" % last)
    sys.exit(1)
sys.stderr.write("[a11oy] NOTE: GGUF weight not obtained (%s); demo tier will serve the HONEST tower-side label. App boots normally.\n" % last)
sys.exit(0)
GGUFPY
# Drop transient download metadata; the real weight stays at /app/models/<file>.
RUN rm -rf /app/models/.cache /root/.cache/huggingface 2>/dev/null || true
ENV A11OY_ALLOY_GGUF=/app/models/qwen2.5-coder-0.5b-instruct-q4_k_m.gguf

# ── BUILD-TIME EXTERNAL-DOWNLOAD AUDIT ───────────────────────────────────────
# … (full rationale: docs/DOCKERFILE_NOTES.md §54)

# ADDITIVE (Live-Data Layer, 2026-06-06, Warhacker): SHARED live-feed proxy module
# … (full rationale: docs/DOCKERFILE_NOTES.md §55)
COPY live_snapshots/ ./live_snapshots/

# ADDITIVE (Investor-WOW Layer, 2026-06-08, Dev1): a11oy_dev1_endpoints.py exposes
# … (full rationale: docs/DOCKERFILE_NOTES.md §56)

# ADDITIVE (Vertical Packs Layer, 2026-06-08, Dev2): a11oy_vertical_feeds.py exposes
# … (full rationale: docs/DOCKERFILE_NOTES.md §57)

# ADDITIVE (Deep Feeds Layer, 2026-06-08, Dev-A): a11oy_deva_feeds.py exposes the 10
# … (full rationale: docs/DOCKERFILE_NOTES.md §58)

# ADDITIVE (Provenance & Trust Anchor, 2026-06-08): a11oy_amaru_feeds.py exposes the
# … (full rationale: docs/DOCKERFILE_NOTES.md §59)

# ADDITIVE (MINED UPGRADES, 2026-06, Yachay): four self-contained operator surfaces,
# … (full rationale: docs/DOCKERFILE_NOTES.md §60)

# ADDITIVE (RE-SWEEP WAVE 2, 2026-06, Yachay): four MORE operator surfaces from the
# … (full rationale: docs/DOCKERFILE_NOTES.md §61)

# ADDITIVE (WAVE9/10 INSTILLATION, 2026-06): the "Proven Formulas (experimental)"
# … (full rationale: docs/DOCKERFILE_NOTES.md §62)
COPY bounties/ ./bounties/

# ---------------------------------------------------------------------------
# … (full rationale: docs/DOCKERFILE_NOTES.md §63)
COPY szl_feature_badge.py feature_provenance.json ./
COPY proofs/lutar-lean/Lutar/Thesis/TH_V18_08_KhipuChecksumInvariant.lean ./proofs/lutar-lean/Lutar/Thesis/TH_V18_08_KhipuChecksumInvariant.lean
COPY proofs/lutar-lean/Lutar/Thesis/TH_V18_05_ReceiptTransduction.lean ./proofs/lutar-lean/Lutar/Thesis/TH_V18_05_ReceiptTransduction.lean
COPY proofs/lutar-lean/Lutar/Round13/Lambda_Uniqueness.lean ./proofs/lutar-lean/Lutar/Round13/Lambda_Uniqueness.lean
COPY proofs/lutar-lean/Lutar/KhipuConsensus.lean ./proofs/lutar-lean/Lutar/KhipuConsensus.lean

# ---------------------------------------------------------------------------
# … (full rationale: docs/DOCKERFILE_NOTES.md §64)
COPY szl_connectors/ ./szl_connectors/

# ADDITIVE (Task: HF Dataset Bucket Foundation): the ONE shared Hugging Face
# … (full rationale: docs/DOCKERFILE_NOTES.md §65)



# --- ESTATE ECOSYSTEM FOUNDATION (Dev5, 2026-06): byte-identical shared modules ---
# … (full rationale: docs/DOCKERFILE_NOTES.md §66)
COPY static/shared/szl_label_engine.js static/shared/szl_receipt_cosign.js static/shared/szl_codename_sanitizer.js static/shared/szl_holo3d.js ./static/shared/

# --- GOVERNANCE / EVAL / CALIBRATION layer (Dev B, 2026-06): ADDITIVE ---
# … (full rationale: docs/DOCKERFILE_NOTES.md §67)
COPY policy/colang/roe_core.co policy/colang/killinchu_threat.co ./policy/colang/
# GOVERNED AUTO-REVIEW (Integration I2) — keystone autonomy layer: governed +
# … (full rationale: docs/DOCKERFILE_NOTES.md §68)
COPY scripts/check_tau_eval.py ./scripts/check_tau_eval.py
# Lean4Agent workflow-invariant scaffold (ROADMAP / EXPERIMENTAL — not a verified
# proof yet; rendered as ROADMAP in the UI). Shipped so the .lean source is in
# the image for audit; no Lean toolchain is invoked at runtime.
COPY lean4agent/WorkflowInvariants.lean lean4agent/README.md ./lean4agent/

# GRC ALIGNMENT surface (Lane I5) — in-product ISO 42001 / NIST AI RMF / 800-53 /
# … (full rationale: docs/DOCKERFILE_NOTES.md §69)
COPY compliance/oscal/a11oy-component-definition.json ./compliance/oscal/a11oy-component-definition.json
COPY compliance/rego/classification_boundary.rego compliance/rego/human_override_required.rego compliance/rego/deployment_readiness.rego compliance/rego/manifest.json ./compliance/rego/

# HOLOGRAPHIC 3D ENERGY SHOWCASE (Lane energy/06, 2026-06-14). The shared szl3d 3D
# … (full rationale: docs/DOCKERFILE_NOTES.md §70)
COPY a11oy_threat_intel.py a11oy_live_feeds.py a11oy_signing_key.py a11oy_dev1_endpoints.py a11oy_vertical_feeds.py a11oy_deva_feeds.py a11oy_devb_endpoints.py a11oy_amaru_feeds.py szl_governance_gateway.py szl_abacus_verify.py szl_decision_uncertainty.py szl_gor_audit.py szl_sovereign_search.py szl_consensus_clusters.py szl_mission_ledger.py szl_budget_router.py szl_wave910_proofs.py szl_evidence_research.py szl_uds_fleet.py szl_readiness.py szl_quantum_bio.py szl_mosaic_governance.py szl_unified_formulas.py szl_cuas_formulas.py szl_contracting.py szl_bounties.py szl_putnam.py szl_connectors_serve.py szl_connector_mcp.py szl_conjecture_factory.py szl_hf_bucket.py szl_metrics_prom.py szl_research_infra.py szl_dark_surfaces_register.py szl_anatomy_loop.py szl_anatomy_brainloop.py conduction_aphasia.py szl_a11oy_live_feeds.py szl_jack.py szl_codename_gate.py szl_ecosystem_routes.py szl_organ_health.py a11oy_governance_endpoints.py szl_tau_eval.py szl_calibration.py szl_conformal.py szl_colang_policy.py szl_ietf_receipt.py a11oy_autoreview.py a11oy_grc.py a11oy_grc_data.py a11oy_grc_restraint.py szl3d_holographic.py szl_rekor_anchor.py szl_circuit_graphs.py szl_semantic_entropy.py szl_kv_cache.py szl_diffusion_llm.py szl_latent_attention.py szl_testtime_scaling.py ./
# feat/a11oy-models: live external model intel (LMArena Elo + HF Hub + Pareto) for llm/arena tabs.
# … (full rationale: docs/DOCKERFILE_NOTES.md §71)
COPY static/3d/ ./static/3d/
# Standalone a11oy holographic energy page (/energy-holographic) + the upgraded HF energy
# … (full rationale: docs/DOCKERFILE_NOTES.md §72)
COPY static/energy_3d.js ./static/energy_3d.js
# Grid Energy Harvest honest dashboard (/energy-harvest); served via _ptg_serve from /app/web/.
# … (full rationale: docs/DOCKERFILE_NOTES.md §73)
COPY web/agentic-gpu.html web/governance.html web/autoreview.html web/energy-holographic.html web/energy.html web/energy-3d.html web/energy-harvest.html web/immune.html web/materials.html web/proof.html web/trust.html web/code.html ./web/
# a11oy /code GOVERNED RUN-LOOP view (2026-07-06): standalone sovereign page (0 CDN)
# … (full rationale: docs/DOCKERFILE_NOTES.md §74)

# GOVERNED MODEL-HARNESS (Wave F module + Wave G /code wire-in, 2026-07-07):
# … (full rationale: docs/DOCKERFILE_NOTES.md §75)
COPY harness_profiles/ ./harness_profiles/

# GOVERNED AGENT LOOP (Wave J, Dev 5): szl_agent_loop_governed.py COMPOSES the /code
# … (full rationale: docs/DOCKERFILE_NOTES.md §76)

# GOVERNED RAG · retrieval-with-receipts (Wave J · Dev 4, 2026-07-07):
# … (full rationale: docs/DOCKERFILE_NOTES.md §77)

# SOVEREIGN FLYWHEEL BRIDGE (Wave M · Dev 2, 2026-07-07): szl_sovereign_flywheel.py is
# … (full rationale: docs/DOCKERFILE_NOTES.md §78)

# Wave O (Dev 4): the BRAIN vault as a first-class RAG corpus source. Imported by
# … (full rationale: docs/DOCKERFILE_NOTES.md §79)

# WAVE-Q FRONTIER INDEX (honest ecosystem catalog + self-audit). Per-file COPY (this
# … (full rationale: docs/DOCKERFILE_NOTES.md §80)

# WAVE-S DEV 5: WHAT'S NEW (honest auto-derived estate changelog). Per-file COPY (this
# … (full rationale: docs/DOCKERFILE_NOTES.md §81)

# HONESTY WALL (feat/frontier-honestywall) — per-file COPY (this Dockerfile has NO
# … (full rationale: docs/DOCKERFILE_NOTES.md §82)

# BRAIN MEMORY FRESHNESS (feat/frontier-brainmemory) — per-file COPY (this Dockerfile has NO
# … (full rationale: docs/DOCKERFILE_NOTES.md §83)

# AGENT OS MAP (feat/frontier-agentos) — per-file COPY (this Dockerfile has NO
# … (full rationale: docs/DOCKERFILE_NOTES.md §84)

# BRAINGROUND (feat/frontier-brainground) — per-file COPY (this Dockerfile has NO
# … (full rationale: docs/DOCKERFILE_NOTES.md §85)

# BRAIN CONSENSUS (feat/frontier-brainconsensus) — per-file COPY (this Dockerfile has NO
# … (full rationale: docs/DOCKERFILE_NOTES.md §86)
COPY szl_brainconsensus.py ./szl_brainconsensus.py
# BRAIN QUERY AUDIT (feat/frontier-brainqueryaudit) — append-only, hash-linked ledger
# … (full rationale: docs/DOCKERFILE_NOTES.md §87)
COPY szl_brainqueryaudit.py ./szl_brainqueryaudit.py
# Wave 22: content-addressed corpus admission + fail-closed Brain reranker/feed.
# No model weights, trainer, or network harvester are included.
COPY szl_braincorpus.py szl_brain_reranker.py ./
# BRAIN LINEAGE (feat/frontier-brainlineage) — NODE-ORIGIN lineage over the SAME
# … (full rationale: docs/DOCKERFILE_NOTES.md §88)
COPY szl_brainlineage.py ./szl_brainlineage.py
# BRAIN EXPLAIN (feat/frontier-brainexplain) — per-file COPY (this Dockerfile has NO
# … (full rationale: docs/DOCKERFILE_NOTES.md §89)
COPY szl_brainexplain.py ./szl_brainexplain.py
# BRAIN GAPS (feat/frontier-braingaps) — per-file COPY (this Dockerfile has NO
# … (full rationale: docs/DOCKERFILE_NOTES.md §90)
COPY szl_braingaps.py ./szl_braingaps.py
COPY szl_spend_cap.py ./szl_spend_cap.py





# WAVE R Dev 1 — boot-resilience env/secret preflight. Per-file COPY (this
# … (full rationale: docs/DOCKERFILE_NOTES.md §91)
COPY a11oy_model_intel.py a11oy_experimental_tier.py a11oy_markets.py szl_agent_tts.py szl_gated_delta.py szl_blocksparse.py szl_retrieval_attn.py szl_model_harness.py szl_agent_loop_governed.py szl_crypto_pipeline.py szl_confattest.py szl_agent_operate.py szl_agentloop_brain.py szl_governed_rag.py szl_sovereign_flywheel.py szl_brain_corpus.py szl_verify_transcript.py szl_frontier_index.py szl_whatsnew.py szl_honestywall.py szl_brainmemory.py szl_agentos.py szl_brainground.py szl_brainuncertainty.py szl_brainhealth.py szl_brainwatch.py szl_boot_preflight.py szl_guarded_surface.py szl_status_aggregate.py szl_brainconstitution.py szl_brainagent.py szl_surface_manifests.py szl_source_attestation.py szl_compute_pool_contract.py ./
COPY static/3d/surfaces/gateddelta.js static/3d/surfaces/blocksparse.js static/3d/surfaces/retrievalattn.js static/3d/surfaces/governedagent.js static/3d/surfaces/cryptopipeline.js static/3d/surfaces/confattest.js static/3d/surfaces/agentops.js static/3d/surfaces/frontierindex.js static/3d/surfaces/whatsnew.js static/3d/surfaces/opsdash.js ./static/3d/surfaces/

# FORGE-FAMILY WALL (2026-07-14): /api/forge/family — server-side ed25519
# … (full rationale: docs/DOCKERFILE_NOTES.md §92)
COPY a11oy_forge_family.py ./a11oy_forge_family.py

# KHIPU DEMO TAB (2026-07-16): /api/khipu/demo — three RECORDED Khipu navigator
# … (full rationale: docs/DOCKERFILE_NOTES.md §93)
COPY a11oy_khipu_demo.py ./a11oy_khipu_demo.py
COPY a11oy_khipu_demo_traces.json ./a11oy_khipu_demo_traces.json

# KHIPU DEMO PAGE (2026-07-16): a11oy_khipu_demo_nav.py attaches the idempotent
# … (full rationale: docs/DOCKERFILE_NOTES.md §94)
COPY a11oy_khipu_demo_nav.py ./a11oy_khipu_demo_nav.py

# QUANT SIGNALS WALL (2026-07-16): /api/quant/signals + /signals — the quant
# … (full rationale: docs/DOCKERFILE_NOTES.md §95)
COPY a11oy_quant_signals.py ./a11oy_quant_signals.py
COPY a11oy_quant_signals_nav.py ./a11oy_quant_signals_nav.py

# ECOSYSTEM ATLAS + ANATOMY V5 (2026-07-16): versioned public inventory API,
# real deep-link pages, and the read-only live digital twin. pages/ is copied
# wholesale above; this per-file image copies only the new Python registrar.
COPY a11oy_ecosystem_atlas.py ./a11oy_ecosystem_atlas.py

# AYLLU COUNCIL WALL (2026-07-21): /api/ayllu/wall + /ayllu/wall — server-side
# per-request DSSE re-verification of committed council decision receipts,
# fetched from the public GitHub repo. Fail-closed; key honesty in-band.
COPY a11oy_ayllu_wall.py ./a11oy_ayllu_wall.py

# git_sha wireup (FORGE-INSTRUCTION-gitsha-quiet-window): surface the deployed commit
# … (full rationale: docs/DOCKERFILE_NOTES.md §96)
ARG SZL_GIT_SHA=unknown
ARG SZL_BUILD_TIME=unknown
ENV SZL_GIT_SHA=${SZL_GIT_SHA} \
    SZL_BUILD_TIME=${SZL_BUILD_TIME} \
    A11OY_ORG_RAG_DB=/app/data/a11oy_org_rag.db

# The Second Brain's SQLite index is rebuildable, but a mounted /app/data keeps
# … (full rationale: docs/DOCKERFILE_NOTES.md §97)
VOLUME ["/app/data"]
CMD ["python", "serve.py"]


# Build cache-bust 2026-06-05T00:00Z (Orchestrator Squad):
# … (full rationale: docs/DOCKERFILE_NOTES.md §98)

# Build cache-bust 2026-06-06T09:00Z (model-integration squad, Opus 4.8):
# … (full rationale: docs/DOCKERFILE_NOTES.md §99)
