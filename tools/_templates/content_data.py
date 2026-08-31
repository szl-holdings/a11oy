"""Structured content seeded by szl_master_bootstrap.py.

Pure Python literals here; szl_master_bootstrap renders them to the
SZL-YAML-1 subset via tools/szl_miniyaml.py. Kept separate so the payload
document, the bootstrap tool, and the review agents all read one source.
"""

# ---------------------------------------------------------------------------
# EU AI Act Article 12 logging conformance profile (11 mapped entries)
# Grounded citations: EUR-Lex Regulation (EU) 2024/1689. Six-month retention
# floor: Art. 19(1) (provider) and Art. 26(6) (deployer) over Art. 12(1) logs;
# encoded here as 180 days per CANON Law 10.
# ---------------------------------------------------------------------------

CONFORMANCE_PROFILE = {
    "yaml_subset": "SZL-YAML-1",
    "profile": "eu-ai-act-article-12-logging",
    "schema_version": 1,
    "regulation": "Regulation (EU) 2024/1689",
    "scope_note": (
        "Article 12 logging conformance profile. This is NOT a claim of EU AI "
        "Act compliance. Applicability, classification, and deployer "
        "obligations are customer-specific."
    ),
    "retention_minimum_days": 180,
    "out_of_scope": [
        "Art. 12(3)(b): reference database checks apply to Annex III 1(a) biometric systems only",
        "Art. 12(3)(c): matched input data applies to Annex III 1(a) biometric systems only",
    ],
    "entries": [
        {
            "provision": "Art. 12(1)",
            "requirement": "automatic recording of events (logs) over the lifetime of the system",
            "jsonpath": "$.receipt_id",
            "validator": "nonempty_string",
            "status": "MAPPED",
            "note": "one receipt per governed action, recorded at execution time, not assembled later",
        },
        {
            "provision": "Art. 12(2)(a)",
            "requirement": "recording of events relevant to identifying risk situations and substantial modifications",
            "jsonpath": "$.decision.effective_side_effect_class",
            "validator": "enum_side_effect_class",
            "status": "MAPPED",
            "note": "blast radius is priced per action in four never-collapsed classes",
        },
        {
            "provision": "Art. 12(2)(b)",
            "requirement": "facilitating post-market monitoring (Art. 72)",
            "jsonpath": "$.retention_days",
            "validator": "gte_180",
            "status": "MAPPED",
            "note": "records persist at or above the retention floor so monitoring can consult them",
        },
        {
            "provision": "Art. 12(2)(c)",
            "requirement": "monitoring the operation of the system (Art. 26(5))",
            "jsonpath": "$.decision.decision",
            "validator": "enum_allow_deny",
            "status": "MAPPED",
            "note": "every action records its allow or deny decision",
        },
        {
            "provision": "Art. 12(3)(a) start",
            "requirement": "recording of the period of each use, start date and time",
            "jsonpath": "$.observation_window.start",
            "validator": "rfc3339_timestamp",
            "status": "MAPPED",
            "note": "governed period opens at a recorded timestamp",
        },
        {
            "provision": "Art. 12(3)(a) end",
            "requirement": "recording of the period of each use, end date and time",
            "jsonpath": "$.observation_window.end",
            "validator": "rfc3339_timestamp",
            "status": "MAPPED",
            "note": "governed period closes at a recorded timestamp",
        },
        {
            "provision": "Art. 12(3)(d)",
            "requirement": "identification of the natural persons involved in verification of results (Art. 14(5))",
            "jsonpath": "$.predicate.actor.actor_id",
            "validator": "nonempty_string",
            "status": "MAPPED",
            "note": "every receipt names the responsible natural person",
        },
        {
            "provision": "Art. 12(3)(d) constraint",
            "requirement": "service accounts cannot stand in for natural persons",
            "jsonpath": "$.predicate.actor.is_service_account",
            "validator": "const_false",
            "status": "MAPPED",
            "note": "structurally unviolatable: the schema pins is_service_account to false",
        },
        {
            "provision": "Art. 12(1) authenticity support",
            "requirement": "recorded events must resist backdating",
            "jsonpath": "$.predicate.rfc3161_token",
            "validator": "nonempty_string",
            "status": "MAPPED",
            "note": "RFC 3161 trusted timestamp token, or the literal UNAVAILABLE when the TSA was unreachable",
        },
        {
            "provision": "Art. 12(1) clock support",
            "requirement": "clock state at record time is disclosed",
            "jsonpath": "$.predicate.ntp_synced",
            "validator": "boolean",
            "status": "MAPPED",
            "note": "true only when the host clock was NTP-synced when the receipt was issued",
        },
        {
            "provision": "Art. 19(1) and Art. 26(6) retention floor",
            "requirement": "Art. 12(1) logs kept at least six months by provider and deployer",
            "jsonpath": "$.retention_days",
            "validator": "gte_180",
            "status": "MAPPED",
            "note": "the schema enforces retention_days >= 180 (six months, per CANON Law 10)",
        },
    ],
}

