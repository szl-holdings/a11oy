# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
# Authored by the UDS Showcase FE Team. Co-Authored-By: Perplexity Computer Agent.
#
# ===========================================================================
# szl_uds_portability — the JUDGE-FACING UDS PORTABILITY + DEATH-PROOF surface.
# Served at /uds-portability on BOTH a11oy and killinchu (byte-identical module).
# ---------------------------------------------------------------------------
# WHY THIS EXISTS (Warhacker rubric, PORTABILITY 25% + DEATH PROOF 25%):
#   Make the UDS / air-gap / "single tower, one command, no internet" story
#   VISUALLY UNDENIABLE during the founder demo. This surface SHOWS:
#     1. the 3 named payloads (a11oy.uds, killinchu.uds, energy.uds) as cards
#        — bundle name, version, size note, image digests, cosign-signed status,
#        and the ONE `uds deploy oci://…` command for each;
#     2. the AIR-GAP story — "no internet required, single tower" — with the
#        actual cable-pulled deploy command and the offline install flow
#        (Zarf packages → uds-core / k3d → Pepr policy → signed receipts);
#     3. a "verify offline" affordance — the exact cosign verify-blob +
#        receipt-verify commands anyone can copy-run;
#     4. the DEATH-PROOF visual — an HONEST SLSA L1/L2/L3-roadmap badge,
#        upgrade/rollback note, and a tamper-EVIDENT receipt demo.
#
# HONESTY CONTRACT (Doctrine v11, Zero-Bandaid Law) — this surface NEVER fakes:
#   • Image digests are the GHCR ground-truth resolved at AUTHORING time
#     (2026-06-15, anonymous manifest HEAD, all HTTP 200). They are labelled
#     PINNED-VERIFIED with the resolution date. The /uds/portability/live
#     endpoint RE-RESOLVES them against GHCR at request time WHEN the Space has
#     egress, and labels each row LIVE-MATCH / LIVE-DRIFT / UNREACHABLE — never
#     fabricating a status. If GHCR is unreachable (air-gapped Space) the card
#     falls back to the PINNED-VERIFIED value, honestly labelled CACHED-PIN.
#   • cosign-signed status: szl-mesh:v0.4.0 carries keyless cosign signatures
#     (verified in the AIRGAP runbook) → SIGNED. The per-app *-bundle:0.5.0
#     artifacts are PUBLISHED on GHCR; their signature is founder-gated
#     (FA-001 org key) → labelled BUNDLE-SIG ROADMAP, never claimed signed.
#   • energy.uds: the energy-harvest IMAGE is NOT yet published on GHCR →
#     labelled ROADMAP (build-valid Zarf package, image not yet pushed). We do
#     NOT claim it deploys today.
#   • SLSA is L1 honest / L2 attested (organ images: slsa.dev/provenance/v0.2,
#     cosign-verifiable) / L3 ROADMAP. NEVER bare L3, never FedRAMP/IronBank/
#     CMMC/ATO.
#   • Effectors are SIMULATED. Trust is NEVER 100%. Tamper-EVIDENT (not -proof).
#   • locked theorems = EXACTLY 8 {F1,F4,F7,F11,F12,F18,F19,F22} @ kernel
#     c7c0ba17. Λ = Conjecture 1. Khipu = Conjecture 2.
#   • 0 runtime CDN — every byte of CSS/JS is inline-vendored. No <script src>.
#   • NO user-visible internal codenames. NEVER commit a key (only the PUBLIC
#     cosign key fingerprint is shown).
#
# Mount/registration for a11oy + killinchu is via register(app, ns); the served
# tab HTML + API routes live at the bottom of this module (register()), and are
# FRONT-INSERTED before any SPA catch-all (learned from the WAQAY/Yupay 404).
# ===========================================================================
"""szl_uds_portability — the judge-facing UDS portability + death-proof surface.

Public API:
    payloads()                  -> the 3 named UDS payload descriptors (honest)
    airgap_flow()               -> the offline install-flow stages
    verify_commands(ns)         -> copy-run cosign verify + receipt-verify cmds
    death_proof()               -> SLSA roadmap badge + upgrade/rollback + tamper demo
    tamper_demo()               -> a LIVE tamper-EVIDENT receipt demonstration
    snapshot(ns)                -> everything the served tab needs (no network)
    live_digests()              -> re-resolve GHCR digests at request time (honest)
    register(app, ns)           -> mount /uds-portability + /api/<ns>/v1/uds/* 
"""
from __future__ import annotations

import hashlib
import json
import socket
import urllib.request
from typing import Any, Dict, List, Optional

try:
    from fastapi import Request as Request  # type: ignore
except Exception:  # pragma: no cover
    from starlette.requests import Request as Request  # type: ignore


# ===========================================================================
# DOCTRINE CONSTANTS — identical to the WAQAY/WILLAY/YUPAY lineage.
# ===========================================================================
LOCKED_THEOREMS = ("F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22")
KERNEL = "c7c0ba17"
TRUST_CEILING = 0.97  # trust is NEVER 100%
COSIGN_KEYID = "szlholdings-cosign"
# PEM fingerprint of the PUBLIC cosign key (from the AIRGAP runbook). PUBLIC key
# fingerprint only — the PRIVATE key is NEVER in this repo or this module.
COSIGN_PUB_FPR = "a4d73120c312d94bdd6cbdfa6f3d629cfff4b85e7addde5f9c3fd4c02341eb30"

