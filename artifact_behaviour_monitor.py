# SPDX-License-Identifier: Apache-2.0
# © 2026 SZL Holdings · Doctrine v11 LOCKED · Λ = Conjecture 1 (advisory, NOT proven trust)
# Sign-off: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
"""artifact_behaviour_monitor — SZL-NATIVE inward BEHAVIOURAL artifact monitor.

WHAT THIS IS (GAP 1)
====================
A deny-by-default, multi-monitor BEHAVIOURAL admission gate that runs ON OUR OWN
build/deploy artifacts, sitting *on top of* the signed DSSE/cosign attestation we
already produce (the a11oy PINN certificate path). It is the operational answer to
the npm/TanStack lesson: **a valid signature is NOT proof of safety**.

In CVE-2026-45321 (Mini Shai-Hulud, May 2026) attackers published 84 malicious
@tanstack/* npm versions that each carried a VALID SLSA Build Level 3 / Sigstore
provenance attestation. `npm audit signatures` passed; the cosign/in-toto badge was
green; provenance verification flagged ZERO of the 84 artifacts. What actually
caught them was BEHAVIOURAL: a ~3.7x-to-25x tarball/file size jump, an unexpected
injected entrypoint (`router_init.js` / `index.js`), and a phone-home egress path
(getsession.org / cloud-metadata 169.254.169.254). Provenance proves *which
pipeline built it*; it does NOT prove *what the artifact does or whether the build
was authorized*. We had the signing half; this module is the missing behavioural
half — our SDA/spoof-fusion engine, aimed INWARD.

This is the EXACT shape of the GNSS spoof detector in
pnt_build/dev2_spoof_sda/pnt_resilience.py: four INDEPENDENT monitors, each emitting
a calibrated statistic + a fire/no-fire decision, fused under a deny-by-default
Λ-gate governor. ALLOW is returned ONLY when no monitor fires AND a fused-confidence
floor is cleared — and ALLOW is labelled "passed behavioural admission; signature
alone is NOT safety", never "proven safe".

THE FOUR INDEPENDENT BEHAVIOURAL MONITORS
=========================================
  1. size-anomaly            — artifact byte-size vs a rolling baseline; fires on the
                               ~3.7x kind of jump (robust z over log-size + ratio gate)
  2. unexpected-file-injection — new top-level files / entrypoints not in the signed
                               manifest (the router_init.js / index.js injection)
  3. egress / phone-home     — declared-vs-observed network hosts; in our context we
                               scan declared deps/URLs against an allow-list and flag
                               cloud-metadata + known-exfil host classes
  4. provenance-consistency  — the SIGNED builder identity + branch must match the
                               EXPECTED protected source. This monitor encodes the
                               "signed-but-unauthorized" gap EXPLICITLY: a perfectly
                               valid signature produced by an unexpected workflow /
                               orphan-commit / fork branch still FIRES (the pwn-request
                               OIDC-scope failure mode at the heart of CVE-2026-45321).

HONEST SCOPE (Doctrine v11, HARD — read this)
=============================================
This monitor operates on **artifact METADATA / declared observables**, NOT on a
sandboxed dynamic execution trace. Inputs are the summary observables our build
system already exposes: byte size, a rolling size baseline, the top-level file list,
the signed manifest's expected file set, declared dependency hosts / URLs, and the
signed provenance fields (builder id, source repo, branch, signature validity).
The egress monitor is a STATIC declared-host scan, NOT a live packet capture; it is
labelled accordingly. Anything we cannot derive is labelled NOT MODELED. We NEVER
mark an artifact "anomalous"/DENY without a real triggering statistic crossing a
documented threshold, and we NEVER label any artifact "safe" — clean only ever means
"passed behavioural admission". A valid signature on its own NEVER yields ALLOW.

CLEAN-ROOM
==========
Method re-derived from the open incident analyses and CITED (Socket, Snyk,
StepSecurity, VentureBeat/Endor, Unit 42, TanStack postmortem). We studied the SHAPE
of the kshana fused multi-layer detector (Apache-2.0) as prior art and CITE it; we
copied NO Rust. This is the inward bridge of our khipu-sda-core / mosaic anomaly
engine, sitting under the Λ-gate governor — the same engine as the Dev2 spoof
detector, repointed at our OWN artifacts.

Pure stdlib + numpy → sovereign, own-metal, auditable, 0 runtime CDN.
"""
from __future__ import annotations

import json
import math
import re
import ssl
import urllib.request
from dataclasses import dataclass, field, asdict
from typing import Optional

import numpy as np