# ---------------------------------------------------------------------------
# COMMERCIAL_LEDGER — 24 rows, every row UNKNOWN, every row blocks_raise.
# CANON section 8: no model may invent these values.
# ---------------------------------------------------------------------------

LEDGER_ROWS = [
    ("arr", "What is the current annual recurring revenue from signed contracts", "no billing system or signed contracts exist to compute it from", "financials"),
    ("mrr", "What is the current monthly recurring revenue", "no billing system exists to measure it", "financials"),
    ("contracted_vs_recognized_revenue", "How much revenue is contracted versus recognized under our revenue recognition policy", "no contracts and no revenue recognition policy exist", "financials"),
    ("paying_customers", "How many distinct paying customers are there today", "no payment has ever been received for a11oy", "customers"),
    ("gross_margin", "What is the gross margin on the product", "no price and no unit cost model exist; also blocked by contradiction B-04", "unit_economics"),
    ("nrr", "What is net revenue retention", "no cohort of paying customers exists to measure; also blocked by contradiction B-04", "unit_economics"),
    ("cac_payback", "What is customer acquisition cost payback in months", "no acquisition spend and no paying customers exist; also blocked by contradiction B-04", "unit_economics"),
    ("cash_on_hand", "How much cash does the company hold", "no audited bank statement has been attached to this ledger", "financials"),
    ("monthly_burn", "What is the average monthly net burn", "no bookkeeping export exists to compute it", "financials"),
    ("runway_months", "How many months of runway remain at current burn", "requires cash on hand and monthly burn, both UNKNOWN", "financials"),
    ("burn_multiple", "What is the burn multiple", "requires net burn and net new ARR, both UNKNOWN; also blocked by contradiction B-04", "unit_economics"),
    ("published_price", "What is the published price of the product", "no pricing page or price list has been published", "pricing"),
    ("buyer_persona", "Who is the named buyer persona with budget authority", "hypotheses exist in strategy notes but no interviewed buyer has confirmed one", "gtm"),
    ("pricing_model", "What pricing model does the product use", "no model has been chosen among per-seat, per-action, or platform fee", "pricing"),
    ("design_partner_count", "How many signed design partners are actively testing the product", "no signed design partner agreement exists", "customers"),
    ("conversion_rate", "What is the pilot to paid conversion rate", "no pilots have completed; no funnel exists to measure", "gtm"),
    ("zero_config_use_cases", "How many zero-config use cases work end to end against the target of 3", "the wedge is being bootstrapped; no use case has passed a buyer-run test", "product"),
    ("cofounder_advisor_name", "Who is the committed co-founder or named advisor", "Stephen Lutar is solo; no co-founder or advisor has signed (see contradiction B-05)", "team"),
    ("cap_table_cleanliness", "Is the cap table clean and fully documented", "no counsel-verified cap table export has been attached", "legal"),
    ("contributor_ip_assignments", "Do all contributors have signed IP assignment agreements", "no signed IP assignment paperwork has been attached", "legal"),
    ("model_bom_status", "Does a complete model bill of materials exist for every model in the estate", "no Model BOM register has been created for the ~15 Hugging Face models", "ai_governance"),
    ("dataset_license_register", "Does a license register exist covering all datasets", "no license register has been created for the ~30 Hugging Face datasets", "ai_governance"),
    ("soc2_status", "What is the SOC 2 attestation status", "SOC 2 work has not been started; no auditor engaged", "security_readiness"),
    ("eu_design_partner", "Is there at least one EU-based design partner for the Article 12 profile", "no EU design partner conversation has reached a signed agreement", "customers"),
]