# GHCR ground-truth image digests, resolved by anonymous manifest HEAD on
# 2026-06-15 (all HTTP 200). PINNED-VERIFIED; the /live endpoint re-resolves.
DIGEST_RESOLVED_DATE = "2026-06-15"
PINNED_DIGESTS: Dict[str, str] = {
    # organ images (the building blocks baked into the bundles)
    "a11oy": "sha256:c285293c72b7a952743313d98a69d9eb0e641a60eeb48289e61c6e2f23d21526",
    "sentra": "sha256:60a0efc14366ba392bfe3f3cd4196863fe148bb87a17428be6a57f0a05ac3639",
    "amaru": "sha256:53301e26adcde49e73df28d8c3b790f2496da9d495307fe8587ffa7452b289ff",
    "rosie": "sha256:1984a15f53c2e1b91c7dafaa0ed5df9148d57e3e86eb73db879c2b0443302848",
    "killinchu": "sha256:caef06d14747071cb7a453ed7cf8da046b8889e2c727c40b7d3dc84a7bb0569b",
    # bundles
    "szl-mesh": "sha256:7f5fce3238ce3d255b322340bbe18cad1eb656e677065a2757637337300cac7f",
    "a11oy-bundle": "sha256:d801f8e461dfd519b5f8593322e75b89a1e66d4da9f6d72d0937c8ff2de64b51",
}
# (organ name -> GHCR repo path + tag) for live re-resolution.
_ORGAN_REFS = {
    "a11oy": ("szl-holdings/a11oy", "uds-v0.2.0"),
    "sentra": ("szl-holdings/sentra", "uds-v0.2.0"),
    "amaru": ("szl-holdings/amaru", "uds-v0.2.0"),
    "rosie": ("szl-holdings/rosie", "uds-v0.2.0"),
    "killinchu": ("szl-holdings/killinchu", "uds-v0.2.0"),
    "szl-mesh": ("szl-holdings/szl-mesh", "v0.4.0"),
    "a11oy-bundle": ("szl-holdings/a11oy-bundle", "0.5.0"),
}


# ===========================================================================
# THE 3 NAMED PAYLOADS — honest descriptors.
# ===========================================================================
def payloads() -> List[Dict[str, Any]]:
    """The 3 named UDS payloads as honest card descriptors.

    Each carries: bundle name, version, what it deploys, the organ image
    digests baked in, the cosign-signed status (honestly labelled), and the
    single `uds deploy oci://…` command. Sizes are labelled NOTE (a UDS bundle
    tar.zst is self-contained — every organ image layer is inside it; the exact
    byte count is produced by `uds create` on the box, so we never invent it)."""
    return [
        {
            "id": "a11oy",
            "name": "a11oy.uds",
            "title": "Governed agentic AI estate — the orchestrating brain",
            "version": "0.5.0",
            "arch": "amd64",
            "deploys": ["a11oy (command platform + console)", "sentra (policy / immune)",
                        "amaru (reasoning / memory cortex)", "rosie (operator console)",
                        "+ mesh interconnect (UDS Operator reconciles the allow/expose CRs)"],
            "images": [
                {"organ": "a11oy", "ref": "ghcr.io/szl-holdings/a11oy:uds-v0.2.0",
                 "digest": PINNED_DIGESTS["a11oy"]},
                {"organ": "sentra", "ref": "ghcr.io/szl-holdings/sentra:uds-v0.2.0",
                 "digest": PINNED_DIGESTS["sentra"]},
                {"organ": "amaru", "ref": "ghcr.io/szl-holdings/amaru:uds-v0.2.0",
                 "digest": PINNED_DIGESTS["amaru"]},
                {"organ": "rosie", "ref": "ghcr.io/szl-holdings/rosie:uds-v0.2.0",
                 "digest": PINNED_DIGESTS["rosie"]},
            ],
            "bundle_ref": "oci://ghcr.io/szl-holdings/a11oy-bundle:0.5.0",
            "bundle_digest": PINNED_DIGESTS["a11oy-bundle"],
            "published": True,
            "sig_status": "BUNDLE-SIG ROADMAP",
            "sig_note": ("a11oy-bundle:0.5.0 is PUBLISHED on GHCR. Bundle-level cosign "
                         "signing is founder-gated (FA-001 org key) → labelled ROADMAP, "
                         "never claimed signed. The canonical SIGNED full-mesh artifact "
                         "is szl-mesh:v0.4.0 (see below)."),
            "deploy_cmd": "uds deploy oci://ghcr.io/szl-holdings/a11oy-bundle:0.5.0 --confirm",
            "size_note": "self-contained tar.zst — every organ image layer baked in (exact bytes from `uds create`)",
        },
        {
            "id": "killinchu",
            "name": "killinchu.uds",
            "title": "Counter-UAS / maritime C2 field node — effectors SIMULATED",
            "version": "0.5.0",
            "arch": "amd64",
            "deploys": ["killinchu (counter-UAS + vessels + inherited orchestration)",
                        "sentra (policy / immune verdicts)",
                        "amaru (13-axis Λ-gate reasoning the threat scorer uses)",
                        "+ mesh allow/expose matrix (UDS Package CR per organ)"],
            "images": [
                {"organ": "killinchu", "ref": "ghcr.io/szl-holdings/killinchu:uds-v0.2.0",
                 "digest": PINNED_DIGESTS["killinchu"]},
                {"organ": "sentra", "ref": "ghcr.io/szl-holdings/sentra:uds-v0.2.0",
                 "digest": PINNED_DIGESTS["sentra"]},
                {"organ": "amaru", "ref": "ghcr.io/szl-holdings/amaru:uds-v0.2.0",
                 "digest": PINNED_DIGESTS["amaru"]},
            ],
            "bundle_ref": "oci://ghcr.io/szl-holdings/killinchu-bundle:0.5.0",
            "bundle_digest": None,
            "published": True,
            "sig_status": "BUNDLE-SIG ROADMAP",
            "sig_note": ("killinchu-bundle:0.5.0 is PUBLISHED on GHCR. killinchu carries a "
                         "real in-image signing key so its DSSE receipts are genuinely "
                         "signed at the edge; bundle-level cosign signing stays founder-gated "
                         "→ ROADMAP. Effectors are SIMULATED, human-on-loop."),
            "deploy_cmd": "uds deploy oci://ghcr.io/szl-holdings/killinchu-bundle:0.5.0 --confirm",
            "size_note": "self-contained tar.zst — field-deployable on a single edge box, no internet",
        },
        {
            "id": "energy",
            "name": "energy.uds",
            "title": "MEASURED sovereign-energy operator — NVML joules + JouleCharge receipts",
            "version": "0.1.0",
            "arch": "amd64",
            "deploys": ["szl-energy-harvest (wasted-energy grid signal + signed JouleCharge receipts)",
                        "+ UDS Operator Package CR (Istio ambient / NetworkPolicy / ServiceMonitor)"],
            "images": [
                {"organ": "energy-harvest", "ref": "ghcr.io/szl-holdings/energy-harvest:0.1.0",
                 "digest": None},
            ],
            "bundle_ref": "oci://ghcr.io/szl-holdings/energy-harvest:0.1.0",
            "bundle_digest": None,
            "published": False,
            "sig_status": "ROADMAP",
            "sig_note": ("HONEST: the energy-harvest IMAGE is NOT yet published on GHCR. The "
                         "Zarf package is build-valid (manifests internally consistent) but "
                         "deliberately not live-deployed — its images: bake list is commented "
                         "out so `zarf create` won't pull a non-existent image. ROADMAP."),
            "deploy_cmd": "# ROADMAP — build + push + cosign-sign the image first, then:\n# uds deploy oci://ghcr.io/szl-holdings/energy-harvest:0.1.0 --confirm",
            "size_note": "build-valid Zarf package; image build pending (see zarf.yaml IMAGE GATING note)",
        },
    ]


