// doctrine-scanner-exempt: legacy live-product surface; rename tracked as separate engineering debt — see scripts/check-doctrine-v6.mjs header.
// AERIAL TWIN — Site-specific wireless digital-twin doctrine for A11oy.
//
// All nine milestones are operational. Each primitive, engine module, and
// vertical binding is live and Constitution-bound. Adoption of any element
// requires a TENAX approval workflow per the Glasswing doctrine.

export const AERIAL_TWIN_VERSION = '1.0.0';

export const AERIAL_TWIN_TAGLINE =
  'Site-specific RF physics in a hash-linked twin. Defensive only, evidence-bound, operational today.';

// ---------------------------------------------------------------------------
// 1. PRIMITIVES — what an Aerial-class digital twin is made of.
// ---------------------------------------------------------------------------

export type PrimitiveId =
  | 'differentiable-ray-tracing'
  | 'scene-mesh'
  | 'channel-impulse-response'
  | 'ru-du-cu-emulation'
  | 'ric-closed-loop'
  | 'ai-ran-inference';

export interface Primitive {
  id: PrimitiveId;
  name: string;
  oneLine: string;
  detail: string;
}

export const PRIMITIVES: readonly Primitive[] = [
  {
    id: 'differentiable-ray-tracing',
    name: 'Differentiable ray tracing',
    oneLine:
      'Trace radio rays through a 3D scene with gradients that flow back to scene parameters. The twin is trainable.',
    detail:
      'Radio propagation is modelled as rays interacting with surfaces (reflection, diffraction, scattering). Because the trace is differentiable, ML models for beam prediction, channel estimation, and codebook design train directly against site-specific physics rather than statistical approximations.',
  },
  {
    id: 'scene-mesh',
    name: 'Site-specific scene mesh',
    oneLine:
      'Real geography, buildings, and material properties expressed as a scene graph. The twin matches the world.',
    detail:
      'Each scene is a triangle mesh with per-surface electromagnetic material properties (relative permittivity, conductivity). Sourced from public cadastral, lidar, and OSM data plus material catalogues; never from scraped proprietary scans.',
  },
  {
    id: 'channel-impulse-response',
    name: 'Channel impulse response generation',
    oneLine:
      'For any (transmitter, receiver) pair in the scene, the twin yields a per-tap CIR. Feeds every downstream radio model.',
    detail:
      'CIRs are synthesised by tracing rays per subcarrier, then summing complex-amplitude contributions. Output is a (tx, rx, time, frequency) tensor consumable by physical-layer simulators or ML training pipelines.',
  },
  {
    id: 'ru-du-cu-emulation',
    name: 'End-to-end RU / DU / CU emulation',
    oneLine:
      'Radio Unit + Distributed Unit + Centralised Unit run as software stacks against the twin\u2019s CIRs. Test the whole RAN before touching real spectrum.',
    detail:
      'Open RAN splits the base station into RU (radio), DU (real-time PHY/MAC), and CU (RRC/PDCP). Wiring software RAN stacks to the twin\u2019s CIR feed produces a closed software-only test bed with full interface compliance.',
  },
  {
    id: 'ric-closed-loop',
    name: 'RIC closed-loop integration',
    oneLine:
      'xApps and rApps see the twin via E2/A1/O1 the same way they see real RAN. Train the controller in twin, ship the policy to production.',
    detail:
      'The RAN Intelligent Controller (Near-RT and Non-RT) consumes E2 telemetry and emits policy. Pointing the RIC at the twin lets ML xApps train safely; once approved through Mirror Eval and dual-key sign-off, the same xApp is promoted against the real network.',
  },
  {
    id: 'ai-ran-inference',
    name: 'AI-RAN inference path',
    oneLine:
      'CUDA-accelerated PHY layer where ML models replace classical signal-processing blocks. The twin produces training data; the runtime serves inference.',
    detail:
      'Beam management, channel decoding, and link adaptation are handled by neural networks trained on site-specific labelled data produced by the twin. The inference path runs behind the connector firewall in a hardened capability compartment.',
  },
];

// ---------------------------------------------------------------------------
// 2. ENGINE MODULES — our six capability implementations.
// ---------------------------------------------------------------------------

export type EngineModuleId =
  | 'ray-propagation-engine'
  | 'cir-synthesis-engine'
  | 'ran-stack-emulator'
  | 'ran-software-core'
  | 'ric-integration-layer'
  | 'signal-validation-engine';

export interface EngineModule {
  id: EngineModuleId;
  name: string;
  oneLine: string;
  capability: string;
  primitive: PrimitiveId;
}

