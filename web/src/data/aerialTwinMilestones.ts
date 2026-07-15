// AERIAL TWIN — operational milestone packs.
//
// Each pack is one of the 9 milestones in the Aerial Twin doctrine roadmap,
// rendered as its own visitable surface under /a11oy/aerial-twin/<slug>.
// The first milestone (the doctrine page itself) is the parent surface; the
// remaining 8 are defined here.
//
// Each pack documents what shipped today: the operational capability that
// each engine module exposes, the deliverables that depend on it, and the
// guardrails that keep it in scope.

export type MilestoneSlug =
  | 'sionna-eval'
  | 'vessels-port'
  | 'terra-building'
  | 'sentra-anomaly'
  | 'federated-ledger'
  | 'ric-binding'
  | 'ai-ran'
  | 'attestation-soc2';

export type MilestonePhase = '0\u20136' | '7\u201312' | '13\u201324';

export interface MilestoneKpi {
  label: string;
  value: string | number;
  sub: string;
}

export interface Deliverable {
  id: string;
  name: string;
  oneLine: string;
  detail: string;
  module: string;
}

export interface EngineCapability {
  module: string;
  capability: string;
  detail: string;
}

export interface MilestoneGuardrail {
  layer: string;
  control: string;
  enforcedBy: string;
}

export interface MilestonePack {
  slug: MilestoneSlug;
  number: number;
  phase: MilestonePhase;
  title: string;
  tagline: string;
  doctrine: string;
  kpis: readonly MilestoneKpi[];
  deliverables: readonly Deliverable[];
  oss: readonly EngineCapability[];
  guardrails: readonly MilestoneGuardrail[];
  related: readonly MilestoneSlug[];
}

// ---------------------------------------------------------------------------
// 2 \u2014 Sionna RT evaluation harness
// ---------------------------------------------------------------------------

const M2_SIONNA_EVAL: MilestonePack = {
  slug: 'sionna-eval',
  number: 2,
  phase: '0\u20136',
  title: 'Sionna RT evaluation harness',
  tagline: 'A sandboxed twin engine wrapping public Sionna RT against a single reference scene. Reproducible CIRs, gated by Mirror Eval.',
  doctrine:
    'Stand up the smallest credible twin engine. One public scene catalogue entry, one ray tracer (Sionna RT, Apache-2.0), one set of materials (ITU-R P.2040). Output channel impulse responses are hash-anchored and reproducible across runs. Every simulation is a Mirror Eval episode with a baseline comparison gate.',
  kpis: [
    { label: 'TWIN ENGINE', value: '1', sub: 'Sionna RT 1.x in compartment' },
    { label: 'REFERENCE SCENE', value: '1', sub: 'public catalogue (Munich)' },
    { label: 'CIR REPRODUCIBILITY', value: 'hash', sub: 'scene + ruleset + seed' },
    { label: 'PROMOTION GATE', value: 'Mirror Eval', sub: 'baseline-delta bounded' },
  ],
  deliverables: [
    {
      id: 'twin-engine',
      name: 'Sandboxed twin engine',
      oneLine: 'Sionna RT runs inside a TENAX capability compartment with no egress to RF hardware.',
      detail: 'Capability compartment strips the egress namespace down to a read-only scene store and a write-only CIR sink. Engine version, ruleset version, and scene hash are captured per call.',
      module: 'TENAX Sandbox + A11oy Capability Registry',
    },
    {
      id: 'reference-scene',
      name: 'Reference scene catalogue',
      oneLine: 'A single public scene (Munich from the open Sionna catalogue) for the v1 engine.',
      detail: 'Triangle mesh + per-surface ITU-R P.2040 materials. Scene hash committed to Cerberus per release. No owner-supplied geometry yet \u2014 that lands in milestone 4 (Terra in-building).',
      module: 'A11oy Scene Store + Hephaestus Provenance',
    },
    {
      id: 'cir-snapshots',
      name: 'Reproducible CIR snapshots',
      oneLine: 'Per (tx, rx, frequency, seed) tuple the engine writes a hash-anchored impulse-response tensor.',
      detail: 'Outputs sit in the per-tenant evidence partition. Re-running the same tuple yields a byte-identical tensor; any drift triggers a Mirror Eval failure.',
      module: 'Cerberus Evidence Vault',
    },
    {
      id: 'mirror-eval-gate',
      name: 'Mirror Eval CIR gate',
      oneLine: 'Every CIR batch is compared against a frozen baseline. Excess delta blocks downstream promotion.',
      detail: 'Default metric is per-tap complex-amplitude L2 distance, with thresholds per scene. Failures are routed to the TENAX Approval Queue.',
      module: 'A11oy Mirror Eval + TENAX Approval Queue',
    },
    {
      id: 'planner-action',
      name: 'A11oy planner action',
      oneLine: 'Planner can invoke aerial.twin.simulate with a typed payload and receive a signed evidence handle back.',
      detail: 'Action signature, parameter schema, and output schema are registered in the A11oy capability registry. Constitution admission is required before promotion.',
      module: 'A11oy Planner + Capability Registry',
    },
  ],
  oss: [
    {
      module: 'Aerial Twin Engine',
      capability: 'Differentiable ray tracer with UTD diffraction and ITU-R P.2040 materials.',
      detail: 'Wrapped behind the A11oy capability registry. Scene + ruleset + seed are hashed and committed to Cerberus per call. Engine release is pinned through Hephaestus provenance; no in-tree forks.',
    },
    {
      module: 'A11oy PHY Adapter',
      capability: 'OFDM resource grid + CIR ingest matched to the engine\u2019s tensor layout.',
      detail: 'Downstream PHY blocks consume CIR tensors directly. The harness ships no learned PHY weights at v1 \u2014 only the typed I/O contract.',
    },
    {
      module: 'Lab Validation Pipeline',
      capability: 'Owner-licensed SDR captures decoded with a known flowgraph for ground-truth comparison.',
      detail: 'Runs lab-side behind a service boundary. Used to bound engine error against measured signal; never drives production output.',
    },
  ],
  guardrails: [
    { layer: 'Sandbox', control: 'Engine has no egress to RF hardware. Outputs are write-only to the evidence vault.', enforcedBy: 'TENAX capability compartment + connector firewall.' },
    { layer: 'Reproducibility', control: 'Scene hash, ruleset hash, seed, and engine version are required for every call.', enforcedBy: 'A11oy capability registry pre-call validator.' },
    { layer: 'Promotion', control: 'No CIR batch is consumed downstream until the Mirror Eval gate passes.', enforcedBy: 'Mirror Eval policy attached to aerial.twin.simulate.' },
  ],
  related: ['vessels-port', 'terra-building'],
};

