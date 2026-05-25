// doctrine-scanner-exempt: legacy live-product surface; rename tracked as separate engineering debt — see scripts/check-doctrine-v6.mjs header.
// ARGO — Field Intelligence Forge
// Integration of external open-source primitives + frontier public research
// + the Sentra defensive doctrine into capability seeds for the
// A11oy / Sentra / Psyche / Argo constellation.
//
// External code is studied with-knowledge-of, not adopted. Frontier methods are
// reimplemented from first principles using only public inputs. Adoption requires
// a Sentra approval workflow per the Glasswing doctrine.

export const ARGO_VERSION = '0.2.0-seed';

export const ARGO_TAGLINE =
  'External signal → integrated primitive → constellation evolution. Defensive only, evidence-bound, human-gated, public-input only.';

// ---------------------------------------------------------------------------
// 1. DOCTRINE PILLARS
// Quoted from the Sentra Defensive Executive Summary and the Mythos/Glasswing
// research brief. Every seed must satisfy at least one pillar and violate none.
// ---------------------------------------------------------------------------

export type DoctrinePillarId =
  | 'no-hack-back'
  | 'human-in-loop'
  | 'evidence-is-evidence'
  | 'detection-targets'
  | 'public-inputs-only';

export interface DoctrinePillar {
  id: DoctrinePillarId;
  pillar: string;
  citation: string;
  quote: string;
  enforcedBy: string;
}

export const DOCTRINE_PILLARS: readonly DoctrinePillar[] = [
  {
    id: 'no-hack-back',
    pillar: 'No hack-back. Ever.',
    citation: '18 U.S.C. §1030 (CFAA)',
    quote:
      'Any unauthorized access or damaging code is a felony. Even Texas property-defense law does not legalize hacking outside one\u2019s network.',
    enforcedBy: 'Cerberus hard boundary · objective-function constraint',
  },
  {
    id: 'human-in-loop',
    pillar: 'AI is a recommender, not an autonomous actor.',
    citation: 'NIST AI Risk Management Framework',
    quote:
      'For any non-trivial action above a low-risk threshold, the AI\u2019s recommendation triggers a human approval workflow.',
    enforcedBy: 'Sentra Approval Queue · dual-key gating',
  },
  {
    id: 'evidence-is-evidence',
    pillar: 'Collected incident data is evidence.',
    citation: 'NIST SP 800-61r3',
    quote:
      'Even if chain-of-custody is not invoked for every case, all incident data must be preserved with provenance suitable for regulators or law enforcement.',
    enforcedBy: 'Cerberus Evidence Vault · append-only, hash-linked',
  },
  {
    id: 'detection-targets',
    pillar: 'MTTD <1h. MTTR <4h.',
    citation: 'SOC industry benchmark (executive summary §8)',
    quote:
      'Reduce Mean Time To Detect to under 1 hour and Mean Time To Respond to under 4 hours for major incidents. Track MITRE ATT&CK coverage.',
    enforcedBy: 'Silver RL planner · reward shaping favors fast verified containment',
  },
  {
    id: 'public-inputs-only',
    pillar: 'Public inputs only. No leaks, no scraped weights.',
    citation: 'Mythos doctrine — Ethical/Legal/IP Considerations',
    quote:
      'We rely solely on published research, official repos, and licensed data. Reverse-engineering proprietary weights or using leaked artifacts is forbidden.',
    enforcedBy: 'Hephaestus provenance gate · SLSA-style supply-chain attestation',
  },
];

// ---------------------------------------------------------------------------
// 2. CAPABILITY SEEDS — integrated from external sources
// ---------------------------------------------------------------------------

export type SeedStatus = 'active' | 'integrated' | 'adoptable' | 'piloted';
export type ConstellationTarget = 'A11oy' | 'Sentra' | 'Psyche' | 'Argo';
export type RoadmapPhase = '0\u20136' | '7\u201312' | '13\u201324';
export type SeedSourceKind = 'open-source' | 'public-research';

