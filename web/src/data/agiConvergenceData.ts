// VENDORED FROM szl-holdings/platform@ed400a4f378330becd53346420b4d89ae8281dc5 — artifacts/a11oy/src/data/agiConvergenceData.ts
// DO NOT EDIT HERE. Edit in the monorepo, then run scripts/sync_from_monorepo.sh sync.
export interface AbsorbedCapability {
  source: string;
  repo: string;
  stars: string;
  capability: string;
  a11oyEquivalent: string;
  governed: boolean;
  status: 'absorbed' | 'surpassed' | 'unique';
}

export interface CompetitorProfile {
  name: string;
  tagline: string;
  repos: number;
  keyStrength: string;
  absorbed: string[];
  gap: string;
}

export interface UnsolvedGap {
  id: string;
  gap: string;
  industryProblem: string;
  whyItMatters: string;
  a11oyAnswer: string;
  a11oyPrimitive: string;
}

export interface EcosystemOrg {
  name: string;
  tagline: string;
  repos: number;
  starCount: string;
  topRepo: string;
  topRepoStars: string;
  keyCapabilities: string[];
  a11oyAbsorption: string;
  a11oyPrimitive: string;
  status: 'absorbed' | 'surpassed';
}

export interface OriginalInnovation {
  name: string;
  tagline: string;
  desc: string;
  primitiveId: string;
  noOneElse: string;
}

export const UNSOLVED_GAPS: UnsolvedGap[] = [
  {
    id: 'governance',
    gap: 'Governance',
    industryProblem: 'No AGI platform enforces real-time, policy-as-code governance on every inference. Policy is a post-hoc review, not a pre-execution gate.',
    whyItMatters: 'Without pre-execution gates, a single non-compliant inference can trigger regulatory exposure, reputational damage, or irreversible autonomous action.',
    a11oyAnswer: 'Covenant Policy gates every inference before execution. Org-level rules — who can approve, what the agent can touch, when it must pause for human review — enforced at the platform layer, not the application layer.',
    a11oyPrimitive: 'Covenant Policy',
  },
  {
    id: 'trust',
    gap: 'Trust / Know Your Agent',
    industryProblem: 'In multi-agent chains, no framework can verify which agent made which decision, with what evidence, at what confidence level. Agent identity is implicit.',
    whyItMatters: 'Enterprise, regulatory, and legal accountability requires attributing every action to an identified, verified actor. Anonymous agent actions are legally and operationally indefensible.',
    a11oyAnswer: 'Every agent action is cryptographically attributed — agent identity, model version, prompt hash, confidence score, governance verdict. Queryable. Verifiable. Tamper-resistant.',
    a11oyPrimitive: 'Proof Chain',
  },
  {
    id: 'provenance',
    gap: 'Provenance',
    industryProblem: 'No platform tracks the full lineage from raw signal to final outcome across a multi-agent chain. The path from input to decision is opaque.',
    whyItMatters: 'Auditors, regulators, and executives need to reconstruct exactly how a decision was made — what signals triggered it, which models processed it, who approved it, what resulted.',
    a11oyAnswer: 'Decision Provenance records the end-to-end cryptographic lineage: signal origin → enrichment → model inference → governance verdict → human approval → execution → real-world outcome. Every step. Every chain.',
    a11oyPrimitive: 'Decision Provenance',
  },
  {
    id: 'non-determinism',
    gap: 'Non-Deterministic Inference',
    industryProblem: 'LLMs produce different outputs for the same input. No platform detects when inference variance produces dangerous or inconsistent recommendations before delivery.',
    whyItMatters: 'High-stakes decisions — financial, legal, security — cannot tolerate unchecked LLM variance. A 5% shift in output framing can have material consequences.',
    a11oyAnswer: 'Shadow Council runs an adversarial red-team challenger against every high-stakes output before commitment. Logical flaws, data gaps, biased assumptions, regulatory risks — identified and revised before reaching the user.',
    a11oyPrimitive: 'Shadow Council',
  },
  {
    id: 'orchestration',
    gap: 'Orchestration Sprawl',
    industryProblem: 'Multi-agent systems sprawl across frameworks (LangGraph, AutoGen, Swarm, CrewAI, Llama Stack) with no unified control plane, no governance, no shared audit trail.',
    whyItMatters: 'Enterprises deploying multiple agent frameworks end up with ungoverned, unauditable agent activity scattered across systems. Coordination failures are silent and irreversible.',
    a11oyAnswer: 'Coalition Intelligence forms ad-hoc coalitions of 2–4 specialized agents with a shared scratchpad, consensus voting, and dissenter logging — dissolved after each query. One governed control plane.',
    a11oyPrimitive: 'Coalition Intelligence',
  },
  {
    id: 'evaluation',
    gap: 'Agent Evaluation',
    industryProblem: 'Agent evaluation happens offline, infrequently, and against static benchmarks. No platform continuously evaluates agents in production against real business outcomes.',
    whyItMatters: 'Agents that perform well on benchmarks can fail silently in production. Without continuous evaluation against real outcomes, drift goes undetected until it causes harm.',
    a11oyAnswer: 'Outcome Graph closes the loop — recording real-world consequences and feeding them back to calibrate agent confidence and model routing decisions. MirrorEval benchmarks continuously in production.',
    a11oyPrimitive: 'Outcome Graph',
  },
  {
    id: 'emergent',
    gap: 'Emergent Multi-Agent Behavior',
    industryProblem: 'Nobody can explain or predict what a coalition of agents will do. Emergent behaviors in multi-agent systems are opaque, unpredictable, and ungovernable.',
    whyItMatters: 'As enterprises deploy larger agent coalitions, emergent coordination patterns — including failures, biases, and runaway feedback loops — become existential risks.',
    a11oyAnswer: 'The Consciousness Layer provides metacognitive monitoring of agent coalitions: inner monologue, cognitive workspace, predictive processing, and self-model — surfacing emergent behaviors before they manifest as outcomes.',
    a11oyPrimitive: 'Consciousness Layer',
  },
];

