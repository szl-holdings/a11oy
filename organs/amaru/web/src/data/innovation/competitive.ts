/**
 * Amaru — Competitive Intelligence Brief
 *
 * Research across 10 leading open-source and public reverse ETL / data-activation
 * projects on GitHub. Patterns are studied and re-implemented from first principles.
 * No GPL/AGPL source is vendored. No competitor source code is copied.
 *
 * Seed data is deterministic; no Math.random() or Date.now().
 */

export interface CompetitiveProject {
  readonly id: string;
  readonly name: string;
  readonly category: string;
  readonly githubStars: number;
  readonly maturitySignal: 'pioneer' | 'maturing' | 'established' | 'canonical';
  readonly license: 'MIT' | 'Apache-2.0' | 'ELv2' | 'BSL' | 'AGPL';
  readonly shortDescription: string;
  readonly patternsAbsorbed: readonly {
    readonly pattern: string;
    readonly detail: string;
    readonly amaruReinterpretation: string;
  }[];
  readonly gap: string;
  readonly innovationLinks: readonly string[];
}

export const COMPETITIVE_PROJECTS: readonly CompetitiveProject[] = [
  {
    id: 'proj-connector-cloud',
    name: 'Connector Cloud (OSS core)',
    category: 'EL / connector platform',
    githubStars: 15800,
    maturitySignal: 'established',
    license: 'MIT',
    shortDescription: 'Large-scale connector ecosystem with declarative source/destination schemas, incremental-sync cursors, and a pluggable catalog API. The de-facto standard for connector contract definitions.',
    patternsAbsorbed: [
      {
        pattern: 'Catalog / Discover / Read / Write protocol',
        detail: 'Structured catalog discovery separates schema negotiation from data delivery. Catalog is versioned, re-negotiated on every connection change.',
        amaruReinterpretation: 'Cartographer\'s probe-and-profile pipeline follows the same lifecycle: discover schema, version-stamp a catalog entry, then gate activation on catalog freshness.',
      },
      {
        pattern: 'Incremental cursor state',
        detail: 'Per-stream cursor values written to a state store after every successful batch. Restart from last committed cursor on failure.',
        amaruReinterpretation: 'Courier persists cursor_value + cursor_updated_at per sync. Fixer reads the cursor on retry — no full-scan on partial failure.',
      },
    ],
    gap: 'No governance layer. No policy enforcement. No coalition. No proof chain. Connectors deliver data; what happens after is someone else\'s problem.',
    innovationLinks: ['destination-discovery', 'drift-repair'],
  },
  {
    id: 'proj-transform-layer',
    name: 'Transform Layer (OSS)',
    category: 'transformation / semantic layer',
    githubStars: 9200,
    maturitySignal: 'canonical',
    license: 'Apache-2.0',
    shortDescription: 'SQL-first transformation framework with DAG lineage, model versioning, and test assertions. Sets the gold standard for composable data models and documentation-as-code.',
    patternsAbsorbed: [
      {
        pattern: 'Model DAG + lineage',
        detail: 'Every model knows its upstream sources and downstream consumers. Lineage is first-class: breakage propagates through the graph instantly.',
        amaruReinterpretation: 'Amaru\'s Lineage Graph traces every edge: source → model → mapping → destination → outcome. Proof-anchor badges sit on every edge as evidence.',
      },
      {
        pattern: 'Contract tests on models',
        detail: 'Schema assertions are part of the model definition. Test failure blocks the model from being promoted.',
        amaruReinterpretation: 'Verity runs field-contract assertions after every delivery. Disputes block Outcome learning until resolved — same conceptual gate, Amaru-native.',
      },
      {
        pattern: 'Semantic model as documentation',
        detail: 'Column descriptions, data type contracts, PII annotations live inside the model definition YAML.',
        amaruReinterpretation: 'RelayModel.fields carries piiClass, description, type, and nullable per field. Cartographer populates it; Sentinel enforces it.',
      },
    ],
    gap: 'Models activate into a warehouse. Getting data out of the warehouse and into SaaS destinations requires an entirely separate ETL layer with no shared lineage.',
    innovationLinks: ['lineage', 'audience-sql'],
  },
  {
    id: 'proj-reverse-etl-pioneer',
    name: 'Reverse ETL Pioneer',
    category: 'reverse ETL / activation',
    githubStars: 4100,
    maturitySignal: 'maturing',
    license: 'MIT',
    shortDescription: 'First-generation open-source reverse ETL that proved warehouse-to-SaaS sync was a category. Introduced audience SQL, destination field mapping UI, and basic scheduling.',
    patternsAbsorbed: [
      {
        pattern: 'Audience SQL as activation primitive',
        detail: 'Operators write a SQL query against the warehouse; the result set becomes the audience for a sync. Simple, powerful, warehouse-native.',
        amaruReinterpretation: 'Audience SQL Studio extends this with live row-count preview, PII gate overlay, and a "what destinations can receive this" compatibility matrix — all before the first byte moves.',
      },
      {
        pattern: 'Field mapping UI with transform library',
        detail: 'Visual drag-and-drop mapping with a curated transform menu (concat, format, lookup). Reduces error rate vs. hand-writing ETL.',
        amaruReinterpretation: 'Amaru\'s Mapper agent proposes mappings with confidence scores. The UI reviews proposals rather than building from scratch — a governed shift from authoring to approval.',
      },
    ],
    gap: 'No governance. No PII gating. No proof chain. Field mapping is manual; there is no agent-driven recommendation or confidence scoring.',
    innovationLinks: ['audience-sql', 'mapper-accuracy'],
  },
  {
    id: 'proj-activation-platform',
    name: 'Data Activation Platform (SaaS-native OSS SDK)',
    category: 'activation / audience segmentation',
    githubStars: 3600,
    maturitySignal: 'maturing',
    license: 'ELv2',
    shortDescription: 'Warehouse-native activation with audience builder, identity resolution, and destination-specific field normalization. Strong focus on marketing use cases and lookalike audiences.',
    patternsAbsorbed: [
      {
        pattern: 'Identity stitching across sources',
        detail: 'Resolve the same customer across CRM, warehouse, and support by matching on email, phone, and external IDs. Build a unified "golden profile" for activation.',
        amaruReinterpretation: 'Golden Record / Identity Stitching surface unifies records across RelaySource types with confidence scoring. Conflict resolution is operator-governed; the resolved identity propagates to all downstream syncs.',
      },
      {
        pattern: 'Destination-specific normalization',
        detail: 'Each destination adapter knows its field schema and emits normalization instructions. Platform auto-applies normalization before delivery.',
        amaruReinterpretation: 'Destination Contract Auto-Discovery synthesizes field-contract norms from adapter probes. Mapper uses the synthesized contract to score and propose transforms.',
      },
    ],
    gap: 'Identity resolution is black-box; operators can\'t inspect or override confidence thresholds. No proof chain for the merge decisions.',
    innovationLinks: ['golden-record', 'destination-discovery'],
  },
  {
    id: 'proj-data-pipeline-engine',
    name: 'Data Pipeline Engine (OSS)',
    category: 'pipeline orchestration',
    githubStars: 32000,
    maturitySignal: 'canonical',
    license: 'Apache-2.0',
    shortDescription: 'Task-graph orchestrator for data pipelines. Declarative DAG, scheduling, retry, and backfill. The backbone of most modern data stacks for pipeline scheduling.',
    patternsAbsorbed: [
      {
        pattern: 'Replay / backfill semantics',
        detail: 'Any run can be re-triggered for a specific time window. The engine tracks state so re-runs are idempotent.',
        amaruReinterpretation: 'Activation Simulation Theater uses snapshot-based replay: freeze the state at a point in time, re-run the coalition against the snapshot, inject failures, observe responses. Deterministic, replay-grade.',
      },
      {
        pattern: 'Sensor / trigger model',
        detail: 'Pipelines can be triggered by external events (file landing, API webhook, upstream pipeline completion) rather than only cron.',
        amaruReinterpretation: 'Reverse-Reverse ETL extends this to destination-side mutations: a CRM signal (lead marked lost) triggers an inbound event that feeds back into Outcomes. The loop closes.',
      },
    ],
    gap: 'Orchestration only. No activation semantics, no PII governance, no destination contracts, no proof chain.',
    innovationLinks: ['sim-theater', 'closed-loop'],
  },
  {
    id: 'proj-streaming-warehouse',
    name: 'Streaming Warehouse Bridge (OSS)',
    category: 'streaming / CDC',
    githubStars: 7400,
    maturitySignal: 'established',
    license: 'Apache-2.0',
    shortDescription: 'Change Data Capture toolkit that streams database mutations (inserts, updates, deletes) from PostgreSQL/MySQL into downstream sinks. Strong schema drift detection.',
    patternsAbsorbed: [
      {
        pattern: 'Schema drift detection + schema registry',
        detail: 'Tracks the "expected" schema per stream and alerts on drift (column added, type changed, column dropped). Schema registry keeps version history.',
        amaruReinterpretation: 'Schema Drift Auto-Repair goes further: Cartographer + Mapper + Fixer collaborate to detect drift, predict impact across dependent mappings, and propose governed repair proposals with diff preview and blast radius — presented in-app, not as raw alerts.',
      },
    ],
    gap: 'Drift alerts only. No impact prediction. No automated repair proposals. No governance gate on the repair path.',
    innovationLinks: ['drift-repair'],
  },
  {
    id: 'proj-event-routing-engine',
    name: 'Event Routing Engine (OSS)',
    category: 'CDP / event routing',
    githubStars: 6800,
    maturitySignal: 'established',
    license: 'Apache-2.0',
    shortDescription: 'Server-side event routing that captures clickstream and server events and fans them out to multiple destinations. Introduced destination-native event contracts.',
    patternsAbsorbed: [
      {
        pattern: 'Destination-native event contracts',
        detail: 'Each destination plugin declares the events it can receive, the fields it requires, and the transformations it applies. Mismatches fail at the contract layer, not at delivery.',
        amaruReinterpretation: 'RelayDestination.fieldContractStrength is derived from probed contracts. Destination Contract Auto-Discovery probes a new adapter\'s schema, operations, and rate-limit semantics to synthesize a complete RelayDestination record.',
      },
      {
        pattern: 'Fan-out delivery with per-destination retry',
        detail: 'A single event fans out to N destinations; each destination has an independent retry queue and failure log.',
        amaruReinterpretation: 'Courier\'s per-batch retry is independent per destination. Each batch gets its own evidence trail.',
      },
    ],
    gap: 'Event-only model. No batch/bulk activation. No SQL audience builder. No PII governance layer.',
    innovationLinks: ['destination-discovery', 'audience-sql'],
  },
  {
    id: 'proj-observability-framework',
    name: 'Data Observability Framework (OSS)',
    category: 'data observability / quality',
    githubStars: 5100,
    maturitySignal: 'maturing',
    license: 'Apache-2.0',
    shortDescription: 'ML-based anomaly detection for data pipelines. Monitors freshness, volume, and distribution drift. Integrates with dbt, Airflow, and Spark for lineage correlation.',
    patternsAbsorbed: [
      {
        pattern: 'Observability as first-class pipeline primitive',
        detail: 'Observability isn\'t a dashboard bolted on; it\'s instrumented into every step of the pipeline as metrics, events, and traces.',
        amaruReinterpretation: 'Amaru\'s Observability surface correlates RelayRunEvents, policy hits, delivery latencies, and outcome lifts. Every agent emits structured events to the proof ledger.',
      },
      {
        pattern: 'Cost-aware pipeline monitoring',
        detail: 'Tracks compute cost per pipeline run and alerts when cost per record exceeds threshold. Helps ops teams identify wasteful syncs.',
        amaruReinterpretation: 'Sync Cost & Carbon Predictor: Forecaster estimates API call volume, rate-limit headroom, $ cost, and carbon footprint before a sync runs. Budget gates block over-budget syncs.',
      },
    ],
    gap: 'Observability only. No activation semantics. No governance. No agent-driven remediation — alerts require human response.',
    innovationLinks: ['cost-carbon', 'mapper-accuracy'],
  },
  {
    id: 'proj-policy-engine',
    name: 'Open Policy Engine (OSS)',
    category: 'policy / governance',
    githubStars: 9100,
    maturitySignal: 'established',
    license: 'Apache-2.0',
    shortDescription: 'General-purpose policy engine with a declarative Rego DSL. Widely used for authorization and compliance checks in cloud infrastructure.',
    patternsAbsorbed: [
      {
        pattern: 'Declarative, composable policy DSL',
        detail: 'Policies are pure functions: given input data, they produce allow/deny with a reason. Composable, version-controlled, testable.',
        amaruReinterpretation: 'Policy-as-Code DSL: an A11oy-native activation policy language (e.g., `block when fields.pii_class >= sensitive and destination.piiAllowed = false`) with visual rule-builder fallback, version history, and Sentra-anchored audit.',
      },
    ],
    gap: 'General-purpose. No activation-domain semantics. No PII class awareness. No mapping or sync concept. Requires significant adaptation to be useful in an activation context.',
    innovationLinks: ['policy-dsl'],
  },
  {
    id: 'proj-feedback-loop-platform',
    name: 'ML Feedback Loop Platform (OSS)',
    category: 'MLOps / outcome capture',
    githubStars: 3200,
    maturitySignal: 'maturing',
    license: 'MIT',
    shortDescription: 'Platform for capturing ML model prediction outcomes and feeding them back as training signals. Closes the prediction→outcome loop for model retraining.',
    patternsAbsorbed: [
      {
        pattern: 'Destination-side outcome capture',
        detail: 'Captures what actually happened downstream (a predicted conversion vs. actual conversion) and feeds it back as a labeled training example.',
        amaruReinterpretation: 'Reverse-Reverse ETL: destination mutations (CRM rep marks lead lost) are captured and fed back as outcome signals. Forecaster updates its lift prediction model. The activation learning loop closes without manual intervention.',
      },
      {
        pattern: 'Confidence calibration over time',
        detail: 'Tracks predicted vs. actual outcomes to recalibrate model confidence thresholds. Under-confident models become bolder; over-confident models get tighter gates.',
        amaruReinterpretation: 'Mapping Confidence Calibration: Verity tracks Mapper\'s recommended-vs-accepted ratio over time. The calibration surface shows where confidence is mis-set and lets operators approve recalibration.',
      },
    ],
    gap: 'ML-only framing. No activation or data-movement context. No policy gate on outcome capture. No proof chain for the feedback loop.',
    innovationLinks: ['closed-loop', 'mapper-accuracy'],
  },
];