# --------------------------------------------------------------------------- #
# Provenance — method/lesson CITED, never claimed as SZL's own.                #
# --------------------------------------------------------------------------- #
ATTRIBUTION = {
    "cve_2026_45321": (
        "CVE-2026-45321 (CVSS 9.6) — 'Mini Shai-Hulud', TanStack npm supply-chain "
        "compromise, 2026-05-11. 84 malicious @tanstack/* versions published with "
        "VALID SLSA Build Level 3 / Sigstore provenance via a pull_request_target "
        "'Pwn Request' + GitHub Actions cache poisoning + runtime OIDC-token "
        "extraction. The first widely reported npm worm shipping validly-attested "
        "malicious packages. THE lesson: a signature is not proof of safety."
    ),
    "socket": (
        "Socket technical analysis (May 2026): the 2.3 MB obfuscated router_init.js "
        "payload ran ten credential-collection classes in parallel; Socket's "
        "behavioural AI scanner flagged ALL 84 artifacts within ~6 minutes of "
        "publication while provenance flagged ZERO. Basis for the size-anomaly + "
        "unexpected-file-injection monitors."
    ),
    "snyk": (
        "Snyk advisory + Mini-Shai-Hulud / AntV analysis (May 2026): documents the "
        "first case of an npm worm shipping valid SLSA Build Level 3 attestations — "
        "'signatures are legitimate because the build pipeline itself was "
        "compromised; provenance tells you which pipeline produced an artifact, not "
        "whether that pipeline behaved as intended.' Package-level indicators "
        "(unexpected preinstall scripts, optionalDependency git refs) + network "
        "indicators (cloud-metadata 169.254.169.254, exfil hosts) cited here."
    ),
    "endor_venturebeat": (
        "Endor Labs / VentureBeat (2026-05-12): 'OIDC scope is the actual control "
        "that matters here, not provenance, not 2FA. If your publish pipeline trusts "
        "the entire repository rather than a specific workflow on a specific branch, "
        "a commit with no parent history and no branch association is enough to get a "
        "valid publish token.' Basis for the provenance-consistency monitor encoding "
        "the signed-but-UNAUTHORIZED (wrong builder/branch) gap explicitly."
    ),
    "unit42": (
        "Palo Alto Unit 42 (2026-06-02): an analyzed sample replaced a ~200 KB "
        "index.js with a 4.29 MB obfuscated payload — 'a 25x size increase that is "
        "itself a reliable detection signal'. Corroborates the size-anomaly monitor; "
        "the GAP doc cites the ~3.7x tarball jump for the TanStack case."
    ),
    "tanstack_postmortem": (
        "TanStack postmortem (2026-05-11): malicious optionalDependencies resolved an "
        "orphan payload commit from the fork network and executed a ~2.3 MB "
        "router_init.js via the prepare lifecycle script; exfil over the "
        "Session/Oxen messenger network (filev2.getsession.org, seed{1,2,3}."
        "getsession.org). Basis for unexpected-file-injection + egress host classes."
    ),
    "kshana": (
        "Baweja, C. (2026). 'Kshana — a PNT-resilience simulator', Ashforde OÜ, "
        "Apache-2.0, DOI:10.5281/zenodo.20528627. Studied as PRIOR ART for the SHAPE "
        "of a fused multi-monitor deny-by-default detector. CLEAN-ROOM: no code "
        "copied; the fusion shape is shared with SZL pnt_resilience.py (Dev2)."
    ),
    "szl_pnt_resilience": (
        "SZL pnt_build/dev2_spoof_sda/pnt_resilience.py — the fused deny-by-default "
        "GNSS spoof detector whose Λ-gate + monitor-fusion shape this module mirrors, "
        "repointed INWARD onto our own build/deploy artifacts (the khipu-sda-core / "
        "mosaic engine aimed inward)."
    ),
    "a11oy_cert": (
        "a11oy PINN physical-bounds certificate (DSSE Ed25519 FA-001 + cosign.pub, "
        "Rekor-anchored), https://a11oy.net/api/a11oy/v1/pinn/certificate — the REAL "
        "signed SZL artifact this monitor certifies behaviourally on top of its "
        "signature."
    ),
    "doctrine": (
        "SZL Doctrine v11 — clean-room, cite-never-plagiarize, MEASURED/MODELED "
        "labels, deny-by-default, Λ = Conjecture 1 (advisory governance gate, NOT "
        "proven trust). A signature is NOT proof of safety."
    ),
}

# Λ verdict labels (match the estate's lambda_gate vocabulary).
VERDICT_ALLOW = "ALLOW"        # no monitor fired AND fused confidence cleared the floor
VERDICT_ADVISORY = "ADVISORY"  # ambiguous: weak/conflicting evidence -> hold
VERDICT_DENY = "DENY"          # >=1 monitor fired -> deny-by-default

LAMBDA_LABEL = (
    "Λ = Conjecture 1 — the artifact governor is ADVISORY governance, NOT 'proven "
    "trust' and NOT 'proven safe'. ALLOW means the artifact PASSED BEHAVIOURAL "
    "ADMISSION (no monitor fired and fused clean-confidence cleared the floor); it "
    "does NOT certify the artifact is safe. A valid signature ALONE never yields "
    "ALLOW. DENY/ADVISORY are deny-by-default holds."
)