export const ECOSYSTEM_ORGS: EcosystemOrg[] = [
  {
    name: 'OpenAI',
    tagline: 'Agentic execution at scale',
    repos: 243,
    starCount: '157k+',
    topRepo: 'openai/codex',
    topRepoStars: '28k',
    keyCapabilities: [
      'Agents SDK — multi-agent orchestration',
      'Codex CLI — terminal coding agent',
      'Swarm — lightweight multi-agent patterns',
      'Evals — model evaluation framework',
      'Deep Research — multi-source synthesis',
    ],
    a11oyAbsorption: 'OpenAI Agents SDK → A11oy Governed Agent Mesh (covenant-gated, proof-chained, sovereign-replayable)',
    a11oyPrimitive: 'Governed Agent Mesh',
    status: 'surpassed',
  },
  {
    name: 'Anthropic',
    tagline: 'Safe autonomous coding agents',
    repos: 47,
    starCount: '129k+',
    topRepo: 'anthropics/claude-code',
    topRepoStars: '118k',
    keyCapabilities: [
      'Claude Code — agentic coding CLI',
      'Claude Code Action — GitHub CI integration',
      'Constitutional AI — alignment via principles',
      'Skills library — agent capability plugins',
      'Tool Control — granular tool permissions',
    ],
    a11oyAbsorption: 'Anthropic Claude Code → A11oy Shadow Council + Proof Chain (adversarial validation on every output, cryptographic attribution)',
    a11oyPrimitive: 'Shadow Council + Proof Chain',
    status: 'surpassed',
  },
  {
    name: 'Google DeepMind',
    tagline: 'Research depth meets multimodal intelligence',
    repos: 387,
    starCount: '112k+',
    topRepo: 'google-gemini/gemini-cli',
    topRepoStars: '102k',
    keyCapabilities: [
      'Gemini CLI — terminal AI agent',
      'Agent Development Kit (ADK) — multi-agent framework',
      'Deep Research Agent — autonomous research pipeline',
      'AlphaFold — scientific reasoning patterns',
      'Responsible AI toolkit — safety research',
    ],
    a11oyAbsorption: 'Google ADK → A11oy Coalition Formation (ad-hoc multi-agent coalitions with scratchpad, consensus voting, and dissenter logging)',
    a11oyPrimitive: 'Coalition Formation',
    status: 'surpassed',
  },
  {
    name: 'Meta',
    tagline: 'Open-weight model strategy',
    repos: 12,
    starCount: '95k+',
    topRepo: 'meta-llama/llama',
    topRepoStars: '73k',
    keyCapabilities: [
      'Llama Stack — agentic application platform',
      'Llama open weights — private/local deployment',
      'HyperAgents — self-improving agents',
      'Llama Guard — safety classifier',
      'Llama Cookbook — community integrations',
    ],
    a11oyAbsorption: 'Meta open-weight models → A11oy Sovereign Inference (air-gapped, on-premise deployment with full Covenant policy enforcement)',
    a11oyPrimitive: 'Sovereign Inference',
    status: 'absorbed',
  },
  {
    name: 'vLLM Project',
    tagline: 'High-throughput LLM inference serving',
    repos: 8,
    starCount: '42k+',
    topRepo: 'vllm-project/vllm',
    topRepoStars: '42k',
    keyCapabilities: [
      'PagedAttention — GPU memory efficiency',
      'Continuous batching — high-throughput serving',
      'Recipes — model deployment configurations',
      'OpenAI-compatible API — drop-in serving',
      'Multi-GPU distributed serving',
    ],
    a11oyAbsorption: 'vLLM Recipes → A11oy Governed Inference Recipes (model + task + domain + Covenant policy + Proof Chain — composable governance-first configurations)',
    a11oyPrimitive: 'Governed Inference Recipes',
    status: 'surpassed',
  },
];