// ---------------------------------------------------------------------------
// 3 \u2014 Vessels port-coverage demo
// ---------------------------------------------------------------------------

const M3_VESSELS_PORT: MilestonePack = {
  slug: 'vessels-port',
  number: 3,
  phase: '0\u20136',
  title: 'Vessels port-coverage demo',
  tagline: 'One reference port. Per-berth coverage maps and vessel-to-shore link budgets, signed and bound to the Vessels asset registry.',
  doctrine:
    'The first vertical the twin serves. A single reference port (public OSM mesh), two bands (mid-band and mmWave), and four sea-state regimes. Output is a per-berth heatmap + per-route link-budget timeline + a signed coverage attestation per berth, bound to the Vessels asset ID.',
  kpis: [
    { label: 'REFERENCE PORT', value: '1', sub: 'public OSM mesh' },
    { label: 'BANDS', value: '2', sub: '3.5 GHz mid + 28 GHz mmWave' },
    { label: 'SEA-STATE REGIMES', value: '4', sub: 'calm \u2192 rough' },
    { label: 'ATTESTATION SIG', value: 'Cerberus', sub: 'bound to asset ID' },
  ],
  deliverables: [
    {
      id: 'port-mesh',
      name: 'Reference port mesh',
      oneLine: 'Triangle mesh of a single port assembled from public cadastral and OSM Buildings data.',
      detail: 'Per-surface materials drawn from the ITU-R P.2040 catalogue. Mesh is checked into the scene store with a hash and version. No proprietary terminal scans, no scraped vendor BIM.',
      module: 'Aerial Twin Scene Store + Hephaestus',
    },
    {
      id: 'coverage-heatmap',
      name: 'Per-berth coverage heatmap',
      oneLine: 'Received-power map across each berth, computed for both the mid-band and mmWave band.',
      detail: 'Coverage map is a regular grid at 1 m spacing per berth. Output rendered in the Vessels surface as a layered overlay on the existing port plan.',
      module: 'Vessels + Aerial Twin Engine',
    },
    {
      id: 'link-budget',
      name: 'Vessel-to-shore link budget timeline',
      oneLine: 'For each scheduled arrival, a timeline of expected link budget under the prevailing sea state and weather.',
      detail: 'Pulls vessel ETA from the Vessels schedule, sea state from the existing weather feed, and CIR distributions from the twin. Output is a per-arrival risk score on the Vessels operations board.',
      module: 'Vessels Schedule + Aerial Twin Engine',
    },
    {
      id: 'attestation',
      name: 'Signed coverage attestation',
      oneLine: 'Per-berth attestation PDF: signed, hash-bound to the asset ID and the scene version.',
      detail: 'Generated by the existing investor-doc PDF renderer pattern. Stored in Cerberus with a signature chain back to the engine + scene + ruleset.',
      module: 'Vessels + Cerberus + PDF renderer',
    },
    {
      id: 'asset-binding',
      name: 'Vessels asset-registry binding',
      oneLine: 'Every twin output is keyed to a Vessels asset ID (berth, crane, mooring point).',
      detail: 'No floating outputs. If the asset is retired in Vessels, the attestation moves to historical evidence and is excluded from active operations.',
      module: 'Vessels Asset Registry + Cerberus',
    },
  ],
  oss: [
    {
      module: 'Aerial Twin Engine \u2014 Coverage Map',
      capability: 'Per-cell received-power computation across a regular receiver grid with antenna-pattern application per transmitter.',
      detail: 'Maps render directly into the Vessels surface as the canonical output. Each map is hash-bound to the scene and ruleset versions; no notebook artefacts.',
    },
    {
      module: 'A11oy gNB Twin',
      capability: 'Software gNB driven by the twin\u2019s CIR feed, with FAPI-style PHY/MAC split and slot-based scheduling.',
      detail: 'Acts as the radio counterpart to the Vessels schedule. Pinned tag, vendored patches via Hephaestus, no live emission.',
    },
    {
      module: 'Sea-State Link Budget',
      capability: 'BLER curves derived from twin CIRs under each of the four sea-state regimes.',
      detail: 'Each timeline tap carries its scene + sea-state context. Surfaces on the Vessels operations board as a per-arrival risk score.',
    },
  ],
  guardrails: [
    { layer: 'Inputs', control: 'Public OSM and cadastral data only. Owner-provided port plans flow through the gated ingestion in milestone 4.', enforcedBy: 'A11oy ingestion gate.' },
    { layer: 'Emission', control: 'Twin reads, never transmits. Vessels asset registry is read-only from the twin\u2019s side.', enforcedBy: 'TENAX connector firewall.' },
    { layer: 'Asset binding', control: 'No twin output is published without a live Vessels asset ID.', enforcedBy: 'Cerberus emit gate.' },
  ],
  related: ['sionna-eval', 'sentra-anomaly', 'attestation-soc2'],
};

