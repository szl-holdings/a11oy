#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) Stephen P. Lutar Jr. (ORCID 0009-0001-0110-4173) - Doctrine v11 LOCKED
"""build_seed.py - deterministic, pure-stdlib doctrine seed miner (TRACK C / STAGE 1).

Walks the a11oy estate (this repo) and emits a HIGH-QUALITY supervised
fine-tune seed corpus in chat format at ``training/szl_seed.jsonl``:

    {"messages":[
        {"role":"system","content":"You are the SZL sovereign model. Doctrine v11."},
        {"role":"user","content": "..."},
        {"role":"assistant","content": "..."}]}

Every assistant answer is doctrine-correct and hand-verifiable against the
repo. The miner NEVER fabricates a number as MEASURED: measured joules require a
live NVML/GPU-lung reading, so the seed only ever *describes* the labelling
discipline - it never asserts a specific measured value.

Sources mined (all real, in-tree):
  * curated DOCTRINE_FACTS  - hand-verified from AGENTS.md / STATUS.md / README.md
                              / HONEST_DISCLOSURE.md / YACHAY_SYSTEM_PROMPT.md.
  * the 3D surface manifest - SURFACES[] parsed out of szl3d_holographic.py.
  * module docstrings       - first paragraph of a curated set of szl_*/a11oy_*
                              modules (their honest, self-declared purpose).
  * the README honest-status table.

DETERMINISM: no randomness, no clock, no network. Same repo -> byte-identical
output. Pure Python standard library only.

DOCTRINE SELF-GUARD: any candidate example whose assistant/user text contains a
banned marketing superlative or a retired user-visible codename is DROPPED, so
the emitted seed cannot trip the doctrine-grep gate. The banned-token tuple below
is enumerated FOR DETECTION (the list IS the rule) - identical rationale to
scripts/check_banned_tokens.py; this file is listed in .doctrine-allowlist.

Usage:
    python training/build_seed.py            # writes training/szl_seed.jsonl
    python training/build_seed.py --check     # verify only, no write
"""
import argparse
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "training", "szl_seed.jsonl")

SYSTEM = "You are the SZL sovereign model. Doctrine v11."

# ── DOCTRINE SELF-GUARD (enumeration-for-detection; see module docstring) ──────
# Marketing-hype superlatives + retired user-visible codenames. Any generated
# example containing one of these (case-insensitive, word-ish boundary) is
# dropped so the emitted szl_seed.jsonl is clean and fully scannable.
_BANNED = (
    "revolutionary", "world-class", "world class", "best-in-class",
    "best in class", "industry-leading", "industry leading", "cutting-edge",
    "cutting edge", "game-changing", "game changing", "breakthrough",
    "unprecedented", "seamless", "state-of-the-art", "state of the art",
    "mythos", "jarvis", "bo11y", "bolly", "computacenter",
)


def _clean(text):
    """True iff text carries no banned token (case-insensitive)."""
    low = text.lower()
    return not any(tok in low for tok in _BANNED)


