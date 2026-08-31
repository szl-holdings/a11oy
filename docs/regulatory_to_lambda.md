# Regulatory → Λ-Axis Mapping Reference
## Doctrine v6 · R3 Vertical Governance Receipts

> **Purpose**: Comprehensive cross-reference of all 10 Doctrine v6 Λ-axes to their primary regulatory grounding across the 10 vertical policy domains. Each axis lists 3–5 representative regulations with precise citations. Weight annotation (★ = high, ○ = medium, · = advisory).

---

## Doctrine v6 Λ-Axis Definitions

| ID  | Axis           | Description                                                            |
|-----|----------------|------------------------------------------------------------------------|
| Λ1  | Transparency   | Obligations to disclose AI system capabilities, limitations, and logic |
| Λ2  | Accountability | Assignment of legal and operational responsibility for AI decisions     |
| Λ3  | Privacy        | Protection of personal and sensitive data processed by AI systems      |
| Λ4  | Fairness       | Non-discrimination, equity, and representative coverage requirements   |
| Λ5  | Safety         | Prevention of physical, operational, and systemic harm                 |
| Λ6  | Security       | Protection against unauthorized access, adversarial manipulation       |
| Λ7  | Auditability   | Tamper-evident logging and verifiable record-keeping                   |
| Λ8  | Robustness     | Resistance to distribution shift, adversarial perturbation, failure    |
| Λ9  | Explainability | Human-interpretable rationale for AI outputs                           |
| Λ10 | Sovereignty    | Jurisdictional control over data and AI system deployment              |

---

## Λ1 — Transparency

**Core Obligation**: AI systems must disclose their nature, capabilities, limitations, and decision logic to affected parties and regulators.

| Regulation | Citation | Vertical | Weight | Mechanism |
|-----------|----------|----------|--------|-----------|
| EU AI Act Art. 13 — Transparency for deployers | Regulation (EU) 2024/1689 Art. 13 | LegalTech, Pharma | ★ mandatory | Instructions-for-use document; capabilities/limitations disclosure; IFU hash in receipt |
| GDPR Art. 5(1)(a) — Lawfulness and transparency | Regulation (EU) 2016/679 Art. 5(1)(a) | LegalTech, Academic | ★ mandatory | Privacy notice; algorithmic transparency statement; processing basis disclosure |
| SOX § 404 — Internal controls transparency | Pub. L. 107-204 § 404; 17 CFR § 240.13a-15(f) | Financial | ★ mandatory | ICFR documentation; AI model control evidence in Merkle DAG |
| DO-178C § 5.5 — Traceability | RTCA DO-178C § 5.5; SAE ARP4754B § 5.2 | Aviation | ★ mandatory | Requirements-to-code traceability matrix; receipt annotation |
| NIST SP 800-171 Rev 3 § 3.12.4 — System Security Plans | NIST SP 800-171 Rev 3 Control 3.12.4 | Defense | ○ mandatory | AI system security plan; architecture and provenance documentation |

**Λ1 Receipt Requirements**: Receipt chain entry must include `disclosure_hash` (SHA3-256 of disclosure document), `disclosure_type` enum, and `target_audience` field.

---

## Λ2 — Accountability

**Core Obligation**: Named human or institutional principals must be legally responsible for AI system decisions; accountability must be traceable through the receipt chain.

| Regulation | Citation | Vertical | Weight | Mechanism |
|-----------|----------|----------|--------|-----------|
| SOX § 302 — CEO/CFO certification | Pub. L. 107-204 § 302; 17 CFR § 240.13a-15 | Financial | ★ mandatory | Named signatory in receipt chain root; qualified electronic signature |
| COPE AI Authorship (2023) — Disclosure of AI use | COPE Position Statement (2023) | Academic | ★ mandatory | AI system version + inference timestamp in authorship disclosure receipt |
| eIDAS 2.0 Art. 25 — QES legal equivalence | Regulation (EU) 2024/1183 Art. 25 | LegalTech | ★ mandatory | QES via EUDIW; certificate hash in receipt leaf node |
| 21 CFR § 11.50 — Electronic signature manifestations | 21 C.F.R. § 11.50 | Pharma | ★ mandatory | Name, date/time, and signature meaning in receipt metadata |
| SAE J3016 Level 4 ADS accountability | SAE J3016_202104 § 3.14 | Automotive | ★ mandatory | ADS as accountable entity; scene hash + fallback state in decision receipt |