// ---------------------------------------------------------------------------
// 4 \u2014 Terra in-building twin
// ---------------------------------------------------------------------------

const M4_TERRA_BUILDING: MilestonePack = {
  slug: 'terra-building',
  number: 4,
  phase: '7\u201312',
  title: 'Terra in-building twin',
  tagline: 'Single-floor mmWave + sub-6 coverage twin for one reference asset, with owner-provided geometry intake and a signed pre-leasing attestation.',
  doctrine:
    'The first vertical that consumes owner-provided geometry. A single class-A office floor, mmWave + sub-6 coverage per square meter, mmWave shadowing analysis per workspace, and a signed pre-leasing attestation. Owner geometry never re-shared across tenants.',
  kpis: [
    { label: 'REFERENCE FLOOR', value: '4500 m\u00b2', sub: 'class-A office, single floor' },
    { label: 'BANDS', value: '2', sub: 'sub-6 + 28 GHz mmWave' },
    { label: 'GRID RESOLUTION', value: '0.5 m', sub: 'coverage per square' },
    { label: 'ATTESTATION', value: 'PDF', sub: 'pre-leasing artefact' },
  ],
  deliverables: [
    {
      id: 'floor-mesh',
      name: 'Reference floor mesh',
      oneLine: 'A single class-A office floor expressed as an OpenUSD scene with per-surface materials.',
      detail: 'Mesh derived from owner-provided floor plan plus the public ITU-R P.2040 material catalogue. Per-tenant: never shared across customers.',
      module: 'Terra Asset Registry + Aerial Twin Scene Store',
    },
    {
      id: 'coverage-grid',
      name: 'Coverage grid per square meter',
      oneLine: 'Sub-6 and mmWave received-power maps at 0.5 m grid spacing across the floor.',
      detail: 'Output overlays directly onto the Terra floor view. Per-cell coverage value is bound to the scene + ruleset hash for reproducibility.',
      module: 'Terra + Aerial Twin Engine',
    },
    {
      id: 'shadowing',
      name: 'mmWave shadowing analysis',
      oneLine: 'Per-workspace shadowing profile that flags blockage hotspots before installation.',
      detail: 'Computed from the diffraction + reflection path types in the twin. Surfaces in the Terra workspace planner as a coverage risk per seat.',
      module: 'Terra Workspace Planner',
    },
    {
      id: 'attestation-pdf',
      name: 'Pre-leasing attestation PDF',
      oneLine: 'A signed, brand-styled PDF the owner can attach to a lease packet.',
      detail: 'Built on the existing investor-doc PDF renderer pattern. Cover page + per-band coverage map + workspace shadowing + scene hash + signature chain.',
      module: 'Terra + Cerberus + PDF renderer',
    },
    {
      id: 'geometry-intake',
      name: 'Owner-provided geometry intake',
      oneLine: 'Sandboxed ingestion path for owner-supplied floor plans (DWG / IFC / GLB).',
      detail: 'Conversion runs in a TENAX capability compartment with no egress. Output is committed to the per-tenant scene partition only.',
      module: 'TENAX Sandbox + A11oy Ingestion Gate',
    },
  ],
  oss: [
    {
      module: 'Aerial Twin Engine \u2014 Indoor Path Tracer',
      capability: 'Indoor path tracing with UTD diffraction and scattering for mmWave shadowing modelling.',
      detail: 'Output renders natively into the Terra floor view. Per-tenant scene partition prevents cross-customer leakage.',
    },
    {
      module: 'A11oy DAS Topology Generator',
      capability: 'Distributed antenna system topology generated from the floor mesh with indoor gNB simulation.',
      detail: 'Owner can A/B alternate antenna placements before installation. Topology is data-driven from the scene rather than hand-configured.',
    },
    {
      module: 'A11oy Real-time PHY Backend (optional)',
      capability: 'Disciplined real-time PHY/MAC backend, selectable per tenant where service-boundary licensing is acceptable.',
      detail: 'Lives strictly behind a network service boundary. Never linked into closed-source binaries; off by default.',
    },
  ],
  guardrails: [
    { layer: 'Tenant scope', control: 'Owner-provided geometry stays on-tenant. Federated layer pools statistics only (milestone 6).', enforcedBy: 'Cerberus per-tenant partition.' },
    { layer: 'Ingestion', control: 'All owner geometry conversion runs in a sandboxed compartment with no network egress.', enforcedBy: 'TENAX capability compartment.' },
    { layer: 'Provenance', control: 'Every PDF carries a signature chain back to the scene + ruleset + engine version.', enforcedBy: 'Hephaestus provenance gate + Cerberus.' },
  ],
  related: ['vessels-port', 'attestation-soc2'],
};

