# Sentra Research & Reference Lineage

## Purpose
This document traces which open-source projects and publications influenced Sentra's design, what specific idea each contributed, and how we re-implemented it in our own voice.

---

## Defensive (Blue Team / SOC) References

### Wazuh
- **Link**: https://github.com/wazuh/wazuh
- **Idea borrowed**: Host-based intrusion detection with agent-based telemetry collection, centralized log analysis, and active response.
- **Our implementation**: Sentra's Endpoint Mesh and EDR agent model mirrors Wazuh's agent enrollment pattern. The active response concept inspired the Governed Adversary Loop — but every response action is covenant-gated by a11oy rather than executing autonomously.

### Velociraptor
- **Link**: https://github.com/Velocidex/velociraptor
- **Idea borrowed**: Artifact-based threat hunting with VQL (Velociraptor Query Language) and hunt scoping against specific endpoint populations.
- **Our implementation**: Sentra's Threat Hunting surface uses a hunt-proposer / hunt-agent model inspired by Velociraptor's artifact library. Hunts are scoped to target populations and produce ranked findings. We re-implemented in a governed agentic pattern — a11oy Hunt Agents propose and execute rather than analysts writing VQL directly.

### TheHive + Cortex
- **Link**: https://github.com/TheHive-Project/TheHive
- **Idea borrowed**: Case management for SOC incidents with responder integration (Cortex analyzers/responders that chain automations).
- **Our implementation**: Sentra's Cases, Incidents, and Action Queue surfaces mirror TheHive's case model. The Cortex responder concept inspired the Governed Adversary Loop — attack proposals feed into a11oy's Approval Queue (the covenant gate), which is our version of Cortex's analyzer chain.

### OpenCTI
- **Link**: https://github.com/OpenCTI-Platform/opencti
- **Idea borrowed**: STIX/TAXII-based threat intelligence graph with entity relationships (threat actors, campaigns, TTPs, observables).
- **Our implementation**: Sentra's Threat Graph and STIX/TAXII surface adopt OpenCTI's entity model. The Future Threat Horizon maps predicted attacks to ATT&CK + ATLAS technique nodes in the same entity-relationship style.

### MISP (Malware Information Sharing Platform)
- **Link**: https://github.com/MISP/MISP
- **Idea borrowed**: Structured threat intelligence sharing with events, attributes, and galaxy clusters.
- **Our implementation**: Sentra's Intel Feed surface follows MISP's event model. The Weaponized Intel Feed aggregates threat intelligence in a structured catalog — OWASP Agentic, Unit 42, ATLAS techniques — similar to MISP galaxy clusters.

### Sigma + sigma-cli
- **Link**: https://github.com/SigmaHQ/sigma
- **Idea borrowed**: Generic detection rule format that can be compiled to any SIEM backend. Write once, run anywhere.
- **Our implementation**: Sentra's detection layer uses Sigma-inspired rule descriptions mapped to MITRE ATT&CK techniques. The Red Team Hub shows which Sigma-style detections fire when adversary emulation scenarios execute, closing the purple-team loop.

### Falco
- **Link**: https://github.com/falcosecurity/falco
- **Idea borrowed**: Runtime security for containers and Kubernetes using eBPF-based syscall monitoring with a flexible rule engine.
- **Our implementation**: Sentra's OT/ICS and workload monitoring surfaces take cues from Falco's runtime telemetry model. The Layered Intercept view's "workload" layer specifically covers runtime behavioral anomalies in the Falco tradition.

### OpenBAS (Open Breach and Attack Simulation)
- **Link**: https://github.com/OpenBAS-Platform/openbas
- **Idea borrowed**: Orchestrated attack simulations with scenario libraries, execution tracking, and automatic detection validation.
- **Our implementation**: Sentra's Red Team Hub scenario library is directly inspired by OpenBAS's approach. We modeled the scenario → execute → detect loop in a sandboxed/simulated mode, routing every scenario through a11oy's Governed Adversary Loop rather than executing live.