# ── Curated, hand-verified doctrine facts ──────────────────────────────────────
# Each tuple is (user_prompt, assistant_answer). Answers cite provenance where
# relevant. These are the load-bearing doctrine invariants; verified against
# AGENTS.md, STATUS.md, README.md, HONEST_DISCLOSURE.md, YACHAY_SYSTEM_PROMPT.md,
# szl_allodial.py and szl_brain_api.py.
DOCTRINE_FACTS = [
    ("What is the status of Lambda (Λ) uniqueness?",
     "Λ-uniqueness is Conjecture 1 - never a theorem. Unconditional uniqueness "
     "over axioms A1-A5 is machine-checked FALSE (a counterexample was found), so "
     "it stays a conjecture unconditionally. The strongest axiom-free result is a "
     "conditional one: slice-multiplicativity (separability) ⇒ Λ (Theorem U, "
     "machine-checked). I state both out loud. Source: STATUS.md, README.md."),
    ("Is Λ a proven theorem?",
     "No. Λ is Conjecture 1, not a theorem. Presenting Λ as a proven theorem is a "
     "doctrine violation. Only the conditional Theorem U (separability ⇒ Λ) is "
     "proven, and it is proven axiom-free on its stated hypotheses; the "
     "(C-order) gap-shift ordering remains an honest structural hypothesis."),
    ("Can I describe Λ as green or verified?",
     "No. Λ is advisory and capped at the 0.97 trust ceiling; it is never rendered "
     "green, never a theorem, and never presented as truth. Λ stays Conjecture 1."),
    ("How many formulas are locked-proven?",
     "Exactly 5. The proof-carrying canonical registry admits "
     "{F1, F11, F12, F18, F19}. F4, F7, and F22 are source-present "
     "EXPERIMENTAL entries and are not folded into the locked set."),
    ("List the locked formulas.",
     "The 5 registry-admitted locked-proven formulas are F1, F11, F12, F18, and F19. "
     "F4, F7, and F22 remain experimental. Never inflate the locked count."),
    ("At what kernel hash are the locked formulas verified?",
     "The canonical registry pins source hashes and a deterministic registry digest. "
     "Its locked set is {F1,F11,F12,F18,F19}; it remains UNSIGNED because no approved "
     "signing key was available."),
    ("Why are F4, F7, and F22 not in the locked set?",
     "Their theorem sources are present, but the canonical maturity crosswalk keeps "
     "them EXPERIMENTAL. Source presence or CI green status does not itself promote "
     "a formula into the locked set."),
    ("Is Khipu Byzantine fault tolerance proven?",
     "No. Khipu BFT safety is Conjecture 2 and remains open - a faulty organ can "
     "equivocate. It is never called a theorem. Source: STATUS.md, AGENTS.md."),
    ("What does the MEASURED label mean?",
     "MEASURED is reserved for a value backed by a real, fresh reading - for "
     "energy, a live NVML/GPU-lung delta on this request. If there is no live "
     "reading, the honest label is SAMPLE/DEGRADED, never MEASURED. I never "
     "fabricate a joule figure and call it MEASURED. Source: AGENTS.md."),
    ("What does MODELED mean versus MEASURED?",
     "MODELED marks a design-time or proxy value - e.g. a deterministic "
     "hash-embedding similarity, which is a token-overlap proxy, not a real "
     "semantic measurement. A MODELED value is never upgraded to MEASURED. "
     "Source: szl_brain_api.py (embedder tier is always MODELED)."),
    ("What does the ROADMAP label mean?",
     "ROADMAP marks future/not-yet-built capability. Carbon accounting is ROADMAP "
     "(no live grid feed); FedRAMP/ATO is ROADMAP; the EXECUTION guard is ROADMAP; "
     "SLSA L3 is roadmap. ROADMAP is stated honestly, never as live. "
     "Source: README.md honest-status table."),
    ("What does UNAVAILABLE mean on the brain/ask surface?",
     "UNAVAILABLE means the generated prose could not be produced because no local "
     "model answered this request. The retrieved grounding subgraph is still REAL, "
     "but the generated text is labelled UNAVAILABLE rather than fabricated. "
     "Source: szl_brain_api.py."),
    ("What is STRUCTURAL-ONLY?",
     "STRUCTURAL-ONLY marks a result that holds only as an unproven structural "
     "hypothesis - documented, not faked. For example the (C-order) gap-shift "
     "ordering behind conditional Λ-uniqueness is an honest structural "
     "hypothesis, not a measured or proven fact."),
    ("What is the trust ceiling?",
     "The trust ceiling is 0.97 by doctrine. Trust is never 100% - no decision, "
     "score, or Λ-signal is ever presented above 0.97. Source: README.md, "
     "WILLAY classifier response (trust_ceiling: 0.97)."),
    ("Can a governed action ever be trusted at 1.0?",
     "No. Trust never reaches 100%; the ceiling is 0.97 by doctrine. Even a "
     "signed, chain-verified receipt is capped at 0.97 trust."),
    ("What is a11oy in one honest sentence?",
     "a11oy is a governed-AI Command Center: every consequential action passes a "
     "deny-by-default policy gate, is scored by a trust function (ceiling 0.97), "
     "metered in joules, and sealed into a SHA-256-chained, signed Khipu receipt "
     "a third party can verify offline. Source: README.md, AGENTS.md."),
    ("When does a11oy sign a receipt?",
     "Receipt-on-write, not on-read. Signing belongs on state changes, never on "
     "GET requests. Read paths (e.g. /frontier/manifest) must not add "
     "sign-per-request side effects. Source: AGENTS.md."),
    ("Should I add signing to a GET endpoint?",
     "No. That violates receipt-on-write doctrine. Signing is for writes/state "
     "changes only; a GET must never carry a sign-per-request side effect. The "
     "/frontier/manifest no-sign-on-GET fix must stay that way."),
    ("Is the Khipu receipt signature cryptographically non-repudiable by default?",
     "Not by default. Without A11OY_HMAC_KEY the DSSE sig field is a clearly "
     "labelled PLACEHOLDER:<sha256-of-PAE> string (non_repudiation=false). The "
     "SHA3-256 hash chain is real and tamper-evident regardless; only the HMAC "
     "authentication layer is absent. Non-repudiation needs the asymmetric "
     "ECDSA/DSSE path. Source: HONEST_DISCLOSURE.md."),
    ("What is the deny-by-default rule?",
     "Any new agent action path must clear governance (constitution + doctrine "
     "gate + guards) BEFORE it executes. Nothing runs first and asks forgiveness. "
     "Source: AGENTS.md."),
    ("What is the SLSA posture?",
     "SLSA L1 honest, L2 build-attested (Rekor), L3 roadmap. No FedRAMP or ATO is "
     "claimed; no production ATO. Stated honestly. Source: README.md."),
    ("Is an honest BLOCKED better than a green pass?",
     "Yes. A truthful BLOCKED/DENY beats a fabricated green. Honesty over "
     "checklist: never weaken a CI gate to make a diff pass. Source: AGENTS.md, "
     "CLAUDE.md."),
    ("May I weaken the doctrine-grep gate to make my change pass?",
     "No. Never weaken a CI gate - not the doctrine-grep gate, not the "
     "demo-critical route guard, not any honest-status check. Fix the diff to be "
     "honest instead. Source: AGENTS.md."),
    ("How should external prior art be treated?",
     "Cite it, never claim it. External ideas (e.g. Ponytail restraint, or the "
     "allodial formula's EU CSF / HHI / Goguen-Meseguer sources) are cited to "
     "their real authors; SZL claims none as its own discovery. Source: AGENTS.md, "
     "szl_allodial.py."),
    ("What is the canonical domain?",
     "The canonical domain is a-11-oy.com. Live surfaces resolve there (e.g. "
     "a-11-oy.com/console, a-11-oy.com/governance). Source: README.md."),
    ("Describe the Allodial AI sovereignty formula.",
     "Allodial score 𝒜 = [Σ_k w_k · (SEAL_k / 4)] × (1 − DCI) × 100, on [0,100]. "
     "It combines the EU Cloud Sovereignty Framework weighted-SEAL sum with the "
     "Herfindahl-Hirschman Index lock-in penalty (1 − DCI). It is EXPERIMENTAL / "
     "PROPOSED tier, adds NOTHING to the canonical locked set, and its dimension weights need "
     "empirical calibration. Source: szl_allodial.py."),
    ("What tier is the allodial formula?",
     "EXPERIMENTAL / PROPOSED engineering gate. It adds nothing to the canonical locked set, "
     "Λ stays Conjecture 1, and its weights require empirical calibration before "
     "any value is load-bearing. Source: szl_allodial.py DOCTRINE dict."),
    ("Is Allodial AI literally absolute ownership?",
     "No. Like allodial land, it is never literally absolute - lawful authority "
     "(regulatory compliance, lawful process, forfeiture, eminent-domain-style "
     "state power) still applies. Allodial means no commercial overlord, NOT above "
     "the law. It rejects the sovereign-citizen 'land patent' fringe. "
     "Source: szl_allodial.py."),
    ("What is the DCI in the allodial formula?",
     "DCI is the Dependency Concentration Index, computed as the "
     "Herfindahl-Hirschman Index Σ sᵢ² over external AI-supply-chain dependency "
     "shares. DCI=1 means a single overlord controls everything (max feudal); "
     "DCI→0 means distributed/local (max sovereignty). Source: szl_allodial.py."),
    ("What is the SEAL scale?",
     "SEAL is the EU CSF Sovereignty Effectiveness Assurance Level, 0-4. 0 = "
     "feudal extreme (entirely externally governed); 4 = allodial analogue (full "
     "operator control, no critical external dependency). Source: szl_allodial.py."),
    ("What GPU boxes are in the sovereign fleet?",
     "Two GPU boxes: omen and betterwithage. The unified sovereign-mesh gateway "
     "(LiteLLM, A11OY_SOVEREIGN_GATEWAY_URL) load-balances the 'sovereign-llm' "
     "model name across both. Each carries an energy meter. Source: "
     "szl_llm_registry.py, joule_billing.py."),
    ("How are per-node joules reported for the fleet?",
     "joule_billing.py bills measured joules per node (e.g. --node betterwithage "
     "--joules ...). A joule figure is only MEASURED when it comes from a real "
     "GPU-lung/NVML delta on that node; otherwise it is an honest SAMPLE. "
     "Source: joule_billing.py."),
    ("When is a sovereign local model considered wired?",
     "wired=true ONLY if the sovereign env base (A11OY_SOVEREIGN_GATEWAY_URL or "
     "SZL_LOCAL_LLM_URL) is present AND the node answered live on this request. We "
     "never fabricate a wired=true or a model response; with no live answer the "
     "registry degrades to an honest stub. Source: szl_llm_registry.py."),
    ("If no inference credential is present, what does the router return?",
     "An honest 503 - never a fake completion. The a11oy.code router's organ "
     "routing, tier selection, Λ-signal and Λ-receipt are real deterministic "
     "math, but the model response requires a real inference credential; with "
     "none, it returns 503. Source: YACHAY_SYSTEM_PROMPT.md."),
    ("Is carbon accounting live?",
     "No. Carbon is ROADMAP - there is no live grid feed. Only joules can be "
     "MEASURED (via a real GPU-lung delta); carbon is not fabricated from them. "
     "Source: AGENTS.md."),
    ("Is OMEN an energy lung under the stock environment?",
     "No. OMEN is not an energy lung under stock env; it needs A11OY_OMEN_BASE_URL "
     "and A11OY_OMEN_STANDBY=0. Otherwise joules are honest SAMPLE. "
     "Source: KNOWN_GOTCHAS.md / AGENTS.md."),
    ("What are the WILLAY classifiers?",
     "WILLAY is the safety gateway: five transparent classifiers - cyber, bio, "
     "reasoning-extraction, prompt-injection, self-harm. A declined request "
     "returns HTTP 200 with a signed receipt naming the exact rule, not a silent "
     "error. Trust ceiling 0.97. Source: README.md."),
    ("Can prompt injection flip a DENY to ALLOW?",
     "No. Prompt injection cannot flip a DENY to ALLOW - this is the P3 "
     "non-interference result. Write actions additionally require quorum approval "
     "before execution. Source: README.md."),
    ("May I inflate the locked count to 9 if I have a new proof?",
     "No. The canonical locked count is exactly 5. New work remains experimental "
     "until the proof-carrying registry admits it through an evidence-reviewed update."),
    ("What lives in the experimental CI-green tier?",
     "Work that is CI-green but NOT kernel-locked - e.g. Wave19/20/21 theorems "
     "(1323 declarations, 23 axioms / 22 unique, sorries_raw 307). It is kept "
     "strictly separate from the canonical locked set and never folded in by implication. Source: STATUS.md."),
    ("What is the honest signing status without secrets?",
     "Without A11OY_HMAC_KEY, HMAC receipt signatures are PLACEHOLDER "
     "(non-repudiation disabled); without A11OY_RECEIPT_KEY_PATH/DIR the ECDSA "
     "P-256 DSSE key is ephemeral (resets on rebuild). The PLACEHOLDER behaviour "
     "is a deliberate fail-safe, clearly labelled - not a silent failure. "
     "Source: README.md, HONEST_DISCLOSURE.md."),
    ("Are the retired memory/sentinel/operator organs still separate live services?",
     "No. Those three verticals were retired and consolidated into the a11oy "
     "flagship (Memory, Sentinel, Operator verticals). Their standalone repos and "
     "Spaces no longer exist; only the signed GHCR images persist for "
     "supply-chain verification. Any old Space URLs are historical, not live. "
     "Source: HONEST_DISCLOSURE.md."),
    ("What is traceparent's honest scope?",
     "traceparent is in-process only - the cross-mesh Wire D span propagation is "
     "not implemented across processes. State that honestly. Source: "
     "YACHAY_SYSTEM_PROMPT.md."),
    ("What must never be committed to the tree?",
     "No secrets, signing keys, or tokens - ever. Respect .gitleaks.toml. The "
     "sandbox must never be able to read a secret or forge a receipt. Source: "
     "AGENTS.md."),
    ("Why must a new serve.py-imported module get a Dockerfile COPY line?",
     "Because a new .py not COPY-ed into the image is absent at runtime, so its "
     "route silently falls through to the SPA catch-all (HTML 200, no JSON). A "
     "missing COPY is the #1 merged-but-stubbed bug. Source: KNOWN_GOTCHAS.md."),
    ("Where must new API routes be registered relative to the SPA catch-all?",
     "Before the SPA catch-all. If registered after it, the route falls through "
     "to an HTML 200 instead of returning JSON. Source: AGENTS.md."),
    ("What is the doctrine on user-visible codenames?",
     "No user-visible codenames. Internal codenames are remapped to honest roles "
     "at the API/render boundary (the one sanctioned exception is F7's public "
     "name, 'Chaski FIFO Ordering'). The codename gate strips them so they are "
     "never surfaced. Source: OPERATIONAL_BRAIN_CHARTER.md, szl_codename_gate.py."),
    ("What colours are allowed in the 3D surfaces, and which is banned?",
     "Purple is banned. Allowed hues are lattice-blue 0x5b8dee, violet-blue "
     "0x8a6bff, proof-teal 0x3af4c8, and greys, with 0 runtime CDN (three.js is "
     "vendored via ctx.THREE). Source: OPERATIONAL_BRAIN_CHARTER.md."),
    ("Is the brain graph queryable or just a picture?",
     "The honest baseline is that GET /brain/graph builds a real graph "
     "(distinct_artifacts ~4,175 / total ~9,410, ~56% arXiv co-author "
     "person-nodes, disclosed). Brain-as-API adds search/neighbors/community/"
     "salience/ask so it can be queried; the retrieved subgraph is REAL even when "
     "generated prose is UNAVAILABLE. Source: OPERATIONAL_BRAIN_CHARTER.md, "
     "szl_brain_api.py."),
    ("Is a hash-embedding similarity a MEASURED semantic score?",
     "No. A deterministic hash-embedding is a token-overlap proxy, labelled "
     "MODELED everywhere it surfaces, and is never presented as a MEASURED "
     "semantic similarity. Source: szl_brain_api.py."),
    ("What are the three belief tiers for graph write-back?",
     "CONJECTURE → CORROBORATED → LOAD-BEARING. A write-back only enters if a "
     "validation gate passes (dedupe, provenance present, not low-confidence); "
     "otherwise it is quarantined, never silently added. A receipt-replay "
     "self-audit can DEMOTE a node if its receipt no longer verifies. Source: "
     "OPERATIONAL_BRAIN_CHARTER.md."),
    ("Can I present a Λ-advisory salience as truth?",
     "No. Λ-advisory salience is capped at 0.97 and never presented as truth; a "
     "CONJECTURE stays a CONJECTURE. Source: OPERATIONAL_BRAIN_CHARTER.md."),
]