// ---------------------------------------------------------------------------
// 5 \u2014 TENAX RF anomaly classifier
// ---------------------------------------------------------------------------

const M5_SENTRA_ANOMALY: MilestonePack = {
  slug: 'sentra-anomaly',
  number: 5,
  phase: '7\u201312',
  title: 'TENAX RF anomaly classifier',
  tagline: 'A twin-vs-reality delta classifier (rogue cell, jammer, IMSI catcher). Promoted via Mirror Eval. Findings flow into the TENAX Approval Queue.',
  doctrine:
    'Use the twin as the predicted baseline. Compare against owner-licensed spectrum captures. Anything the twin says cannot exist becomes a finding for TENAX to triage. Three classes at v1: rogue base station, broadband jamming, IMSI catcher.',
  kpis: [
    { label: 'CLASSES', value: '3', sub: 'rogue cell · jammer · IMSI catcher' },
    { label: 'DELTA METRIC', value: 'CIR L2', sub: 'per-tap distance' },
    { label: 'PROMOTION GATE', value: 'Mirror Eval', sub: 'bounded false-positive rate' },
    { label: 'EVIDENCE PATH', value: 'Cerberus', sub: 'append-only ledger' },
  ],
  deliverables: [
    {
      id: 'delta-engine',
      name: 'Twin-vs-reality delta engine',
      oneLine: 'Computes a per-tap complex-amplitude L2 distance between predicted CIR and observed CIR.',
      detail: 'Observed CIRs come from owner-licensed spectrum captures only. Engine outputs a per-(time, location, frequency) delta tensor.',
      module: 'A11oy Mirror Eval + Aerial Twin Engine',
    },
    {
      id: 'classifier',
      name: 'Three-class anomaly classifier',
      oneLine: 'Rogue cell, broadband jamming, and IMSI catcher classes at v1.',
      detail: 'Trained on synthetic adversarial CIRs generated in twin only. Classifier head is small and explainable; per-class scores are surfaced in the TENAX finding card.',
      module: 'TENAX Risk Engine + Silver RL Planner',
    },
    {
      id: 'promotion-gate',
      name: 'Mirror Eval promotion gate',
      oneLine: 'Classifier cannot ship to production without passing a frozen-eval false-positive bound.',
      detail: 'Default v1 bound: false-positive rate < 1% on a frozen evaluation set of legitimate captures from each tenant.',
      module: 'A11oy Mirror Eval',
    },
    {
      id: 'approval-queue',
      name: 'Approval Queue integration',
      oneLine: 'Every finding lands in the TENAX Approval Queue with the twin baseline and the captured signal as evidence.',
      detail: 'Operator can accept, dismiss with reason, or escalate. All actions are written to the Cerberus ledger.',
      module: 'TENAX Approval Queue + Cerberus',
    },
    {
      id: 'evidence-binding',
      name: 'Cerberus evidence binding',
      oneLine: 'Every finding carries the scene hash, ruleset, classifier version, capture-source attestation, and operator decision.',
      detail: 'Evidence chain is append-only and externally attestable. Required for any cross-vertical promotion of the finding.',
      module: 'Cerberus Evidence Vault',
    },
  ],
  oss: [
    {
      module: 'A11oy Differentiable Delta Path',
      capability: 'End-to-end differentiable PHY blocks for the twin-vs-reality delta computation.',
      detail: 'Lets the classifier head train jointly against twin and observed CIRs. No learned PHY weights ship in the runtime; only the typed graph.',
    },
    {
      module: 'Lab Capture Pipeline',
      capability: 'Owner-licensed SDR capture \u2192 flowgraph \u2192 framed CIR estimate, handed to Mirror Eval as a typed batch.',
      detail: 'Runs lab-side behind a service boundary. Capture provenance is attested by Hephaestus before any batch enters Mirror Eval.',
    },
    {
      module: 'A11oy xApp Candidate Registration',
      capability: 'Classifier is packaged as a twin-trained xApp candidate with manifest, lifecycle hooks, and policy slots.',
      detail: 'At this milestone the classifier stops at a TENAX finding. Promotion to a real RIC is the milestone-7 deliverable.',
    },
  ],
  guardrails: [
    { layer: 'Captures', control: 'Real-world captures must be owner-licensed or owner-owned. No third-party spectrum scraping.', enforcedBy: 'A11oy ingestion gate + Hephaestus capture attestation.' },
    { layer: 'Sandbox', control: 'All adversarial training runs in twin only. No live emission from any classifier path.', enforcedBy: 'TENAX capability compartment.' },
    { layer: 'Decision', control: 'Findings are advisory until a human operator approves. No autonomous take-down.', enforcedBy: 'TENAX Approval Queue + Constitution rule.' },
  ],
  related: ['sionna-eval', 'ric-binding', 'attestation-soc2'],
};