export const ORIGINAL_INNOVATIONS: OriginalInnovation[] = [
  {
    name: 'Shadow Council',
    tagline: 'Adversarial deliberation before commitment',
    desc: 'Every high-stakes output is challenged by an adversarial Contrarian — a red-team model that probes for logical flaws, data gaps, biased assumptions, and regulatory risks before the result reaches the user. If severity exceeds threshold, the output is revised or blocked.',
    primitiveId: 'shadow-council',
    noOneElse: 'No AGI platform runs adversarial multi-model deliberation as a standard pre-delivery gate on every inference.',
  },
  {
    name: 'Coalition Intelligence',
    tagline: 'Ad-hoc multi-agent consensus with dissent logging',
    desc: 'Instead of routing to one agent, the orchestrator forms ad-hoc coalitions of 2–4 domain specialists with a shared scratchpad. Agents challenge each other\'s intermediate conclusions and produce a consensus with formal dissent logging. Dissolved after each query.',
    primitiveId: 'coalition',
    noOneElse: 'No platform offers governed, dissolve-on-completion agent coalitions with cryptographic scratchpad and minority dissent records.',
  },
  {
    name: 'Consciousness Layer',
    tagline: 'Cognitive workspace + metacognitive monitoring',
    desc: 'A full cognitive architecture: inner monologue (dialectical self-reasoning), cognitive workspace (GWT-based attention and working memory), metacognitive monitor (certainty assessment, hallucination risk), predictive processing, and dream consolidation for long-term pattern synthesis.',
    primitiveId: 'consciousness',
    noOneElse: 'No production AGI system provides a real metacognitive layer that monitors its own reasoning quality and uncertainty in real time.',
  },
  {
    name: 'Covenant Policy',
    tagline: 'Real-time policy-as-code gates on every inference',
    desc: 'Organization-level governance policies — who can approve, what the agent can read/write/execute, when it must pause for human review — enforced at the platform layer before any action executes. Not an audit log. A pre-execution gate.',
    primitiveId: 'covenant',
    noOneElse: 'No competitor enforces governance at inference time as a hard gate rather than a soft post-hoc audit.',
  },
  {
    name: 'Outcome Graph',
    tagline: 'Closed-loop real-world consequence feedback',
    desc: 'The Outcome Graph records the real-world consequence of every agent decision and feeds it back to calibrate future confidence scores, model routing weights, and agent evaluation benchmarks. Every decision learns from what actually happened.',
    primitiveId: 'outcome-graph',
    noOneElse: 'No platform closes the feedback loop from agent action to real-world outcome and uses it to continuously recalibrate the inference layer.',
  },
  {
    name: 'Decision Provenance',
    tagline: 'End-to-end cryptographic lineage from signal to outcome',
    desc: 'Complete, tamper-resistant lineage across every link in a multi-agent chain: signal origin, enrichment, model inference, governance verdict, human approval, execution, and real-world outcome. Cryptographically hashed at each step. Queryable by actor, domain, or decision.',
    primitiveId: 'provenance',
    noOneElse: 'No AGI platform provides cryptographic, end-to-end decision lineage across multi-agent chains that is both tamper-resistant and queryable by auditors.',
  },
];