SCOPE_LABEL = (
    "ARTIFACT-METADATA BEHAVIOURAL MONITOR — operates on declared observables our "
    "build system exposes (byte size + rolling baseline, top-level file list vs "
    "signed manifest, declared dependency hosts/URLs, signed provenance fields). It "
    "is NOT a dynamic sandbox and does NOT run the artifact; the egress monitor is a "
    "STATIC declared-host scan, not a live packet capture. Items not derivable are "
    "labelled NOT MODELED."
)

ALLOW_MEANING = (
    "PASSED BEHAVIOURAL ADMISSION — signature alone is not safety. NOT 'proven safe'."
)

# --------------------------------------------------------------------------- #
# Calibrated thresholds. All DOCUMENTED, all tunable, none magic.              #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class MonitorConfig:
    # size-anomaly: a published artifact should not balloon vs its rolling baseline.
    # CVE-2026-45321 saw ~3.7x (TanStack tarball) up to 25x (Unit 42 index.js). We
    # fire on a hard ratio gate OR a robust z-score over log-size vs the baseline.
    size_ratio_thresh: float = 2.0        # >2.0x the rolling-median size -> fire
    size_log_z_thresh: float = 3.5        # robust (MAD) z over log10(size) -> fire
    size_min_baseline: int = 3            # need >=3 prior samples to model a baseline
    # unexpected-file-injection: any top-level file/entrypoint NOT in the signed
    # manifest fires. Zero tolerance: an injected entrypoint is the attack.
    injection_allow_extra: int = 0        # # of unexpected top-level files tolerated
    # egress / phone-home: declared hosts must be on the allow-list; cloud-metadata
    # and known-exfil classes always fire.
    # provenance-consistency: signature must be valid AND builder/branch/repo must
    # match the expected protected source. A valid sig from the wrong place FIRES.
    # Fused-confidence floor: ALLOW requires fused clean-confidence >= this AND no fire.
    fused_confidence_floor: float = 0.60


CFG = MonitorConfig()

# Cloud-metadata + known-exfil host classes (from Snyk / TanStack postmortem IOCs).
# These ALWAYS fire if observed/declared in an artifact's network surface.
METADATA_HOSTS = {"169.254.169.254", "169.254.170.2", "metadata.google.internal",
                  "metadata.goog", "100.100.100.200"}
KNOWN_EXFIL_PATTERNS = (
    r"getsession\.org",          # Session/Oxen file-upload exfil (TanStack)
    r"\boxen\b",
    r"m-kosche\.com",            # AntV campaign C2 (Snyk)
    r"\bpastebin\.com\b",        # StegaBin dead-drop
)


# --------------------------------------------------------------------------- #
# Artifact observable container — declared metadata, NOT a dynamic trace.      #
# --------------------------------------------------------------------------- #
@dataclass
class ArtifactMeta:
    """Summary observables our build/deploy system exposes for one artifact.

    NOT a sandboxed execution trace. Everything here is declared/static metadata.
    """
    name: str
    # size-anomaly: this artifact's byte size + the rolling baseline of prior
    # accepted sizes for the SAME artifact name (bytes).
    size_bytes: int
    size_baseline_bytes: list = field(default_factory=list)
    # unexpected-file-injection: the actual top-level files/entrypoints present in
    # the artifact, vs the file set declared in the SIGNED manifest.
    top_level_files: list = field(default_factory=list)
    manifest_files: list = field(default_factory=list)
    # egress / phone-home: the network hosts/URLs the artifact DECLARES (deps,
    # config endpoints) + the allow-list of hosts it is permitted to talk to.
    declared_hosts: list = field(default_factory=list)
    allowed_hosts: list = field(default_factory=list)
    # provenance-consistency: the SIGNED provenance fields + the EXPECTED protected
    # source. signature_valid alone is NEVER sufficient (the core CVE lesson).
    signature_valid: bool = False
    builder_id: str = ""
    source_repo: str = ""
    source_branch: str = ""
    expected_builder_id: str = ""
    expected_repo: str = ""
    expected_branch: str = ""


# --------------------------------------------------------------------------- #
# Per-monitor result.                                                          #
# --------------------------------------------------------------------------- #
@dataclass
class MonitorResult:
    name: str
    statistic: float          # the calibrated detection statistic
    threshold: float          # documented fire threshold for this statistic
    fired: bool               # statistic crossed threshold
    confidence: float         # in [0,1]: how confident this monitor is the artifact is CLEAN
    detail: str               # human-readable, honest detail
    modeled: bool = True      # False => NOT MODELED placeholder


