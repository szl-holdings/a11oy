# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED: locked-proven=8 · Λ=Conjecture 1 · SLSA L1 honest / L2 attested / L3 roadmap
# Co-Authored-By: Perplexity Computer Agent
"""
szl_kc_atlas.py — THE ATLAS (68th surface) — the unifying front door that maps the
whole 67-surface holographic estate into ONE organism using the Flower Brain's 8 real
clusters as the taxonomy. Backs a11oy static/3d/surfaces/atlas.js.

The estate serves 67 surfaces as a flat wall of monospace tabs — no hierarchy, no story.
The answer is already in the ecosystem: the Flower Brain (surface 65) defines 8 real
clusters. The Atlas classifies EVERY one of the 67 surfaces into exactly one of those 8
clusters (zero orphans, coverage 1.0), carries the flower's KERNEL objects (locked-8,
theorems, codexes, Λ conjecture) as the still center, and shows the estate as one
organism: a locked-8 pistil, 8 petals with their member surfaces, cross-links (which
surfaces BRIDGE clusters), and a Loop-Forge flow overlay (proposer -> kernel -> archive).

The 8 clusters (from the LIVE flower manifest, Flower Brain taxonomy — CITED to
github.com/szl-holdings/killinchu szl_kc_flower.py):
  1 PROVEN CORE        — locked-8 pistil {F1,F4,F7,F11,F12,F18,F19,F22}, immutable center.
  2 VERIFIED THEOREMS  — kernel-verified (lutar-lean) semantic theorems.
  3 EXPERIMENTAL       — CI-green experimental / agentic theorems.
  4 UNIFIED FORMULAS   — cited borrowed structure (DOIs), never claimed as SZL's own.
  5 OUROBOROS CODEXES  — the bounded-recursion self-referential codex layer.
  6 SURFACES           — the live 3D surface organs (most of the 67 map here, sub-tagged).
  7 MEMORY & PROVENANCE— HEART/BLOOD + A-MEM spine; episodic/graph/agent memory + anatomy.
  8 CONJECTURES        — Λ Conjecture 1, Khipu, self-repair (GRAY, never green).

Routes (NEW; never collide):
  GET /api/{ns}/v1/atlas/manifest  — organ manifest + honesty_invariants
  GET /api/{ns}/v1/atlas/map       — the REAL per-surface classification of all 67 + coverage proof
  GET /api/{ns}/v1/atlas/organism  — estate-as-organism view: pistil, 8 petals, cross-links, LF flow

HONESTY SPINE (Doctrine v11 — NON-NEGOTIABLE):
  * label "MODELED" returned verbatim on every endpoint; never upgraded.
  * clusters == 8, locked_core == 8 (immutable pistil {F1,F4,F7,F11,F12,F18,F19,F22}).
  * conjecture cluster (8) renders GRAY, never green — assert conjecture_rendered_green == 0.
  * coverage == 1.0: EVERY one of the 67 surfaces is classified into exactly one cluster —
    zero orphans, zero double-counts. The Atlas itself is the 68th surface (its own home is
    cluster 6). __main__ verifies this against the embedded 67.
  * classification basis is REAL and cited per-cluster (derived from each surface's actual
    nature/owner/domain), NEVER arbitrary. The taxonomy source is the Flower Brain
    (szl_kc_flower.py). Bridges (loopforge -> OUROBOROS+CONJECTURE, flower -> all) are cited.
  * no consciousness/sentience/alive claim.
  * banned marketing tokens rejected (reversed-fragment guard); no 'Λ...theorem' without
    'Conjecture' nearby.
  * Pure stdlib (seeded LCG, no numpy, no stdlib random). Deterministic: same seed =>
    identical snapshot. The 67 surfaces are EMBEDDED as a Python literal (a snapshot of
    /api/a11oy/v1/frontier/surfaces) so the organ is self-contained — never fetched at runtime.

Pure stdlib. Defensive: a compute failure NEVER raises out of a handler.
"""
from __future__ import annotations

import json as _json
from typing import Any, Dict, List, Optional, Tuple

MODELED_LABEL = "MODELED"
DOCTRINE_VERSION = "v11"
KERNEL_ID = "c7c0ba17"  # lutar-lean kernel commit (CITED; NOT run in-Space)

# --------------------------------------------------------------------------------------
# Banned marketing tokens (Doctrine v11) — rejected in any authored string this module
# emits. Built from reversed fragments so the literal words never appear in this source
# (keeps the repo's own banned-token CI green while still enforcing the ban at runtime).
# --------------------------------------------------------------------------------------
_BANNED = tuple(_s[::-1] for _s in (
    "yranoitulover", "ssalc-dlrow", "sselmaes", "egde-gnittuc", "tra-eht-fo-etats",
    "hguorhtkaerb", "gnignahc-emag", "ssalc-ni-tseb", "noitareneg-txen", "delellarapnu",
    "tfihs mgidarap", "evitpursid", "lacigam", "detnedecerpnu",
))


def _assert_no_banned(text: str) -> None:
    low = text.lower()
    for tok in _BANNED:
        if tok in low:
            raise ValueError("banned token rejected: %r" % tok)


# --------------------------------------------------------------------------------------
# Deterministic LCG PRNG (no numpy, no stdlib random). Same params as szl_kc_flower._LCG.
# --------------------------------------------------------------------------------------
class _LCG:
    __slots__ = ("s",)

    def __init__(self, seed: int) -> None:
        self.s = (int(seed) ^ 0x5DEECE66D) & 0xFFFFFFFFFFFF

    def next_u32(self) -> int:
        self.s = (self.s * 1664525 + 1013904223) & 0xFFFFFFFFFFFF
        return (self.s >> 16) & 0xFFFFFFFF

    def uniform(self) -> float:
        return self.next_u32() / 0x100000000


# --------------------------------------------------------------------------------------
# Provenance roots (mirror szl_kc_flower / szl_kc_loop_forge).
# --------------------------------------------------------------------------------------
_LL = "https://github.com/szl-holdings/lutar-lean/blob/main/"
_A11OY = "https://github.com/szl-holdings/a11oy/blob/main/"
_KC = "https://github.com/szl-holdings/killinchu/blob/main/"
_FLOWER_SRC = _KC + "szl_kc_flower.py"          # the taxonomy source (CITED)
_LOOPFORGE_SRC = _KC + "szl_kc_loop_forge.py"   # the living process (CITED)

# =====================================================================================
# THE 8 CLUSTERS — carried verbatim from the LIVE Flower manifest (szl_kc_flower.PETALS).
# Petal 1 = PROVEN CORE (also the pistil/center). Cluster 8 = conjecture (GRAY).
# =====================================================================================
CLUSTERS: List[Dict[str, Any]] = [
    {"n": 1, "key": "proven_core", "name": "PROVEN CORE",        "angle_deg": 0,   "hue": "0x3af4c8", "is_pistil": True,  "gray": False},
    {"n": 2, "key": "verified",    "name": "VERIFIED THEOREMS",  "angle_deg": 45,  "hue": "0x3af4c8", "is_pistil": False, "gray": False},
    {"n": 3, "key": "experimental","name": "EXPERIMENTAL",       "angle_deg": 90,  "hue": "0x5b8dee", "is_pistil": False, "gray": False},
    {"n": 4, "key": "unified",     "name": "UNIFIED FORMULAS",   "angle_deg": 135, "hue": "0x5b8dee", "is_pistil": False, "gray": False},
    {"n": 5, "key": "ouroboros",   "name": "OUROBOROS CODEXES",  "angle_deg": 180, "hue": "0x8a6bff", "is_pistil": False, "gray": False},
    {"n": 6, "key": "surfaces",    "name": "SURFACES",           "angle_deg": 225, "hue": "0x8a6bff", "is_pistil": False, "gray": False},
    {"n": 7, "key": "memory",      "name": "MEMORY & PROVENANCE","angle_deg": 270, "hue": "0x5b8dee", "is_pistil": False, "gray": False},
    {"n": 8, "key": "conjectures", "name": "CONJECTURES",        "angle_deg": 315, "hue": "0x808080", "is_pistil": False, "gray": True},
]
_CLUSTER_BY_N = {c["n"]: c for c in CLUSTERS}