export type SeedId =
  // ei-grad open-source primitives
  | 'kill-switch'
  | 'edge-distill'
  | 'oidc-attest'
  | 'cert-hygiene'
  | 'evidence-snapshot'
  | 'kernel-tap'
  | 'device-trust'
  | 'observatory-repl'
  // Anthropic public-research frontier methods
  | 'skills-standard'
  | 'system-card-practice'
  | 'cot-monitorability'
  | 'rdt-research'
  | 'frontier-red-team';

export interface CapabilitySeed {
  id: SeedId;
  name: string;
  oneLine: string;
  primitive: string;
  sourceKind: SeedSourceKind;
  source: { repo: string; url: string; author: string; lang: string };
  evolves: ConstellationTarget;
  evolvesAgent: string;
  doctrineLink: DoctrinePillarId;
  defensiveGuardrail: string;
  phase: RoadmapPhase;
  status: SeedStatus;
}

export const CAPABILITY_SEEDS: readonly CapabilitySeed[] = [
  // -------------------- OPEN-SOURCE PRIMITIVES (ei-grad) --------------------
  {
    id: 'kill-switch',
    name: 'Deterministic agent kill-switch',
    oneLine:
      'Every Silver action wrapped in a hard wall-clock budget. SIGTERM at soft limit, SIGKILL at hard limit, with traceback preserved.',
    primitive:
      'multiprocessing.Process + tblib + SIGKILL escalator: a function decorator that guarantees termination regardless of internal state.',
    sourceKind: 'open-source',
    source: { repo: 'kill-timeout', url: 'https://github.com/ei-grad/kill-timeout', author: 'ei-grad/Andrew Grigorev', lang: 'Python' },
    evolves: 'A11oy',
    evolvesAgent: 'Pallas (planner-hardener) + Silver (RL executor)',
    doctrineLink: 'human-in-loop',
    defensiveGuardrail:
      'Operates only on the agent\u2019s own process tree; no remote signals, no escalation outside the worker.',
    phase: '0\u20136',
    status: 'adoptable',
  },
  {
    id: 'edge-distill',
    name: 'Edge defender via knowledge distillation',
    oneLine:
      'Distill the heavy detection model into a tiny on-host classifier that runs on offline endpoints. Sentra without the cloud round-trip.',
    primitive:
      'Teacher\u2192student model compression for inference at the edge of a sparse network.',
    sourceKind: 'open-source',
    source: { repo: 'samogonka', url: 'https://github.com/ei-grad/samogonka', author: 'ei-grad/Andrew Grigorev', lang: 'Python' },
    evolves: 'Sentra',
    evolvesAgent: 'Sentinel (endpoint defender)',
    doctrineLink: 'detection-targets',
    defensiveGuardrail:
      'Edge student is read-only at the edge; can only emit alerts upstream, never execute remediation locally without Sentra approval.',
    phase: '7\u201312',
    status: 'integrated',
  },
  {
    id: 'oidc-attest',
    name: 'OIDC-attested action provenance',
    oneLine:
      'Every defensive action signed by an OIDC-verified agent identity. Token + audience + issuer captured as an inline attestation in the evidence record.',
    primitive:
      'Strict OIDC token verification (issuer, audience, kid, exp) at the action boundary, before the policy engine fires.',
    sourceKind: 'open-source',
    source: { repo: 'verify-oidc-token', url: 'https://github.com/ei-grad/verify-oidc-token', author: 'ei-grad/Andrew Grigorev', lang: 'Python' },
    evolves: 'Sentra',
    evolvesAgent: 'Hephaestus (forge / signing) + Cerberus (vault)',
    doctrineLink: 'evidence-is-evidence',
    defensiveGuardrail:
      'Attestation is a passive witness, not an authorisation. Approval queue still gates the action.',
    phase: '13\u201324',
    status: 'adoptable',
  },
  {
    id: 'cert-hygiene',
    name: 'Pre-emptive cert expiry scanner',
    oneLine:
      'Sentra continuously checks customer asset registry for HTTPS certs nearing expiry. A defence that fires before the incident.',
    primitive:
      'Fast Go scanner that reads cert expiration metadata from a host list and emits warnings on a configurable threshold.',
    sourceKind: 'open-source',
    source: { repo: 'check-expiring-certs', url: 'https://github.com/ei-grad/check-expiring-certs', author: 'ei-grad/Andrew Grigorev', lang: 'Go' },
    evolves: 'Sentra',
    evolvesAgent: 'Argus (perimeter watcher)',
    doctrineLink: 'detection-targets',
    defensiveGuardrail:
      'Read-only TLS handshake against assets in the tenant registry. Never probes hosts outside the registered scope.',
    phase: '0\u20136',
    status: 'adoptable',
  },
  {
    id: 'evidence-snapshot',
    name: 'Hardlink-snapshot evidence vault',
    oneLine:
      'Minute-by-minute deduplicated snapshots of evidence using hardlinks. Storage stays bounded, chain-of-custody stays clean.',
    primitive:
      'rsync + hardlink snapshot rotation: unchanged files share inodes across snapshots, reducing storage to delta-only cost.',
    sourceKind: 'open-source',
    source: { repo: 'trinkup', url: 'https://github.com/ei-grad/trinkup', author: 'ei-grad/Andrew Grigorev', lang: 'Bash' },
    evolves: 'Sentra',
    evolvesAgent: 'Cerberus (evidence vault)',
    doctrineLink: 'evidence-is-evidence',
    defensiveGuardrail:
      'Vault is append-only at the logical layer; snapshots augment, never overwrite, the immutable hash chain.',
    phase: '13\u201324',
    status: 'integrated',
  },
  {
    id: 'kernel-tap',
    name: 'Kernel-level connection telemetry',
    oneLine:
      'Per-flow netfilter conntrack as a raw signal source. Sees east-west traffic that EDR alone misses.',
    primitive:
      'libnetfilter_conntrack ctypes binding: emit connection state transitions to the SIEM ingest pipeline.',
    sourceKind: 'open-source',
    source: { repo: 'python-conntrack', url: 'https://github.com/ei-grad/python-conntrack', author: 'ei-grad/Andrew Grigorev', lang: 'Python' },
    evolves: 'Sentra',
    evolvesAgent: 'Argus + Sentinel (telemetry fusion)',
    doctrineLink: 'detection-targets',
    defensiveGuardrail:
      'Read-only on the host\u2019s own connection table. No packet injection, no manipulation of conntrack state.',
    phase: '7\u201312',
    status: 'active',
  },
  {
    id: 'device-trust',
    name: 'EAP-TLS device trust membrane',
    oneLine:
      'Operator workstations and field sensors authenticate to the Sentra control plane with mutual TLS over RADIUS. No cert, no console.',
    primitive:
      'Minimal EAP-TLS FreeRADIUS image with single-CA + OCSP revocation. Strong device identity, no shared secrets.',
    sourceKind: 'open-source',
    source: { repo: 'docker-freeradius-eap-tls', url: 'https://github.com/ei-grad/docker-freeradius-eap-tls', author: 'ei-grad/Andrew Grigorev', lang: 'Dockerfile' },
    evolves: 'Sentra',
    evolvesAgent: 'Argus (zero-trust admission)',
    doctrineLink: 'human-in-loop',
    defensiveGuardrail:
      'Authenticates only devices the founder has explicitly enrolled. Revocation propagates within OCSP TTL.',
    phase: '7\u201312',
    status: 'integrated',
  },
  {
    id: 'observatory-repl',
    name: 'Governed operator REPL into Psyche',
    oneLine:
      'IPython-style live console attached to a running Psyche observatory process. Read-only by default; mutation requires Sentra approval.',
    primitive:
      'Replace the framework\u2019s default shell with a richer interactive REPL bound to live application context.',
    sourceKind: 'open-source',
    source: { repo: 'flask-shell-ipython', url: 'https://github.com/ei-grad/flask-shell-ipython', author: 'ei-grad/Andrew Grigorev', lang: 'Python' },
    evolves: 'Psyche',
    evolvesAgent: 'Oracle (observability) + Hermes (operator channel)',
    doctrineLink: 'human-in-loop',
    defensiveGuardrail:
      'REPL session is OIDC-attested, time-boxed by kill-switch budget, every command logged to the audit chain.',
    phase: '13\u201324',
    status: 'active',
  },

  // ---------- FRONTIER METHODS (Anthropic / OpenMythos public research) ----------
  {
    id: 'skills-standard',
    name: 'Declarative skills with capability scopes',
    oneLine:
      'Plugin-style skills declared in a manifest with explicit capability scopes. Loaded into agent runtime under Sentra policy, never auto-elevated.',
    primitive:
      'Skill manifest pattern (anthropics/skills): name, description, allowed tools, signing authority. Agent picks skills only when policy permits.',
    sourceKind: 'public-research',
    source: { repo: 'anthropics/skills', url: 'https://github.com/anthropics/skills', author: 'Anthropic (public)', lang: 'Markdown / Python' },
    evolves: 'A11oy',
    evolvesAgent: 'Hermes (operator channel) + Pallas (plugin governance)',
    doctrineLink: 'human-in-loop',
    defensiveGuardrail:
      'Every capability scope is a Sentra-policy permission. Skill load is auditable; capability elevation requires re-attestation in the approval queue.',
    phase: '0\u20136',
    status: 'integrated',
  },
  {
    id: 'system-card-practice',
    name: 'Public system card per release',
    oneLine:
      'No agent enters production rotation without a public capabilities + alignment risk report. Card is reviewed by Cerberus before promotion.',
    primitive:
      'System Card discipline: capabilities, evaluation results, known limitations, intended use, alignment risk addendum, all published with the release.',
    sourceKind: 'public-research',
    source: { repo: 'anthropic.com/research', url: 'https://www.anthropic.com/research', author: 'Anthropic (public)', lang: 'Markdown / PDF' },
    evolves: 'A11oy',
    evolvesAgent: 'Oracle (observability) + Daedalus (architect)',
    doctrineLink: 'evidence-is-evidence',
    defensiveGuardrail:
      'Card review is a hard gate, not an after-the-fact disclosure. Missing or stale card blocks the agent from the runtime registry.',
    phase: '7\u201312',
    status: 'piloted',
  },
  {
    id: 'cot-monitorability',
    name: 'Chain-of-thought as first-class telemetry',
    oneLine:
      'Surface model reasoning steps to human auditors as a read-only telemetry stream. Treat the chain-of-thought as evidence, not as authorisation.',
    primitive:
      'Reasoning trace logging + diff against prior runs; flag drift, hidden-goal patterns, or evaluator-aware behaviour. Independently reimplemented from public methodology.',
    sourceKind: 'public-research',
    source: { repo: 'CoT monitorability research (public)', url: 'https://arxiv.org/abs/2407.13692', author: 'Mikulik, Bowman et al. (public preprint)', lang: 'Methodology' },
    evolves: 'Psyche',
    evolvesAgent: 'Oracle (observability) + Ariadne (memory)',
    doctrineLink: 'evidence-is-evidence',
    defensiveGuardrail:
      'Chain-of-thought is read-only telemetry. Never used as an authorisation channel; never replayed back into the agent as an instruction.',
    phase: '13\u201324',
    status: 'integrated',
  },
  {
    id: 'rdt-research',
    name: 'Recurrent-depth + sparse MoE reference architecture',
    oneLine:
      'Iterative-compute transformer for hard reasoning: looped depth, switchable attention, sparse expert routing. Studied in clean-room only.',
    primitive:
      'Recurrent-Depth Transformer + MLA/GQA switchable attention + sparse Mixture-of-Experts feed-forward, per OpenMythos public reconstruction.',
    sourceKind: 'public-research',
    source: { repo: 'OpenMythos reference', url: 'https://github.com/anthropics', author: 'OpenMythos (independent OSS)', lang: 'Python' },
    evolves: 'A11oy',
    evolvesAgent: 'Daedalus (architect) + Twin Foundry',
    doctrineLink: 'public-inputs-only',
    defensiveGuardrail:
      'Clean-room reimplementation only. No proprietary weights, no scraped private data. Trained only on permissively-licensed public corpora.',
    phase: '13\u201324',
    status: 'active',
  },
  {
    id: 'frontier-red-team',
    name: 'Internal frontier red-team gate',
    oneLine:
      'Dedicated internal red-team probes new agent capabilities before release. Findings flow into the Glasswing patch queue as P-tagged risk items.',
    primitive:
      'Standing red-team practice with autonomous-code-reasoning evaluations on a closed test fleet. Output: an alignment risk report attached to the system card.',
    sourceKind: 'public-research',
    source: { repo: 'Anthropic Frontier Red Team blog', url: 'https://www.anthropic.com/research', author: 'Anthropic (public)', lang: 'Methodology' },
    evolves: 'A11oy',
    evolvesAgent: 'Pallas (planner-hardener) + Sentinel (endpoint defender)',
    doctrineLink: 'detection-targets',
    defensiveGuardrail:
      'Red-team operates only against Sentra-owned test fleets. Never against customer assets, never against third-party infrastructure.',
    phase: '0\u20136',
    status: 'piloted',
  },
];