// ---------------------------------------------------------------------------
// 6 \u2014 Federated RF episode ledger v1
// ---------------------------------------------------------------------------

const M6_FEDERATED_LEDGER: MilestonePack = {
  slug: 'federated-ledger',
  number: 6,
  phase: '7\u201312',
  title: 'Federated RF episode ledger v1',
  tagline: 'Tenants opt in to share aggregated CIR statistics, never raw captures. Contributions earn Defender Credits.',
  doctrine:
    'A federated layer that pools channel statistics across consenting tenants without ever moving raw spectrum, scene geometry, or per-vessel / per-floor identifiers off-tenant. Contribution earns Defender Credits in the existing economy.',
  kpis: [
    { label: 'POOL UNIT', value: 'CIR stats', sub: 'per-band per-environment' },
    { label: 'RAW EGRESS', value: '0 B', sub: 'never leaves tenant' },
    { label: 'CONSENT MODEL', value: 'opt-in', sub: 'lifecycle managed' },
    { label: 'INCENTIVE', value: 'Defender Credits', sub: 'per accepted contribution' },
  ],
  deliverables: [
    {
      id: 'aggregator',
      name: 'Per-tenant CIR statistics aggregator',
      oneLine: 'On-tenant aggregator that emits descriptors (delay-spread distribution, K-factor, pathloss exponents) \u2014 never raw CIRs.',
      detail: 'Runs inside the tenant\u2019s capability compartment. Output schema is fixed and auditable. Differential-privacy noise is added before emission for sensitive descriptors.',
      module: 'A11oy Federation + TENAX Sandbox',
    },
    {
      id: 'pooling-contract',
      name: 'Cross-tenant pooling contract',
      oneLine: 'A typed federation contract specifying which descriptors flow, at what cadence, with what privacy budget.',
      detail: 'Versioned alongside the Constitution. Any change requires Constitution review and dual-key approval.',
      module: 'A11oy Federation Contract + Constitution',
    },
    {
      id: 'defender-credits',
      name: 'Defender Credits accrual',
      oneLine: 'Every accepted contribution earns Defender Credits in the existing economy.',
      detail: 'Credit value scales with novelty (new environment class) and quality (passes the federation Mirror Eval). Spend paths reuse the existing Defender Credits surface.',
      module: 'Defender Credits',
    },
    {
      id: 'consent-lifecycle',
      name: 'Tenant opt-in / opt-out lifecycle',
      oneLine: 'Tenants can join, pause, and withdraw. Withdrawal removes the tenant from future pooling and is reversible.',
      detail: 'Withdrawal does not retroactively unpool past contributions, since those are already aggregated. The audit trail makes this explicit.',
      module: 'A11oy Federation + Tenant Admin',
    },
    {
      id: 'partition',
      name: 'Cerberus per-tenant partition',
      oneLine: 'Raw CIRs and scene geometry are stored only in the tenant\u2019s Cerberus partition.',
      detail: 'Federation pooling reads only the aggregator output, never the raw partition. Partition boundaries are enforced at the storage layer.',
      module: 'Cerberus Evidence Vault',
    },
  ],
  oss: [
    {
      module: 'A11oy Statistical Descriptor Aggregator',
      capability: 'Per-tenant descriptors of channel impulse responses (delay spread, K-factor, doppler) emitted with a fixed, auditable schema.',
      detail: 'Differential-privacy noise applied before emission. Pool consumers see only the joint distribution, never per-tenant samples.',
    },
    {
      module: 'A11oy Federation Contract',
      capability: 'Typed, versioned, signed governance object describing what flows, at what cadence, with what privacy budget.',
      detail: 'Contract version is committed to Cerberus before activation. Any change requires Constitution review and dual-key approval.',
    },
    {
      module: 'A11oy Pooling Trainer',
      capability: 'Pool consumers train locally with the pooled distribution as a prior.',
      detail: 'No gradients are federated and no raw data crosses tenant boundaries; only the smaller, less reversible descriptor distribution is shared.',
    },
  ],
  guardrails: [
    { layer: 'Egress', control: 'No raw CIR, no raw scene, no per-asset identifier ever leaves the tenant.', enforcedBy: 'A11oy federation ingress filter + Cerberus partition.' },
    { layer: 'Privacy', control: 'Differential-privacy noise budget per descriptor family; budget exhaustion blocks further contributions for the period.', enforcedBy: 'Aggregator policy + audit log.' },
    { layer: 'Consent', control: 'Tenant must opt in explicitly. Withdrawal is reversible going forward, never retroactive.', enforcedBy: 'Tenant admin + signed contract version.' },
    { layer: 'Incentive', control: 'Defender Credits are earned only for contributions that pass the federation Mirror Eval gate.', enforcedBy: 'Defender Credits gate.' },
  ],
  related: ['sentra-anomaly', 'ric-binding', 'attestation-soc2'],
};