export const ENGINE_MODULES: readonly EngineModule[] = [
  {
    id: 'ray-propagation-engine',
    name: 'Ray Propagation Engine',
    oneLine:
      'Differentiable ray tracer that turns a 3D scene into trainable channel data with full gradient flow.',
    capability:
      'Handles all path types — line-of-sight, reflected, diffracted (UTD), and scattered — against per-surface material catalogues. GPU-accelerated, scene-hash anchored, and sandboxed inside a TENAX capability compartment with no egress to RF hardware.',
    primitive: 'differentiable-ray-tracing',
  },
  {
    id: 'cir-synthesis-engine',
    name: 'CIR Synthesis Engine',
    oneLine:
      'GPU-accelerated, fully differentiable PHY-layer simulator that converts ray paths into per-tap channel impulse responses.',
    capability:
      'Implements differentiable LDPC decoders, channel estimators, and MIMO detectors. All outputs are hash-anchored against the scene and ruleset version. The radio-eval harness runs directly against this engine.',
    primitive: 'channel-impulse-response',
  },
  {
    id: 'ran-stack-emulator',
    name: 'RAN Stack Emulator',
    oneLine:
      'Open 5G NR gNB stack (RU/DU/CU) wired to the twin\u2019s CIR feed. The default software RAN test bed.',
    capability:
      'FAPI-style functional split between PHY and MAC. Numerology and slot-based scheduling driven entirely by twin-derived channel data. Pinned to a tagged release through the Hephaestus provenance gate; all patches vendored.',
    primitive: 'ru-du-cu-emulation',
  },
  {
    id: 'ran-software-core',
    name: 'RAN Software Core',
    oneLine:
      'Production-grade 5G RAN alternative for customers operating under a network-service boundary.',
    capability:
      'Disciplined real-time PHY/MAC design; selectable as a per-tenant DU/CU backend. Runs strictly behind a network-service boundary and is never linked into closed-source binaries. AGPL compliance enforced by the connector firewall.',
    primitive: 'ru-du-cu-emulation',
  },
  {
    id: 'ric-integration-layer',
    name: 'RIC Integration Layer',
    oneLine:
      'xApp and rApp registration, E2/A1/O1 interface emulation, and gated promotion path from twin to production RIC.',
    capability:
      'The xApp and rApp registration model is mirrored in the A11oy capability registry. Every twin-trained xApp carries a Cerberus-anchored manifest and passes a Mirror Eval gate before promotion. No xApp can quietly land in production.',
    primitive: 'ric-closed-loop',
  },
  {
    id: 'signal-validation-engine',
    name: 'Signal Validation Engine',
    oneLine:
      'SDR-backed flowgraph pipeline that validates twin CIR output against real-world signals on owned hardware.',
    capability:
      'Lab-only validation running behind a service boundary. Captures are owner-licensed and never enter production. Used to bound engine prediction error against ground truth, ensuring the twin\u2019s CIR fidelity meets the Mirror Eval threshold before any deployment.',
    primitive: 'ai-ran-inference',
  },
];

// ---------------------------------------------------------------------------
// 3. VERTICAL BINDINGS — which SZL products harness the twin and how.
// ---------------------------------------------------------------------------

export type VerticalId = 'vessels' | 'terra' | 'sentra';

export interface VerticalBinding {
  id: VerticalId;
  vertical: string;
  context: string;
  useCases: readonly string[];
  twinOutput: string;
  guardrail: string;
}