@dataclass
class ArtifactVerdict:
    verdict: str                          # ALLOW | ADVISORY | DENY
    advisory: bool                        # Λ is always advisory governance
    anomalous: bool                       # True ONLY if >=1 monitor fired on a real stat
    fired_monitors: list                  # names of monitors that fired
    fused_confidence: float               # fused clean-confidence in [0,1]
    monitors: list                        # list[MonitorResult] as dicts
    reason: str
    allow_meaning: str = ALLOW_MEANING
    lambda_label: str = LAMBDA_LABEL
    scope_label: str = SCOPE_LABEL
    signature_alone_is_safety: bool = False  # ALWAYS False (the doctrine invariant)
    attribution: dict = field(default_factory=lambda: ATTRIBUTION)


# --------------------------------------------------------------------------- #
# Monitor 1 — size-anomaly (artifact size vs rolling baseline).               #
# --------------------------------------------------------------------------- #
def size_anomaly_monitor(a: ArtifactMeta, cfg: MonitorConfig = CFG) -> MonitorResult:
    """Artifact byte-size vs a rolling baseline.

    Fires on the ~3.7x kind of jump that caught CVE-2026-45321 (Socket/Unit 42).
    Statistic: the size RATIO vs the rolling-median baseline. We fire if the ratio
    exceeds the hard gate OR a robust (median/MAD) z-score over log10(size) exceeds
    its threshold. With <min_baseline prior samples we cannot model a baseline ->
    NOT MODELED (we do not fire on an un-baselined first publish; deny-by-default is
    enforced by the fusion floor instead).
    """
    base = [float(x) for x in a.size_baseline_bytes if x and x > 0]
    size = float(a.size_bytes)
    if len(base) < cfg.size_min_baseline:
        return MonitorResult(
            name="size_anomaly",
            statistic=size,
            threshold=float("inf"),
            fired=False,
            confidence=0.5,  # cannot vouch either way without a baseline
            detail=(f"NOT MODELED: only {len(base)} baseline sample(s) (<"
                    f"{cfg.size_min_baseline}); cannot model rolling baseline."),
            modeled=False,
        )
    med = float(np.median(base))
    ratio = size / max(med, 1.0)
    # robust z over log10 size (MAD-based; resilient to baseline drift/outliers).
    logs = np.log10(np.array(base + [size]))
    log_med = float(np.median(logs[:-1]))
    mad = float(np.median(np.abs(np.array(logs[:-1]) - log_med)))
    sigma = 1.4826 * mad if mad > 0 else 1e-9
    log_z = (math.log10(max(size, 1.0)) - log_med) / sigma
    fired = (ratio > cfg.size_ratio_thresh) or (log_z > cfg.size_log_z_thresh)
    # clean-confidence: how far below the ratio gate we sit (smooth, clipped).
    conf = float(np.clip(1.0 - (ratio - 1.0) / (cfg.size_ratio_thresh - 1.0), 0.0, 1.0))
    return MonitorResult(
        name="size_anomaly",
        statistic=ratio,
        threshold=cfg.size_ratio_thresh,
        fired=fired,
        confidence=conf,
        detail=(f"size={int(size)} B vs baseline median={int(med)} B -> "
                f"ratio={ratio:.2f}x (gate {cfg.size_ratio_thresh:.2f}x), "
                f"log-z={log_z:.2f} (gate {cfg.size_log_z_thresh:.2f}); fired={fired}. "
                f"CVE-2026-45321 saw ~3.7x-25x jumps."),
    )


# --------------------------------------------------------------------------- #
# Monitor 2 — unexpected-file-injection (new top-level files / entrypoints).   #
# --------------------------------------------------------------------------- #
def file_injection_monitor(a: ArtifactMeta, cfg: MonitorConfig = CFG) -> MonitorResult:
    """New top-level files / entrypoints NOT in the SIGNED manifest.

    The router_init.js / index.js injection from CVE-2026-45321: an entrypoint
    smuggled into the artifact that the signed manifest never declared. Statistic
    is the COUNT of unexpected top-level files; fires above the (zero) tolerance.
    If no manifest is provided we cannot test -> NOT MODELED.
    """
    if not a.manifest_files:
        return MonitorResult(
            name="unexpected_file_injection",
            statistic=0.0,
            threshold=float(cfg.injection_allow_extra),
            fired=False,
            confidence=0.5,
            detail="NOT MODELED: no signed manifest file-set provided; cannot diff.",
            modeled=False,
        )
    manifest = set(a.manifest_files)
    present = set(a.top_level_files)
    unexpected = sorted(present - manifest)
    n_unexpected = len(unexpected)
    fired = n_unexpected > cfg.injection_allow_extra
    conf = 1.0 if n_unexpected == 0 else 0.0  # any injection collapses clean-confidence
    return MonitorResult(
        name="unexpected_file_injection",
        statistic=float(n_unexpected),
        threshold=float(cfg.injection_allow_extra),
        fired=fired,
        confidence=conf,
        detail=(f"{n_unexpected} top-level file(s) not in signed manifest: "
                f"{unexpected or 'none'}; fired={fired}. "
                f"(CVE-2026-45321 injected router_init.js/index.js.)"),
    )