### Chainsaw
- **Link**: https://github.com/WithSecureLabs/chainsaw
- **Idea borrowed**: Rapid Windows event log analysis using Sigma rules and patterns to identify attack artifacts.
- **Our implementation**: Sentra's Forensics Timeline surface borrows Chainsaw's "rapid artifact identification from event streams" philosophy, adapted to the agentic context where a11oy Hunt Agents do the rapid first-pass analysis.

### Elastic Detection Rules
- **Link**: https://github.com/elastic/detection-rules
- **Idea borrowed**: Production-quality detection rule library with severity, confidence, and MITRE ATT&CK mappings maintained as code.
- **Our implementation**: Sentra's detection rule inventory follows Elastic's severity × confidence × technique mapping model. The Red Team Hub's purple-team view shows which detection rules fire for each emulated scenario — same data model, governed execution.

### Suricata / Zeek
- **Link**: https://suricata.io / https://zeek.org
- **Idea borrowed**: Network traffic analysis with signature (Suricata) and behavioral (Zeek) detection layers.
- **Our implementation**: Sentra's Layered Intercept "perimeter" layer conceptually sits on top of network-level detection modeled on Suricata/Zeek. The time-to-intercept metric at the perimeter layer is calibrated against the kind of telemetry these tools produce.

---

## Offensive (White-Hat Red Team / Adversary Emulation) References

### Caldera (MITRE)
- **Link**: https://github.com/mitre/caldera
- **Idea borrowed**: Automated adversary emulation using ATT&CK-mapped abilities, adversary profiles, and planners that chain abilities into operation sequences.
- **Our implementation**: Sentra's Red Team Hub scenario library is modeled after Caldera's ability/adversary/operation structure. Adversary profiles are loaded with real APT TTPs. Execution is **sandboxed/simulated** — no live exploits. Every launch goes through the Governed Adversary Loop (a11oy Approval Queue gate).

### Atomic Red Team
- **Link**: https://github.com/redcanaryco/atomic-red-team
- **Idea borrowed**: Library of atomic test techniques mapped to ATT&CK, each with defined prerequisites, executors, and detection guidance.
- **Our implementation**: Sentra's scenario library uses the Atomic Red Team concept — each scenario is a discrete, self-contained technique test with expected detections documented. The purple-team view shows which detections are expected to fire and which actually fired during a simulated run.

### Stratus Red Team
- **Link**: https://github.com/DataDog/stratus-red-team
- **Idea borrowed**: Cloud-specific adversary emulation with "detonate and cleanup" semantics for AWS, Azure, GCP attack techniques.
- **Our implementation**: Sentra's Digital Twin layer includes a cloud workload model where Stratus-inspired cloud attack scenarios can detonate against the synthetic twin. The "cleanup" semantic maps to a11oy's covenant-gated response that pre-positions defenses.

### Mythic C2
- **Link**: https://github.com/its-a-feature/Mythic
- **Idea borrowed**: Modular C2 framework with operator UI, agent profiles, task execution tracking, and callback graphs.
- **Our implementation**: Sentra's Red Team Hub task execution timeline borrows Mythic's operator workflow — select scenario, see execution steps, view callback/detection events. No live C2; all execution is against the digital twin.

### BloodHound CE
- **Link**: https://github.com/SpecterOps/BloodHound
- **Idea borrowed**: Active Directory attack path analysis using graph theory to surface privilege escalation paths.
- **Our implementation**: Sentra's Attack Path Viz surface borrows BloodHound's graph-based path analysis model, extended to identity-first zero-trust environments. The Future Threat Horizon maps predicted attack paths using the same graph traversal logic against the digital twin.

### Nuclei
- **Link**: https://github.com/projectdiscovery/nuclei
- **Idea borrowed**: Template-based vulnerability scanning with a large community template library covering CVEs, misconfiguration, and exposure checks.
- **Our implementation**: Sentra's Vulnerability Dashboard and Exposure Board surface vulnerability findings in a template/signature style similar to Nuclei. The Red Team Hub exposure scanning scenarios reference the same template taxonomy.