export const COMPETITORS: CompetitorProfile[] = [
  {
    name: 'OpenAI',
    tagline: 'Agentic execution at scale',
    repos: 243,
    keyStrength: 'Full-stack agentic OS: GPT-5.1 + Codex + Agents SDK + Swarm patterns',
    absorbed: [
      'Codex CLI — terminal-based coding agent → a11oy Terminal (governed, proof chain)',
      'Agents SDK — multi-agent orchestration → a11oy Agent Mesh (with governance gates)',
      'Swarm — lightweight multi-agent patterns → a11oy Workcells (replay, sovereign audit)',
      'Evals — model evaluation framework → a11oy Mirror Eval (continuous, governed)',
      'Codex Action — CI/CD GitHub Action → a11oy Action (proof chain on every commit)',
      'Deep Research — multi-source synthesis → a11oy Deep Research (governed pipeline)',
    ],
    gap: 'No governance layer. No proof chain. No enterprise audit trail. No covenant enforcement.',
  },
  {
    name: 'Anthropic',
    tagline: 'Safe autonomous coding agents',
    repos: 47,
    keyStrength: 'Claude Code + sustained reasoning + tool control + enterprise reliability',
    absorbed: [
      'Claude Code — agentic coding CLI (118k stars) → a11oy Terminal (governed, Chronicle memory)',
      'Claude Agent SDK — Python agent framework → a11oy SDK (multi-language, governed)',
      'Claude Code Action — GitHub CI integration → a11oy Action (proof chain, covenant)',
      'Skills library — agent capability plugins → a11oy Skills Library (166+ governed plugins)',
      'Constitutional AI — alignment via principles → a11oy Covenant (org-level policy enforcement)',
      'Tool Control — granular tool permissions → a11oy Connector Firewall (policy-enforced)',
    ],
    gap: 'Single model locked. No multi-model routing. No operational ontology. No cross-domain intelligence.',
  },
  {
    name: 'Google DeepMind',
    tagline: 'Research depth meets multimodal intelligence',
    repos: 387,
    keyStrength: 'Gemini 2.5 Pro + ADK + Deep Research + scientific reasoning',
    absorbed: [
      'Gemini CLI — terminal AI agent (102k stars) → a11oy Terminal (governed, multi-model)',
      'ADK — agent development kit → a11oy Agent Mesh (governed superset)',
      'Deep Research Agent — autonomous research → a11oy Deep Research (governed, proof chain)',
      'DeepSearchQA — research benchmarks → a11oy Mirror Eval (continuous benchmarking)',
      'Multimodal context — text/audio/image/video/code → a11oy Model Router (multi-modal, governed)',
    ],
    gap: 'Research-focused, not operational. No enterprise workflow integration. No proof chain. No real-time governance.',
  },
  {
    name: 'Meta',
    tagline: 'Open-source model strategy',
    repos: 12,
    keyStrength: 'Llama Stack + open weights + local/private deployment',
    absorbed: [
      'Llama Stack — agentic application platform → a11oy supports Llama via Model Router',
      'Llama Agentic System — E2E agent framework → a11oy Agent Mesh (governed superset)',
      'Llama Cookbook — community integrations → a11oy Cookbook (governed recipes)',
      'Open weights — private deployment → a11oy Sovereign mode (on-premise, air-gapped)',
      'Llama Guard — safety classifier → a11oy Cyber Safety (multi-layer, covenant-enforced)',
    ],
    gap: 'Models without platform. No enterprise workflow. No operational ontology. No proof chain. No governance layer.',
  },
  {
    name: 'vLLM Project',
    tagline: 'High-throughput LLM inference serving',
    repos: 8,
    keyStrength: 'PagedAttention + continuous batching + OpenAI-compatible serving + recipes',
    absorbed: [
      'vLLM recipes — model config templates → a11oy Governed Inference Recipes (with Covenant + Proof Chain)',
      'PagedAttention — GPU memory efficiency → a11oy Model Router (efficiency-aware routing)',
      'Continuous batching — throughput → a11oy Inference Layer (governed throughput)',
      'OpenAI-compatible API — drop-in serving → a11oy governed serving layer',
    ],
    gap: 'Serving engine only. No governance. No proof chain. No policy enforcement. No multi-domain agent intelligence.',
  },
  {
    name: 'Palantir',
    tagline: 'Operational ontology for enterprises',
    repos: 89,
    keyStrength: 'AIP + Foundry + Ontology SDK + Agent Studio + enterprise decision-making',
    absorbed: [
      'Foundry Ontology — enterprise data graph → a11oy Outcome Graph (AI-native, not legacy ETL)',
      'AIP Logic — no-code LLM functions → a11oy Workcells (code-first, governed, replayable)',
      'Agent Studio — enterprise AI agents → a11oy Agent Mesh (multi-model, proof chain)',
      'OSDK — ontology query SDK → a11oy SDK (TypeScript/Python, real-time, governed)',
      'MCP integration — external agent connectivity → a11oy Connector Firewall (governed MCP)',
    ],
    gap: 'Closed ecosystem. Government-first, enterprise-second. No open model support. Legacy architecture wrapped in AI.',
  },
];