// ---------------------------------------------------------------------------
// 7 \u2014 O-RAN SC RIC binding
// ---------------------------------------------------------------------------

const M7_RIC_BINDING: MilestonePack = {
  slug: 'ric-binding',
  number: 7,
  phase: '13\u201324',
  title: 'O-RAN SC RIC binding',
  tagline: 'Twin and real RAN expose the same E2 / A1 / O1 interface to A11oy-managed xApps. Promotion is twin \u2192 staging \u2192 prod with dual-key approval.',
  doctrine:
    'Wire the twin to the standard control plane. xApps trained in twin see the same E2 telemetry shape as production. Promotion is a gated lane: twin \u2192 staging \u2192 prod, dual-key approval, with a 24-hour staging soak.',
  kpis: [
    { label: 'INTERFACES', value: '3', sub: 'E2 · A1 · O1' },
    { label: 'PROMOTION LANE', value: '3 stages', sub: 'twin \u2192 staging \u2192 prod' },
    { label: 'APPROVAL', value: 'dual-key', sub: 'platform + vertical owner' },
    { label: 'STAGING SOAK', value: '24h', sub: 'minimum' },
  ],
  deliverables: [
    {
      id: 'e2-termination',
      name: 'E2 termination point',
      oneLine: 'Twin emits E2 telemetry indistinguishable from a production RAN to xApps.',
      detail: 'Built on the O-RAN SC ric-plt termination pattern. Service models supported at v1: KPM (Key Performance Measurement), RC (RAN Control).',
      module: 'A11oy RIC Adapter + Aerial Twin Engine',
    },
    {
      id: 'a1-policy',
      name: 'A1 policy receiver',
      oneLine: 'Non-RT RIC policy can target the twin first, then promote to real RAN.',
      detail: 'A1 policy types are versioned and signed. Constitution review required to register a new policy type.',
      module: 'A11oy A1 Receiver + Constitution',
    },
    {
      id: 'o1-management',
      name: 'O1 management interface',
      oneLine: 'Twin exposes the standard O1 management surface for configuration and FCAPS.',
      detail: 'Read-only at v1: configuration is sourced from the A11oy capability registry rather than O1 NETCONF writes. O1 alarms feed the TENAX finding stream.',
      module: 'A11oy O1 Adapter + TENAX',
    },
    {
      id: 'xapp-registry',
      name: 'Twin-trained xApp registry',
      oneLine: 'Every twin-trained xApp is registered with manifest, training-data lineage, and Mirror Eval result.',
      detail: 'Registry entries are append-only. Re-registration with the same name requires a Constitution review.',
      module: 'A11oy Capability Registry + Cerberus',
    },
    {
      id: 'promotion-lane',
      name: 'Twin \u2192 staging \u2192 prod promotion lane',
      oneLine: 'A typed lane with dual-key approval and a 24h staging soak before any production xApp activation.',
      detail: 'Each transition emits a signed evidence record. A staging failure rolls back automatically; a prod failure pages the on-call and rolls back.',
      module: 'A11oy Promotion Engine + TENAX Approval Queue',
    },
  ],
  oss: [
    {
      module: 'A11oy RIC Adapter',
      capability: 'Near-RT RIC termination: E2 termination, subscription manager, xApp orchestration.',
      detail: 'Subscriptions are managed by the A11oy capability registry so they are typed and approval-gated rather than free-form.',
    },
    {
      module: 'A11oy xApp Template',
      capability: 'xApp lifecycle hooks, RMR messaging, configuration loading, plus a Constitution-bound manifest.',
      detail: 'Every xApp ships with a required Mirror Eval reference and a signed provenance footer before it can register.',
    },
    {
      module: 'A11oy A1 Receiver',
      capability: 'Typed A1 policy objects with lifecycle and conflict resolution.',
      detail: 'Policies must register as typed capabilities. Conflicts defer to the TENAX Approval Queue rather than a silent override.',
    },
    {
      module: 'A11oy Deployment Manager',
      capability: 'Helm-based xApp packaging and lifecycle management.',
      detail: 'Deployments are gated by the A11oy promotion lane. Helm charts are built reproducibly and committed to Cerberus before activation.',
    },
  ],
  guardrails: [
    { layer: 'Promotion', control: 'No xApp lands in production without dual-key approval and a 24h staging soak.', enforcedBy: 'A11oy promotion engine + TENAX Approval Queue.' },
    { layer: 'Configuration', control: 'O1 is read-only at v1; configuration writes flow through the A11oy capability registry instead.', enforcedBy: 'A11oy O1 adapter policy.' },
    { layer: 'Provenance', control: 'Every E2 subscription, A1 policy, and xApp deployment carries a signed provenance footer.', enforcedBy: 'Hephaestus + Cerberus.' },
  ],
  related: ['sentra-anomaly', 'ai-ran'],
};

