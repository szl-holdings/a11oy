<!-- doctrine-scanner-exempt: legacy live-product surface; rename tracked as separate engineering debt — see scripts/check-doctrine-v6.mjs header. -->
# A11oy Research & Reference Lineage

## Purpose
This document traces which open-source projects and publications influenced A11oy's design, what specific idea each contributed, and how we re-implemented it in our own voice.

---

## Agentic AI Runtimes & Orchestration

### Anthropic Constitutional AI / Responsible Scaling Policy
- **Link**: https://www.anthropic.com/research/constitutional-ai-harmlessness-from-ai-feedback
- **Idea borrowed**: The notion of a constitution as a hierarchical set of principles that govern model behavior at inference time, not just training time.
- **Our implementation**: A11oy's Constitution is a runtime-enforced contract, not just documentation. Every agent action cites which article it honored or refused. We extended this with the new **Adversarial Covenants** chapter (Article IX) that governs what the predictive swarm is allowed to simulate — matching Anthropic's responsible scaling commitments but in an operational, proof-chained form.

### Anthropic Mythos / Agent Research
- **Link**: https://www.anthropic.com/research (agent architecture papers)
- **Idea borrowed**: Structured tool use, multi-step reasoning with intermediate artifacts, and the idea of a "proof chain" that lets humans audit each reasoning step.
- **Our implementation**: Praxis (A11oy's AI assistant) emits a proof packet for every answer — model, lane, latency, cost, tool calls, trust score. The Praxis toolbar implements named first-class actions (Analyze, Search the Web, GitHub) rather than unlabeled icons.

### LangGraph (LangChain)
- **Link**: https://github.com/langchain-ai/langgraph
- **Idea borrowed**: Cyclical graph-based agent workflows where state is passed explicitly between nodes, enabling loops, branches, and human-in-the-loop checkpoints.
- **Our implementation**: A11oy's Playbook Engine uses a similar node graph model (trigger → action → decision → gate → HITL → remediation) but adds covenant policy enforcement at each node boundary. Every policy-gated node produces a proof ledger entry.

### Microsoft AutoGen
- **Link**: https://github.com/microsoft/autogen
- **Idea borrowed**: Multi-agent conversations where specialized agents collaborate, with a human-proxy pattern for HITL integration.
- **Our implementation**: A11oy's Swarm Orchestrator assembles agent pools with explicit role assignments, bilateral scope approval for cross-agent tool sharing, and intelligence compartmentalization. The "governed adversary loop" in the Predictive Defense Cortex adapts AutoGen's multi-agent pattern with constitutional covenant gates.

### CrewAI
- **Link**: https://github.com/joaomdmoura/crewAI
- **Idea borrowed**: Task decomposition across a crew with defined roles — analyst, researcher, writer. Sequential and parallel task execution with crew-level context sharing.
- **Our implementation**: The Swarm Orchestrator's mission model (each agent has a role, progress bar, and inter-agent intelligence graph) is inspired by CrewAI's crew concept, but adds proof-ledger logging for every intelligence-sharing event.

### OpenDevin / SWE-agent
- **Link**: https://github.com/OpenDevin/OpenDevin
- **Idea borrowed**: Agentic code execution with sandboxing, environment state, and iterative action-observation loops.
- **Our implementation**: A11oy's Praxis GitHub tool operates in a read-only inspection mode — it can search repos and pull file context but cannot write code without explicit HITL approval, honoring Article II of the Constitution.

### Letta (MemGPT)
- **Link**: https://github.com/cpacker/MemGPT
- **Idea borrowed**: Agents with hierarchical memory — in-context, archival, and recall — enabling persistent, long-running agent identities.
- **Our implementation**: A11oy's memory layer separates agent working memory from the archival proof ledger. The Adversary Swarm agents maintain per-run memory of the digital twin's state while their outcomes are persisted in the cortex prediction database.

### DSPy
- **Link**: https://github.com/stanfordnlp/dspy
- **Idea borrowed**: Declarative, optimized prompt programming — signatures, modules, and automatic optimization.
- **Our implementation**: A11oy's model router uses a lane-based dispatch (fast / sovereign / reason / code) that mirrors DSPy's module philosophy. Each lane has its own signature and the router optimizes selection based on cost, latency, and trust requirements.

### smolagents (Hugging Face)
- **Link**: https://github.com/huggingface/smolagents
- **Idea borrowed**: Minimal, auditable agent loops with code execution as a first-class tool.
- **Our implementation**: A11oy's tool boundary enforcement (connector firewall + MCP token scoping) mirrors smolagents' philosophy of small, auditable tool surfaces. We extended it with zero-trust credential rotation.

### Mastra
- **Link**: https://github.com/mastraai/mastra
- **Idea borrowed**: TypeScript-native agentic framework with built-in memory, tracing, and integration connectors.
- **Our implementation**: A11oy's TypeScript-first architecture and the proof chain API shape are inspired by Mastra's developer experience. Our implementation adds governance gates not present in Mastra.

---

## Frontier Safety & Governance

### NIST AI Risk Management Framework (AI RMF)
- **Link**: https://airc.nist.gov/docs/AI_RMF_Playbook.pdf
- **Idea borrowed**: GOVERN → MAP → MEASURE → MANAGE lifecycle with organizational accountability for AI risk.
- **Our implementation**: A11oy's four governance primitives (Constitution, Approval Queue, Proof Ledger, Model Router) directly mirror the RMF quadrant. The Constitution is the GOVERN layer; the Proof Ledger is the MEASURE layer.

### MITRE ATLAS
- **Link**: https://atlas.mitre.org/
- **Idea borrowed**: A structured adversarial ML threat catalog analogous to ATT&CK but for AI systems. 84 techniques across the ML attack lifecycle.
- **Our implementation**: A11oy's ATLAS Shield surface maps each of the 84 techniques to a specific defense layer. The Adversary Swarm agents are each loaded with ATLAS technique profiles.

### OWASP LLM Top 10 / Agentic Security Initiative
- **Link**: https://owasp.org/www-project-top-10-for-large-language-model-applications/
- **Idea borrowed**: Prompt injection, insecure output handling, overreliance, training data poisoning — the canonical risk taxonomy for LLM deployments.
- **Our implementation**: A11oy's ATLAS Shield OWASP Agentic section maps all 10 risks to specific runtime controls. Agent Zero Trust's MCP token scoping directly addresses OWASP A01 (Prompt Injection) and A06 (Excessive Agency).

### AISI Evaluation Methodology (UK AI Safety Institute)
- **Link**: https://www.gov.uk/government/publications/aisi-approach-to-evaluations
- **Idea borrowed**: Structured capability evaluations before deployment, with defined threat scenarios and red-teaming protocol.
- **Our implementation**: A11oy's MirrorEval and the Alignment Review Gate are modeled on AISI's eval methodology — structured dimensions, threshold gates, mandatory re-evaluation on model substitution (Article VI).

---

## Predictive Defense Cortex — Specific Lineage

### Swarm-vs-Twin Pattern
- **Inspired by**: Caldera's adversary emulation architecture (MITRE) + OpenAI Swarm's multi-agent coordination
- **Our twist**: Runs faster than wall-clock time in a sandboxed digital twin. Governed by Adversarial Covenants (Article IX) throughout. Every swarm step produces a proof packet.

### Prediction Ranking Model
- **Inspired by**: Elastic Detection Rules' severity × confidence scoring + Velociraptor's threat hunt scoring
- **Our twist**: Likelihood × Impact × Time-to-Exploit triple-factor ranking mapped to both ATT&CK and ATLAS techniques, with forward-looking horizon windows (24h / 72h / 168h).

### Pre-emptive Countermove Proposer
- **Inspired by**: TheHive + Cortex's automated response playbooks + Iron Dome's layered intercept doctrine
- **Our twist**: Every countermove is a covenant-gated Approval Queue item with the constitutional clause cited. The operator approves or denies from inside Sentra; the decision flows into a11oy's proof ledger.

### Adversarial Covenants (Article IX)
- **Inspired by**: Anthropic's Responsible Scaling Policy's capability thresholds + NIST AI RMF's GOVERN layer
- **Our twist**: Machine-readable covenant DSL clauses that govern what the swarm can simulate, what countermoves it can stage, and what evidence threshold triggers pre-emptive action. Fully editable, versioned, with diff history.