**Λ2 Receipt Requirements**: Receipt must carry `principal_id` (DID or X.509 distinguished name), `role` (operator/provider/deployer), `signature_algorithm`, and `delegation_chain` if accountability is delegated.

---

## Λ3 — Privacy

**Core Obligation**: Personal and sensitive data processed by AI systems must be subject to purpose limitation, data minimisation, consent, and access controls.

| Regulation | Citation | Vertical | Weight | Mechanism |
|-----------|----------|----------|--------|-----------|
| HIPAA 45 CFR § 164.502 — PHI use and disclosure | 45 C.F.R. § 164.502(a) | Healthcare | ★ mandatory | Minimum-necessary gating on AI inference; purpose-limited receipt |
| HIPAA 45 CFR § 164.514(b) — De-identification | 45 C.F.R. § 164.514(b) | Healthcare | ★ mandatory | Expert Determination or Safe Harbor; re-ID risk ≤ 0.05 |
| GDPR Art. 5 — Data protection principles | Regulation (EU) 2016/679 Art. 5(1)(c)(e) | LegalTech | ★ mandatory | Data minimisation; storage limitation; processing basis receipt |
| Common Rule 45 CFR § 46.111(a)(7) — Privacy safeguards | 45 C.F.R. § 46.111(a)(7) | Academic | ★ mandatory | k-anonymity k≥5 or DP ε≤1.0; privacy parameter receipt per dataset epoch |
| ISO TR 4804:2020 — In-vehicle telemetry GDPR compliance | ISO TR 4804:2020 § 6.3 | Automotive | ○ mandatory | Consent-receipted trip data; pseudonymisation before ML training |

**Λ3 Receipt Requirements**: Receipt must include `lawful_basis` (Art. 6 / Art. 9 basis or HIPAA exception), `data_category`, `retention_limit_days`, and `de_id_method` where applicable.

---

## Λ4 — Fairness

**Core Obligation**: AI systems must not discriminate against protected groups; training data and model outputs must demonstrate representative and equitable coverage.

| Regulation | Citation | Vertical | Weight | Mechanism |
|-----------|----------|----------|--------|-----------|
| ECOA/FCRA Adverse Action — Credit decisions | 15 U.S.C. § 1681m; 12 CFR § 202.9 | Financial | ★ mandatory | Machine-readable reason codes; CFPB guidance on AI credit models |
| Common Rule 45 CFR § 46.111 — Equitable subject selection | 45 C.F.R. § 46.111(a)(3) | Academic | ★ mandatory | Demographic stratification; IRB equity review; receipt with demographic hash |
| EU AI Act Art. 53 — GPAI fairness for research | Regulation (EU) 2024/1689 Art. 53 | Academic, LegalTech | ○ mandatory | Training data summary; evaluation results published; EU AI Act database |
| ISO 21448:2022 § 8 — SOTIF triggering conditions (pedestrian bias) | ISO 21448:2022 § 8 | Automotive | · recommended | Pedestrian detection equity across skin tone/age; bias receipts |
| DOE AI Strategy 2024 § 3.2 — Energy equity | U.S. DOE AI Strategy (2024) § 3.2 | Energy | · recommended | Demand response equity; census-tract metadata in receipt |

**Λ4 Receipt Requirements**: Receipt must include `fairness_metric` (e.g., demographic_parity, equalized_odds), `protected_attributes` list, `metric_value` (float), and `test_dataset_hash`.

---

## Λ5 — Safety