export interface InnovationCapability {
  readonly id: string;
  readonly number: number;
  readonly title: string;
  readonly tagline: string;
  readonly description: string;
  readonly route: string;
  readonly agents: readonly string[];
  readonly crossLink: readonly { label: string; route: string }[];
  readonly status: 'shipped';
}

export const INNOVATION_CAPABILITIES: readonly InnovationCapability[] = [
  {
    id: 'audience-sql',
    number: 1,
    title: 'Audience SQL Studio',
    tagline: 'Visual + SQL hybrid editor with live row-count preview and PII gating.',
    description: 'Define activation audiences over models using SQL or a visual builder. Live row-count preview before any data moves. PII gate overlay shows which fields are blocked. Destination compatibility matrix shows which systems can receive this audience.',
    route: '/innovation/audience-sql',
    agents: ['cartographer', 'mapper', 'sentinel'],
    crossLink: [{ label: 'Models', route: '/models' }],
    status: 'shipped',
  },
  {
    id: 'lineage',
    number: 2,
    title: 'Lineage Graph',
    tagline: 'End-to-end source→outcome node-link visualization with proof-anchor badges.',
    description: 'Full lineage from source through model, mapping, destination, to outcome. Every edge carries a proof-anchor badge. Click any node to navigate to its Amaru surface.',
    route: '/innovation/lineage',
    agents: ['cartographer', 'scribe'],
    crossLink: [{ label: 'Mappings', route: '/mappings' }],
    status: 'shipped',
  },
  {
    id: 'drift-repair',
    number: 3,
    title: 'Schema Drift Auto-Repair',
    tagline: 'Cartographer + Mapper + Fixer detect drift and propose governed repair PRs.',
    description: 'When a source schema changes, the coalition detects impact across all dependent mappings, predicts blast radius, and proposes in-app repair proposals with diff preview and one-click approval.',
    route: '/innovation/drift-repair',
    agents: ['cartographer', 'mapper', 'fixer'],
    crossLink: [{ label: 'Mappings', route: '/mappings' }, { label: 'Sources', route: '/sources' }],
    status: 'shipped',
  },
  {
    id: 'golden-record',
    number: 4,
    title: 'Golden Record / Identity Stitching',
    tagline: 'Entity resolution unifying records across sources with confidence scoring.',
    description: 'Unify records for the same entity across CRM, warehouse, and support sources. Confidence scoring, conflict resolution, and a single activation identity used across all downstream syncs.',
    route: '/innovation/golden-record',
    agents: ['cartographer', 'verity', 'sentinel'],
    crossLink: [{ label: 'Sources', route: '/sources' }, { label: 'Models', route: '/models' }],
    status: 'shipped',
  },
  {
    id: 'cost-carbon',
    number: 5,
    title: 'Sync Cost & Carbon Predictor',
    tagline: 'Forecaster-driven estimator with API, rate, $, and carbon footprint estimates.',
    description: 'Before any sync runs, Forecaster estimates API call volume, rate-limit headroom, dollar cost (modeled), and energy / carbon footprint. Budget gates are a new policy type that block or warn based on these estimates.',
    route: '/innovation/cost-carbon',
    agents: ['forecaster', 'sentinel'],
    crossLink: [{ label: 'Syncs', route: '/syncs' }, { label: 'Policies', route: '/policies' }],
    status: 'shipped',
  },
  {
    id: 'closed-loop',
    number: 6,
    title: 'Reverse-Reverse ETL',
    tagline: 'Captures destination mutations and feeds them back as outcome signals.',
    description: 'When a CRM rep marks a lead lost, Amaru captures that mutation as an outcome signal, feeds it to Forecaster for lift recalibration, and updates the Outcomes surface. The activation learning loop closes.',
    route: '/innovation/closed-loop',
    agents: ['courier', 'forecaster', 'scribe'],
    crossLink: [{ label: 'Outcomes', route: '/outcomes' }],
    status: 'shipped',
  },
  {
    id: 'sim-theater',
    number: 7,
    title: 'Activation Simulation Theater',
    tagline: 'Replay syncs against a frozen snapshot and inject failures for chaos drills.',
    description: 'Replay any sync against a frozen state snapshot. Inject failures (rate limit, schema mismatch, PII flagged, destination outage) and watch the agent coalition respond. Full event timeline output.',
    route: '/innovation/sim-theater',
    agents: ['cartographer', 'mapper', 'courier', 'sentinel', 'verity', 'fixer'],
    crossLink: [{ label: 'Agents', route: '/agents' }, { label: 'Runs', route: '/runs' }],
    status: 'shipped',
  },
  {
    id: 'mapper-accuracy',
    number: 8,
    title: 'Mapping Confidence Calibration',
    tagline: 'Verity-driven Mapper accuracy tracking and self-tuning thresholds.',
    description: 'Tracks Mapper\'s recommended-vs-accepted ratio over time. Surfaces a calibration heatmap and allows operators to approve threshold recalibration. The Mapper accuracy metric appears in the Agents surface.',
    route: '/innovation/mapper-accuracy',
    agents: ['mapper', 'verity'],
    crossLink: [{ label: 'Agents', route: '/agents' }, { label: 'Mappings', route: '/mappings' }],
    status: 'shipped',
  },
  {
    id: 'destination-discovery',
    number: 9,
    title: 'Destination Contract Auto-Discovery',
    tagline: 'Probe a new adapter and synthesize a full RelayDestination record automatically.',
    description: 'When a new destination adapter is registered, Cartographer probes its schema, supported operations, and rate-limit semantics. A complete RelayDestination record is synthesized with field-contract strength scoring — no manual registration required.',
    route: '/innovation/destination-discovery',
    agents: ['cartographer', 'sentinel'],
    crossLink: [{ label: 'Destinations', route: '/destinations' }],
    status: 'shipped',
  },
  {
    id: 'policy-dsl',
    number: 10,
    title: 'Policy-as-Code DSL',
    tagline: 'Composable activation policy language with visual builder fallback.',
    description: 'A small A11oy-native DSL for expressing activation policies. Visual rule-builder fallback for non-technical operators. Version history and Sentra-anchored audit. Replaces ad-hoc enum-based policy conditions with composable, testable rules.',
    route: '/innovation/policy-dsl',
    agents: ['sentinel', 'scribe'],
    crossLink: [{ label: 'Policies', route: '/policies' }],
    status: 'shipped',
  },
];