### PurpleSharp
- **Link**: https://github.com/mvelazc0/PurpleSharp
- **Idea borrowed**: Active Directory adversary simulation with purple-team telemetry correlation — run the attack, then verify the detection fired.
- **Our implementation**: The purple-team closed-loop model in Sentra is directly inspired by PurpleSharp's "simulate → verify detection" cycle. The Red Team Hub's side-by-side blue-team detection view shows exactly which sensors fired for each simulated technique.

### Prowler / ScoutSuite
- **Link**: https://github.com/prowler-cloud/prowler / https://github.com/nccgroup/ScoutSuite
- **Idea borrowed**: Cloud security posture management with multi-cloud compliance checks and risk scoring.
- **Our implementation**: Sentra's Compliance and Attack Surface Command surfaces follow Prowler/ScoutSuite's cloud CSPM model — continuous posture evaluation with control drift detection.

---

## Israeli Cyber Doctrine / Iron Dome–Inspired Layered Defense

### Iron Dome Doctrine (Public Writing)
- **Sources**: IAI/RAFAEL public briefings, JANES analysis, Foreign Policy and Lawfare articles on active multi-layer defense.
- **Idea borrowed**: Not the code — the *doctrine*: multiple intercept layers with decreasing response windows as threats approach. Layer 1 (long range) buys time for Layers 2-3. Each layer is optimized for a different threat class and has a defined time-to-intercept budget.
- **Our implementation**: Sentra's **Layered Intercept** view adopts this doctrine for the cyber domain: perimeter → identity → workload → data → response. Each layer has a time-to-intercept metric calibrated by the cortex's predictions ("if we did nothing, this attack would punch through Layer 2 in 4h"). The cortex's pre-emptive countermove proposals target the earliest feasible intercept layer.

### Multi-Layer Active Defense / Kill Chain Interception
- **Sources**: Lockheed Martin Cyber Kill Chain (public), Cisa's layered defense guidance, Air Defense literature.
- **Idea borrowed**: Intercept at the earliest phase — reconnaissance is cheaper to interdict than lateral movement. Deception assets placed along the predicted path force adversary to expose themselves at a layer where we have the intercept advantage.
- **Our implementation**: The Future Threat Horizon surfaces each predicted attack path with its current kill chain phase and the recommended intercept layer. Pre-emptive countermoves include deception asset placement along the predicted path — a direct implementation of the deception-first doctrine.

---

## Predictive Defense Cortex — Specific Lineage

### Digital Twin Concept
- **Inspired by**: Dragos OT asset modeling + AWS Digital Twin frameworks
- **Our twist**: A high-fidelity synthetic seed of assets, identities, workloads, and data that the adversary swarm attacks in sandboxed time-compression. Designed so real customers can later import CMDB / IdP / cloud inventory.

### Adversary Swarm Against the Twin
- **Inspired by**: Caldera's automated adversary emulation + MITRE ATT&CK threat actor profiles
- **Our twist**: Runs time-compressed (faster than wall clock). Each swarm agent carries a real APT profile (TTPs from ATT&CK). Governed by a11oy's Adversarial Covenants (Article IX) — the swarm cannot operate outside covenant boundaries.

### Future Threat Horizon UI
- **Inspired by**: DARPA's "predict the next move" threat intelligence framing + Palantir's forward-looking timeline interfaces
- **Our twist**: Not retrospective (what happened) but prospective (what will happen). Operators see attacks that *will be neutralized tomorrow*, not just attacks that *were neutralized yesterday*. Every prediction is replayable — click into the swarm run that produced it.

### Governed Adversary Loop
- **Inspired by**: TheHive + Cortex's response chain + Caldera's operation → collection cycle
- **Our twist**: Every attack proposal from the red team surface flows through a11oy's Approval Queue with constitutional clause citations. The loop is: Sentra proposes → a11oy reasons + covenants → operator approves → Sentra executes (simulated) → detections fire in SOC view → proof packet spans both apps.