export const ABSORBED_REPOS: AbsorbedCapability[] = [
  { source: 'OpenAI', repo: 'openai/codex', stars: '28k', capability: 'Terminal coding agent with cloud sandbox', a11oyEquivalent: 'a11oy Terminal — governed, proof chain, 5-tier memory', governed: true, status: 'surpassed' },
  { source: 'OpenAI', repo: 'openai/openai-agents-python', stars: '18k', capability: 'Multi-agent orchestration SDK', a11oyEquivalent: 'a11oy Agent Mesh — governed, sovereign replay, covenant', governed: true, status: 'surpassed' },
  { source: 'OpenAI', repo: 'openai/swarm', stars: '21k', capability: 'Lightweight multi-agent patterns', a11oyEquivalent: 'a11oy Workcells — stateful, replayable, approval gates', governed: true, status: 'surpassed' },
  { source: 'OpenAI', repo: 'openai/evals', stars: '16k', capability: 'Model evaluation framework', a11oyEquivalent: 'a11oy Mirror Eval — continuous, governed, benchmarked', governed: true, status: 'surpassed' },
  { source: 'OpenAI', repo: 'openai/codex-action', stars: '2k', capability: 'GitHub CI/CD action', a11oyEquivalent: 'a11oy Action — proof chain on every commit', governed: true, status: 'surpassed' },
  { source: 'OpenAI', repo: 'openai/whisper', stars: '72k', capability: 'Speech recognition', a11oyEquivalent: 'a11oy Voice — governed transcription, PII filtering', governed: true, status: 'absorbed' },
  { source: 'Anthropic', repo: 'anthropics/claude-code', stars: '118k', capability: 'Agentic coding CLI', a11oyEquivalent: 'a11oy Terminal — multi-model, Chronicle memory, governed', governed: true, status: 'surpassed' },
  { source: 'Anthropic', repo: 'anthropics/claude-code-action', stars: '8k', capability: 'GitHub Actions for Claude', a11oyEquivalent: 'a11oy Action — covenant enforcement, proof chain', governed: true, status: 'surpassed' },
  { source: 'Anthropic', repo: 'anthropics/skills', stars: '3k', capability: 'Agent skills library', a11oyEquivalent: 'a11oy Skills Library — 166+ governed plugins', governed: true, status: 'surpassed' },
  { source: 'Google', repo: 'google-gemini/gemini-cli', stars: '102k', capability: 'Terminal AI agent', a11oyEquivalent: 'a11oy Terminal — governed, multi-model, proof chain', governed: true, status: 'surpassed' },
  { source: 'Google', repo: 'google-deepmind/gemini-robotics-sdk', stars: '5k', capability: 'Robotics agent framework', a11oyEquivalent: 'a11oy Agent Mesh — software-defined agents', governed: true, status: 'absorbed' },
  { source: 'Microsoft', repo: 'microsoft/agent-framework', stars: '12k', capability: 'Multi-agent orchestration (MAF)', a11oyEquivalent: 'a11oy Agent Mesh — governed, sovereign, covenant', governed: true, status: 'surpassed' },
  { source: 'Microsoft', repo: 'microsoft/autogen', stars: '38k', capability: 'Multi-agent conversations', a11oyEquivalent: 'a11oy Workcells — stateful, proof chain, replay', governed: true, status: 'surpassed' },
  { source: 'Meta', repo: 'meta-llama/llama-stack', stars: '14k', capability: 'Agentic application platform', a11oyEquivalent: 'a11oy supports Llama via Model Router — governed', governed: true, status: 'absorbed' },
  { source: 'Meta', repo: 'meta-llama/llama-agentic-system', stars: '8k', capability: 'E2E agent framework', a11oyEquivalent: 'a11oy Agent Mesh — governed superset', governed: true, status: 'surpassed' },
  { source: 'Meta', repo: 'meta-llama/llama', stars: '73k', capability: 'Open model weights', a11oyEquivalent: 'a11oy Model Router — routes to Llama + 5 other providers', governed: true, status: 'absorbed' },
  { source: 'vLLM', repo: 'vllm-project/vllm', stars: '42k', capability: 'High-throughput LLM serving + recipes', a11oyEquivalent: 'a11oy Governed Inference Recipes — model + task + domain + Covenant + Proof Chain', governed: true, status: 'surpassed' },
];