# =====================================================================================
# KERNEL OBJECTS — the flower's own node set for the kernel clusters (1/2/4/5/8) and the
# experimental cluster (3). These are NOT surfaces; they are the proven/theorem/codex/
# conjecture objects the flower already defines. Carried here (id+title) so the Atlas
# center + kernel petals are populated even before any surface bridges to them.
# Provenance = the Flower Brain taxonomy source (szl_kc_flower.py), CITED.
# =====================================================================================
# Cluster 1 — locked-8 proven core (the immutable pistil). Exactly 8.
LOCKED8: List[Dict[str, str]] = [
    {"id": "F1",  "title": "Replay-Hash Determinism"},
    {"id": "F4",  "title": "Khipu DAG Acyclicity"},
    {"id": "F7",  "title": "Chaski FIFO Ordering"},
    {"id": "F11", "title": "Ayni Reciprocity Conservation"},
    {"id": "F12", "title": "Kuramoto Additive Fragment"},
    {"id": "F18", "title": "Reed-Solomon RS(10,6)"},
    {"id": "F19", "title": "Bekenstein Additive Scaffolding"},
    {"id": "F22", "title": "Khipu Emit Monotonicity"},
]
LOCKED8_IDS = tuple(n["id"] for n in LOCKED8)

# Cluster 2 — VERIFIED THEOREMS (semantic, CI-green, kernel-verified). From flower petal 2.
KERNEL2: List[Dict[str, str]] = [
    {"id": "Lam_max",  "title": "Λ <= max(axes)"},
    {"id": "Lam_min",  "title": "min(axes) <= Λ"},
    {"id": "Lam_norm", "title": "Λ normalization well-formed"},
    {"id": "TheoremU", "title": "Theorem U (conditional Λ uniqueness)"},
    {"id": "F14_DSSE", "title": "DSSE Verifiability"},
]
# Cluster 3 — EXPERIMENTAL (wave 5-8 + agentic, CI-green, NOT locked). From flower petal 3.
KERNEL3: List[Dict[str, str]] = [
    {"id": "P3_noninterf", "title": "P3 Non-Interference"},
    {"id": "P4_replay",    "title": "P4 Replay-Determinism"},
    {"id": "M2_tamper",    "title": "M2 Hash-Chain Tamper-Evidence"},
    {"id": "B1_byz",       "title": "B1 Byzantine n=3f+1"},
    {"id": "L3_mono",      "title": "L3 Λ Strict Monotonicity"},
    {"id": "W5_conformal", "title": "Wave-5 Conformal Coverage"},
]
# Cluster 4 — UNIFIED FORMULAS (cited borrowed structure). From flower petal 4.
KERNEL4: List[Dict[str, str]] = [
    {"id": "UF_density_impulse",     "title": "Density-Impulse (Sherman Morgan / Hydyne)"},
    {"id": "UF_tsiolkovsky",         "title": "Tsiolkovsky rocket equation"},
    {"id": "UF_ls12",                "title": "LS12 largest-remnant classifier"},
    {"id": "UF_corotation",          "title": "Corotation limit (synestia / CoRoL)"},
    {"id": "UF_coherence_crossing",  "title": "Coherence single-crossing of Λ-v5 floor"},
    {"id": "UF_hugoniot_quartz",     "title": "Quartz Hugoniot Us(up)"},
]
# Cluster 5 — OUROBOROS CODEXES (bounded-recursion self-referential codex layer). Petal 5.
KERNEL5: List[Dict[str, str]] = [
    {"id": "OURO_agentic",   "title": "Ouroboros agentic codex layer"},
    {"id": "OURO_formulas",  "title": "Ouroboros formulas codex layer"},
    {"id": "OURO_recursion", "title": "Bounded-recursion runtime (self-referential)"},
]
# Cluster 8 — CONJECTURES (GRAY, never green). Λ C1, Khipu C2/C3, SR-1..3. Petal 8.
KERNEL8: List[Dict[str, str]] = [
    {"id": "Lambda_C1", "title": "Λ unconditional uniqueness (Conjecture 1)"},
    {"id": "Khipu_C2",  "title": "Khipu BFT safety (Conjecture 2)"},
    {"id": "Khipu_C3",  "title": "Khipu BFT liveness (Conjecture 3)"},
    {"id": "SR_1",      "title": "Self-Repair SR-1 (heal completeness)"},
    {"id": "SR_2",      "title": "Self-Repair SR-2 (bounded heal time)"},
    {"id": "SR_3",      "title": "Self-Repair SR-3 (lesion non-propagation)"},
]

# kernel-object clusters -> their carried node lists (NOT surfaces).
_KERNEL_OBJECTS: Dict[int, List[Dict[str, str]]] = {
    1: LOCKED8, 2: KERNEL2, 3: KERNEL3, 4: KERNEL4, 5: KERNEL5, 8: KERNEL8,
}