LEDGER_DOC = {
    "yaml_subset": "SZL-YAML-1",
    "ledger": "COMMERCIAL_LEDGER",
    "schema_version": 1,
    "generated_by": "tools/szl_master_bootstrap.py",
    "zero_bandaid": (
        "No claim without evidence. Every row starts UNKNOWN because no "
        "audited evidence exists yet. UNKNOWN is an audited state; an empty "
        "field is an oversight. No model may invent these values (CANON "
        "section 8)."
    ),
    "rows": [
        {
            "id": row_id,
            "category": category,
            "question": question,
            "state": "UNKNOWN",
            "value": None,
            "blocks_raise": True,
            "evidence": None,
            "why_unknown": reason,
            "last_audited": "2026-08-30",
        }
        for row_id, question, reason, category in LEDGER_ROWS
    ],
}

# ---------------------------------------------------------------------------
# claims-ledger seed. Zero-Bandaid: every VERIFIED claim carries evidence;
# anything else is UNKNOWN or UNAVAILABLE and states why.
# ---------------------------------------------------------------------------

CLAIMS_LEDGER_DOC = {
    "yaml_subset": "SZL-YAML-1",
    "ledger": "claims-ledger",
    "schema_version": 1,
    "zero_bandaid": (
        "A public claim lacking evidence auto-demotes to UNKNOWN. This file "
        "is enforced by tools/release_gate.py."
    ),
    "claims": [
        {
            "id": "clm-product-claim",
            "claim": (
                "a11oy issues signed, offline-verifiable receipts proving "
                "what an AI agent was authorized to do, what it actually "
                "did, and whether the required evidence exists"
            ),
            "state": "VERIFIED",
            "evidence": [
                {
                    "kind": "demonstration",
                    "ref": "tools/demo_harness.py",
                    "note": "the 12-step acceptance demo exercises sign, verify, tamper, incompleteness, replay, and redaction checks",
                    "status": "supports",
                }
            ],
            "last_audited": "2026-08-30",
        },
        {
            "id": "clm-solo-founder",
            "claim": "SZL Holdings is a solo-founder company led by Stephen Lutar, Poughkeepsie NY, Python-first",
            "state": "VERIFIED",
            "evidence": [
                {
                    "kind": "canon",
                    "ref": "payload CANON section 1",
                    "note": "estate facts audited across ten review rounds in the source thread",
                    "status": "supports",
                }
            ],
            "last_audited": "2026-08-30",
        },
        {
            "id": "clm-competitor-funding",
            "claim": "Zenity, Obsidian, and Hush announced rounds on or around 4 August 2026",
            "state": "VERIFIED",
            "evidence": [
                {
                    "kind": "press",
                    "ref": "payload CANON section 5",
                    "note": "searched in-thread; dates as found",
                    "status": "supports",
                }
            ],
            "last_audited": "2026-08-30",
        },
        {
            "id": "clm-conformance-profile",
            "claim": "the Article 12 logging conformance profile is mapped and machine-checked",
            "state": "UNKNOWN",
            "evidence": [
                {
                    "kind": "gap",
                    "ref": "evidence/conformance/eu-ai-act-article-12.yaml",
                    "note": "mapping exists and demo step 9 checks it, but no third-party review or recorded demo run is attached yet",
                    "status": "partial",
                }
            ],
            "last_audited": "2026-08-30",
        },
    ],
}
