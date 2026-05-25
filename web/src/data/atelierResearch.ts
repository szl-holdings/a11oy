export type CompetitiveCategory = 'hosting' | 'marketplace' | 'framework' | 'agent-builder';

export interface CompetitiveEntry {
  platform: string;
  category: CompetitiveCategory;
  strengths: string[];
  weaknesses: string[];
  atelierAdvantage: string;
  govGap: string;
}

export const COMPETITIVE_RESEARCH: CompetitiveEntry[] = [
  {
    platform: 'Hugging Face Spaces',
    category: 'hosting',
    strengths: [
      'Massive community gallery with browse-and-fork discovery',
      'ZeroGPU burst inference for low-cost ML demos',
      'First-class Gradio and Streamlit integration',
      'Model and dataset cards co-located with deployable demos',
      'Public embed support via iframes',
    ],
    weaknesses: [
      'Ranking is popularity-driven (likes, downloads) — gameable and uncorrelated with safety',
      'No constitutional binding — Spaces can take any action a developer ships',
      'No proof chain or cryptographic audit trail',
      'No tenant context, audience tiers, or human-approval hierarchy',
      'No cross-domain signal mesh between Spaces',
    ],
    atelierAdvantage:
      'Atelier replaces popularity ranking with governance score, audit completeness, and proof score — every Space earns its rank by behaving well, not by going viral.',
    govGap:
      'Zero governance enforcement layer — Spaces are untrusted by default and there is no way to bind a Space to a constitution, approval gate, or evidence requirement.',
  },
  {
    platform: 'Replicate',
    category: 'hosting',
    strengths: [
      'Versioned model artifacts via Cog containers',
      'Clean prediction REST API with webhook callbacks',
      'Cold-start GPU scheduling tuned for inference',
      'Fine-tuning pipelines as a managed product',
    ],
    weaknesses: [
      'Stateless model endpoints — no agent loop, no memory, no policy layer',
      'No human-in-the-loop approval primitives',
      'No proof chain — predictions vanish after the response is returned',
      'No cross-tenant or cross-vertical signal awareness',
    ],
    atelierAdvantage:
      'Spaces are governed agents with proof chains and approval gates — not stateless prediction endpoints. Every output is policy-checked and replayable from the evidence ledger.',
    govGap:
      'No constitution, no approval policy, no evidence requirements — Replicate treats models as pure functions and leaves all governance to the caller.',
  },
  {
    platform: 'Modal',
    category: 'framework',
    strengths: [
      'Serverless GPU with decorator-based Python deployment',
      'Ephemeral sandboxes for isolated execution',
      'Scheduled functions and parallel fan-out execution',
      'Cost-per-second GPU billing with fast cold starts',
    ],
    weaknesses: [
      'Pure infrastructure layer — no agent, governance, or UI primitives',
      'Sandbox isolation is process-level, not policy-level',
      'No discovery surface, no marketplace, no embed model',
      'No notion of tenant, audience tier, or constitution',
    ],
    atelierAdvantage:
      'Atelier execution is governance-first: every sandbox is constitutionally-scoped, MirrorEval-scored, and proof-chained — Modal stops at compute, Atelier delivers a governed agent surface on top.',
    govGap:
      'Governance is entirely the user’s responsibility — Modal provides no policy enforcement, evidence retention, or approval hierarchy out of the box.',
  },
  {
    platform: 'Vercel v0',
    category: 'framework',
    strengths: [
      'Generative UI streaming via the AI SDK and React Server Components',
      'Tight integration with Next.js and the Vercel deployment surface',
      'useChat and useCompletion hooks for fast frontend wiring',
      'Strong tool-call orchestration and streaming UX patterns',
    ],
    weaknesses: [
      'Frontend-first — no enterprise audit trail or tenant isolation',
      'No constitution layer; tool calls are governed by ad-hoc system prompts',
      'No cross-domain signal mesh; no governed marketplace',
      'No human-approval hierarchy or audience tier gating',
    ],
    atelierAdvantage:
      'Atelier Spaces are enterprise-grade governed agents with full audit trails — not generative UI components. Every tool call is policy-checked and proof-chained, and embeds carry tenant context across origins.',
    govGap:
      'No formal governance envelope — v0 produces UI, not policy. Tool execution relies on prompt discipline rather than enforced constitutional capability lists.',
  },
  {
    platform: 'Poe',
    category: 'marketplace',
    strengths: [
      'Polished consumer marketplace with creator monetization',
      'Multi-bot chat and per-bot knowledge files',
      'Subscription-gated premium bots and revenue share',
      'Frictionless authoring for non-technical creators',
    ],
    weaknesses: [
      'Consumer-first — no tenant isolation, no enterprise governance',
      'No proof chain, no MirrorEval, no approval gates',
      'Bots can hallucinate freely with no enforced evidence requirements',
      'No cross-domain or cross-tenant signal subscription model',
    ],
    atelierAdvantage:
      'Spaces are constitutionally-bound enterprise agents with proof chains. Atelier swaps consumer virality for sovereign governance — privileged actions require tenant + human approval.',
    govGap:
      'No governance layer at all — Poe is a chatbot store, with no concept of constitutions, evidence, or human approval hierarchies.',
  },
  {
    platform: 'OpenAI GPTs',
    category: 'agent-builder',
    strengths: [
      'Guided builder UX with knowledge files and Actions (OpenAPI)',
      'GPT Store discovery surface and creator monetization',
      'Tight ChatGPT integration and fast time-to-publish',
      'Image generation and code interpreter built in',
    ],
    weaknesses: [
      'Locked to a single model family',
      'System-prompt governance is brittle and easily bypassed',
      'No cryptographic proof chain or external audit verification',
      'No cross-vertical signal mesh and no tenant-bound embed model',
    ],
    atelierAdvantage:
      'Atelier Spaces are model-agnostic (Anthropic, OpenAI, Gemini, Groq, DeepSeek) and run through a governed model router. Constitution DSL is more expressive and enforceable than GPT system prompts, and proof chains persist across runs.',
    govGap:
      'Governance is a system-prompt convention, not an enforced contract — Actions can be invoked without policy checks, evidence requirements, or approval gates.',
  },
  {
    platform: 'Dify',
    category: 'agent-builder',
    strengths: [
      'Visual drag-and-drop agent and workflow builder',
      'RAG pipelines with built-in knowledge bases',
      'API publish target and team workspace primitives',
      'Self-hosted open-source option',
    ],
    weaknesses: [
      'Governance is configured per-node and easily skipped',
      'No constitutional binding across an entire agent surface',
      'No cryptographic proof chain or external audit attestation',
      'No native cross-domain signal subscriptions',
    ],
    atelierAdvantage:
      'Governance is constitutionally enforced, not configured per-node. Every Atelier Space carries a proof chain, MirrorEval scoring, and a human-approval gate hierarchy by default — not as bolt-ons.',
    govGap:
      'Per-node guardrails only — there is no agent-wide constitution, no enforced evidence requirements, and no audit-grade proof retention.',
  },
  {
    platform: 'AWS Bedrock Agents',
    category: 'agent-builder',
    strengths: [
      'Fully managed agent orchestration on AWS',
      'Action groups via Lambda and knowledge bases via OpenSearch',
      'Guardrails layer for content filtering and PII redaction',
      'Multi-agent collaboration and session management',
    ],
    weaknesses: [
      'AWS infrastructure lock-in and Lambda-only action execution',
      'Audit trail lives inside CloudWatch — not externally verifiable',
      'No portable, human-readable constitution DSL',
      'No cross-vertical NEXUS signal mesh',
    ],
    atelierAdvantage:
      'Atelier Spaces are portable across infrastructure, the constitution DSL is human-readable and auditable, and proof chains are cryptographic and externally verifiable — not AWS-internal log entries.',
    govGap:
      'Guardrails are content-level filters, not a constitutional capability/prohibition contract — and audit evidence is locked inside the AWS tenant rather than cryptographically attestable.',
  },
];

export const ATELIER_DIFFERENTIATORS: string[] = [
  'Every Space is bound to a human-readable constitution DSL with explicit capabilities and prohibitions',
  'Cryptographic proof chain on every run — externally verifiable, not vendor-locked audit logs',
  'Native cross-domain NEXUS signal subscriptions between Spaces and verticals',
  'Tenant-aware embed model: Spaces carry tenant context across origins via secured postMessage',
  'Audience tier gating (internal / enterprise / public) enforced at authoring time, not runtime hope',
  'Governance leaderboards ranked by proof score and audit completeness — not likes or downloads',
  'Multi-tier human approval hierarchy is a first-class primitive, not a prompt convention',
  'Model-agnostic governed router (Anthropic, OpenAI, Gemini, Groq, DeepSeek) with policy-checked routing',
  'Vertical-tuned templates with pre-bound constitutions for real-estate, legal, cyber, maritime, defense, executive',
  'MirrorEval scoring and evidence requirements are enforced before any output leaves the Space',
];

export const RESEARCH_LAST_UPDATED: string = '2026-05-04';