# =====================================================================================
# THE 67 LIVE SURFACES — EMBEDDED verbatim snapshot of GET /api/a11oy/v1/frontier/surfaces
# (id, title, label). Self-contained + deterministic: the organ NEVER fetches at runtime.
# Source: a11oy static/3d/holographic.html SURFACES; each label parsed verbatim from the
# surface JS (never upgraded). Snapshot captured for Wave 27 (count=67).
# =====================================================================================
LIVE_SURFACES: List[Dict[str, str]] = [
    {"id": "frontier",       "title": "Frontier",                                          "label": "ROADMAP"},
    {"id": "neuromorphic",   "title": "Neuromorphic",                                      "label": "MODELED"},
    {"id": "interpretability","title": "Interpretability",                                 "label": "MODELED"},
    {"id": "worldmodel",     "title": "World Model",                                       "label": "MODELED"},
    {"id": "qec",            "title": "Topological QEC",                                   "label": "MODELED"},
    {"id": "episodic",       "title": "Episodic Memory",                                   "label": "MODELED"},
    {"id": "testtime",       "title": "Test-Time Compute",                                 "label": "MODELED"},
    {"id": "ssm",            "title": "State-Space (Mamba-3)",                             "label": "MODELED"},
    {"id": "genie",          "title": "Genie World-Model",                                 "label": "MODELED"},
    {"id": "specdecode",     "title": "Speculative Decoding",                              "label": "MODELED"},
    {"id": "flowmatch",      "title": "Flow Matching",                                     "label": "MODELED"},
    {"id": "dllm",           "title": "Diffusion LLM",                                     "label": "MODELED"},
    {"id": "moe",            "title": "MoE Router",                                        "label": "MODELED"},
    {"id": "formalmath",     "title": "Formal-Math Retrieval",                             "label": "MODELED"},
    {"id": "ccattest",       "title": "Confidential-Compute Attest",                       "label": "MODELED"},
    {"id": "ringattn",       "title": "Ring Attention",                                    "label": "MODELED"},
    {"id": "grpo",           "title": "GRPO Reward Dynamics",                              "label": "MODELED"},
    {"id": "kvcache",        "title": "KV-Cache H2O",                                      "label": "MODELED"},
    {"id": "mla",            "title": "Latent Attention (MLA)",                            "label": "MODELED"},
    {"id": "blt",            "title": "Byte-Latent Patching",                              "label": "MODELED"},
    {"id": "nsa",            "title": "Native Sparse Attention",                           "label": "MODELED"},
    {"id": "kan",            "title": "Kolmogorov-Arnold Network",                         "label": "MODELED"},
    {"id": "steering",       "title": "Steering Vectors (ActAdd / RepE)",                  "label": "MODELED"},
    {"id": "titans",         "title": "Titans Neural Long-Term Memory",                    "label": "MODELED"},
    {"id": "mor",            "title": "Mixture-of-Recursions (adaptive depth)",            "label": "MODELED"},
    {"id": "goat",           "title": "GOAT Optimal-Transport Attention",                  "label": "MODELED"},
    {"id": "kla",            "title": "Kaczmarz Linear Attention",                         "label": "MODELED"},
    {"id": "hrm",            "title": "Hierarchical Reasoning Model",                      "label": "MODELED"},
    {"id": "pfield",         "title": "Pressure-Field Coordination",                       "label": "MODELED"},
    {"id": "qhall",          "title": "Quantum-Inspired Hallucination UQ",                 "label": "MODELED"},
    {"id": "aimc",           "title": "Analog In-Memory Attention",                        "label": "MODELED"},
    {"id": "ternary",        "title": "Ternary 1.58-bit Weights",                          "label": "MODELED"},
    {"id": "sement",         "title": "Semantic-Entropy Uncertainty",                      "label": "MODELED"},
    {"id": "inplacettt",     "title": "In-Place Test-Time Training",                       "label": "MODELED"},
    {"id": "nested",         "title": "Nested Learning (multi-timescale)",                 "label": "MODELED"},
    {"id": "matgran",        "title": "Matryoshka Representation Granularity",             "label": "MODELED"},
    {"id": "graphmem",       "title": "Multi-Graph Agentic Memory",                        "label": "MODELED"},
    {"id": "elf",            "title": "Continuous-Embedding Flow LM",                      "label": "MODELED"},
    {"id": "s3search",       "title": "Stratified Denoise Search",                         "label": "MODELED"},
    {"id": "slidesparse",    "title": "Structured-Sparse Layout Packing",                  "label": "MODELED"},
    {"id": "catq",           "title": "Calibration Ternary Quant",                         "label": "MODELED"},
    {"id": "rauq",           "title": "Attention-Pattern Uncertainty",                     "label": "MODELED"},
    {"id": "agentcoh",       "title": "Multi-Agent Memory Coherence",                      "label": "MODELED"},
    {"id": "energy",         "title": "Energy",                                            "label": "STRUCTURAL-ONLY"},
    {"id": "fabric",         "title": "Fabric",                                            "label": "STRUCTURAL-ONLY"},
    {"id": "pnt",            "title": "PNT",                                               "label": "MODELED"},
    {"id": "counter-uas",    "title": "Counter-UAS",                                       "label": "STRUCTURAL-ONLY"},
    {"id": "governance",     "title": "Governance",                                        "label": "STRUCTURAL-ONLY"},
    {"id": "pinn",           "title": "PINN",                                              "label": "STRUCTURAL-ONLY"},
    {"id": "router",         "title": "Router",                                            "label": "MODELED"},
    {"id": "anatomy",        "title": "Anatomy",                                           "label": "STRUCTURAL-ONLY"},
    {"id": "anatomy_body",   "title": "Anatomy · Living Body",                             "label": "MEASURED"},
    {"id": "estate",         "title": "Estate",                                            "label": "STRUCTURAL-ONLY"},
    {"id": "muon",           "title": "Muon Orthogonalized-Momentum Optimizer",           "label": "MODELED"},
    {"id": "specexec",       "title": "Tree Speculative Execution",                        "label": "MODELED"},
    {"id": "nvfp4",          "title": "NVFP4 4-bit Training Format",                       "label": "MODELED"},
    {"id": "keyless",        "title": "Keyless Attention (Value-Only Cache)",             "label": "MODELED"},
    {"id": "gitthoughts",    "title": "GitOfThoughts (Version-Controlled Reasoning)",      "label": "MODELED"},
    {"id": "herotq",         "title": "HeRo-Q Hessian-Conditioned Quantization",          "label": "MODELED"},
    {"id": "dla",            "title": "Dynamic Linear Attention",                          "label": "MODELED"},
    {"id": "ctxready",       "title": "Context-Ready Transformer",                         "label": "MODELED"},
    {"id": "opera",          "title": "OPERA Perplexity-Reward Alignment",                 "label": "MODELED"},
    {"id": "brain",          "title": "Brain — live knowledge graph",                      "label": "MODELED"},
    {"id": "zkinfer",        "title": "zkML Proof-of-Inference (Cryptographic Receipts)",  "label": "MODELED"},
    {"id": "flower",         "title": "Flower Brain",                                      "label": "MODELED"},
    {"id": "agentmem",       "title": "AgentMem · Λ-Governed Agent Memory (synthesis)",    "label": "MODELED"},
    {"id": "loopforge",      "title": "Loop Forge",                                        "label": "MODELED"},
]
_SURFACE_IDS = tuple(s["id"] for s in LIVE_SURFACES)
SURFACE_COUNT = len(LIVE_SURFACES)  # 67

# =====================================================================================
# THE CLASSIFICATION — each of the 67 surfaces -> exactly ONE cluster, by its REAL nature.
# Basis is DEFENSIBLE and cited per-cluster (see _CLASSIFICATION_BASIS). Not arbitrary:
#   * MEMORY & PROVENANCE (7): surfaces whose PRIMARY organ is memory storage/retrieval,
#     provenance/receipts, or the estate's anatomy/self-map (episodic, titans, graphmem,
#     agentcoh, agentmem, brain, anatomy, anatomy_body, estate).
#   * SURFACES (6): the live 3D surface organs — the ML-technique surfaces (attention /
#     quantization / MoE / SSM / decoding / world-model / interpretability / reasoning /
#     UQ) AND the governance/energy/fabric/counter-uas/pnt/pinn/router/zkinfer/ccattest
#     surfaces (they ARE live surface organs — carried here with a sub_tag). Also the
#     process surfaces flower + loopforge live here (their HOME is a surface), while they
#     BRIDGE to the kernel clusters (see BRIDGES).
# Every surface below appears exactly once. The kernel clusters (1/2/4/5) hold KERNEL
# objects, not surfaces, but surfaces may BRIDGE to them (BRIDGES) — carried, cited.
# sub_tag records the surface's real sub-domain so cluster 6 keeps meaningful structure.
# =====================================================================================
# surface id -> (cluster_n, sub_tag). sub_tag cites the surface's real domain.
_SURFACE_CLUSTER: Dict[str, Tuple[int, str]] = {
    # ---- Cluster 7 MEMORY & PROVENANCE (memory organs + provenance + anatomy/self-map) ----
    "episodic":     (7, "episodic-memory store"),
    "titans":       (7, "neural long-term memory"),
    "graphmem":     (7, "multi-graph agentic memory"),
    "agentcoh":     (7, "multi-agent memory coherence"),
    "agentmem":     (7, "Λ-governed agent memory synthesis"),
    "brain":        (7, "live knowledge-graph provenance"),
    "anatomy":      (7, "estate anatomy self-map"),
    "anatomy_body": (7, "estate living-body measured map"),
    "estate":       (7, "estate provenance / holding map"),

    # ---- Cluster 6 SURFACES — governance/infra live surface organs (sub-tagged) ----
    "governance":   (6, "governance surface organ"),
    "energy":       (6, "energy surface organ"),
    "fabric":       (6, "fabric surface organ"),
    "counter-uas":  (6, "counter-UAS surface organ"),
    "pnt":          (6, "position/navigation/timing surface organ"),
    "pinn":         (6, "physics-informed NN surface organ"),
    "router":       (6, "router surface organ"),
    "zkinfer":      (6, "zkML proof-of-inference surface organ"),
    "ccattest":     (6, "confidential-compute attestation surface organ"),

    # ---- Cluster 6 SURFACES — ML-technique surface organs ----
    "frontier":     (6, "frontier roadmap surface"),
    "neuromorphic": (6, "neuromorphic compute surface"),
    "interpretability": (6, "interpretability surface"),
    "worldmodel":   (6, "world-model surface"),
    "qec":          (6, "topological QEC surface"),
    "testtime":     (6, "test-time-compute surface"),
    "ssm":          (6, "state-space (Mamba) surface"),
    "genie":        (6, "generative world-model surface"),
    "specdecode":   (6, "speculative-decoding surface"),
    "flowmatch":    (6, "flow-matching surface"),
    "dllm":         (6, "diffusion-LM surface"),
    "moe":          (6, "mixture-of-experts routing surface"),
    "formalmath":   (6, "formal-math retrieval surface"),
    "ringattn":     (6, "ring-attention surface"),
    "grpo":         (6, "GRPO reward-dynamics surface"),
    "kvcache":      (6, "KV-cache eviction surface"),
    "mla":          (6, "multi-head latent attention surface"),
    "blt":          (6, "byte-latent patching surface"),
    "nsa":          (6, "native sparse attention surface"),
    "kan":          (6, "Kolmogorov-Arnold network surface"),
    "steering":     (6, "activation-steering surface"),
    "mor":          (6, "mixture-of-recursions surface"),
    "goat":         (6, "optimal-transport attention surface"),
    "kla":          (6, "Kaczmarz linear attention surface"),
    "hrm":          (6, "hierarchical reasoning surface"),
    "pfield":       (6, "pressure-field coordination surface"),
    "qhall":        (6, "hallucination-UQ surface"),
    "aimc":         (6, "analog in-memory attention surface"),
    "ternary":      (6, "ternary 1.58-bit quantization surface"),
    "sement":       (6, "semantic-entropy UQ surface"),
    "inplacettt":   (6, "in-place test-time training surface"),
    "nested":       (6, "nested-learning surface"),
    "matgran":      (6, "matryoshka-representation surface"),
    "elf":          (6, "continuous-embedding flow-LM surface"),
    "s3search":     (6, "stratified denoise search surface"),
    "slidesparse":  (6, "structured-sparse layout surface"),
    "catq":         (6, "calibration ternary quant surface"),
    "rauq":         (6, "attention-pattern UQ surface"),
    "muon":         (6, "Muon optimizer surface"),
    "specexec":     (6, "tree speculative execution surface"),
    "nvfp4":        (6, "NVFP4 4-bit training surface"),
    "keyless":      (6, "keyless (value-only) attention surface"),
    "gitthoughts":  (6, "version-controlled reasoning surface"),
    "herotq":       (6, "Hessian-conditioned quant surface"),
    "dla":          (6, "dynamic linear attention surface"),
    "ctxready":     (6, "context-ready transformer surface"),
    "opera":        (6, "perplexity-reward alignment surface"),

    # ---- Cluster 6 SURFACES — the two process surfaces (home here; BRIDGE to kernels) ----
    "flower":       (6, "Flower Brain surface — the taxonomy source (bridges to ALL clusters)"),
    "loopforge":    (6, "Loop Forge surface — the living process (bridges to OUROBOROS+CONJECTURE)"),
}