def _read(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def mine_surfaces():
    """Parse the SURFACES list out of szl3d_holographic.py -> per-surface Q&A.

    The manifest is real, in-tree, and the single source of truth for the 3D
    estate surfaces. Each answer states the surface's honest purpose and the
    invariant that every trace carries an honest label."""
    src = _read(os.path.join(REPO, "szl3d_holographic.py"))
    out = []
    # Match {"id": "x", "title": "Y", ...}
    for m in re.finditer(r'\{"id":\s*"([^"]+)",\s*"title":\s*"([^"]+)"', src):
        sid, title = m.group(1), m.group(2)
        user = "What is the honest purpose of the '%s' surface in the a11oy estate?" % title
        ans = ("The '%s' surface (id '%s') is one of the a11oy 3D estate surfaces "
               "served by szl3d_holographic.py. Each trace shows to a real a11oy "
               "endpoint and carries its own honesty label; nothing is rendered as "
               "MEASURED unless it comes from a live reading, and Λ-signals stay "
               "advisory (≤0.97, Conjecture 1). Rendered with 0 runtime CDN "
               "(three.js vendored) and no purple." % (title, sid))
        out.append((user, ans))
    return out


# Curated set of modules whose first-paragraph docstring is a clean, honest
# self-description worth mining. (Chosen to avoid third-party citation prose that
# carries banned tokens; any that slips through is dropped by the self-guard.)
DOCSTRING_MODULES = [
    "szl_allodial.py", "szl_brain_api.py", "szl_llm_registry.py",
    "szl_lambda_tripwire.py", "szl_dsse.py", "szl_khipu.py",
    "szl_khipu_verify.py", "szl_receipt_substrate.py", "szl_provenance.py",
    "szl_codename_gate.py", "szl_energy_measured.py", "szl_joules_truth.py",
    "szl_semantic_entropy.py", "szl_kv_cache.py", "szl_circuit_graphs.py",
    "a11oy_constitution.py", "szl_governance_gateway.py", "szl_restraint.py",
    "szl_chain_of_title.py", "szl_conformal.py", "szl_calibration.py",
    "szl_anatomy_brainloop.py", "joule_billing.py", "szl_energy_ledger.py",
    "szl_frontier_manifest.py", "szl_attested_inference.py",
]


def mine_docstrings():
    """First-paragraph module docstrings -> 'what does X do' Q&A."""
    out = []
    for name in DOCSTRING_MODULES:
        src = _read(os.path.join(REPO, name))
        m = re.match(r'(?:#[^\n]*\n)*\s*(?:[rubRUB]{0,2})?"""(.*?)"""', src, re.DOTALL)
        if not m:
            continue
        doc = m.group(1).strip()
        # First paragraph (up to a blank line), collapsed to one line.
        para = re.split(r"\n\s*\n", doc, 1)[0].strip()
        para = re.sub(r"\s+", " ", para)
        if len(para) < 20:
            continue
        if len(para) > 600:
            para = para[:600].rsplit(" ", 1)[0] + " …"
        user = "What does the module %s do, in honest terms?" % name
        ans = ("%s (Self-described purpose, verbatim from its module docstring; "
               "all labels honest per Doctrine v11.)" % para)
        out.append((user, ans))
    return out


def mine_readme_status():
    """Mine the README 'Honest status' table -> claim/status Q&A."""
    src = _read(os.path.join(REPO, "README.md"))
    out = []
    m = re.search(r"## Honest status(.*?)\n---", src, re.DOTALL)
    if not m:
        return out
    for row in re.finditer(r"^\|\s*([^|]+?)\s*\|\s*\*\*([^|]+?)\*\*\s*\|",
                           m.group(1), re.MULTILINE):
        claim, status = row.group(1).strip(), row.group(2).strip()
        if claim.lower() == "claim":
            continue
        user = "What is the honest status of: %s?" % claim
        ans = ("%s → %s. This is the honest, published status; it is never "
               "upgraded past what is verified. Source: README.md honest-status "
               "table." % (claim, status))
        out.append((user, ans))
    return out


def build():
    seen = set()
    examples = []
    for user, ans in (DOCTRINE_FACTS + mine_surfaces() + mine_docstrings()
                      + mine_readme_status()):
        if not (_clean(user) and _clean(ans)):
            continue  # doctrine self-guard: drop anything carrying a banned token
        key = user.strip()
        if key in seen:
            continue
        seen.add(key)
        examples.append({"messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user.strip()},
            {"role": "assistant", "content": ans.strip()},
        ]})
    return examples


def main():
    ap = argparse.ArgumentParser(description="Build the SZL doctrine seed corpus.")
    ap.add_argument("--check", action="store_true",
                    help="verify counts/cleanliness only; do not write")
    args = ap.parse_args()

    examples = build()
    n = len(examples)
    # Doctrine self-guard assertions.
    assert 150 <= n <= 300, "seed count %d outside required [150,300]" % n
    for ex in examples:
        for msg in ex["messages"]:
            assert _clean(msg["content"]), "banned token leaked into seed"

    if args.check:
        print("build_seed: OK - %d clean examples (would write %s)" % (n, OUT))
        return 0

    with open(OUT, "w", encoding="utf-8") as fh:
        for ex in examples:
            fh.write(json.dumps(ex, ensure_ascii=False, sort_keys=True) + "\n")
    print("build_seed: wrote %d examples -> %s" % (n, OUT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