**Core Obligation**: AI systems must identify, assess, and mitigate risks of physical, operational, or systemic harm to humans or critical infrastructure.

| Regulation | Citation | Vertical | Weight | Mechanism |
|-----------|----------|----------|--------|-----------|
| ISO 26262-4:2018 § 7 — Technical safety requirements | ISO 26262-4:2018 § 7; ISO 26262-3:2018 § 7 | Automotive | ★ mandatory | ASIL-D safety goals; probability of failure < 10^-8/h; safety case receipt |
| DO-178C § 6.4 / DO-333 — Structural coverage (MC/DC) | RTCA DO-178C § 6.4; RTCA DO-333 § FM.6.4 | Aviation | ★ mandatory | MC/DC coverage for DAL-B; formal method proofs; coverage receipt |
| E.O. 14110 § 4.2 — National security AI safety | E.O. 14110 § 4.2 (Oct 2023) | Defense | ★ mandatory | Human-on-the-loop kill switch; HotL token in autonomous decision receipt |
| NERC CIP-009-6 R1 — BES recovery plans | NERC CIP-009-6 Requirement R1 | Energy | ★ mandatory | AI-assisted restoration with human override; operator confirmation token |
| HITECH Act § 13402 / 45 CFR § 164.400 — Breach notification | Pub. L. 111-5 § 13402 | Healthcare | ○ mandatory | AI re-identification anomaly detection; 60-day notification trigger |

**Λ5 Receipt Requirements**: Receipt must include `hazard_id`, `safety_integrity_level` (ASIL/DAL), `risk_reduction_factor`, and `verification_method` (testing/formal_proof/analysis).

---

## Λ6 — Security

**Core Obligation**: AI systems and their data must be protected against unauthorized access, adversarial manipulation, supply-chain compromise, and cyber incidents.

| Regulation | Citation | Vertical | Weight | Mechanism |
|-----------|----------|----------|--------|-----------|
| HIPAA 45 CFR § 164.312(a)(2)(i) — Unique user ID | 45 C.F.R. § 164.312(a)(2)(i) | Healthcare | ★ mandatory | Cryptographically bound identity token in receipt chain per PHI access |
| NERC CIP-007-6 R4 — Security event monitoring | NERC CIP-007-6 Requirement R4; 18 CFR § 40.7 | Energy | ★ mandatory | Anomaly detection receipts within 15 min; Merkle DAG integrity |
| DFARS 252.204-7012 — Covered defense information | DFARS 252.204-7012(b); 48 CFR § 252.204-7012 | Defense | ★ mandatory | 72-hour incident reporting; AI IOC hash receipt within 1 hour |
| UNECE R 155 — Automotive CSMS | UNECE Regulation No. 155 (2021) | Automotive | ★ mandatory | TARA for AI attack surfaces; threat analysis security receipt |
| 21 CFR § 11.10(e) — Secure audit trails | 21 C.F.R. § 11.10(e) | Pharma | ★ mandatory | Tamper-evident TAI64N-timestamped Merkle DAG |

**Λ6 Receipt Requirements**: Receipt must include `threat_model_version`, `authentication_method` (FIDO2/PIV/password), `encryption_algorithm`, `key_rotation_epoch`, and `incident_id` if triggered.

---

## Λ7 — Auditability

**Core Obligation**: AI systems must maintain tamper-evident, time-stamped logs of all significant events; records must be verifiable by external auditors and regulators.