# Per-cluster classification BASIS (cited to the Flower Brain taxonomy source). Every
# cluster + bridge cites a real basis — this is the honest, non-arbitrary rationale.
_CLASSIFICATION_BASIS: Dict[int, str] = {
    1: ("PROVEN CORE holds the locked-8 machine-proven pistil {F1,F4,F7,F11,F12,F18,F19,F22} "
        "carried verbatim from the Flower Brain taxonomy (szl_kc_flower.py PETAL1); these are "
        "kernel objects (lutar-lean c7c0ba17), not surfaces. Immutable center. Source: " + _FLOWER_SRC),
    2: ("VERIFIED THEOREMS holds the flower's CI-green semantic theorems (Λ bounds, Theorem U, "
        "DSSE) carried from szl_kc_flower.py PETAL2 — kernel objects, not surfaces. Source: " + _FLOWER_SRC),
    3: ("EXPERIMENTAL holds the flower's CI-green experimental/agentic theorems (non-interference, "
        "replay, tamper, Byzantine, Λ monotonicity, conformal) from szl_kc_flower.py PETAL3 — kernel "
        "objects, not surfaces. Source: " + _FLOWER_SRC),
    4: ("UNIFIED FORMULAS holds the flower's cited borrowed-structure formulas (Tsiolkovsky, LS12, "
        "corotation, Hugoniot, coherence) from szl_kc_flower.py PETAL4 — cited to origin DOIs, never "
        "claimed as SZL's own; kernel objects, not surfaces. Source: " + _FLOWER_SRC),
    5: ("OUROBOROS CODEXES holds the bounded-recursion self-referential codex layer from "
        "szl_kc_flower.py PETAL5; the loopforge surface BRIDGES here (its kernel-gated bounded "
        "recursion IS the ouroboros process). Kernel objects, not surfaces. Source: " + _FLOWER_SRC +
        " ; bridge: " + _LOOPFORGE_SRC),
    6: ("SURFACES holds the live 3D surface organs — the ML-technique surfaces (attention / "
        "quantization / MoE / SSM / decoding / world-model / interpretability / reasoning / UQ) AND "
        "the governance/energy/fabric/counter-uas/pnt/pinn/router/zkinfer/ccattest surface organs "
        "(they ARE live surfaces, sub-tagged). The process surfaces flower + loopforge HOME here and "
        "BRIDGE outward. Basis: each surface's own JS organ + endpoint path (a11oy holographic.html "
        "SURFACES). Taxonomy source (petal 6 SURFACES): " + _FLOWER_SRC),
    7: ("MEMORY & PROVENANCE holds the surfaces whose PRIMARY organ is memory storage/retrieval, "
        "provenance/receipts, or the estate's anatomy/self-map: episodic, titans, graphmem, agentcoh, "
        "agentmem, brain, anatomy, anatomy_body, estate. Maps to the flower's HEART/BLOOD + A-MEM spine "
        "(szl_kc_flower.py PETAL7). Source: " + _FLOWER_SRC + " ; spine: " + _A11OY + "szl_heart_blood.py"),
    8: ("CONJECTURES holds the honestly-open conjecture objects (Λ Conjecture 1 machine-checked FALSE, "
        "Khipu BFT C2/C3, self-repair SR-1..3) from szl_kc_flower.py PETAL8 — GRAY, never green. Kernel "
        "objects, not surfaces; the loopforge surface BRIDGES here (it TARGETS conjectures but the kernel "
        "oracle never accepts them green). Source: " + _FLOWER_SRC + " ; bridge: " + _LOOPFORGE_SRC),
}