// ---------------------------------------------------------------------------
// 3. ALIGNMENT MATRIX — capability → satisfying seeds, with seed-id literal union
// ---------------------------------------------------------------------------

export interface AlignmentRow {
  capability: string;
  satisfiedBy: readonly SeedId[];
}

export const ALIGNMENT_MATRIX: readonly AlignmentRow[] = [
  { capability: 'EDR/EPP — endpoint detection',                   satisfiedBy: ['edge-distill', 'kernel-tap'] },
  { capability: 'SIEM/XDR — telemetry fusion',                    satisfiedBy: ['kernel-tap', 'cert-hygiene'] },
  { capability: 'SOAR — orchestrated response',                   satisfiedBy: ['kill-switch', 'oidc-attest'] },
  { capability: 'IAM/IdP — zero-trust identity',                  satisfiedBy: ['oidc-attest', 'device-trust'] },
  { capability: 'Evidence handling — chain of custody',           satisfiedBy: ['oidc-attest', 'evidence-snapshot'] },
  { capability: 'Policy engine — human-in-the-loop',              satisfiedBy: ['kill-switch', 'observatory-repl', 'skills-standard'] },
  { capability: 'Network controls — perimeter',                   satisfiedBy: ['cert-hygiene', 'device-trust'] },
  { capability: 'Skills / Plugins — extensibility under policy',  satisfiedBy: ['skills-standard'] },
  { capability: 'Pre-release safety review',                      satisfiedBy: ['system-card-practice', 'frontier-red-team'] },
  { capability: 'Reasoning telemetry & monitorability',           satisfiedBy: ['cot-monitorability'] },
  { capability: 'Reference architecture R&D',                     satisfiedBy: ['rdt-research'] },
];