// ---------------------------------------------------------------------------
// 8 \u2014 AI-RAN inference path
// ---------------------------------------------------------------------------

const M8_AI_RAN: MilestonePack = {
  slug: 'ai-ran',
  number: 8,
  phase: '13\u201324',
  title: 'AI-RAN inference path',
  tagline: 'Twin-trained ML blocks (beam prediction, channel estimation) served via a CUDA-accelerated runtime behind the connector firewall.',
  doctrine:
    'The first ML blocks promoted from twin to inference. Beam prediction and channel estimation at v1, both trained in twin, both compared A/B against the classical baseline. Runtime sits behind the TENAX connector firewall.',
  kpis: [
    { label: 'ML BLOCKS', value: '2', sub: 'beam · channel-est' },
    { label: 'TRAINING SOURCE', value: 'twin only', sub: 'no production data' },
    { label: 'A/B BASELINE', value: 'classical', sub: 'always co-deployed' },
    { label: 'PROVENANCE', value: 'per batch', sub: 'manifest in Cerberus' },
  ],
  deliverables: [
    {
      id: 'beam-predictor',
      name: 'Beam predictor (twin-trained)',
      oneLine: 'Predicts the best beam from sub-6 reference signals, trained against twin-derived ground truth.',
      detail: 'Architecture: small ResNet over reference-signal magnitude, output is a beam-index distribution. Mirror Eval gate enforces a top-k accuracy floor against held-out twin scenes.',
      module: 'A11oy Model Router + Aerial Twin Engine',
    },
    {
      id: 'channel-estimator',
      name: 'Channel estimator (twin-trained)',
      oneLine: 'Replaces the classical least-squares estimator on a per-symbol basis where it beats classical in twin.',
      detail: 'Output is the same complex CIR tensor as the classical block. Co-deployed with classical estimator; A/B selector decides per-frame.',
      module: 'A11oy Model Router',
    },
    {
      id: 'runtime',
      name: 'Inference runtime sandbox',
      oneLine: 'CUDA-accelerated inference in a TENAX capability compartment with pinned model artefacts.',
      detail: 'Compartment has read-only access to the model store and write-only access to the inference-log sink. Model loading is gated by signature verification.',
      module: 'TENAX Sandbox + A11oy Model Router',
    },
    {
      id: 'firewall',
      name: 'Connector-firewall path',
      oneLine: 'All inference traffic flows through TENAX\u2019s connector firewall with per-block egress allowlists.',
      detail: 'Beam predictor and channel estimator have no egress beyond the inference-log sink and the model-router callback.',
      module: 'TENAX Connector Firewall',
    },
    {
      id: 'provenance',
      name: 'Per-batch provenance manifest',
      oneLine: 'Every inference batch carries a manifest: model version, training scene set, ruleset, runtime version.',
      detail: 'Manifest is signed and committed to Cerberus. Required for any cross-vertical promotion of an inference result.',
      module: 'Hephaestus + Cerberus',
    },
  ],
  oss: [
    {
      module: 'A11oy ML PHY Block Contracts',
      capability: 'Tensor-layout contracts for channel estimator, MIMO detector, and OFDM resource grid that match the twin\u2019s output.',
      detail: 'Models trained against twin CIRs are drop-in. Runtime is hardened and sandboxed; no notebook-grade execution.',
    },
    {
      module: 'A11oy Inference Runtime',
      capability: 'CUDA-accelerated PHY runtime with classical baseline + ML block + A/B selector co-deployed in every slot.',
      detail: 'Runtime sits behind the TENAX connector firewall. ML block can be disabled in one switch without taking the slot offline.',
    },
    {
      module: 'A11oy Classical Baseline',
      capability: 'Classical channel estimation and MIMO detection blocks served as the always-on A/B reference.',
      detail: 'Baseline is never disabled. The A/B selector defers to classical on any twin-vs-prod drift detected by Mirror Eval.',
    },
  ],
  guardrails: [
    { layer: 'Training data', control: 'Models are trained on twin-derived data only at v1. No production data ingestion.', enforcedBy: 'A11oy model registry policy.' },
    { layer: 'A/B safety', control: 'Classical baseline is always co-deployed. ML block can be disabled in one switch.', enforcedBy: 'A11oy Model Router.' },
    { layer: 'Egress', control: 'Inference compartment has no network egress beyond the log sink and router callback.', enforcedBy: 'TENAX connector firewall.' },
    { layer: 'Provenance', control: 'Every batch carries a signed manifest covering model + training set + ruleset + runtime.', enforcedBy: 'Hephaestus + Cerberus.' },
  ],
  related: ['ric-binding', 'attestation-soc2'],
};