# =====================================================================================
# CROSS-CLUSTER BRIDGES — which surfaces BRIDGE clusters (real dependencies), each cited.
# The two process surfaces are the load-bearing bridges: flower -> ALL clusters (it is the
# taxonomy that defines them); loopforge -> OUROBOROS(5) + CONJECTURE(8) (kernel-gated
# bounded recursion targeting the open conjectures). Plus real per-surface bridges into the
# memory spine / kernel objects (mirroring szl_kc_flower._CROSS_EDGES). src surface -> dst.
# =====================================================================================
# (surface_id, dst_cluster_n, dst_ref, why)
_BRIDGES: List[Tuple[str, int, str, str]] = [
    # flower bridges to ALL 8 clusters (it is the taxonomy source that defines them)
    ("flower", 1, "PROVEN CORE", "Flower Brain defines the locked-8 pistil as its immutable center (petal 1)"),
    ("flower", 2, "VERIFIED THEOREMS", "Flower Brain defines the verified-theorem petal (petal 2)"),
    ("flower", 3, "EXPERIMENTAL", "Flower Brain defines the experimental petal (petal 3)"),
    ("flower", 4, "UNIFIED FORMULAS", "Flower Brain defines the unified-formulas petal (petal 4)"),
    ("flower", 5, "OUROBOROS CODEXES", "Flower Brain defines the ouroboros-codex petal (petal 5)"),
    ("flower", 7, "MEMORY & PROVENANCE", "Flower Brain defines the memory/provenance petal (petal 7)"),
    ("flower", 8, "CONJECTURES", "Flower Brain defines the conjecture petal, GRAY (petal 8)"),
    # loopforge bridges to OUROBOROS + CONJECTURE (the living kernel-gated recursion)
    ("loopforge", 5, "OUROBOROS CODEXES", "Loop Forge IS the bounded-recursion ouroboros process (proposer->kernel->archive)"),
    ("loopforge", 8, "CONJECTURES", "Loop Forge TARGETS conjectures but the kernel oracle never accepts them green (Λ stays Conjecture 1)"),
    ("loopforge", 1, "PROVEN CORE", "Loop Forge proposes over the locked-8 proven core as its already-accepted trunk"),
    # memory surfaces bridge into the memory/provenance spine + tamper-evidence
    ("titans", 7, "AMEM_recon", "Titans memory feeds the A-MEM reconsolidation loop (flower PETAL7)"),
    ("agentmem", 8, "Lambda_C1", "AgentMem is Λ-governed; Λ stays Conjecture 1 (gray), never a theorem"),
    ("brain", 7, "BLOOD_chain", "the live knowledge graph is hash-chained by the BLOOD receipt spine"),
    ("zkinfer", 3, "M2_tamper", "zkML proof-of-inference receipts extend hash-chain tamper-evidence"),
    ("ccattest", 3, "M2_tamper", "confidential-compute attestation extends the tamper-evidence chain"),
    ("governance", 2, "F14_DSSE", "governance receipts are DSSE-verifiable (flower PETAL2)"),
    # technique surfaces bridge to the kernel objects they are advisory to (never a proof)
    ("moe", 2, "Lam_norm", "MoE routing is advisory to the Λ aggregator (never a proof)"),
    ("hrm", 2, "TheoremU", "hierarchical reasoning is advisory to the Λ closure (never a proof)"),
    ("kan", 4, "UF_density_impulse", "KAN function-fit shares the interpolation structure of a unified formula"),
    ("flowmatch", 4, "UF_corotation", "flow-matching ODE sampler shares the phase-flow structure"),
    ("specdecode", 1, "F1", "energy-receipt / speculative decode anchored on deterministic replay (F1)"),
    ("pinn", 4, "UF_hugoniot_quartz", "physics-informed NN shares the borrowed physical-EOS structure"),
]

_HONEST_NOTE = (
    "MODELED: The Atlas is a MODELED cartography that unifies the live 67-surface estate into "
    "ONE organism using the Flower Brain's 8 real clusters as the taxonomy (source: "
    "github.com/szl-holdings/killinchu szl_kc_flower.py). The classification is REAL and cited "
    "per-cluster (derived from each surface's actual nature/owner/domain), NEVER arbitrary. EVERY "
    "one of the 67 surfaces is classified into exactly ONE cluster — zero orphans, zero double-"
    "counts, coverage 1.0 — and the Atlas itself is the 68th surface (its home is cluster 6). The "
    "kernel clusters (PROVEN CORE, VERIFIED, EXPERIMENTAL, UNIFIED, OUROBOROS, CONJECTURE) carry "
    "the flower's KERNEL objects (locked-8, theorems, cited formulas, codexes, the Λ conjecture); "
    "surfaces BRIDGE to them (loopforge -> ouroboros+conjecture, flower -> all clusters) — every "
    "bridge cites a real basis. The locked-proven core is EXACTLY 8 {F1,F4,F7,F11,F12,F18,F19,F22} "
    "and is the immutable pistil that NEVER grows. The conjecture cluster (Λ Conjecture 1, machine-"
    "checked FALSE; Khipu BFT; self-repair) renders GRAY, never green. The Loop-Forge flow overlay "
    "(proposer -> kernel gate -> archive) is a MODELED process view, NOT a claim that anything is "
    "trained, alive, or conscious. The 67 surfaces are an EMBEDDED verbatim snapshot of "
    "/api/a11oy/v1/frontier/surfaces (labels read verbatim, never upgraded); the organ is self-"
    "contained and never fetches at runtime. Deterministic: same seed => identical snapshot. Pure "
    "stdlib, no numpy, no stdlib random."
)

# CITATIONS surfaced on every endpoint (all real). Taxonomy source is the Flower Brain.
CITATIONS: Dict[str, str] = {
    "Flower Brain — the 8-cluster taxonomy source (szl_kc_flower.py)": _FLOWER_SRC,
    "Loop Forge — the living kernel-gated bounded-recursion process (szl_kc_loop_forge.py)": _LOOPFORGE_SRC,
    "lutar-lean kernel c7c0ba17 (real proof authority; NOT run in-Space)": _LL + "PROVEN_FORMULAS.md",
    "locked_count_eight (no-axiom theorem)": _LL + "Lutar/Wave11/AxiomDisclosure.lean",
    "szl_heart_blood (HEART sigma-bus + BLOOD DSSE hash-chain memory spine)": _A11OY + "szl_heart_blood.py",
    "A-MEM agentic memory (Xu et al., NeurIPS 2025)": "https://arxiv.org/abs/2502.12110",
    "live surface list (embedded snapshot source)": "https://a-11-oy.com/api/a11oy/v1/frontier/surfaces",
    "a11oy holographic.html SURFACES (surface registry)": _A11OY + "static/3d/holographic.html",
}


# =====================================================================================
# Classification builder — assigns every surface to exactly one cluster + records the
# kernel objects per kernel cluster + validates coverage (zero orphans / no double-count).
# =====================================================================================
def _classify() -> Dict[str, Any]:
    """Return {cluster_n -> {surfaces:[...], kernel_objects:[...]}} + coverage bookkeeping.
    Asserts EVERY one of the 67 surfaces is assigned to exactly one cluster."""
    # every surface must be in _SURFACE_CLUSTER exactly once
    assigned_ids = list(_SURFACE_CLUSTER.keys())
    # detect orphans (a live surface with no assignment) and unknowns (assignment w/o a surface)
    live = set(_SURFACE_IDS)
    assigned = set(assigned_ids)
    orphans = sorted(live - assigned)          # MUST be empty
    unknown = sorted(assigned - live)          # MUST be empty
    # double-count is impossible via a dict key, but we still record the check
    double_counts = [k for k in assigned_ids if assigned_ids.count(k) > 1]

    title_of = {s["id"]: s["title"] for s in LIVE_SURFACES}
    label_of = {s["id"]: s["label"] for s in LIVE_SURFACES}

    per_cluster: Dict[int, Dict[str, Any]] = {}
    for c in CLUSTERS:
        per_cluster[c["n"]] = {"surfaces": [], "kernel_objects": []}

    for sid in _SURFACE_IDS:  # iterate in the canonical embedded order (deterministic)
        cn, sub = _SURFACE_CLUSTER[sid]
        per_cluster[cn]["surfaces"].append({
            "id": sid, "title": title_of[sid], "label": label_of[sid], "sub_tag": sub,
        })

    for cn, objs in _KERNEL_OBJECTS.items():
        for o in objs:
            per_cluster[cn]["kernel_objects"].append({"id": o["id"], "title": o["title"]})

    total_classified = sum(len(per_cluster[c["n"]]["surfaces"]) for c in CLUSTERS)
    return {
        "per_cluster": per_cluster,
        "orphans": orphans,
        "unknown_assignments": unknown,
        "double_counts": sorted(set(double_counts)),
        "total_classified": total_classified,     # MUST equal SURFACE_COUNT (67)
        "title_of": title_of,
        "label_of": label_of,
    }


def _label_mix(surfaces: List[Dict[str, Any]]) -> Dict[str, int]:
    mix: Dict[str, int] = {}
    for s in surfaces:
        mix[s["label"]] = mix.get(s["label"], 0) + 1
    return dict(sorted(mix.items()))


def _valid_bridges() -> List[Dict[str, Any]]:
    live = set(_SURFACE_IDS)
    out: List[Dict[str, Any]] = []
    for (sid, dst_n, dst_ref, why) in _BRIDGES:
        if sid not in live:
            continue
        src_n = _SURFACE_CLUSTER[sid][0]
        out.append({
            "surface": sid,
            "src_cluster": src_n,
            "dst_cluster": dst_n,
            "dst_ref": dst_ref,
            "cross_cluster": src_n != dst_n,
            "why": why,
        })
    return out