| Regulation | Citation | Vertical | Weight | Mechanism |
|-----------|----------|----------|--------|-----------|
| HIPAA 45 CFR § 164.312(b) — Audit controls | 45 C.F.R. § 164.312(b) | Healthcare | ★ mandatory | Merkle DAG; p50 write ≤ 5 µs per Doctrine v6 §4.7 |
| SOX § 802 / 18 USC § 1519 — Document integrity | Pub. L. 107-204 § 802; 18 U.S.C. § 1519 | Financial | ★ mandatory | Append-only SHA3-256 Merkle DAG; cryptographic non-alteration proof |
| NERC CIP-010-4 R1 — Configuration change management | NERC CIP-010-4 Requirement R1 | Energy | ★ mandatory | Pre/post-update configuration diff receipts |
| DO-178C § 12.3 / Table A-10 — Configuration management | RTCA DO-178C § 12.3 | Aviation | ★ mandatory | DER-signed change-control receipts; configuration baseline |
| 21 CFR § 11.10(e) — Time-stamped audit trails | 21 C.F.R. § 11.10(e) | Pharma | ★ mandatory | GAMP 5 Category 5 validation; audit trail per user/system action |

**Λ7 Receipt Requirements**: Receipt must include `event_type`, `actor_id`, `timestamp_tai64n`, `prev_receipt_hash` (chain link), `merkle_root`, and `quorum_signatures` array.

---

## Λ8 — Robustness

**Core Obligation**: AI systems must withstand distribution shift, adversarial perturbation, hardware faults, and operational stress without unsafe degradation.

| Regulation | Citation | Vertical | Weight | Mechanism |
|-----------|----------|----------|--------|-----------|
| SR 11-7 — Model validation and ongoing monitoring | Federal Reserve SR 11-7 § III.C–D | Financial | ★ mandatory | Independent adversarial robustness testing; validation epoch in receipt |
| DO-178C § 6.4 / DO-333 FM.6.3.2 — Formal proof completeness | RTCA DO-178C § 6.4; RTCA DO-333 § FM.6.3.2 | Aviation | ★ mandatory | Lipschitz bounds; formal proof receipts for inference guarantees |
| 21 CFR § 11.10(a) — GxP system validation | 21 C.F.R. § 11.10(a) | Pharma | ★ mandatory | ISPE GAMP 5 Category 5; validation protocol hash in receipt |
| NERC CIP-013-2 R1 — Supply chain risk | NERC CIP-013-2 Requirement R1 | Energy | ★ mandatory | AI model SBOM receipts; provenance verification before BES deployment |
| CMMC L3 / NIST 800-171 § 3.11.2 — Vulnerability scanning | NIST SP 800-171 Rev 3 Control 3.11.2 | Defense | ★ mandatory | Quarterly adversarial robustness scans; scan result commitment receipts |

**Λ8 Receipt Requirements**: Receipt must include `robustness_metric` (e.g., PGD_ε, Lipschitz_bound), `test_methodology`, `dataset_hash`, `pass_threshold`, and `result` (pass/fail/conditional).

---

## Λ9 — Explainability

**Core Obligation**: AI outputs affecting human interests must be accompanied by interpretable, human-understandable explanations at a level of detail proportionate to the decision stakes.

| Regulation | Citation | Vertical | Weight | Mechanism |
|-----------|----------|----------|--------|-----------|
| GDPR Art. 22 / EDPB Guidelines 1/2022 — Automated decision-making | Regulation (EU) 2016/679 Art. 22 | LegalTech | ★ mandatory | Meaningful explanation per EDPB § 58; logic + significance + envisaged consequences |
| ECOA / FCRA 15 USC § 1681m — Adverse action notices | 15 U.S.C. § 1681m(a); 12 C.F.R. § 202.9 | Financial | ★ mandatory | Principal reason codes; CFPB AI explanation guidance; reason-code receipt |
| EU AI Act Art. 13 — Transparency for deployers | Regulation (EU) 2024/1689 Art. 13 | All high-risk | ★ mandatory | IFU with interpretability method; explanation receipt per inference |
| ISO 26262-6:2018 § 9 — ML explainability for ASIL-B+ | ISO 26262-6:2018 § 9; ISO TR 29119-11 | Automotive | ★ mandatory | Saliency maps or decision trees as explanation receipts |
| EASA CP No. 2 (2023) — ML explanation for aviation | EASA Concept Paper on ML (Oct 2023) | Aviation | ★ mandatory | Level 1/2 ML explanation; operational scenario coverage documented |