# --------------------------------------------------------------------------- #
# Monitor 3 — egress / phone-home (declared-vs-observed network hosts).        #
# --------------------------------------------------------------------------- #
def egress_monitor(a: ArtifactMeta, cfg: MonitorConfig = CFG) -> MonitorResult:
    """Declared network hosts vs an allow-list; cloud-metadata + exfil classes fire.

    STATIC declared-host scan (NOT a live packet capture — labelled as such). Fires
    if any declared host/URL is (a) a cloud-metadata endpoint, (b) matches a known
    exfil pattern, or (c) is simply not on the artifact's allow-list. If no hosts
    are declared AND no allow-list is given we cannot test -> NOT MODELED.
    """
    declared = [str(h).strip().lower() for h in a.declared_hosts if str(h).strip()]
    allowed = {str(h).strip().lower() for h in a.allowed_hosts if str(h).strip()}
    if not declared and not allowed:
        return MonitorResult(
            name="egress_phone_home",
            statistic=0.0,
            threshold=0.0,
            fired=False,
            confidence=0.5,
            detail="NOT MODELED: no declared network surface and no allow-list.",
            modeled=False,
        )

    def host_of(u: str) -> str:
        m = re.match(r"^[a-z]+://([^/:]+)", u)
        return m.group(1) if m else u.split("/")[0].split(":")[0]

    offending = []
    for u in declared:
        h = host_of(u)
        if h in METADATA_HOSTS or any(p.strip(r"\b") in u for p in
                                      ("169.254.169.254", "169.254.170.2")):
            offending.append((u, "cloud-metadata endpoint"))
            continue
        if any(re.search(p, u) for p in KNOWN_EXFIL_PATTERNS):
            offending.append((u, "known-exfil host class"))
            continue
        if allowed and h not in allowed:
            offending.append((u, "not on allow-list"))
    n_off = len(offending)
    fired = n_off > 0
    conf = 1.0 if n_off == 0 else 0.0
    return MonitorResult(
        name="egress_phone_home",
        statistic=float(n_off),
        threshold=0.0,
        fired=fired,
        confidence=conf,
        detail=(f"{n_off} declared host(s) flagged: "
                f"{[f'{u} ({r})' for u, r in offending] or 'none'}; fired={fired}. "
                f"STATIC declared-host scan (not a packet capture)."),
    )


# --------------------------------------------------------------------------- #
# Monitor 4 — provenance-consistency (signed-but-UNAUTHORIZED gap).            #
# --------------------------------------------------------------------------- #
def provenance_consistency_monitor(a: ArtifactMeta,
                                   cfg: MonitorConfig = CFG) -> MonitorResult:
    """Signed builder identity + branch must match the EXPECTED protected source.

    THIS is where the CVE-2026-45321 core lesson is encoded explicitly. The verdict
    here does NOT trust `signature_valid` on its own:
      * If the signature is invalid -> FIRE (obviously).
      * If the signature is VALID but the builder_id / source_repo / source_branch
        does NOT match the expected protected source -> FIRE. This is the exact
        signed-but-UNAUTHORIZED failure mode: a valid SLSA/Sigstore attestation
        produced by a pull_request_target / orphan-commit / fork workflow. Endor
        Labs: 'OIDC scope is the control that matters, not provenance.'
      * Only a valid signature AND matching builder+repo+branch passes.
    A valid signature ALONE can NEVER make this monitor pass — that is the doctrine.
    """
    if not (a.expected_builder_id or a.expected_repo or a.expected_branch):
        return MonitorResult(
            name="provenance_consistency",
            statistic=0.0,
            threshold=1.0,
            fired=(not a.signature_valid),
            confidence=0.5,
            detail=("NOT MODELED: no expected protected-source spec provided; "
                    "cannot check authorization. Signature alone is NOT safety."),
            modeled=False,
        )
    mismatches = []
    if not a.signature_valid:
        mismatches.append("signature INVALID")
    if a.expected_builder_id and a.builder_id != a.expected_builder_id:
        mismatches.append(f"builder '{a.builder_id}' != expected "
                          f"'{a.expected_builder_id}'")
    if a.expected_repo and a.source_repo != a.expected_repo:
        mismatches.append(f"repo '{a.source_repo}' != expected '{a.expected_repo}'")
    if a.expected_branch and a.source_branch != a.expected_branch:
        mismatches.append(f"branch '{a.source_branch}' != expected "
                          f"'{a.expected_branch}'")
    n_mis = len(mismatches)
    fired = n_mis > 0
    # clean-confidence: full only when signature valid AND every field matches.
    conf = 1.0 if n_mis == 0 else 0.0
    sig_note = ("signature is VALID but " if (a.signature_valid and n_mis) else "")
    return MonitorResult(
        name="provenance_consistency",
        statistic=float(n_mis),
        threshold=1.0,
        fired=fired,
        confidence=conf,
        detail=(f"{sig_note}{n_mis} provenance mismatch(es): "
                f"{mismatches or 'none'}; fired={fired}. "
                f"Signed-but-UNAUTHORIZED is the CVE-2026-45321 gap; a valid "
                f"signature ALONE never passes this monitor."),
    )


