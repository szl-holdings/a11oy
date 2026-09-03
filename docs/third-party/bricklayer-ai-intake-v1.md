# Bricklayer.ai → Aegis Proof Cells clean-room intake

**Observed:** 2026-09-03  
**Disposition:** `REFERENCE_ONLY_CLEAN_ROOM`  
**Affiliation:** none  
**External implementation imported:** no  
**Bricklayer source code copied:** no

## Purpose

This record separates public architectural observation from software reuse. Bricklayer.ai
publishes product and engineering descriptions of a coordinated AI workforce for security
operations. No official public Bricklayer implementation repository was identified in the
bounded GitHub search performed for this build. Public website content is not a software
license and is not treated as permission to copy source, prompts, procedures, text, visual
identity, trademarks, or private platform behavior.

Aegis Proof Cells is therefore an original SZL implementation. It adopts only abstract
operating ideas that are common to modern security operations: role specialization,
evidence-preserving handoffs, reusable procedures, tenant segmentation, independent policy
enforcement, analyst oversight, and auditable outcomes.

## Public Bricklayer architectural observations

1. **Coordinated specialist workforce**  
   Source: https://www.bricklayer.ai/platform/  
   Observation: specialist agents are assembled around security goals and approved
   procedures, with human oversight and auditable activity.

2. **Multi-Agent Context Engineering (MACE)**  
   Source: https://www.bricklayer.ai/insights/multi-agent-context-engineering-mace-the-discipline-behind-investigative-artificial-intelligence-ai/  
   Published: 2025-09-26  
   Observation: investigations need context containers that accumulate evidentiary,
   procedural, investigative, decision, and output context across handoffs.

3. **Insights and Insight Groups**  
   Source: https://www.bricklayer.ai/insights/introducing-insight-groups-structuring-context-for-the-coordinated-ai-soc/  
   Published: 2026-04-20  
   Observation: investigation knowledge is more reusable when it is structured into
   discrete, typed units rather than buried in unstructured task output.

4. **Agentic policy enforcement**  
   Source: https://www.bricklayer.ai/insights/governing-ai-agents-announcing-our-first-patent-in-agentic-policy-enforcement/  
   Published: 2026-03-24  
   Observation: an independent control layer is required when agents can access tools,
   data, and multi-step procedures.

5. **Shared Agentic Library**  
   Source: https://www.bricklayer.ai/insights/introducing-the-shared-agentic-library/  
   Published: 2026-06-03  
   Observation: proven operational capabilities should be packaged as reusable, governed,
   versioned assets.

6. **Credential labels and tenant segmentation**  
   Source: https://www.bricklayer.ai/insights/bricklayer-ai-introduces-credential-labels-and-azure-sentinel-support/  
   Published: 2025-02-21  
   Observation: one procedure may operate across customers or business units only when
   credentials and scope remain explicitly segmented.

7. **Long-term memory and dynamic procedures**  
   Source: https://www.bricklayer.ai/insights/bricklayer-ai-introduces-guided-onboarding-long-term-memory-and-dynamic-procedures-creating-humanlike-intelligence-in-their-ai-agents-built-for-security-operations-centers/  
   Published: 2025-04-28  
   Observation: reusable operational learning and goal-derived procedures are product
   primitives, but retained memory must remain tenant-, rights-, and purpose-bound.

8. **Curated public and internal context sources**  
   Source: https://www.bricklayer.ai/insights/bricklayer-ai-introduces-public-blog-support-and-csv-datastores-to-strengthen-autonomous-investigations-and-report-generation/  
   Published: 2025-03-25  
   Observation: public and organization-specific sources need explicit curation and
   provenance rather than indiscriminate retrieval.

## SZL/Aegis transformation

| Public architectural signal | Original Aegis expression |
|---|---|
| Coordinated workforce | Eleven bounded **Proof Cells** |
| Context containers | Five typed **Evidence Group** classes |
| Structured insights | Source-labelled **Evidence Atoms** |
| Reusable library | Versioned **Procedure Capsules** |
| Credential labels | Secret-free **Tenant Passport connector labels** |
| Policy enforcement | Deny-by-default **Covenant Policy** |
| Audit trail | Deterministic **Proof Chain** receipt |
| Institutional memory | Explicit **Outcome Graph** and **Debrief Packet** |
| Human collaboration | Approval-gated remediation planning |
| Platform actions | Disabled effectors in the public workbench |

The resulting system is not a Bricklayer clone. It uses different names, schemas, interface,
governance, formulas, evidence semantics, and deployment contracts.

## Public standards and code references

The implementation does not vendor these repositories. They provide standards and
architecture references at immutable public revisions:

| Project | Revision | License treatment | Use |
|---|---|---|---|
| `ocsf/ocsf-schema` | `2c61b24c2f21d2ea316fca7d640bb37df3374011` | Apache-2.0 | Normalized defensive-event semantics |
| `mitre-attack/attack-stix-data` | `6cda5ad8462c79e14fbb872f4e09059b18e0cfc4` | Terms review required | Threat-technique context |
| `open-telemetry/opentelemetry-specification` | `eec6fadba46a5002f55ff88ce4405d58a1aa4aec` | Apache-2.0 | Trace and evidence-correlation semantics |
| `open-policy-agent/opa` | `92da7b47f05488487dcbdf1625e405d9141c6c38` | Apache-2.0 | Policy-decision architecture reference |

No source from these projects is copied by the Aegis Proof Cells page or simulator.

## Security and truth boundaries

The public workbench:

- accepts no credential values or secrets;
- sends no case input to external services;
- calls only same-origin, read-only A11oy evidence routes;
- denies cross-tenant scope;
- denies offensive intrusion, exploitation, credential theft, evasion, persistence,
  destructive activity, and malware deployment;
- requires human approval for containment or remediation proposals;
- provides no production authorization;
- binds no effector and performs no external write;
- labels all planning scores `MODELED`;
- caps modeled confidence at `0.97`;
- emits a deterministic SHA-256 client receipt that is explicitly unsigned and unpersisted;
- reports missing or stale evidence as `UNAVAILABLE` or `ABSTAINED`.

## Runtime assets

```text
/static/3d/aegis-proof-cells.html
/static/3d/aegis-proof-cells/app.mjs
/static/3d/aegis-proof-cells/styles.css
/static/3d/aegis-proof-cells/registry.json
```

The files ship through the existing `COPY console/ ./static/` canonical A11oy image contract.
A dedicated post-deployment workflow verifies exact source identity, HTTP behavior, local
asset digests, registry governance, and zero-effectors state.