**Λ9 Receipt Requirements**: Receipt must include `explanation_method` (SHAP/LIME/IntGrad/decision_tree), `explanation_hash`, `target_audience` (regulator/operator/subject), and `fidelity_score` (float in [0,1]).

---

## Λ10 — Sovereignty

**Core Obligation**: Data and AI system deployment must respect jurisdictional boundaries; data subjects and nation-states retain control over cross-border data flows.

| Regulation | Citation | Vertical | Weight | Mechanism |
|-----------|----------|----------|--------|-----------|
| GDPR Art. 44–49 — International transfers | Regulation (EU) 2016/679 Art. 44–49 (SCCs, BCRs, adequacy) | LegalTech | ★ mandatory | Transfer mechanism documented in receipt; SCCs/BCR reference |
| DFARS 252.204-7012 — CUI jurisdictional control | DFARS 252.204-7012; 48 CFR § 252.204-7012 | Defense | ★ mandatory | CUI enclave attestation; jurisdiction token in receipt chain |
| ISPS Code Part A § 9.4 — SSP flag-state jurisdiction | ISPS Code Part A § 9.4 | Maritime | ★ mandatory | Data residency receipt specifying IMO flag-state; SSP access log |
| Dodd-Frank § 1033 / CFPB Rule 1033 — Consumer data portability | Pub. L. 111-203 § 1033; 12 CFR § 1033.201 | Financial | ★ mandatory | Consumer-authorized scope token in export receipt |
| eIDAS 2.0 Art. 3 — European Digital Identity Wallet sovereignty | Regulation (EU) 2024/1183 Art. 3 | LegalTech | ★ mandatory | EUDIW-bound QES; wallet jurisdiction assertion in receipt |

**Λ10 Receipt Requirements**: Receipt must include `jurisdiction_code` (ISO 3166-1 alpha-2), `transfer_mechanism` (adequacy/SCC/BCR/none), `data_residency_region`, and `sovereignty_assertion_hash`.

---

## Cross-Vertical Coverage Matrix

| Vertical        | Λ1 | Λ2 | Λ3 | Λ4 | Λ5 | Λ6 | Λ7 | Λ8 | Λ9 | Λ10 | Count |
|-----------------|----|----|----|----|----|----|----|----|----|----|-------|
| Healthcare      | ○  | ★  | ★  | ·  | ○  | ★  | ★  | ○  | ·  | ○   | 9     |
| Financial       | ★  | ★  | ○  | ★  | ○  | ★  | ★  | ★  | ★  | ★   | 10    |
| Defense         | ★  | ★  | –  | ○  | ★  | ★  | ★  | ★  | ·  | ★   | 9     |
| Aviation        | ★  | ★  | –  | ·  | ★  | ○  | ★  | ★  | ★  | ·   | 8     |
| Automotive      | ★  | ★  | ○  | ○  | ★  | ★  | ★  | ★  | ★  | ★   | 10    |
| Pharmaceutical  | ★  | ★  | ○  | ★  | ★  | ★  | ★  | ★  | ★  | ★   | 10    |
| Energy          | ○  | ★  | ·  | ·  | ★  | ★  | ★  | ★  | ·  | ★   | 8     |
| Maritime        | ○  | ★  | ○  | ·  | ★  | ★  | ★  | ★  | ★  | ★   | 9     |
| LegalTech       | ★  | ★  | ★  | ★  | ○  | ★  | ★  | ★  | ★  | ★   | 10    |
| Academic        | ★  | ★  | ★  | ★  | ○  | ○  | ★  | ·  | ○  | ○   | 8     |
| **Axis total**  | 9  | 10 | 8  | 8  | 9  | 10 | 10 | 9  | 8  | 9   |       |

★ = mandatory, ○ = recommended, · = advisory, – = not applicable

---

*Generated: Doctrine v6 R3 Adversarial Receipts · Receipt chain: SHA3-256 Merkle DAG*