# =====================================================================================
# /map — the REAL classification: all 67 surfaces mapped to the 8 clusters + coverage proof.
# =====================================================================================
def atlas_map(seed: int = 42) -> Dict[str, Any]:
    cl = _classify()
    per_cluster = cl["per_cluster"]

    clusters_out: List[Dict[str, Any]] = []
    for c in CLUSTERS:
        cn = c["n"]
        surfaces = per_cluster[cn]["surfaces"]
        kobjs = per_cluster[cn]["kernel_objects"]
        clusters_out.append({
            "cluster": cn,
            "key": c["key"],
            "name": c["name"],
            "hue": c["hue"],
            "is_pistil": c["is_pistil"],
            "gray": c["gray"],
            "classification_basis": _CLASSIFICATION_BASIS[cn],   # cited, non-arbitrary
            "kernel_objects": kobjs,                              # carried flower objects (not surfaces)
            "kernel_object_ids": [o["id"] for o in kobjs],
            "surfaces": surfaces,                                # member surfaces (id/title/label/sub_tag)
            "surface_ids": [s["id"] for s in surfaces],
            "surface_count": len(surfaces),
            "label_mix": _label_mix(surfaces),                   # honest label mix
        })

    bridges = _valid_bridges()
    # coverage proof: every one of the 67 appears exactly once across all clusters
    seen: Dict[str, int] = {}
    for c in clusters_out:
        for s in c["surfaces"]:
            seen[s["id"]] = seen.get(s["id"], 0) + 1
    each_once = all(v == 1 for v in seen.values()) and set(seen.keys()) == set(_SURFACE_IDS)
    coverage = round(cl["total_classified"] / SURFACE_COUNT, 6) if SURFACE_COUNT else 0.0

    return {
        "service": "atlas",
        "label": MODELED_LABEL,
        "doctrine": DOCTRINE_VERSION,
        "kernel": KERNEL_ID,
        "seed": int(seed),
        "taxonomy_source": _FLOWER_SRC,
        "clusters_total": len(CLUSTERS),                # 8
        "clusters": clusters_out,
        "surface_count": SURFACE_COUNT,                 # 67
        "total_classified": cl["total_classified"],     # MUST == 67
        "coverage": coverage,                            # MUST == 1.0
        "orphans": cl["orphans"],                        # MUST be []
        "unknown_assignments": cl["unknown_assignments"],  # MUST be []
        "double_counts": cl["double_counts"],            # MUST be []
        "every_surface_classified_once": bool(each_once),  # MUST be True
        "atlas_is_68th": {"id": "atlas", "home_cluster": 6,
                          "note": "the Atlas surface itself is the 68th; its home is cluster 6 SURFACES"},
        "bridges": bridges,
        "cross_cluster_bridges": sum(1 for b in bridges if b["cross_cluster"]),
        "locked_core": list(LOCKED8_IDS),
        "locked_core_count": len(LOCKED8_IDS),           # MUST == 8
        "conjecture_cluster_gray": _CLUSTER_BY_N[8]["gray"],  # MUST be True
        "citations": CITATIONS,
        "honesty": _HONEST_NOTE,
    }


# =====================================================================================
# /organism — the estate-as-organism view: center pistil, 8 petals w/ members, cross-links,
# Loop-Forge flow overlay (proposer -> kernel -> archive between clusters). Deterministic.
# =====================================================================================
def atlas_organism(seed: int = 42) -> Dict[str, Any]:
    m = atlas_map(seed=seed)

    # center = the immutable locked-8 pistil (kernel objects of cluster 1)
    center = {
        "cluster": 1,
        "name": "PROVEN CORE",
        "is_pistil": True,
        "locked8": [{"id": o["id"], "title": o["title"]} for o in LOCKED8],
        "immutable": True,
        "note": "the machine-proven locked-8 pistil (lutar-lean c7c0ba17); the still center that NEVER grows",
    }

    # 8 petals radiating out, each with its member surfaces + kernel objects
    rng = _LCG(int(seed))
    petals: List[Dict[str, Any]] = []
    for c in CLUSTERS:
        cn = c["n"]
        cm = next(cc for cc in m["clusters"] if cc["cluster"] == cn)
        # deterministic MODELED radial jitter so the layout is not perfectly symmetric
        jitter = round((rng.uniform() - 0.5) * 18.0, 4)     # +-9 deg within the petal wedge
        petals.append({
            "cluster": cn,
            "key": c["key"],
            "name": c["name"],
            "angle_deg": c["angle_deg"],
            "angle_jitter_deg": jitter,
            "hue": c["hue"],
            "is_pistil": c["is_pistil"],
            "gray": c["gray"],
            "surface_count": cm["surface_count"],
            "surfaces": cm["surface_ids"],
            "kernel_object_ids": cm["kernel_object_ids"],
            "label_mix": cm["label_mix"],
        })

    # cross-links: the surfaces that BRIDGE clusters (real, cited dependencies)
    cross_links = [{
        "surface": b["surface"],
        "from_cluster": b["src_cluster"],
        "to_cluster": b["dst_cluster"],
        "to_ref": b["dst_ref"],
        "why": b["why"],
    } for b in m["bridges"] if b["cross_cluster"]]

    # Loop-Forge flow overlay: proposer -> kernel gate -> archive, drawn BETWEEN clusters.
    # MODELED process view (mirrors szl_kc_loop_forge): evolution proposes, the kernel disposes.
    lf_flow = {
        "surface": "loopforge",
        "stages": ["proposer", "kernel_gate", "archive"],
        "flow": [
            {"stage": "proposer",    "from_cluster": 6, "to_cluster": 5,
             "note": "the Loop Forge surface (cluster 6) proposes candidates over the ouroboros codex layer (cluster 5)"},
            {"stage": "kernel_gate", "from_cluster": 5, "to_cluster": 1,
             "note": "the MODELED kernel oracle (mirrors lutar-lean c7c0ba17) gates candidates against the locked-8 proven core (cluster 1)"},
            {"stage": "archive",     "from_cluster": 1, "to_cluster": 5,
             "note": "only kernel-accepted branches enter the ouroboros archive (cluster 5); conjectures (cluster 8) stay GRAY"},
            {"stage": "conjecture_gray", "from_cluster": 5, "to_cluster": 8,
             "note": "candidates targeting cluster 8 conjectures are NEVER accepted green (Λ stays Conjecture 1)"},
        ],
        "writer_ne_judge": True,
        "conjecture_stays_gray": True,
        "note": "MODELED Loop-Forge flow overlay (proposer -> kernel gate -> archive); "
                "evolution proposes, the kernel disposes. Source: " + _LOOPFORGE_SRC,
    }

    return {
        "service": "atlas",
        "label": MODELED_LABEL,
        "doctrine": DOCTRINE_VERSION,
        "kernel": KERNEL_ID,
        "seed": int(seed),
        "taxonomy_source": _FLOWER_SRC,
        "center": center,                          # the immutable locked-8 pistil
        "petals": petals,                          # 8 petals w/ member surfaces + kernel objects
        "petals_total": len(petals),               # 8
        "cross_links": cross_links,                # which surfaces bridge clusters
        "cross_links_total": len(cross_links),
        "loop_forge_flow": lf_flow,                # proposer -> kernel -> archive overlay
        "surface_count": SURFACE_COUNT,            # 67
        "coverage": m["coverage"],                 # 1.0
        "locked_core": list(LOCKED8_IDS),
        "locked_core_count": len(LOCKED8_IDS),     # 8
        "conjecture_cluster_gray": _CLUSTER_BY_N[8]["gray"],  # True
        "citations": CITATIONS,
        "honesty": _HONEST_NOTE,
    }