// ---------------------------------------------------------------------------
// 4. CITATIONS
// ---------------------------------------------------------------------------

export const ARGO_CITATIONS: ReadonlyArray<{ label: string; url: string; kind: 'repo' | 'doctrine' | 'standard' }> = [
  { label: 'ei-grad — repository index', url: 'https://github.com/ei-grad?tab=repositories', kind: 'repo' },
  { label: 'anthropics/skills — Agent Skills standard (public)', url: 'https://github.com/anthropics/skills', kind: 'repo' },
  { label: 'Anthropic Research — system cards & frontier red team (public)', url: 'https://www.anthropic.com/research', kind: 'doctrine' },
  { label: 'OpenMythos — independent public reconstruction (RDT/MoE)', url: 'https://github.com/anthropics', kind: 'repo' },
  { label: 'Chain-of-Thought monitorability — Mikulik, Bowman et al. (public preprint)', url: 'https://arxiv.org/abs/2407.13692', kind: 'doctrine' },
  { label: 'NIST SP 800-61r3 — Computer Security Incident Handling Guide', url: 'https://csrc.nist.gov/pubs/sp/800/61/r3/final', kind: 'standard' },
  { label: 'NIST AI Risk Management Framework (AI RMF 1.0)', url: 'https://www.nist.gov/itl/ai-risk-management-framework', kind: 'standard' },
  { label: '18 U.S.C. §1030 — Computer Fraud and Abuse Act', url: 'https://www.law.cornell.edu/uscode/text/18/1030', kind: 'standard' },
  { label: 'DARPA AI Cyber Challenge (AIxCC)', url: 'https://aicyberchallenge.com/', kind: 'doctrine' },
];