// ---------------------------------------------------------------------------
// 9 \u2014 Coverage attestation as SOC2 artefact
// ---------------------------------------------------------------------------

const M9_ATTESTATION_SOC2: MilestonePack = {
  slug: 'attestation-soc2',
  number: 9,
  phase: '13\u201324',
  title: 'Coverage attestation as SOC2 artefact',
  tagline: 'Signed coverage attestations cross-referenced into the SOC 2 Type II control surface as evidence of connectivity controls.',
  doctrine:
    'Turn the per-vessel and per-property attestations into recurring SOC 2 evidence. CC6 (logical access) and CC7 (system operations) families benefit. Attestations are versioned, signed, and refreshed on a schedule the auditor can rely on.',
  kpis: [
    { label: 'CONTROL FAMILIES', value: '2', sub: 'CC6 · CC7' },
    { label: 'ATTESTATION SIG', value: 'Cerberus', sub: 'externally verifiable' },
    { label: 'REFRESH', value: 'annual', sub: 'plus on material change' },
    { label: 'AUDIT EXPORT', value: 'JSONL+PDF', sub: 'machine + human' },
  ],
  deliverables: [
    {
      id: 'control-mapping',
      name: 'SOC 2 control mapping',
      oneLine: 'Mapping table that ties each attestation field to a SOC 2 CC6 / CC7 control statement.',
      detail: 'Versioned alongside the Constitution. Audited by the same review path as any policy change. Mapping diff appears in the auditor export.',
      module: 'TENAX Compliance Engine + Constitution',
    },
    {
      id: 'pdf-generator',
      name: 'Per-vertical signed PDF generator',
      oneLine: 'One generator with vertical-specific cover sheets (Vessels berth, Terra parcel).',
      detail: 'Built on the existing investor-doc PDF renderer pattern. Cover sheet, evidence block, signature chain, scene + ruleset hash.',
      module: 'Cerberus + PDF renderer',
    },
    {
      id: 'evidence-binding',
      name: 'Cerberus evidence vault binding',
      oneLine: 'Every attestation is committed to the Cerberus append-only ledger with a stable evidence ID.',
      detail: 'Auditor can dereference any evidence ID to retrieve the signed bundle (PDF + JSON + provenance footer).',
      module: 'Cerberus Evidence Vault',
    },
    {
      id: 'audit-export',
      name: 'Audit trail export',
      oneLine: 'JSONL + PDF export for the auditor: every attestation, every approval, every revocation.',
      detail: 'Export is reproducible from Cerberus and is itself signed. Auditor receives the export plus the signature.',
      module: 'TENAX Compliance Engine',
    },
    {
      id: 'recertification',
      name: 'Annual recertification scheduler',
      oneLine: 'Automated reminders + a forced refresh on material change (scene, ruleset, or vertical scope).',
      detail: 'Recertification job runs on the existing durable-job runner. Failure to recertify within the grace window flags the attestation as expired in Cerberus.',
      module: 'A11oy Durable Jobs + Cerberus',
    },
  ],
  oss: [
    {
      module: 'Cerberus Config-as-Data',
      capability: 'Attestations are typed, versioned, signed configuration objects with a deterministic rollback path.',
      detail: 'Each version is signed and committed before publication. Rollback is a vault operation, not a redeploy.',
    },
    {
      module: 'Aerial Twin Reproducibility Contract',
      capability: 'Same scene + ruleset + seed yields the same output, every time, on demand.',
      detail: 'The auditor can request a re-derivation of any attestation from its inputs. Re-derivation is the evidentiary backbone of the SOC 2 mapping.',
    },
  ],
  guardrails: [
    { layer: 'Provenance', control: 'Every attestation carries a full provenance footer: scene + ruleset + engine + ML versions + operator identity.', enforcedBy: 'Hephaestus + Cerberus.' },
    { layer: 'Reproducibility', control: 'Auditor can request re-derivation from the inputs at any time.', enforcedBy: 'A11oy Mirror Eval + Aerial Twin Engine.' },
    { layer: 'Lifecycle', control: 'Attestations expire and must be recertified annually or on material change.', enforcedBy: 'Durable-job recertification + Cerberus expiry gate.' },
  ],
  related: ['vessels-port', 'terra-building', 'sentra-anomaly'],
};

// ---------------------------------------------------------------------------
// REGISTRY
// ---------------------------------------------------------------------------

export const AERIAL_TWIN_MILESTONES: readonly MilestonePack[] = [
  M2_SIONNA_EVAL,
  M3_VESSELS_PORT,
  M4_TERRA_BUILDING,
  M5_SENTRA_ANOMALY,
  M6_FEDERATED_LEDGER,
  M7_RIC_BINDING,
  M8_AI_RAN,
  M9_ATTESTATION_SOC2,
];

export function getMilestonePack(slug: string): MilestonePack | undefined {
  return AERIAL_TWIN_MILESTONES.find((m) => m.slug === slug);
}