export const VERTICAL_BINDINGS: readonly VerticalBinding[] = [
  {
    id: 'vessels',
    vertical: 'Vessels \u2014 Maritime Intelligence',
    context:
      'Vessels carries port asset registries, AIS feeds, and weather/sea-state context. The site-specific RF twin layered on top makes coastal connectivity a first-class operations surface, with coverage attestations bound to the Vessels asset registry.',
    useCases: [
      'Port 5G coverage planning across berths, cranes, and approach lanes.',
      'Vessel-to-shore link budget under sea state, rain, and ducting conditions.',
      'Defensive RF anomaly modelling: GPS spoofing and AIS jamming scenarios run in twin only.',
      'Shore-station beam-forming optimisation against scheduled vessel arrivals.',
    ],
    twinOutput:
      'Per-berth coverage heatmap, per-route link-budget timeline, per-anomaly playback record bound to the Vessels asset registry.',
    guardrail:
      'Twin reads cadastral / hydrographic data only. No live transmission, no vessel-side captures. RF anomaly playback is sandboxed and approval-gated.',
  },
  {
    id: 'terra',
    vertical: 'Terra \u2014 Real Estate Intelligence',
    context:
      'Terra holds the building, parcel, and material context for every property in scope. The site-specific RF twin delivers defensible coverage attestations per asset, surfaced directly in the Terra floor and workspace views.',
    useCases: [
      'In-building 5G / WiFi coverage prediction before installation.',
      'mmWave shadowing analysis for class-A office and data-centre tenants.',
      'IoT placement optimisation (BLE, LoRaWAN, Zigbee) against the building mesh.',
      'Pre-leasing connectivity attestation as a signed marketing artefact.',
    ],
    twinOutput:
      'Per-floor coverage map, per-tenant connectivity score with confidence interval, attestation PDF bound to the Terra parcel ID and the scene hash.',
    guardrail:
      'Scene meshes derived from public cadastral data plus owner-provided floor plans. Owner-provided geometry is never re-shared across tenants.',
  },
  {
    id: 'sentra',
    vertical: 'TENAX \u2014 Cyber Resilience Command (ex-Sentra \u2014 organ retired 2026-07)',
    context:
      'TENAX operates the EDR mesh, SIEM connectors, and Approval Queue. The site-specific RF twin lets TENAX reason about the RF surface as a first-class asset class, with findings flowing directly into the existing evidence vault.',
    useCases: [
      'Rogue base station detection: compare twin-predicted signal envelope to real-world spectrum captures.',
      'IMSI catcher fingerprinting in a known scene context.',
      'Defensive jamming-resilience scoring per critical site.',
      'RF threat-emulation library run inside the twin for tabletop exercises.',
    ],
    twinOutput:
      'RF risk score per site, anomaly playback timeline, twin-vs-reality delta report committed to the Cerberus evidence vault.',
    guardrail:
      'Twin never emits. Spectrum captures are licensed or owner-owned only. All RF threat scenarios are sandboxed in twin and operator-approved before any action.',
  },
];

// ---------------------------------------------------------------------------
// 4. INNOVATION SEEDS — differentiated capabilities built on the twin core.
// ---------------------------------------------------------------------------

export type SeedStatus = 'active' | 'integrated' | 'adoptable' | 'piloted';

export interface InnovationSeed {
  id: string;
  name: string;
  oneLine: string;
  novelty: string;
  status: SeedStatus;
  module: string;
}

export const INNOVATION_SEEDS: readonly InnovationSeed[] = [
  {
    id: 'federated-rf-ledger',
    name: 'Federated RF episode ledger',
    oneLine:
      'Tenants opt in to share aggregated channel statistics, never raw captures. Contributions earn Defender Credits.',
    novelty:
      'The federated layer pools CIR distributions across consenting customers without ever moving raw spectrum or scene geometry off-tenant. No other platform-level twin operates across multi-tenant RF data under this privacy model.',
    status: 'integrated',
    module: 'A11oy Federation + Defender Credits',
  },
  {
    id: 'evidence-bound-xapp-registry',
    name: 'Evidence-bound xApp registry',
    oneLine:
      'Every RIC xApp is registered with a hash-linked manifest, training-data lineage, and a Mirror Eval pass before promotion.',
    novelty:
      'We pair the xApp registration mechanic with a Cerberus-anchored manifest and a gated promotion path. A twin-trained xApp cannot quietly land in production — every promotion is auditable and operator-approved.',
    status: 'adoptable',
    module: 'A11oy Capability Registry + Cerberus + Mirror Eval',
  },
  {
    id: 'planner-over-ran-graph',
    name: 'A11oy planner over the RAN policy graph',
    oneLine:
      'Natural-language ops directives decompose into typed RIC actions. Same Mythos Layer pattern as the patch loop.',
    novelty:
      'The A11oy planner discipline — typed plans, Constitution admission, dual-key approval — is applied to RAN automation, a domain where most tooling today operates without structured governance.',
    status: 'integrated',
    module: 'A11oy Planner + TENAX Policy Engine',
  },
  {
    id: 'defensive-rf-redteam',
    name: 'Defensive RF red-team in twin',
    oneLine:
      'Jamming, spoofing, and rogue-cell scenarios run in the twin only. Outcomes feed the TENAX Risk Engine.',
    novelty:
      'The frontier red-teaming model from the Mythos Layer is applied to the RF surface. No live spectrum is ever touched; all adversarial scenarios are sandboxed and approval-gated before outcomes are promoted to the TENAX risk surface.',
    status: 'active',
    module: 'TENAX Sandbox + Adversarial Resilience',
  },
  {
    id: 'coverage-attestation',
    name: 'Site-specific coverage attestation',
    oneLine:
      'Combine Terra / Vessels asset registry + twin output + TENAX risk engine into a signed coverage report.',
    novelty:
      'A cross-product surface that turns a transient simulation result into a durable, signed artefact bound to a parcel or vessel ID. The attestation is externally verifiable through the Cerberus evidence chain.',
    status: 'adoptable',
    module: 'Terra + Vessels + Cerberus Evidence Vault',
  },
];

// ---------------------------------------------------------------------------
// 5. SHIPPED MILESTONES — all 9 delivered and operational.
// ---------------------------------------------------------------------------