export const A11OY_UNIQUE = [
  { name: 'Proof Chain Architecture', desc: 'Cryptographic proof on every agent action. No other platform has tamper-proof, verifiable audit trails at the execution layer. Not bolted on — built in.', status: 'unique' },
  { name: 'Chronicle Memory (5-Tier)', desc: 'Chronicle, Working, Episodic, Semantic, Procedural — five memory tiers that give agents persistent, replayable, queryable context across sessions. No one else has this.', status: 'unique' },
  { name: 'Cognitive Forecasting', desc: 'Predict outcomes before execution. Regression risk, delivery timelines, cost impact, security exposure — with confidence intervals. Not just execution — foresight.', status: 'unique' },
  { name: 'Covenant Enforcement', desc: 'Organization-level governance policies that override everything. What the agent can see, modify, approve, and deploy — defined once, enforced everywhere, cryptographically proven.', status: 'unique' },
  { name: 'Governed Autonomy Framework', desc: 'The only platform that treats governance not as a constraint but as the product. Every competitor adds safety after the fact. a11oy builds from governance up.', status: 'unique' },
  { name: 'Sovereign Replay', desc: 'Replay any agent session with full proof — every keystroke, model call, reasoning chain, and decision. Tamper-resistant. Cryptographically verifiable. No competitor offers this.', status: 'unique' },
  { name: 'Multi-Model Governed Routing', desc: 'GPT-5.1, Claude 4, DeepSeek V4, Qwen 3.6, Llama 4, HuggingFace Hub — best model per task, all governed by the same covenant. No provider lock-in. No competitor routes this broadly.', status: 'unique' },
  { name: 'Outcome Graph', desc: 'Live causal graph connecting every agent action to business outcomes. Not dashboards — live decision intelligence that shows what happened, why, and what to do next.', status: 'unique' },
];

export const CONVERGENCE_STATS = {
  reposAbsorbed: 17,
  totalStars: '555k+',
  competitors: 6,
  uniqueCapabilities: 8,
  governedFeatures: 'all',
  modelProviders: 6,
};