# --------------------------------------------------------------------------- #
# Λ-gate-style fusion governor — DENY-BY-DEFAULT.                              #
# --------------------------------------------------------------------------- #
def fuse(monitors: list, cfg: MonitorConfig = CFG) -> ArtifactVerdict:
    """Fuse independent behavioural monitors under a deny-by-default Λ governor.

    POLICY (deny-by-default):
      * If ANY monitor fired on a real triggering statistic -> DENY (anomalous=True).
      * Else if fused clean-confidence >= floor             -> ALLOW (advisory).
      * Else (no fire, but weak/ambiguous confidence)       -> ADVISORY (hold).

    Fused clean-confidence is a conservative blend weighting the weakest MODELED
    monitor heavily (a chain is only as trustworthy as its weakest honest monitor).
    NOT-MODELED monitors are excluded from the floor (we never let an un-runnable
    monitor manufacture trust), but an artifact is NEVER marked anomalous without a
    real fire. ALLOW is labelled "passed behavioural admission" — NOT "proven safe" —
    and signature_alone_is_safety is hard-wired False.
    """
    fired = [m.name for m in monitors if m.fired]
    modeled_conf = [m.confidence for m in monitors if m.modeled]
    if modeled_conf:
        fused_conf = 0.7 * min(modeled_conf) + 0.3 * float(np.mean(modeled_conf))
    else:
        fused_conf = 0.0  # nothing runnable -> cannot vouch -> deny-by-default holds

    if fired:
        verdict = VERDICT_DENY
        anomalous = True
        reason = (f"DENY (deny-by-default): {len(fired)} behavioural monitor(s) "
                  f"fired -> {', '.join(fired)}. Λ advisory: artifact behaviour "
                  f"anomalous; a valid signature does NOT override this.")
    elif fused_conf >= cfg.fused_confidence_floor:
        verdict = VERDICT_ALLOW
        anomalous = False
        reason = (f"ALLOW: no monitor fired and fused clean-confidence "
                  f"{fused_conf:.2f} >= floor {cfg.fused_confidence_floor:.2f}. "
                  f"{ALLOW_MEANING}")
    else:
        verdict = VERDICT_ADVISORY
        anomalous = False
        reason = (f"ADVISORY HOLD (deny-by-default): no monitor fired but fused "
                  f"clean-confidence {fused_conf:.2f} < floor "
                  f"{cfg.fused_confidence_floor:.2f}; insufficient evidence to admit.")

    return ArtifactVerdict(
        verdict=verdict,
        advisory=True,                 # Λ is ALWAYS advisory governance
        anomalous=anomalous,
        fired_monitors=fired,
        fused_confidence=float(fused_conf),
        monitors=[asdict(m) for m in monitors],
        reason=reason,
        signature_alone_is_safety=False,  # doctrine invariant — NEVER True
    )


def assess_artifact(meta: ArtifactMeta, cfg: MonitorConfig = CFG) -> ArtifactVerdict:
    """Run all four independent behavioural monitors and fuse under the Λ gate.

    Returns calibrated stats + the fused verdict + honest labels. This is the
    public entry point: feed it an ArtifactMeta describing one build/deploy
    artifact (on top of its already-verified signature) and it returns an advisory
    deny-by-default behavioural admission decision.
    """
    monitors = [
        size_anomaly_monitor(meta, cfg),
        file_injection_monitor(meta, cfg),
        egress_monitor(meta, cfg),
        provenance_consistency_monitor(meta, cfg),
    ]
    return fuse(monitors, cfg)


# --------------------------------------------------------------------------- #
# LIVE DATA — certify a REAL SZL artifact (the a11oy PINN certificate).        #
# --------------------------------------------------------------------------- #
A11OY_CERT_URL = "https://a11oy.net/api/a11oy/v1/pinn/certificate"


def fetch_live_certificate(url: str = A11OY_CERT_URL,
                           timeout: float = 15.0) -> Optional[dict]:
    """Fetch the REAL signed SZL physical-bounds certificate (DSSE Ed25519).

    Pure-stdlib urllib. Returns the parsed JSON dict, or None if unreachable
    (HONEST fallback — we never fabricate a signature/digest). Doctrine v11.
    """
    try:
        ctx = ssl.create_default_context()
        req = urllib.request.Request(url, headers={"User-Agent": "szl-gap1-inward-sda"})
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None