export interface RoadmapMilestone {
  id: string;
  title: string;
  detail: string;
  module: string;
}

export const ROADMAP: readonly RoadmapMilestone[] = [
  {
    id: 'milestone-doctrine',
    title: 'Aerial Twin doctrine surface live in A11oy',
    detail:
      'Typed primitives, engine module catalogue, vertical bindings, innovation seeds, and the guardrail stack published and Constitution-bound. The canonical reference for all downstream twin work.',
    module: 'A11oy Doctrine Surface',
  },
  {
    id: 'milestone-sionna-eval',
    title: 'Ray propagation evaluation harness',
    detail:
      'Sandboxed twin engine operational against a reference scene catalogue entry. CIRs are hash-anchored and reproducible across runs; Mirror Eval gate is live.',
    module: 'A11oy Mirror Eval + TENAX Sandbox',
  },
  {
    id: 'milestone-vessels-port',
    title: 'Vessels port-coverage surface',
    detail:
      'Reference port coverage heatmaps and vessel-to-shore link-budget timelines rendered in the Vessels surface, signed and bound to the asset registry.',
    module: 'Vessels + Aerial Twin Engine',
  },
  {
    id: 'milestone-terra-building',
    title: 'Terra in-building twin',
    detail:
      'Single-floor mmWave and sub-6 coverage twin operational for a reference asset. Owner-provided geometry intake is live; signed pre-leasing attestations are being issued.',
    module: 'Terra + Aerial Twin Engine + Cerberus',
  },
  {
    id: 'milestone-sentra-anomaly',
    title: 'TENAX RF anomaly classifier',
    detail:
      'Anomaly classifier trained on twin-vs-reality deltas, promoted through Mirror Eval, and integrated with the Approval Queue. Findings flow into the evidence vault.',
    module: 'TENAX Risk Engine + Silver RL Planner',
  },
  {
    id: 'milestone-federated-ledger',
    title: 'Federated RF episode ledger v1',
    detail:
      'Aggregated CIR statistics pooled across consenting tenants. Raw geometry and captures remain on-tenant. Contributions generate Defender Credits.',
    module: 'A11oy Federation + Defender Credits',
  },
  {
    id: 'milestone-ric-binding',
    title: 'RIC integration layer operational',
    detail:
      'Twin and real RAN expose the same E2/A1/O1 interface to A11oy-managed xApps. Promotion path — twin \u2192 staging \u2192 prod with dual-key approval — is live.',
    module: 'A11oy Capability Registry + RIC Integration Layer',
  },
  {
    id: 'milestone-ai-ran',
    title: 'AI-RAN inference path',
    detail:
      'Twin-trained ML blocks (beam prediction, channel estimation) are served via a CUDA-accelerated runtime behind the connector firewall and active in production.',
    module: 'A11oy Model Router + TENAX Connector Firewall',
  },
  {
    id: 'milestone-attestation-soc2',
    title: 'Coverage attestation as SOC2 artefact',
    detail:
      'Signed coverage attestations are cross-referenced into the SOC2 Type II control surface as evidence of connectivity controls.',
    module: 'TENAX Compliance Engine + Cerberus',
  },
];

// ---------------------------------------------------------------------------
// 6. GUARDRAILS — defensive rails specific to the RF / twin surface.
// ---------------------------------------------------------------------------

export interface Guardrail {
  layer: string;
  control: string;
  enforcedBy: string;
}

export const GUARDRAILS: readonly Guardrail[] = [
  {
    layer: 'Inputs',
    control: 'Public cadastral / lidar / OSM data plus owner-provided geometry only. No scraped proprietary scenes.',
    enforcedBy: 'A11oy ingestion gate + Hephaestus provenance attestation per scene.',
  },
  {
    layer: 'Emission',
    control: 'The twin reads. The twin never transmits. No active probing of real spectrum from any twin path.',
    enforcedBy: 'TENAX connector firewall + capability compartment that strips egress to RF hardware.',
  },
  {
    layer: 'Tenant scope',
    control: 'Owner-provided geometry and tenant-specific captures stay on-tenant. Federated layer pools statistics only.',
    enforcedBy: 'A11oy federation contract + Cerberus per-tenant evidence partition.',
  },
  {
    layer: 'Closed-loop approval',
    control: 'Any RIC xApp promotion against real spectrum requires dual-key approval and a 24h staging soak.',
    enforcedBy: 'TENAX Approval Queue + Constitution rule engine.',
  },
  {
    layer: 'Provenance',
    control: 'Scene hash, ruleset version, tool versions, and operator identity captured per twin episode.',
    enforcedBy: 'Hephaestus provenance gate + Cerberus append-only ledger.',
  },
];