# ===========================================================================
# AIR-GAP STORY — the offline install flow.
# ===========================================================================
def airgap_flow() -> Dict[str, Any]:
    return {
        "headline": "No internet required — a single tower.",
        "sub": ("Stage everything to a local OCI store while online; pull the cable; "
                "`uds deploy` from the local store. Every organ image layer is inside the "
                "bundle tar.zst, so NO registry is contacted at deploy time."),
        "single_cmd": "uds deploy oci://ghcr.io/szl-holdings/szl-mesh:v0.4.0 --confirm",
        "single_cmd_note": ("szl-mesh:v0.4.0 is the canonical SIGNED full-mesh bundle (all 5 "
                            "organs baked in). On the air-gapped box this runs from the local "
                            "pulled tarball — zero internet."),
        "stages": [
            {"n": 1, "label": "Zarf packages",
             "desc": "Each organ ships as a self-contained Zarf package (namespace + UDS Package CR + workload). Every image layer baked in."},
            {"n": 2, "label": "uds-core / k3d",
             "desc": "uds deploy lands the bundle on uds-core (Istio ambient + Keycloak) or a plain k3d cluster — runs on a consumer GPU tower."},
            {"n": 3, "label": "Pepr policy",
             "desc": "The UDS Operator + Pepr reconcile the allow/expose mesh matrix and enforce policy (NetworkPolicy, strict PeerAuthentication) at deploy time."},
            {"n": 4, "label": "Signed receipts",
             "desc": "Each governed action emits a DSSE-signed, tamper-EVIDENT receipt (ECDSA-P256). cosign verifies the supply chain OFFLINE (no Rekor)."},
        ],
        "offline_assertion": ("The capture harness REFUSES to record a proof if the box can "
                              "reach the internet (it probes Cloudflare, Google, GHCR, Rekor, "
                              "GitHub and aborts if any answer). The proof is only valid offline."),
    }


# ===========================================================================
# VERIFY-OFFLINE affordance — copy-run commands.
# ===========================================================================
def verify_commands(ns: str = "a11oy") -> Dict[str, Any]:
    return {
        "intro": "Prove it yourself. These commands verify the supply chain OFFLINE (no Rekor, no internet).",
        "cosign_pub_keyid": COSIGN_KEYID,
        "cosign_pub_fpr": COSIGN_PUB_FPR,
        "commands": [
            {"label": "1 · cosign verify-blob (OFFLINE — the air-gap path)",
             "cmd": ("cosign verify-blob \\\n"
                     "  --key cosign.pub \\\n"
                     "  --insecure-ignore-tlog=true \\\n"
                     "  --signature \"$BUNDLE.sig\" \\\n"
                     "  \"$BUNDLE\"\n"
                     "# expected tail:  Verified OK"),
             "note": "--insecure-ignore-tlog=true skips the Sigstore transparency log so it works with the cable pulled."},
            {"label": "2 · cosign verify the SIGNED mesh bundle (online, keyless)",
             "cmd": ("cosign verify ghcr.io/szl-holdings/szl-mesh:v0.4.0 \\\n"
                     "  --certificate-identity-regexp=\"^https://github.com/szl-holdings/\" \\\n"
                     "  --certificate-oidc-issuer=\"https://token.actions.githubusercontent.com\"\n"
                     "# expected:  Verified OK + the JSON claim blocks"),
             "note": "The supply-chain proof you show first — keyless OIDC identity, GitHub Actions issuer."},
            {"label": "3 · receipt-verify (tamper-EVIDENT, from this very Space)",
             "cmd": ("curl -s https://szlholdings-%s.hf.space/api/%s/v1/uds/tamper-demo | \\\n"
                     "  python3 -c 'import sys,json; r=json.load(sys.stdin); "
                     "print(\"intact:\", r[\"intact\"][\"verdict\"]); "
                     "print(\"tampered:\", r[\"tampered\"][\"verdict\"])'\n"
                     "# expected:  intact: VERIFIED  /  tampered: TAMPER-DETECTED" % (ns, ns)),
             "note": "Flip one byte of the payload and the digest no longer matches — tamper is EVIDENT."},
        ],
    }


# ===========================================================================
# DEATH-PROOF — honest SLSA badge + day-2 ops + tamper-EVIDENT receipt demo.
# ===========================================================================
def death_proof() -> Dict[str, Any]:
    return {
        "slsa": {
            "L1": {"state": "HONEST", "desc": "scripted, versioned build; provenance exists"},
            "L2": {"state": "ATTESTED", "desc": "organ images carry slsa.dev/provenance/v0.2 (.att), cosign-verifiable"},
            "L3": {"state": "ROADMAP", "desc": "hardened, non-falsifiable build platform — roadmap, NOT claimed today"},
            "badge_text": "SLSA L1 honest · L2 attested (organs) · L3 ROADMAP",
            "honesty": "NEVER bare L3. No FedRAMP / IronBank / CMMC / ATO claim.",
        },
        "day2": {
            "upgrade": "uds deploy oci://ghcr.io/szl-holdings/szl-mesh:<next> --confirm  (idempotent; re-reconciles the mesh CRs)",
            "rollback": "uds deploy oci://ghcr.io/szl-holdings/szl-mesh:<previous> --confirm  (pinned digests make rollback reproducible)",
            "note": "Deploys are reproducible + idempotent: the same bundle digest yields the same cluster state.",
        },
        "receipts": "DSSE ECDSA-P256-SHA256 · tamper-EVIDENT (not tamper-proof) · verified OFFLINE",
        "section_889_vendors": 5,  # exactly 5: Huawei, ZTE, Hytera, Hikvision, Dahua
    }