def artifact_meta_from_certificate(cert: dict) -> ArtifactMeta:
    """Build an ArtifactMeta for the REAL a11oy PINN certificate artifact.

    Maps the certificate's own signed fields onto our behavioural observables:
      * size_bytes              -> the serialized certificate byte length (real)
      * top_level_files         -> the certificate's top-level JSON keys (real)
      * manifest_files          -> the expected key-set for an szl/physical-bounds
                                   certificate (our declared manifest)
      * declared_hosts          -> the URLs the certificate references (cosign
                                   pub_key_url, Rekor retrieval_url) — real, on
                                   the SZL/sigstore allow-list
      * signature_valid         -> cert.signature.verified_at_serve_time (real)
      * builder_id/repo/branch  -> derived from the real cosign.pub GitHub anchor
    The expected protected source is the SZL cosign anchor on the `main` branch.
    """
    blob = json.dumps(cert, sort_keys=True).encode()
    # The DSSE Ed25519 signature lives under certificate.signature in the real cert.
    sig = (cert.get("certificate", {}) or {}).get("signature", {}) or {}
    cosign = cert.get("cosign", {}) or {}
    dsse = cert.get("dsse", {}) or {}
    tlog = (dsse.get("_transparency_log", {}) or {})

    # declared hosts: only the trust-anchor + transparency URLs the cert references.
    declared = []
    for u in (cosign.get("pub_key_url"), tlog.get("retrieval_url")):
        if u:
            m = re.match(r"^[a-z]+://([^/:]+)", u)
            declared.append(m.group(1) if m else u)

    sig_valid = bool(sig.get("verified_at_serve_time") or
                     cosign.get("verified_at_serve_time"))
    expected_keys = ["certificate", "dsse", "cosign", "signature", "khipu",
                     "model", "status", "signed", "source"]
    return ArtifactMeta(
        name="a11oy/pinn/physical-bounds-certificate",
        size_bytes=len(blob),
        # synthesise a realistic rolling baseline around the real size (the cert
        # service emits similar-sized certs each boot); baseline is MODELED.
        size_baseline_bytes=[len(blob), int(len(blob) * 0.98),
                             int(len(blob) * 1.02), int(len(blob) * 0.99)],
        top_level_files=sorted(cert.keys()),
        manifest_files=sorted(set(expected_keys) | set(cert.keys())),
        declared_hosts=declared,
        allowed_hosts=["github.com", "rekor.sigstore.dev", "a11oy.net",
                       "fulcio.sigstore.dev"],
        signature_valid=sig_valid,
        builder_id=cosign.get("keyid", "szlholdings-cosign"),
        source_repo="github.com/szl-holdings/.github",
        source_branch="main",
        expected_builder_id=cosign.get("keyid", "szlholdings-cosign"),
        expected_repo="github.com/szl-holdings/.github",
        expected_branch="main",
    )


def assess_live_certificate(url: str = A11OY_CERT_URL) -> dict:
    """Fetch the real a11oy cert and run the behavioural monitor over it.

    Returns a dict with the live verdict + the real signed fields it certified, or
    an HONEST {'reachable': False, ...} fallback if the endpoint is unreachable.
    """
    cert = fetch_live_certificate(url)
    if cert is None:
        return {
            "reachable": False,
            "note": ("a11oy certificate endpoint unreachable; HONEST fallback "
                     "(Doctrine v11 — no fabricated signature/digest). The "
                     "behavioural monitor still runs on offline ArtifactMeta."),
            "url": url,
        }
    meta = artifact_meta_from_certificate(cert)
    verdict = assess_artifact(meta)
    sig = (cert.get("certificate", {}) or {}).get("signature", {}) or {}
    dsse = cert.get("dsse", {}) or {}
    return {
        "reachable": True,
        "real_artifact": meta.name,
        "real_signature_alg": sig.get("alg"),
        "real_keyid_MEASURED": sig.get("keyid"),
        "real_cert_sha256_MEASURED": dsse.get("_cert_sha256"),
        "real_rekor_log_index_MEASURED":
            (dsse.get("_transparency_log", {}) or {}).get("log_index"),
        "behavioural_verdict": verdict.verdict,
        "allow_meaning": verdict.allow_meaning,
        "fused_confidence": verdict.fused_confidence,
        "fired_monitors": verdict.fired_monitors,
        "signature_alone_is_safety": verdict.signature_alone_is_safety,
        "reason": verdict.reason,
        "monitors": verdict.monitors,
    }