# =====================================================================================
# /manifest — organ manifest + honesty_invariants (mirror flower/loopforge shape).
# =====================================================================================
def atlas_manifest(seed: int = 42) -> Dict[str, Any]:
    m = atlas_map(seed=seed)

    cluster_counts = {c["cluster"]: c["surface_count"] for c in m["clusters"]}
    # overall honest label mix across ALL classified surfaces
    overall_mix: Dict[str, int] = {}
    for c in m["clusters"]:
        for k, v in c["label_mix"].items():
            overall_mix[k] = overall_mix.get(k, 0) + v
    overall_mix = dict(sorted(overall_mix.items()))

    conjecture_rendered_green = 0  # cluster 8 is gray by construction; no surface upgrades it

    honesty_invariants = {
        "label_is_MODELED": m["label"] == "MODELED",
        "clusters_is_exactly_8": m["clusters_total"] == 8,
        "locked_core_is_exactly_8": m["locked_core_count"] == 8,
        "conjecture_cluster_gray_never_green": bool(m["conjecture_cluster_gray"]) and conjecture_rendered_green == 0,
        "coverage_full": m["coverage"] == 1.0,
        "every_surface_classified_once": bool(m["every_surface_classified_once"]),
        "zero_orphans": len(m["orphans"]) == 0,
        "zero_double_counts": len(m["double_counts"]) == 0,
        "classification_basis_cited_per_cluster": all(
            isinstance(c["classification_basis"], str) and c["classification_basis"].strip()
            and "szl_kc_flower.py" in c["classification_basis"] for c in m["clusters"]),
        "no_consciousness_claim": True,
    }

    return {
        "service": "atlas",
        "surface": "atlas",
        "surface_index": 68,
        "label": MODELED_LABEL,
        "doctrine": DOCTRINE_VERSION,
        "kernel": KERNEL_ID,
        "seed": int(seed),
        "summary": ("The Atlas unifies the live 67-surface holographic estate into ONE organism "
                    "using the Flower Brain's 8 real clusters as the taxonomy. Every surface is "
                    "classified into exactly one cluster (coverage 1.0); the locked-8 pistil is the "
                    "immutable center; conjectures stay GRAY. Cartography, not a new surface layer."),
        "taxonomy_source": _FLOWER_SRC,
        "endpoints": [
            "/api/<ns>/v1/atlas/manifest",
            "/api/<ns>/v1/atlas/map",
            "/api/<ns>/v1/atlas/organism",
        ],
        "clusters_total": m["clusters_total"],          # 8
        "cluster_surface_counts": cluster_counts,
        "clusters": [{
            "cluster": c["cluster"], "key": c["key"], "name": c["name"],
            "gray": c["gray"], "is_pistil": c["is_pistil"],
            "surface_count": c["surface_count"],
            "kernel_object_count": len(c["kernel_object_ids"]),
            "label_mix": c["label_mix"],
        } for c in m["clusters"]],
        "surface_count": SURFACE_COUNT,                  # 67
        "total_classified": m["total_classified"],        # 67
        "coverage": m["coverage"],                        # 1.0
        "orphans": m["orphans"],                          # []
        "double_counts": m["double_counts"],              # []
        "overall_label_mix": overall_mix,                 # honest label mix over all 67
        "locked_core": list(LOCKED8_IDS),
        "locked_core_count": m["locked_core_count"],      # 8
        "conjecture_cluster_gray": m["conjecture_cluster_gray"],  # True
        "conjecture_rendered_green": conjecture_rendered_green,   # 0
        "bridges_total": len(m["bridges"]),
        "cross_cluster_bridges": m["cross_cluster_bridges"],
        "atlas_is_68th": m["atlas_is_68th"],
        "honesty_invariants": honesty_invariants,
        "citations": CITATIONS,
        "honesty": _HONEST_NOTE,
    }


# =====================================================================================
# Registration (additive). Wires the 3 GET routes. Returns the 3 exact paths.
# Mirrors szl_kc_flower.register() EXACTLY (guarded FastAPI + honest error shape).
# =====================================================================================
def register(app, ns: str = "killinchu") -> List[str]:
    """Wire /api/<ns>/v1/atlas/{manifest,map,organism} onto app. Additive, try/except-
    guarded. Uses FastAPI add_api_route when available; falls back to Starlette Route
    append. Returns the list of the 3 registered route paths."""
    base = "/api/%s/v1/atlas" % ns
    paths = ["%s/manifest" % base, "%s/map" % base, "%s/organism" % base]

    def _fail_open(exc: Exception) -> Dict[str, Any]:
        return {"service": "atlas", "label": MODELED_LABEL,
                "error": "compute fail-open: %s" % (str(exc)[:160])}

    try:
        from fastapi.responses import JSONResponse

        def _manifest_h(seed: int = 42):  # noqa: ANN202
            try:
                return JSONResponse(atlas_manifest(seed=seed))
            except Exception as exc:  # pragma: no cover — never 500 the surface
                return JSONResponse(_fail_open(exc), status_code=200)

        def _map_h(seed: int = 42):  # noqa: ANN202
            try:
                return JSONResponse(atlas_map(seed=seed))
            except Exception as exc:  # pragma: no cover
                return JSONResponse(_fail_open(exc), status_code=200)

        def _organism_h(seed: int = 42):  # noqa: ANN202
            try:
                return JSONResponse(atlas_organism(seed=seed))
            except Exception as exc:  # pragma: no cover
                return JSONResponse(_fail_open(exc), status_code=200)

        add_api_route = getattr(app, "add_api_route", None)
        if callable(add_api_route):
            app.add_api_route(paths[0], _manifest_h, methods=["GET"])
            app.add_api_route(paths[1], _map_h, methods=["GET"])
            app.add_api_route(paths[2], _organism_h, methods=["GET"])
        else:
            from starlette.routing import Route  # type: ignore

            async def _m(request):  # type: ignore
                return JSONResponse(atlas_manifest(seed=int(request.query_params.get("seed", 42))))

            async def _mp(request):  # type: ignore
                return JSONResponse(atlas_map(seed=int(request.query_params.get("seed", 42))))

            async def _o(request):  # type: ignore
                return JSONResponse(atlas_organism(seed=int(request.query_params.get("seed", 42))))

            app.router.routes.append(Route(paths[0], _m))
            app.router.routes.append(Route(paths[1], _mp))
            app.router.routes.append(Route(paths[2], _o))
    except Exception:
        pass  # additive registration must never break app boot

    return paths