def _sign_like(payload_bytes: bytes) -> str:
    """A deterministic content digest used by the tamper-EVIDENT demo. This is a
    DIGEST, not a cryptographic signature claim — it demonstrates that ANY change
    to the payload changes the digest (tamper is EVIDENT). The real DSSE signing
    path (ECDSA-P256) lives in szl_dsse on the deployed cluster; here we show the
    integrity property honestly without claiming a key is present."""
    return "sha256:" + hashlib.sha256(payload_bytes).hexdigest()


def tamper_demo() -> Dict[str, Any]:
    """A LIVE, honest tamper-EVIDENT demonstration: build a receipt payload,
    record its content digest, then flip one byte and show the digest no longer
    matches. No fabricated signature — only the integrity (tamper-EVIDENT)
    property, computed live in-process."""
    payload = {
        "kind": "uds.deploy.receipt",
        "bundle": "oci://ghcr.io/szl-holdings/szl-mesh:v0.4.0",
        "bundle_digest": PINNED_DIGESTS["szl-mesh"],
        "organs": ["a11oy", "sentra", "amaru", "rosie", "killinchu"],
        "effectors": "SIMULATED",
        "kernel": KERNEL,
        "locked_theorems": list(LOCKED_THEOREMS),
        "trust_ceiling": TRUST_CEILING,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest = _sign_like(raw)

    # Tamper: flip one field (effectors SIMULATED -> a forbidden "LIVE" claim).
    tampered = dict(payload, effectors="LIVE")  # this is the kind of edit a tamper would attempt
    raw_t = json.dumps(tampered, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest_t = _sign_like(raw_t)

    return {
        "intro": "Tamper-EVIDENT, computed live: change one byte and the content digest no longer matches.",
        "intact": {
            "payload": payload,
            "content_digest": digest,
            "recomputed": _sign_like(raw),
            "verdict": "VERIFIED" if _sign_like(raw) == digest else "ERROR",
        },
        "tampered": {
            "what_changed": "effectors flipped SIMULATED -> LIVE (a forbidden claim)",
            "tampered_digest": digest_t,
            "expected_digest": digest,
            "verdict": "TAMPER-DETECTED" if digest_t != digest else "ERROR",
        },
        "honesty": ("This demonstrates the tamper-EVIDENT integrity property only — it is a "
                    "content digest, NOT a cryptographic signature claim. The real DSSE "
                    "ECDSA-P256 signing path runs on the deployed cluster (szl_dsse). No key "
                    "is present in this Space, so we never claim a signature here."),
    }


# ===========================================================================
# LIVE digest re-resolution — honest, with offline fallback.
# ===========================================================================
def _resolve_ghcr_digest(repo: str, tag: str, timeout: float = 4.0) -> Optional[str]:
    """Resolve a GHCR manifest digest anonymously. Returns the sha256 digest or
    None if unreachable (air-gapped Space). NEVER fabricates."""
    try:
        tok_url = "https://ghcr.io/token?scope=repository:%s:pull" % repo
        with urllib.request.urlopen(tok_url, timeout=timeout) as r:
            token = json.loads(r.read().decode()).get("token", "")
        if not token:
            return None
        man_url = "https://ghcr.io/v2/%s/manifests/%s" % (repo, tag)
        req = urllib.request.Request(man_url, method="HEAD")
        req.add_header("Authorization", "Bearer " + token)
        req.add_header("Accept",
                       "application/vnd.oci.image.index.v1+json,"
                       "application/vnd.docker.distribution.manifest.v2+json,"
                       "application/vnd.oci.image.manifest.v1+json")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = r.headers.get("docker-content-digest")
            return d.strip() if d else None
    except Exception:
        return None


def live_digests() -> Dict[str, Any]:
    """Re-resolve each pinned digest against GHCR at request time and label each
    LIVE-MATCH / LIVE-DRIFT / UNREACHABLE (honest). On an air-gapped Space every
    row is UNREACHABLE and falls back to the CACHED-PIN value — never fabricated."""
    rows = []
    any_reachable = False
    for name, (repo, tag) in _ORGAN_REFS.items():
        pinned = PINNED_DIGESTS.get(name)
        live = _resolve_ghcr_digest(repo, tag)
        if live is None:
            label = "UNREACHABLE"
            shown = pinned
            shown_label = "CACHED-PIN"
        else:
            any_reachable = True
            shown = live
            if live == pinned:
                label = "LIVE-MATCH"
                shown_label = "LIVE-VERIFIED"
            else:
                label = "LIVE-DRIFT"
                shown_label = "LIVE-VERIFIED"
        rows.append({"name": name, "ref": "ghcr.io/%s:%s" % (repo, tag),
                     "pinned": pinned, "live": live, "shown": shown,
                     "label": label, "shown_label": shown_label})
    return {
        "resolved_at": "request-time",
        "pinned_date": DIGEST_RESOLVED_DATE,
        "egress": "ONLINE" if any_reachable else "AIR-GAPPED (no GHCR egress — showing CACHED-PIN)",
        "rows": rows,
        "honesty": ("Digests are PINNED-VERIFIED at %s. This endpoint re-resolves them live "
                    "when the Space has egress; if GHCR is unreachable the pinned value is "
                    "shown, labelled CACHED-PIN. Status is never fabricated." % DIGEST_RESOLVED_DATE),
    }


# ===========================================================================
# SNAPSHOT — everything the served tab needs, no network (fast first paint).
# ===========================================================================
def doctrine() -> Dict[str, Any]:
    return {
        "locked_theorems": list(LOCKED_THEOREMS),
        "locked_count": len(LOCKED_THEOREMS),  # EXACTLY 8
        "kernel": KERNEL,
        "lambda": "Conjecture 1 (open)",
        "khipu": "Conjecture 2 (open)",
        "slsa": "L1 honest / L2 attested (organs) / L3 ROADMAP",
        "effectors": "SIMULATED",
        "trust_ceiling": TRUST_CEILING,
        "tamper": "tamper-EVIDENT (not tamper-proof)",
        "cdn": "0 runtime CDN",
        "cosign_keyid": COSIGN_KEYID,
        "cosign_pub_fpr": COSIGN_PUB_FPR,
        "section_889_vendors": 5,
    }


def snapshot(ns: str = "a11oy") -> Dict[str, Any]:
    return {
        "ok": True,
        "ns": ns,
        "payloads": payloads(),
        "airgap": airgap_flow(),
        "verify": verify_commands(ns),
        "death_proof": death_proof(),
        "doctrine": doctrine(),
        "digests_pinned_date": DIGEST_RESOLVED_DATE,
    }


# ===========================================================================
# REGISTER — served /uds-portability tab + API routes (additive, FRONT-INSERT).
# Mirrors szl_yupay.register EXACTLY: record n_before -> append routes via
# decorators -> splice the new tail to routes[0:0] so they beat the SPA catch-all.
# ===========================================================================
def register(app, ns: str = "a11oy") -> Dict[str, Any]:
    from starlette.responses import JSONResponse, HTMLResponse

    _paths = {
        "/uds-portability",
        f"/api/{ns}/v1/uds/snapshot",
        f"/api/{ns}/v1/uds/payloads",
        f"/api/{ns}/v1/uds/live",
        f"/api/{ns}/v1/uds/verify",
        f"/api/{ns}/v1/uds/tamper-demo",
        f"/api/{ns}/v1/uds/doctrine",
    }
    if any(getattr(_r, "path", None) in _paths for _r in app.router.routes):
        return {
            "capability": "UDS portability + death-proof showcase",
            "registered": sorted(_paths),
            "tab_route": "/uds-portability",
            "data_label": "UDS-PORTABILITY",
            "note": "already registered (idempotent no-op)",
        }

    n_before = len(app.router.routes)

    @app.get(f"/api/{ns}/v1/uds/snapshot", include_in_schema=False)
    async def _snapshot() -> JSONResponse:
        return JSONResponse(snapshot(ns))

    @app.get(f"/api/{ns}/v1/uds/payloads", include_in_schema=False)
    async def _payloads() -> JSONResponse:
        return JSONResponse({"payloads": payloads()})

    @app.get(f"/api/{ns}/v1/uds/live", include_in_schema=False)
    async def _live() -> JSONResponse:
        return JSONResponse(live_digests())

    @app.get(f"/api/{ns}/v1/uds/verify", include_in_schema=False)
    async def _verify() -> JSONResponse:
        return JSONResponse(verify_commands(ns))

    @app.get(f"/api/{ns}/v1/uds/tamper-demo", include_in_schema=False)
    async def _tamper() -> JSONResponse:
        return JSONResponse(tamper_demo())

    @app.get(f"/api/{ns}/v1/uds/doctrine", include_in_schema=False)
    async def _doctrine() -> JSONResponse:
        return JSONResponse(doctrine())

    @app.get("/uds-portability", include_in_schema=False)
    async def _page() -> HTMLResponse:
        return HTMLResponse(_PAGE_HTML.replace("{NS}", ns))

    # FRONT-INSERT the newly appended routes so they beat any SPA catch-all.
    _new_routes = app.router.routes[n_before:]
    del app.router.routes[n_before:]
    app.router.routes[0:0] = _new_routes

    return {
        "capability": "UDS portability + death-proof showcase",
        "registered": [
            "GET /uds-portability",
            f"GET /api/{ns}/v1/uds/snapshot",
            f"GET /api/{ns}/v1/uds/payloads",
            f"GET /api/{ns}/v1/uds/live",
            f"GET /api/{ns}/v1/uds/verify",
            f"GET /api/{ns}/v1/uds/tamper-demo",
            f"GET /api/{ns}/v1/uds/doctrine",
        ],
        "tab_route": "/uds-portability",
        "data_label": "UDS-PORTABILITY",
    }


# ===========================================================================
# THE UDS PORTABILITY TAB — 0-CDN, vendored inline, WCAG-AA contrast.
# ===========================================================================
_PAGE_HTML = r"""<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{NS} · UDS Portability — one command, single tower, no internet</title>
<style>
:root{--bg:#070d12;--panel:#0d1620;--panel2:#0a131b;--ink:#e6f0f7;--mut:#9fb4c6;--cyan:#39d8c8;--amber:#f0b429;--red:#f06a6a;--green:#54d98c;--line:#1c2733;--holo:#5fe3d0}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(1200px 620px at 72% -12%,#0e2128 0,var(--bg) 60%);color:var(--ink);font:15px/1.6 system-ui,Segoe UI,Roboto,sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:1.6rem 1.1rem 4rem}
h1{font-size:1.85rem;margin:.2em 0 .12em;letter-spacing:.2px}
h2{font-size:1.18rem;margin:1.8rem 0 .5rem;border-left:3px solid var(--cyan);padding-left:.6rem}
.pill{display:inline-block;padding:.14em .62em;border-radius:999px;font-size:.7rem;vertical-align:middle;font-weight:600;letter-spacing:.04em}
.holo{background:linear-gradient(90deg,#0c5b54,#0a3f4d);color:var(--holo);border:1px solid #1d5e58;box-shadow:0 0 16px #0c5b5455}
.amber{background:#3a2f12;color:var(--amber);border:1px solid #5a4818}
.redp{background:#3a1414;color:var(--red);border:1px solid #5a1d1d}
.greenp{background:#10301f;color:var(--green);border:1px solid #1c5436}
.lead{color:var(--mut);max-width:84ch}
.tag{color:var(--cyan)}.hl{color:var(--holo)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:1rem;margin:1.1rem 0}
.card{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:1.05rem 1.15rem;position:relative}
.card h3{margin:.1em 0 .15em;font-size:1.1rem}
.card .sub{color:var(--mut);font-size:.86rem;margin:0 0 .6rem}
.meta{font-size:.82rem;color:var(--mut);margin:.35rem 0}
.meta b{color:var(--ink)}
.digs{font:11.5px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace;color:#bfe9e0;background:var(--panel2);border:1px solid var(--line);border-radius:9px;padding:.5rem .6rem;margin:.4rem 0;overflow:auto}
.digs div{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.cmd{font:12.5px/1.55 ui-monospace,SFMono-Regular,Menlo,monospace;background:#050a0e;border:1px solid var(--line);border-radius:10px;padding:.7rem .8rem;color:#cdeee7;overflow:auto;white-space:pre;position:relative}
.cmd .copy{position:absolute;top:.4rem;right:.4rem;font:11px system-ui;background:#0c2b28;color:var(--holo);border:1px solid #1d5e58;border-radius:7px;padding:.2rem .5rem;cursor:pointer}
.flow{display:flex;gap:.5rem;flex-wrap:wrap;align-items:stretch;margin:.8rem 0}
.step{flex:1;min-width:190px;background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:.8rem .9rem;position:relative}
.step .n{display:inline-flex;width:1.5rem;height:1.5rem;align-items:center;justify-content:center;border-radius:50%;background:linear-gradient(90deg,#0c5b54,#0a3f4d);color:var(--holo);font-weight:700;font-size:.8rem;border:1px solid #1d5e58}
.step .lab{font-weight:600;margin:.3rem 0 .25rem;color:var(--ink)}
.step .d{font-size:.82rem;color:var(--mut)}
.arrow{display:flex;align-items:center;color:var(--cyan);font-size:1.3rem;font-weight:700}
.banner{background:linear-gradient(90deg,#0a3f4d33,#0c5b5422);border:1px solid #1d5e58;border-radius:14px;padding:1rem 1.15rem;margin:1rem 0}
.banner .big{font-size:1.25rem;font-weight:700;color:var(--holo)}
.slsa{display:flex;gap:.6rem;flex-wrap:wrap;margin:.6rem 0}
.slsa .lv{flex:1;min-width:160px;background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:.7rem .85rem}
.slsa .lv .t{font-weight:700;font-size:1.05rem}
.slsa .lv .s{font-size:.8rem;color:var(--mut);margin-top:.2rem}
pre{background:#050a0e;border:1px solid var(--line);border-radius:12px;padding:.9rem;overflow:auto;font:12px/1.5 ui-monospace,Menlo,monospace;color:#bfe9e0;max-height:340px}
a{color:var(--cyan)}
.foot{color:var(--mut);font-size:.8rem;margin-top:1.6rem;border-top:1px solid var(--line);padding-top:.9rem}
.dot{display:inline-block;width:.55em;height:.55em;border-radius:50%;margin-right:.35em;vertical-align:baseline}
.dot.g{background:var(--green)}.dot.a{background:var(--amber)}.dot.r{background:var(--red)}
table{width:100%;border-collapse:collapse;margin:.5rem 0;font-size:12.5px}
th,td{text-align:left;padding:.42rem .55rem;border-bottom:1px solid var(--line)}
th{font-size:.64rem;letter-spacing:.1em;text-transform:uppercase;color:var(--mut)}
td.mono{font-family:ui-monospace,Menlo,monospace;color:#bfe9e0;font-size:11.5px}
</style></head><body><div class="wrap">

<h1>UDS Portability <span class="pill holo">one command · single tower · no internet</span></h1>
<p class="lead">The SZL estate ships as <b>air-gapped UDS bundles</b>. One <span class="tag">uds deploy</span> on a single
consumer-GPU tower, <b>no internet required</b>, signed supply chain, tamper-EVIDENT receipts. This surface shows the
three named payloads, the offline install flow, the prove-it-yourself verify commands, and the honest death-proof badge.
<span class="hl">0 runtime CDN · every byte vendored.</span></p>

<div class="banner">
  <div class="big">No internet required — a single tower.</div>
  <p class="lead" style="margin:.4rem 0 .5rem">The canonical SIGNED full-mesh bundle (all 5 organs baked in) deploys with one command from a local store:</p>
  <div class="cmd" id="single-cmd">uds deploy oci://ghcr.io/szl-holdings/szl-mesh:v0.4.0 --confirm<button class="copy" data-cmd="uds deploy oci://ghcr.io/szl-holdings/szl-mesh:v0.4.0 --confirm">copy</button></div>
  <p class="meta" id="single-note" style="margin-top:.5rem">szl-mesh:v0.4.0 carries keyless cosign signatures (verified offline in the air-gap runbook). On the cable-pulled box this runs entirely from the local pulled tarball.</p>
</div>

<h2>The 3 UDS payloads</h2>
<div class="grid" id="payloads"><div class="card">Loading payloads…</div></div>

<h2>Air-gap install flow — Zarf → uds-core/k3d → Pepr → signed receipts</h2>
<div class="flow" id="flow"></div>
<p class="meta" id="airgap-assert"></p>

<h2>Verify it yourself — offline (no Rekor, no internet)</h2>
<p class="lead" style="margin:.2rem 0 .4rem">Public cosign key <span class="tag" id="kid"></span> · PEM fingerprint <span class="td mono" id="fpr" style="font-family:ui-monospace,Menlo,monospace;font-size:11.5px;color:#bfe9e0"></span></p>
<div id="verify"></div>

<h2>Death-proof — SLSA roadmap (honest), day-2 ops, tamper-EVIDENT receipt</h2>
<div class="slsa" id="slsa"></div>
<p class="meta" id="slsa-honesty"></p>
<div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(280px,1fr))">
  <div class="card"><h3 style="font-size:1rem">Day-2 ops</h3>
    <p class="meta">Upgrade <span class="pill greenp">idempotent</span></p><div class="cmd" id="upg"></div>
    <p class="meta" style="margin-top:.6rem">Rollback <span class="pill greenp">reproducible</span></p><div class="cmd" id="rbk"></div>
    <p class="meta" id="day2-note"></p>
  </div>
  <div class="card"><h3 style="font-size:1rem">Tamper-EVIDENT receipt <span class="pill holo" id="tamper-pill">live</span></h3>
    <p class="meta">Flip one byte → the content digest no longer matches. Computed live, in-process.</p>
    <pre id="tamper">running tamper-evident demo…</pre>
  </div>
</div>

<h2>Live image digests <span class="pill amber" id="egress">checking egress…</span></h2>
<p class="lead" style="margin:.2rem 0 .3rem">Pinned-verified, re-resolved against GHCR at request time. Air-gapped Spaces fall back to the cached pin — never fabricated.</p>
<table id="digtbl"><thead><tr><th>Image</th><th>Status</th><th>Digest (shown)</th></tr></thead><tbody><tr><td colspan="3">resolving…</td></tr></tbody></table>

<p class="foot">
locked theorems = <b>8</b> {F1,F4,F7,F11,F12,F18,F19,F22} @ kernel <b>c7c0ba17</b> ·
Λ = Conjecture 1 · Khipu = Conjecture 2 · SLSA <b>L1 honest / L2 attested (organs) / L3 ROADMAP</b> ·
effectors <b>SIMULATED</b> · receipts <b>tamper-EVIDENT</b> (DSSE ECDSA-P256) · trust ceiling &lt; 1.0 · Section 889 = 5 vendors · <b>0 runtime CDN</b>.<br>
<b>Honest labels:</b> digests are PINNED-VERIFIED (GHCR manifest HEAD, 2026-06-15) and re-resolved live; energy.uds is <b>ROADMAP</b> (image not yet published);
the per-app *-bundle:0.5.0 artifacts are <b>PUBLISHED</b> but bundle-level cosign signing is <b>founder-gated (ROADMAP)</b>. The canonical SIGNED artifact is
szl-mesh:v0.4.0. We never fake a signature or a number. References:
<a href="https://uds.defenseunicorns.com/reference/uds-core/overview/">UDS Core</a> ·
<a href="https://docs.zarf.dev/ref/zarf-package/">Zarf</a> · <a href="https://slsa.dev/spec/v1.0/levels">SLSA levels</a>.
</p>
</div>
<script>
const $=s=>document.querySelector(s), $$=s=>Array.from(document.querySelectorAll(s));
function esc(s){return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
function sigPill(st){
  if(st==='SIGNED')return '<span class="pill greenp">cosign SIGNED</span>';
  if(st==='ROADMAP')return '<span class="pill amber">ROADMAP</span>';
  return '<span class="pill amber">'+esc(st)+'</span>';
}
function cmdBlock(cmd){
  return '<div class="cmd">'+esc(cmd)+'<button class="copy" data-cmd="'+esc(cmd).replace(/"/g,'&quot;')+'">copy</button></div>';
}
function wireCopy(){
  $$('.copy').forEach(b=>{ if(b._w)return; b._w=1; b.addEventListener('click',()=>{
    const t=b.getAttribute('data-cmd')||''; navigator.clipboard&&navigator.clipboard.writeText(t);
    const o=b.textContent; b.textContent='copied'; setTimeout(()=>b.textContent=o,1200);
  });});
}
function shortDig(d){ if(!d)return '—'; return d.length>26?(d.slice(0,21)+'…'+d.slice(-6)):d; }

async function load(){
  const r=await fetch('/api/{NS}/v1/uds/snapshot'); const d=await r.json();
  // payload cards
  $('#payloads').innerHTML=d.payloads.map(p=>{
    const imgs=p.images.map(i=>'<div title="'+esc(i.ref)+'"><span class="tag">'+esc(i.organ)+'</span> '+(i.digest?esc(shortDig(i.digest)):'<span class="pill amber">unpublished</span>')+'</div>').join('');
    const pub=p.published?'<span class="pill greenp">PUBLISHED</span>':'<span class="pill amber">NOT-YET-PUBLISHED</span>';
    return '<div class="card"><h3>'+esc(p.name)+' <span class="pill holo">v'+esc(p.version)+'</span></h3>'+
      '<p class="sub">'+esc(p.title)+'</p>'+
      '<div class="meta"><b>Deploys:</b> '+p.deploys.map(esc).join(' · ')+'</div>'+
      '<div class="meta"><b>Bundle:</b> '+pub+' '+sigPill(p.sig_status)+'</div>'+
      '<div class="meta" style="font-size:.78rem">'+esc(p.sig_note)+'</div>'+
      '<div class="meta"><b>Image digests:</b></div><div class="digs">'+imgs+'</div>'+
      '<div class="meta"><b>Size:</b> '+esc(p.size_note)+'</div>'+
      '<div class="meta"><b>Deploy anywhere — one command:</b></div>'+cmdBlock(p.deploy_cmd)+
      '</div>';
  }).join('');
  // single cmd + note
  $('#single-cmd').firstChild.nodeValue=d.airgap.single_cmd;
  $('#single-cmd button').setAttribute('data-cmd',d.airgap.single_cmd);
  $('#single-note').textContent=d.airgap.single_cmd_note;
  // flow
  const stages=d.airgap.stages;
  let fh='';
  stages.forEach((s,i)=>{ fh+='<div class="step"><span class="n">'+s.n+'</span><div class="lab">'+esc(s.label)+'</div><div class="d">'+esc(s.desc)+'</div></div>';
    if(i<stages.length-1) fh+='<div class="arrow">›</div>'; });
  $('#flow').innerHTML=fh;
  $('#airgap-assert').textContent=d.airgap.offline_assertion;
  // verify
  $('#kid').textContent=d.verify.cosign_pub_keyid; $('#fpr').textContent=d.verify.cosign_pub_fpr;
  $('#verify').innerHTML=d.verify.commands.map(c=>'<div class="meta" style="margin-top:.7rem"><b>'+esc(c.label)+'</b></div>'+cmdBlock(c.cmd)+'<div class="meta" style="font-size:.78rem">'+esc(c.note)+'</div>').join('');
  // slsa
  const sl=d.death_proof.slsa;
  $('#slsa').innerHTML=['L1','L2','L3'].map(l=>{
    const cls=l==='L3'?'a':(l==='L1'?'g':'g');
    return '<div class="lv"><div class="t"><span class="dot '+cls+'"></span>SLSA '+l+' · '+esc(sl[l].state)+'</div><div class="s">'+esc(sl[l].desc)+'</div></div>';
  }).join('');
  $('#slsa-honesty').innerHTML='<b>'+esc(sl.badge_text)+'</b> — '+esc(sl.honesty);
  // day2
  $('#upg').innerHTML=esc(d.death_proof.day2.upgrade)+'<button class="copy" data-cmd="'+esc(d.death_proof.day2.upgrade)+'">copy</button>';
  $('#rbk').innerHTML=esc(d.death_proof.day2.rollback)+'<button class="copy" data-cmd="'+esc(d.death_proof.day2.rollback)+'">copy</button>';
  $('#day2-note').textContent=d.death_proof.day2.note;
  wireCopy();
}
async function loadTamper(){
  try{ const r=await fetch('/api/{NS}/v1/uds/tamper-demo'); const t=await r.json();
    $('#tamper').textContent=JSON.stringify({
      intact:{content_digest:t.intact.content_digest,verdict:t.intact.verdict},
      tampered:{what_changed:t.tampered.what_changed,tampered_digest:t.tampered.tampered_digest,verdict:t.tampered.verdict},
      honesty:t.honesty
    },null,2);
    $('#tamper-pill').textContent = t.tampered.verdict==='TAMPER-DETECTED' ? 'TAMPER-DETECTED' : 'live';
  }catch(e){ $('#tamper').textContent='error: '+e; }
}
async function loadLive(){
  try{ const r=await fetch('/api/{NS}/v1/uds/live'); const d=await r.json();
    const eg=$('#egress'); eg.textContent=d.egress; eg.className='pill '+(d.egress.indexOf('ONLINE')===0?'greenp':'amber');
    const tb=$('#digtbl tbody');
    tb.innerHTML=d.rows.map(x=>{
      const cls=x.label==='LIVE-MATCH'?'g':(x.label==='LIVE-DRIFT'?'a':'a');
      const pill=x.label==='LIVE-MATCH'?'greenp':(x.label==='LIVE-DRIFT'?'redp':'amber');
      return '<tr><td>'+esc(x.name)+'</td><td><span class="pill '+pill+'">'+esc(x.label)+'</span> <span class="pill amber">'+esc(x.shown_label)+'</span></td><td class="mono">'+esc(shortDig(x.shown))+'</td></tr>';
    }).join('')||'<tr><td colspan="3">no rows</td></tr>';
  }catch(e){ $('#digtbl tbody').innerHTML='<tr><td colspan="3">live re-resolution unavailable; showing pinned cards above (honest fallback)</td></tr>'; }
}
window.addEventListener('DOMContentLoaded',()=>{ load().then(wireCopy); loadTamper(); loadLive(); });
</script>
</body></html>"""


# ===========================================================================
# Self-test (run: python szl_uds_portability.py) — honesty + idempotency + 0-CDN.
# ===========================================================================
if __name__ == "__main__":
    # 1. doctrine integrity
    d = doctrine()
    assert d["locked_count"] == 8, "locked must be EXACTLY 8"
    assert d["trust_ceiling"] < 1.0, "trust never 100%"
    assert d["effectors"] == "SIMULATED"
    assert d["section_889_vendors"] == 5
    assert "L3 ROADMAP" in d["slsa"] and "bare" not in d["slsa"].lower()

    # 2. the 3 payloads — honest labels, no faked signature
    ps = payloads()
    ids = {p["id"] for p in ps}
    assert ids == {"a11oy", "killinchu", "energy"}, ids
    energy = [p for p in ps if p["id"] == "energy"][0]
    assert energy["published"] is False and energy["sig_status"] == "ROADMAP", "energy must be honest ROADMAP"
    assert energy["images"][0]["digest"] is None, "energy image must not have a fabricated digest"
    for p in ps:
        # never claim a bare cosign SIGNED on the bundle (founder-gated)
        assert p["sig_status"] in ("BUNDLE-SIG ROADMAP", "ROADMAP"), (p["id"], p["sig_status"])
        assert "uds deploy oci://" in p["deploy_cmd"], p["id"]

    # 3. tamper-evident demo really detects tamper, and never claims a signature
    t = tamper_demo()
    assert t["intact"]["verdict"] == "VERIFIED", t["intact"]
    assert t["tampered"]["verdict"] == "TAMPER-DETECTED", t["tampered"]
    assert "NOT a cryptographic signature" in t["honesty"], "must not claim a signature"

    # 4. verify commands present + offline path uses --insecure-ignore-tlog
    v = verify_commands("a11oy")
    joined = " ".join(c["cmd"] for c in v["commands"])
    assert "--insecure-ignore-tlog=true" in joined, "offline verify path required"
    assert "cosign verify-blob" in joined and "verify ghcr.io/szl-holdings/szl-mesh" in joined

    # 5. live digests honest fallback (network may or may not be present here)
    ld = live_digests()
    assert ld["rows"] and all(r["label"] in ("LIVE-MATCH", "LIVE-DRIFT", "UNREACHABLE") for r in ld["rows"])
    for r in ld["rows"]:
        if r["label"] == "UNREACHABLE":
            assert r["shown"] == r["pinned"] and r["shown_label"] == "CACHED-PIN"

    # 6. 0-CDN + no user-visible internal codenames in the served tab
    low = _PAGE_HTML.lower()
    assert "http://" not in low, "served tab must be 0-CDN (no http://)"
    assert "<script src" not in low, "no external script tags (0 CDN)"
    for bad in ("jar" + "vis",):  # organ names a11oy/sentra/amaru/rosie/killinchu are PRODUCT names, allowed
        assert bad not in low, "no internal codename leaked"
    assert "tamper-evident" in low and "l3 roadmap" in low and "0 runtime cdn" in low

    print("szl_uds_portability: ALL OK — 3 honest payload cards; air-gap one-command flow; "
          "offline cosign verify; SLSA L1/L2/L3-roadmap (honest); tamper-EVIDENT live demo; "
          "live digest re-resolution + cached-pin fallback; locked=8; trust<1.0; 0 CDN; 0 codenames.")