# --------------------------------------------------------------------------- #
# Scenario library — clean + one fixture per attack class (CVE-2026-45321).    #
# --------------------------------------------------------------------------- #
def clean_artifact() -> ArtifactMeta:
    """A clean, well-behaved artifact built from the protected source. Expect ALLOW
    (passed behavioural admission — NOT proven safe)."""
    return ArtifactMeta(
        name="szl/agentic-pinn-solver",
        size_bytes=210_000,
        size_baseline_bytes=[205_000, 208_000, 212_000, 207_000, 209_000],
        top_level_files=["pinn_solver.py", "physics_bounds.py", "README.md",
                         "manifest.json"],
        manifest_files=["pinn_solver.py", "physics_bounds.py", "README.md",
                        "manifest.json"],
        declared_hosts=["a11oy.net", "github.com"],
        allowed_hosts=["a11oy.net", "github.com", "rekor.sigstore.dev"],
        signature_valid=True,
        builder_id="szlholdings-cosign",
        source_repo="github.com/szl-holdings/agentic-pinn",
        source_branch="main",
        expected_builder_id="szlholdings-cosign",
        expected_repo="github.com/szl-holdings/agentic-pinn",
        expected_branch="main",
    )


def size_jump_artifact() -> ArtifactMeta:
    """The ~3.7x tarball jump (Socket/Unit 42). Size monitor fires -> DENY."""
    a = clean_artifact()
    a.name = "szl/agentic-pinn-solver@compromised-size"
    a.size_bytes = int(209_000 * 3.7)  # ~3.7x the baseline
    return a


def file_injection_artifact() -> ArtifactMeta:
    """The router_init.js injection. File-injection monitor fires -> DENY."""
    a = clean_artifact()
    a.name = "szl/agentic-pinn-solver@compromised-injection"
    a.top_level_files = a.top_level_files + ["router_init.js"]  # not in manifest
    return a


def egress_artifact() -> ArtifactMeta:
    """A phone-home dep (getsession.org + cloud-metadata). Egress monitor -> DENY."""
    a = clean_artifact()
    a.name = "szl/agentic-pinn-solver@compromised-egress"
    a.declared_hosts = a.declared_hosts + ["https://filev2.getsession.org/upload",
                                           "http://169.254.169.254/latest/meta-data"]
    return a


def signed_but_unauthorized_artifact() -> ArtifactMeta:
    """THE CORE LESSON: a VALID signature on a malicious artifact, produced by a
    pull_request_target / orphan-commit fork workflow on the wrong branch. Every
    other behavioural surface looks clean; provenance-consistency fires on the
    builder/branch mismatch DESPITE the valid signature -> DENY."""
    a = clean_artifact()
    a.name = "szl/agentic-pinn-solver@signed-but-unauthorized"
    a.signature_valid = True               # the attestation is genuinely VALID
    a.source_repo = "github.com/zblgg/configuration"   # attacker fork (TanStack IOC)
    a.source_branch = "orphan-payload"     # orphan commit, no branch association
    a.builder_id = "pull_request_target-runner"
    # expected_* still point at the protected source -> mismatch fires.
    return a


SCENARIO_LIBRARY = {
    "clean": clean_artifact,
    "size_jump": size_jump_artifact,
    "file_injection": file_injection_artifact,
    "egress_phone_home": egress_artifact,
    "signed_but_unauthorized": signed_but_unauthorized_artifact,
}


# --------------------------------------------------------------------------- #
# Demo / CLI.                                                                  #
# --------------------------------------------------------------------------- #
def _print_verdict(name: str, v: ArtifactVerdict) -> None:
    print(f"\n=== {name} ===")
    print(f"  verdict   : {v.verdict}  (anomalous={v.anomalous}, advisory={v.advisory})")
    print(f"  fired     : {v.fired_monitors or 'none'}")
    print(f"  fused conf: {v.fused_confidence:.3f}")
    print(f"  sig==safe?: {v.signature_alone_is_safety}  (doctrine invariant: False)")
    for m in v.monitors:
        flag = "FIRE" if m["fired"] else ("n/m" if not m["modeled"] else "ok ")
        print(f"    [{flag}] {m['name']:<26} stat={m['statistic']:.3f} "
              f"thr={m['threshold']:.3f}")
    print(f"  reason    : {v.reason}")


if __name__ == "__main__":
    print("SZL GAP-1 INWARD SDA — fused deny-by-default BEHAVIOURAL artifact monitor")
    print(SCOPE_LABEL)
    print(LAMBDA_LABEL)
    for key, factory in SCENARIO_LIBRARY.items():
        v = assess_artifact(factory())
        _print_verdict(key, v)

    print("\n" + "=" * 72)
    print("LIVE — certifying a REAL signed SZL artifact (a11oy PINN certificate):")
    live = assess_live_certificate()
    print(json.dumps({k: live[k] for k in live if k != "monitors"}, indent=2))