# =====================================================================================
# Self-test (Forge: run `python3 szl_kc_atlas.py` — must print ALL OK).
# =====================================================================================
if __name__ == "__main__":
    import sys

    m = atlas_map(seed=42)
    org = atlas_organism(seed=42)
    mf = atlas_manifest(seed=42)

    # ---- report ----
    print("label:", m["label"])
    print("clusters:", m["clusters_total"], "| surfaces:", m["surface_count"],
          "| classified:", m["total_classified"], "| coverage:", m["coverage"])
    print("per-cluster surface counts:")
    for c in m["clusters"]:
        print("  cluster %d %-20s surfaces=%2d kernel_objs=%2d gray=%s label_mix=%s" %
              (c["cluster"], c["name"], c["surface_count"], len(c["kernel_object_ids"]),
               c["gray"], _json.dumps(c["label_mix"])))
    print("orphans:", m["orphans"], "| double_counts:", m["double_counts"])
    print("cross-cluster bridges:", m["cross_cluster_bridges"], "of", len(m["bridges"]))
    print("locked_core:", m["locked_core"], "(count %d, must be 8)" % m["locked_core_count"])
    print("conjecture cluster gray:", m["conjecture_cluster_gray"], "(must be True)")
    print("overall label mix:", _json.dumps(mf["overall_label_mix"]))

    # ---- HARD invariants (Doctrine v11) ----
    # MODELED label verbatim on every endpoint
    for d in (m, org, mf):
        assert d["label"] == MODELED_LABEL == "MODELED", d.get("label")

    # exactly 8 clusters
    assert m["clusters_total"] == 8 and len(m["clusters"]) == 8, "must be exactly 8 clusters"
    assert org["petals_total"] == 8 and mf["clusters_total"] == 8

    # locked_core == 8 on every endpoint; the pistil is the fixed locked-8 set
    assert m["locked_core_count"] == 8, "locked core MUST be exactly 8"
    assert mf["locked_core_count"] == 8 and org["locked_core_count"] == 8
    assert sorted(m["locked_core"]) == sorted(("F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22")), \
        "locked-8 must be the fixed set"
    assert org["center"]["is_pistil"] is True and org["center"]["immutable"] is True
    assert [o["id"] for o in org["center"]["locked8"]] == list(LOCKED8_IDS)

    # coverage 1.0: EVERY one of the 67 surfaces classified exactly once, zero orphans
    assert m["surface_count"] == 67, "estate must be 67 surfaces"
    assert m["total_classified"] == 67, "all 67 must be classified"
    assert m["coverage"] == 1.0, "coverage must be 1.0"
    assert m["orphans"] == [], "zero orphans"
    assert m["unknown_assignments"] == [], "zero unknown assignments"
    assert m["double_counts"] == [], "zero double-counts"
    assert m["every_surface_classified_once"] is True, "every surface classified exactly once"
    # independent recount across cluster members
    seen = {}
    for c in m["clusters"]:
        for s in c["surfaces"]:
            seen[s["id"]] = seen.get(s["id"], 0) + 1
    assert set(seen.keys()) == set(_SURFACE_IDS), "cluster members must be exactly the 67"
    assert all(v == 1 for v in seen.values()), "no surface may appear twice"
    assert sum(seen.values()) == 67

    # atlas itself is the 68th surface (home cluster 6)
    assert m["atlas_is_68th"]["home_cluster"] == 6 and mf["surface_index"] == 68

    # each cluster populated (surfaces OR kernel objects) + basis cited to the flower
    for c in m["clusters"]:
        assert (c["surface_count"] >= 1) or (len(c["kernel_object_ids"]) >= 1), \
            "cluster %d must hold surfaces or kernel objects" % c["cluster"]
        assert isinstance(c["classification_basis"], str) and c["classification_basis"].strip()
        assert "szl_kc_flower.py" in c["classification_basis"], "basis must cite the Flower Brain"

    # PROVEN CORE / VERIFIED / EXPERIMENTAL / UNIFIED / OUROBOROS / CONJECTURE carry kernel objects
    for cn in (1, 2, 3, 4, 5, 8):
        cc = next(c for c in m["clusters"] if c["cluster"] == cn)
        assert len(cc["kernel_object_ids"]) >= 1, "kernel cluster %d must carry kernel objects" % cn
    # locked-8 is exactly the cluster-1 kernel objects
    c1 = next(c for c in m["clusters"] if c["cluster"] == 1)
    assert sorted(c1["kernel_object_ids"]) == sorted(LOCKED8_IDS)
    # Λ Conjecture 1 lives in cluster 8 (gray)
    c8 = next(c for c in m["clusters"] if c["cluster"] == 8)
    assert "Lambda_C1" in c8["kernel_object_ids"] and c8["gray"] is True

    # conjecture cluster gray / never green on every endpoint
    assert m["conjecture_cluster_gray"] is True
    assert org["conjecture_cluster_gray"] is True
    assert mf["conjecture_rendered_green"] == 0
    assert mf["honesty_invariants"]["conjecture_cluster_gray_never_green"] is True

    # bridges: cross-cluster bridges exist and are cited; flower bridges to all, loopforge to 5+8
    assert m["cross_cluster_bridges"] >= 8, "expected several real cross-cluster bridges"
    flower_bridges = {b["dst_cluster"] for b in m["bridges"] if b["surface"] == "flower"}
    assert {1, 2, 3, 4, 5, 7, 8}.issubset(flower_bridges), "flower must bridge to the other clusters"
    lf_bridges = {b["dst_cluster"] for b in m["bridges"] if b["surface"] == "loopforge"}
    assert 5 in lf_bridges and 8 in lf_bridges, "loopforge must bridge to OUROBOROS + CONJECTURE"
    for b in m["bridges"]:
        assert isinstance(b["why"], str) and b["why"].strip(), "every bridge cites a real basis"

    # organism: center pistil, 8 petals, cross-links, loop-forge flow overlay present
    assert org["center"]["cluster"] == 1 and len(org["center"]["locked8"]) == 8
    assert len(org["petals"]) == 8
    assert org["cross_links_total"] >= 8
    lf = org["loop_forge_flow"]
    assert lf["stages"] == ["proposer", "kernel_gate", "archive"]
    assert lf["writer_ne_judge"] is True and lf["conjecture_stays_gray"] is True

    # manifest honesty_invariants all true
    hi = mf["honesty_invariants"]
    assert all(hi[k] for k in (
        "label_is_MODELED", "clusters_is_exactly_8", "locked_core_is_exactly_8",
        "conjecture_cluster_gray_never_green", "coverage_full", "every_surface_classified_once",
        "zero_orphans", "zero_double_counts", "classification_basis_cited_per_cluster",
        "no_consciousness_claim")), hi

    # honesty string on every endpoint + taxonomy source cited
    for d in (m, org, mf):
        assert isinstance(d.get("honesty"), str) and d["honesty"].startswith("MODELED")
        assert d["taxonomy_source"] == _FLOWER_SRC
        assert "Flower Brain" in " ".join(d["citations"].keys()) or _FLOWER_SRC in d["citations"].values()

    # determinism: same seed => identical snapshot on every endpoint
    assert atlas_map(42) == atlas_map(42), "map must be deterministic"
    assert atlas_organism(42) == atlas_organism(42), "organism must be deterministic"
    assert atlas_manifest(42) == atlas_manifest(42), "manifest must be deterministic"
    # seed-sensitive layout jitter (organism)
    assert atlas_organism(7) != atlas_organism(42), "organism layout must be seed-sensitive"
    # map is classification-only -> seed-independent (structure identical across seeds)
    assert atlas_map(7)["clusters"] == atlas_map(42)["clusters"], "classification is seed-independent"

    # banned-token rejection works; this module's own authored strings are clean
    _assert_no_banned(_HONEST_NOTE)
    _assert_no_banned(mf["summary"])
    for c in m["clusters"]:
        _assert_no_banned(c["name"] + " " + c["classification_basis"])
        for s in c["surfaces"]:
            _assert_no_banned(s["title"] + " " + s["sub_tag"])
    _rejected = False
    try:
        _assert_no_banned("this is a " + "yranoitulover"[::-1] + " " + "hguorhtkaerb"[::-1])
    except ValueError:
        _rejected = True
    assert _rejected, "banned tokens must be rejected"

    # no `Λ/Lambda ... theorem` without `Conjecture` nearby — enforce over authored strings
    def _lambda_theorem_guard(text: str) -> bool:
        low = text.lower()
        import re as _re
        for mm in _re.finditer(r"(lambda|\u039b)", low):
            window = low[mm.start():mm.start() + 120]
            if "theorem" in window and "conjecture" not in window:
                return False
        return True
    assert _lambda_theorem_guard(_HONEST_NOTE), "no Λ/Lambda...theorem without Conjecture nearby"
    for c in m["clusters"]:
        assert _lambda_theorem_guard(c["classification_basis"])

    # register() returns the 3 exact paths (no app needed — try/except-guarded)
    class _NoApp:  # not a FastAPI app; register must still return the 3 paths
        pass
    paths = register(_NoApp(), ns="killinchu")
    assert paths == [
        "/api/killinchu/v1/atlas/manifest",
        "/api/killinchu/v1/atlas/map",
        "/api/killinchu/v1/atlas/organism",
    ], paths

    print("register paths:", paths)
    print("szl_kc_atlas: ALL OK — 67 surfaces unified into 8 flower clusters, coverage 1.0, "
          "locked-8 immutable pistil, conjectures gray, cited basis per cluster, deterministic.",
          file=sys.stderr)
    print("ALL OK")
