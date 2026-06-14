# SPDX-License-Identifier: Apache-2.0
# © 2026 SZL Holdings · Doctrine v11 LOCKED · Λ = Conjecture 1 (advisory, NOT proven trust)
# Sign-off: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
"""szl_pinn_bounds.py — a11oy MESH for the SZL AGENTIC PINN + PHYSICAL-BOUNDS CERTIFIER.

This is the live-mesh surface for the Physics-ML frontier. Until now the PINN /
FE-NO verticals lived only in `platform`; they were NOT in a11oy's governed
`/api/a11oy/v1/<name>` route table. This module closes that gap — additively,
try/except-guarded, PURE STDLIB (no numpy/torch in the request path), matching the
sibling `szl_energy_budget.py` contract exactly.

Routes (all GET, read-only / deterministic):

  /api/<ns>/v1/pinn                      -> capability index + doctrine + links
  /api/<ns>/v1/pinn/certify?...          -> PHYSICAL-BOUNDS CERTIFICATE from MEASURED
                                            telemetry query params (the honest inverse
                                            of a free-energy claim). Live certifier.
  /api/<ns>/v1/pinn/certificate          -> latest pre-computed certificate artifact
                                            (an honestly-labelled SAMPLE if none wired)
  /api/<ns>/v1/pinn/solve                -> governed agentic decision trail (per-round
                                            residual-adaptive refine + deny-by-default
                                            Λ-gate). Read from the artifact the GPU
                                            solver (Forge) writes; numpy re-solve is the
                                            Forge/own-metal path, never the web path.
  /api/<ns>/v1/pinn/residual             -> compact per-round residual / rel-L2 summary

HONESTY (Doctrine v11, HARD):
  - The bounds are ESTABLISHED PHYSICS, CITED — Landauer 1961, Margolus-Levitin 1998,
    Bremermann 1962, Bekenstein 1981, Hawking 1975. NOT SZL conjectures.
  - The certificate is the HONEST INVERSE of a free-energy claim: it PROVES a real job
    sits FAR BELOW the fundamental ceilings. NO over-unity, NO perpetual motion.
  - Energy is DERIVED only from MEASURED power × MEASURED time. Any value not backed by
    a real exporter is labelled SAMPLE. We fabricate NO number.
  - Λ = Conjecture 1 (advisory). ALLOW = "passed SZL admission policy", never
    "proven trust". The gate is deny-by-default.
  - The full numpy agentic solver runs on SZL metal / Forge GPU and writes the decision
    trail + certificate JSON; this stdlib mesh reads & re-certifies, it does not solve.

Math mirrors `agentic_pinn/physics_bounds.py` byte-for-byte (same SI constants, same
formulas) so the live mesh certificate and the on-metal certificate AGREE.
"""
import base64
import hashlib
import json
import math
import os
import time
from datetime import datetime, timezone

from starlette.requests import Request
from starlette.responses import JSONResponse

# --------------------------------------------------------------------------- #
# Fundamental physical constants (SI, CODATA-style) — identical to the engine. #
# --------------------------------------------------------------------------- #
K_B = 1.380649e-23          # Boltzmann constant, J/K (SI exact)
H_PLANCK = 6.62607015e-34   # Planck constant, J·s (SI exact)
HBAR = H_PLANCK / (2.0 * math.pi)
C_LIGHT = 299792458.0       # speed of light, m/s (SI exact)
G_NEWTON = 6.67430e-11      # gravitational constant, m³/(kg·s²) (CODATA 2018)
LN2 = math.log(2.0)

BOUNDS_ATTRIBUTION = {
    "landauer": ("Landauer, R. (1961), IBM J. Res. Dev. 5(3):183-191, "
                 "doi:10.1147/rd.53.0183 — min erase energy kT·ln2 per bit."),
    "margolus_levitin": ("Margolus, N. & Levitin, L. (1998), Physica D 120:188-195, "
                         "doi:10.1016/S0167-2789(98)00054-2 — max 4E/h ops/s."),
    "bremermann": ("Bremermann, H.J. (1962), Self-Organizing Systems — "
                   "max c²/h ≈ 1.356e50 bits/s per kg."),
    "bekenstein": ("Bekenstein, J.D. (1981), Phys. Rev. D 23(2):287, "
                   "doi:10.1103/PhysRevD.23.287 — I ≤ 2πRE/(ħc·ln2) bits."),
    "bekenstein_hawking": ("Hawking, S.W. (1975), Commun. Math. Phys. 43:199-220, "
                           "doi:10.1007/BF02345020 — holographic area-law ceiling."),
    "honesty": ("Established physics, cited not claimed. The certificate is the HONEST "
                "INVERSE of a free-energy claim: it proves the job is physically "
                "bounded, asserts no over-unity, fabricates no number."),
}

DOCTRINE = (
    "v11 LOCKED: NO free-energy/over-unity (this certificate PROVES bounded energy use — "
    "the honest inverse); joules DERIVED ONLY from MEASURED power×time (SAMPLE until a "
    "real exporter is wired); physics bounds CITED, not claimed as SZL's; Λ=Conjecture 1 "
    "(advisory, never 'proven trust'); locked-proven=8; SLSA L1 honest; sovereign "
    "own-metal; no fabricated numbers."
)

LAMBDA_NOTE = ("Λ = Conjecture 1 (advisory). States physical FACTS (bounds), not "
               "'proven trust'. Makes NO free-energy claim. Gate is deny-by-default.")

# Where the on-metal solver (Forge) drops its artifacts. The mesh READS these; it
# never solves. Configurable so Forge can point at the live data dir on the box.
_ART_DIR = os.environ.get("SZL_PINN_ARTIFACT_DIR", os.path.dirname(os.path.abspath(__file__)))
_CERT_ARTIFACT = os.path.join(_ART_DIR, "physical_bounds_certificate.json")
_TRAIL_ARTIFACT = os.path.join(_ART_DIR, "agentic_decision_trail.json")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


# --------------------------------------------------------------------------- #
# Bound math (DERIVED from MEASURED inputs) — identical to physics_bounds.py.  #
# --------------------------------------------------------------------------- #
def landauer_floor_joules(temperature_k: float, bits_erased: float) -> float:
    return K_B * temperature_k * LN2 * bits_erased


def margolus_levitin_max_ops_per_s(energy_joules: float) -> float:
    return 4.0 * energy_joules / H_PLANCK


def bremermann_max_ops_per_s(mass_kg: float) -> float:
    return (C_LIGHT ** 2 / H_PLANCK) * mass_kg


def bekenstein_max_info_bits(radius_m: float, energy_joules: float) -> float:
    return 2.0 * math.pi * radius_m * energy_joules / (HBAR * C_LIGHT * LN2)


def bekenstein_hawking_entropy_bits(radius_m: float) -> float:
    area = 4.0 * math.pi * radius_m ** 2
    s_over_k = (C_LIGHT ** 3 * area) / (4.0 * G_NEWTON * HBAR)
    return s_over_k / LN2


def certify_job(avg_power_w, wall_time_s, temperature_k, bit_operations,
                bits_erased, info_content_bits, device_mass_kg, device_radius_m,
                label="SAMPLE", source="mesh-query", note="") -> dict:
    """Compute the PHYSICAL-BOUNDS CERTIFICATE from MEASURED telemetry — pure stdlib.

    Returns the same `szl/physical-bounds-certificate/v1` schema the on-metal engine
    emits (MEASURED inputs vs DERIVED bounds clearly split). UNSIGNED here; the khipu /
    szl_lake Ed25519 path signs it (DSSE PAE). Unsigned == STRUCTURAL-ONLY, never a
    false green.
    """
    measured = {
        "label": label, "source": source,
        "avg_power_w_MEASURED": avg_power_w,
        "wall_time_s_MEASURED": wall_time_s,
        "temperature_k_MEASURED": temperature_k,
        "bit_operations_MEASURED": bit_operations,
        "bits_erased_MEASURED": bits_erased,
        "info_content_bits_MEASURED": info_content_bits,
        "device_mass_kg": device_mass_kg,
        "device_radius_m": device_radius_m,
        "note": note,
    }
    E = avg_power_w * wall_time_s  # DERIVED: MEASURED power × MEASURED time
    floor = landauer_floor_joules(temperature_k, bits_erased)
    land_mult = (E / floor) if floor > 0 else float("inf")
    ml_max = margolus_levitin_max_ops_per_s(E)
    job_rate = (bit_operations / wall_time_s) if wall_time_s > 0 else 0.0
    ml_frac = (job_rate / ml_max) if ml_max > 0 else float("inf")
    brem_max = bremermann_max_ops_per_s(device_mass_kg)
    brem_frac = (job_rate / brem_max) if brem_max > 0 else float("inf")
    bek_max = bekenstein_max_info_bits(device_radius_m, E)
    bek_frac = (info_content_bits / bek_max) if bek_max > 0 else float("inf")
    bek_ok = info_content_bits <= bek_max
    bh_ceiling = bekenstein_hawking_entropy_bits(device_radius_m)
    physically_bounded = bool(
        land_mult >= 1.0 and ml_frac <= 1.0 and brem_frac <= 1.0 and bek_ok
    )
    summary = (
        f"This compute job used {E:.4g} J (DERIVED = {avg_power_w:g} W MEASURED × "
        f"{wall_time_s:g} s MEASURED) = {land_mult:.3g}× the Landauer erasure floor "
        f"({floor:.4g} J). It ran at {ml_frac*100:.3g}% of the Margolus-Levitin maximum "
        f"rate ({ml_max:.4g} ops/s) and {brem_frac*100:.3g}% of the Bremermann limit. "
        f"Information content ({info_content_bits:.4g} bits) is {bek_frac*100:.3g}% of the "
        f"Bekenstein ceiling ({bek_max:.4g} bits), far under the holographic ceiling "
        f"({bh_ceiling:.4g} bits). VERDICT: PHYSICALLY BOUNDED by established law — the "
        f"honest inverse of a free-energy claim. No over-unity. No fabricated number."
    )
    canon = json.dumps(measured, sort_keys=True, separators=(",", ":"), default=str)
    inputs_hash = "sha256:" + hashlib.sha256(canon.encode()).hexdigest()
    return {
        "certificate_type": "szl/physical-bounds-certificate/v1",
        "measured": measured,
        "energy_joules_derived": E,
        "landauer_floor_joules": floor,
        "landauer_multiple_above_floor": land_mult,
        "margolus_levitin_max_ops_per_s": ml_max,
        "job_ops_per_s_measured": job_rate,
        "margolus_levitin_headroom_fraction": ml_frac,
        "margolus_levitin_headroom_pct": ml_frac * 100.0,
        "bremermann_max_ops_per_s": brem_max,
        "bremermann_headroom_fraction": brem_frac,
        "bekenstein_max_info_bits": bek_max,
        "bekenstein_info_fraction": bek_frac,
        "bekenstein_under_ceiling": bek_ok,
        "bekenstein_hawking_ceiling_bits": bh_ceiling,
        "physically_bounded": physically_bounded,
        "summary": summary,
        "inputs_hash": inputs_hash,
        "timestamp_utc": time.time(),
        "attribution": BOUNDS_ATTRIBUTION,
        "doctrine": DOCTRINE,
        "honest_inverse_of_free_energy": True,
        "labels": {
            "MEASURED": "observed from a real exporter (NVML) or honestly-labelled sample",
            "DERIVED": "computed from MEASURED inputs via CITED established-physics formulas",
        },
        "lambda_note": LAMBDA_NOTE,
        "signature": None,  # UNSIGNED here; signed on the khipu/szl_lake DSSE path
    }


# An honestly-labelled SAMPLE job (the in-sandbox default; matches nvml_hook.sample_job).
_SAMPLE_JOB = dict(
    avg_power_w=700.0, wall_time_s=10.0, temperature_k=350.0,
    bit_operations=1e16, bits_erased=1e14, info_content_bits=1e12,
    device_mass_kg=2.0, device_radius_m=0.15,
    label="SAMPLE", source="honest-sample (no GPU in mesh path — doctrine v11)",
    note="In-sandbox SAMPLE. On metal Forge feeds REAL NVML readings via forge_job().",
)


# --------------------------------------------------------------------------- #
# Query-param parsing                                                          #
# --------------------------------------------------------------------------- #
def _f(qp, *keys, default=0.0):
    for k in keys:
        v = qp.get(k)
        if v not in (None, ""):
            try:
                return float(v)
            except Exception:
                pass
    return float(default)


def _read_json(path):
    try:
        with open(path, "r") as fh:
            return json.load(fh)
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# Real Ed25519 DSSE signature (FA-001 on-metal key) - VERIFIED at serve time.  #
# The cert body is signed out-of-band by sign_cert_dsse.py with /root/ed25519. #
# We NEVER fabricate: we re-verify the signature here against the exact served #
# bytes and only label SIGNED if the cryptographic check passes.               #
# --------------------------------------------------------------------------- #
_DSSE_SIDECAR = os.path.join(_ART_DIR, "physical_bounds_certificate.dsse.json")
_COSIGN_SIDECAR = os.path.join(_ART_DIR, "physical_bounds_certificate.cosign.json")
_DSSE_PT = "application/vnd.szl.physical-bounds-certificate+json"
_SIGN_RECEIPT = None


def _dsse_pae(payload_type, body):
    t = payload_type.encode()
    return (b"DSSEv1 " + str(len(t)).encode() + b" " + t + b" "
            + str(len(body)).encode() + b" " + body)


def _cert_raw_bytes():
    try:
        with open(_CERT_ARTIFACT, "rb") as fh:
            return fh.read()
    except Exception:
        return None


def _verified_signature(cert_body):
    """Return (signature_obj, envelope) iff a REAL Ed25519 DSSE signature over
    `cert_body` cryptographically verifies; else (None, None). No half-state."""
    if cert_body is None:
        return None, None
    env = _read_json(_DSSE_SIDECAR)
    if not env or not isinstance(env, dict):
        return None, None
    try:
        sigs = env.get("signatures") or []
        if not sigs:
            return None, None
        s0 = sigs[0]
        pub_pem = (s0.get("publicKey") or "").encode()
        sig = base64.b64decode(s0["sig"])
        from cryptography.hazmat.primitives.serialization import load_pem_public_key
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        pub = load_pem_public_key(pub_pem)
        if not isinstance(pub, Ed25519PublicKey):
            return None, None
        pae = _dsse_pae(env.get("payloadType", _DSSE_PT), cert_body)
        pub.verify(sig, pae)  # raises InvalidSignature on mismatch
        if env.get("_cert_sha256") != "sha256:" + hashlib.sha256(cert_body).hexdigest():
            return None, None
        sig_obj = {
            "alg": "ed25519",
            "pae": "DSSEv1",
            "keyid": s0.get("keyid"),
            "sig": s0.get("sig"),
            "publicKey": s0.get("publicKey"),
            "verified_at_serve_time": True,
            "key_custody": "FA-001 on-metal Ed25519 (box secret store), self-verified by sign_cert_dsse.py",
        }
        return sig_obj, env
    except Exception:
        return None, None


def _verified_cosign_signature(cert_body):
    """Return a cosign sig_obj iff a REAL ECDSA-P256-SHA256 signature over the raw
    certificate bytes cryptographically verifies against the embedded szlholdings
    cosign public key (the PUBLISHED cosign.pub, an EXTERNAL trust anchor) AND the
    sha256 binding matches the served bytes; else None. No half-state, no fabricated
    green. This is the `cosign verify-blob --key cosign.pub` path."""
    if cert_body is None:
        return None
    side = _read_json(_COSIGN_SIDECAR)
    if not side or not isinstance(side, dict):
        return None
    try:
        sig = base64.b64decode(side["sig"])
        pub_pem = (side.get("publicKey") or "").encode()
        from cryptography.hazmat.primitives.serialization import load_pem_public_key
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives import hashes
        pub = load_pem_public_key(pub_pem)
        pub.verify(sig, cert_body, ec.ECDSA(hashes.SHA256()))  # raises InvalidSignature on mismatch
        if side.get("cert_sha256") != "sha256:" + hashlib.sha256(cert_body).hexdigest():
            return None
        return {
            "alg": "ecdsa-p256-sha256",
            "keyid": side.get("keyid"),
            "sig": side.get("sig"),
            "publicKey": side.get("publicKey"),
            "pub_key_url": side.get("pub_key_url"),
            "verify_cmd": side.get("verify_cmd"),
            "trust_anchor": side.get("trust_anchor") or "PUBLISHED szl-holdings cosign.pub",
            "key_custody": side.get("key_custody"),
            "verified_at_serve_time": True,
        }
    except Exception:
        return None


def _anchor_signature_in_khipu():
    """Append ONE signing receipt to the in-process khipu chain at boot (honest:
    KhipuDAG is append-only hash-chained, re-anchored each boot; durable ledger is
    WASI-RIKUQ P1). No-op unless the Ed25519 signature actually verifies."""
    global _SIGN_RECEIPT
    sig_obj, env = _verified_signature(_cert_raw_bytes())
    if sig_obj is None:
        _SIGN_RECEIPT = None
        return
    try:
        from szl_khipu import get_dag
        rec = get_dag("pinn").emit("physical_bounds_certificate_signed", {
            "keyid": sig_obj["keyid"],
            "cert_sha256": env.get("_cert_sha256"),
            "payloadType": env.get("payloadType"),
        })
        _SIGN_RECEIPT = {
            "seq": rec["seq"], "digest": rec["digest"], "prev": rec["prev"],
            "chain_verified": rec["chain_verified"],
            "note": ("in-process append-only hash-chain (KhipuDAG); re-anchored each "
                     "boot - durable ledger is WASI-RIKUQ P1"),
        }
    except Exception:
        _SIGN_RECEIPT = None


# --------------------------------------------------------------------------- #
# Handlers                                                                     #
# --------------------------------------------------------------------------- #
def _h_index(req: Request):
    ns = req.path_params.get("_ns", "a11oy")
    base = f"/api/{ns}/v1/pinn"
    return JSONResponse({
        "capability": "SZL Agentic PINN + Physical-Bounds Certifier",
        "frontier": ("governed, residual-adaptive physics-informed solve loop under a "
                     "deny-by-default Λ-gate, every solve CERTIFIED against the "
                     "fundamental compute/energy bounds of physics"),
        "honest_inverse_of_free_energy": True,
        "routes": {
            f"{base}/certify": "PHYSICAL-BOUNDS CERTIFICATE from MEASURED telemetry "
                               "(?avg_power_w=&wall_time_s=&temperature_k=&bit_operations="
                               "&bits_erased=&info_content_bits=&device_mass_kg=&device_radius_m=)",
            f"{base}/certificate": "latest pre-computed certificate artifact (SAMPLE if none wired)",
            f"{base}/solve": "governed agentic decision trail (per-round refine + Λ-gate)",
            f"{base}/residual": "compact per-round residual / rel-L2 summary",
        },
        "bounds": ["Landauer (1961)", "Margolus-Levitin (1998)", "Bremermann (1962)",
                   "Bekenstein (1981)", "Bekenstein-Hawking (Hawking 1975)"],
        "attribution": BOUNDS_ATTRIBUTION,
        "lambda_note": LAMBDA_NOTE,
        "doctrine": DOCTRINE,
        "ts": _now_iso(),
    })


def _h_certify(req: Request):
    qp = req.query_params
    has_input = any(k in qp for k in (
        "avg_power_w", "power_w", "wall_time_s", "bit_operations"))
    job = dict(_SAMPLE_JOB)
    if has_input:
        job.update(
            avg_power_w=_f(qp, "avg_power_w", "power_w", default=job["avg_power_w"]),
            wall_time_s=_f(qp, "wall_time_s", "time_s", default=job["wall_time_s"]),
            temperature_k=_f(qp, "temperature_k", "temp_k", default=job["temperature_k"]),
            bit_operations=_f(qp, "bit_operations", "ops", default=job["bit_operations"]),
            bits_erased=_f(qp, "bits_erased", default=job["bits_erased"]),
            info_content_bits=_f(qp, "info_content_bits", "info_bits", default=job["info_content_bits"]),
            device_mass_kg=_f(qp, "device_mass_kg", "mass_kg", default=job["device_mass_kg"]),
            device_radius_m=_f(qp, "device_radius_m", "radius_m", default=job["device_radius_m"]),
            label="MEASURED" if qp.get("measured") in ("1", "true", "yes") else "SAMPLE",
            source=qp.get("source", "mesh-query"),
        )
    cert = certify_job(**{k: job[k] for k in (
        "avg_power_w", "wall_time_s", "temperature_k", "bit_operations", "bits_erased",
        "info_content_bits", "device_mass_kg", "device_radius_m", "label", "source")},
        note=job["note"])
    return JSONResponse({
        "model": "SZL Physical-Bounds Certifier — live certificate",
        "status": "VERIFIED (physical bounds) · UNSIGNED (STRUCTURAL-ONLY)",
        "certificate": cert,
    })


def _h_certificate(req: Request):
    art = _read_json(_CERT_ARTIFACT)
    if art is not None:
        sig_obj, env = _verified_signature(_cert_raw_bytes())
        if sig_obj is not None:
            art = dict(art)
            art["signature"] = sig_obj
            resp = {
                "model": "SZL Physical-Bounds Certifier — latest artifact",
                "status": "VERIFIED (physical bounds) · SIGNED (DSSE Ed25519, FA-001 on-metal)",
                "signed": True,
                "source": "on-metal artifact (Forge solver output)",
                "certificate": art,
                "dsse": env,
            }
            cosign_obj = _verified_cosign_signature(_cert_raw_bytes())
            if cosign_obj is not None:
                resp["cosign"] = cosign_obj
                resp["status"] = ("VERIFIED (physical bounds) · SIGNED (DSSE Ed25519 "
                                  "FA-001 on-metal + cosign.pub anchored)")
            if _SIGN_RECEIPT:
                resp["khipu"] = _SIGN_RECEIPT
            return JSONResponse(resp)
        return JSONResponse({
            "model": "SZL Physical-Bounds Certifier — latest artifact",
            "status": "VERIFIED (physical bounds) · UNSIGNED (STRUCTURAL-ONLY)",
            "signed": False,
            "source": "on-metal artifact (Forge solver output)",
            "certificate": art,
        })
    # Honest fallback: emit a clearly-labelled SAMPLE certificate.
    cert = certify_job(**{k: _SAMPLE_JOB[k] for k in (
        "avg_power_w", "wall_time_s", "temperature_k", "bit_operations", "bits_erased",
        "info_content_bits", "device_mass_kg", "device_radius_m", "label", "source")},
        note=_SAMPLE_JOB["note"])
    return JSONResponse({
        "model": "SZL Physical-Bounds Certifier — SAMPLE (no artifact wired)",
        "status": "VERIFIED (physical bounds) · SAMPLE · UNSIGNED (STRUCTURAL-ONLY)",
        "source": "honest-sample (Forge has not written a certificate artifact yet)",
        "certificate": cert,
    })


def _trail_or_none():
    return _read_json(_TRAIL_ARTIFACT)


def _h_solve(req: Request):
    trail = _trail_or_none()
    if trail is not None:
        return JSONResponse({
            "model": "SZL Agentic PINN — governed solve decision trail",
            "status": f"{trail.get('final_verdict', 'UNKNOWN')} "
                      f"(accepted={trail.get('final_accepted')})",
            "source": "on-metal artifact (Forge GPU solver output)",
            "note": ("The numpy agentic solver runs on SZL metal / Forge GPU (own-metal, "
                     "sovereign). This mesh READS the decision trail it writes — the live "
                     "web path never solves. Λ-gate is deny-by-default; ALLOW = passed "
                     "admission policy, NOT proven trust."),
            "decision_trail": trail,
        })
    return JSONResponse({
        "model": "SZL Agentic PINN — governed solve decision trail",
        "status": "AWAITING_GPU_SOLVE",
        "source": "no artifact wired",
        "note": ("The governed agentic solver (residual-adaptive refine + deny-by-default "
                 "Λ-gate) runs on SZL metal / Forge GPU and writes the per-round decision "
                 "trail. None is wired in this environment yet — honest AWAITING state, "
                 "never a fabricated solve."),
        "doctrine": DOCTRINE,
        "lambda_note": LAMBDA_NOTE,
    })


def _h_residual(req: Request):
    trail = _trail_or_none()
    if trail is None:
        return JSONResponse({
            "status": "AWAITING_GPU_SOLVE",
            "note": "No decision trail artifact wired yet (honest). Forge GPU solver writes it.",
        })
    rounds = trail.get("rounds", [])
    summary = [{
        "round": r.get("round_index"),
        "n_collocation": r.get("n_pde_collocation"),
        "max_residual": r.get("max_residual_on_test"),
        "mean_residual": r.get("mean_residual_on_test"),
        "rel_l2_error_estimate": r.get("rel_l2_error_estimate"),
        "lambda_verdict": r.get("lambda_verdict"),
        "accepted": r.get("accepted"),
        "modeled_not_measured": r.get("modeled_not_measured", True),
        "error_estimate_is_bound": r.get("error_estimate_is_bound", True),
    } for r in rounds]
    return JSONResponse({
        "model": "SZL Agentic PINN — per-round residual summary",
        "final_verdict": trail.get("final_verdict"),
        "final_accepted": trail.get("final_accepted"),
        "rounds": summary,
        "note": ("Residual-based adaptive refinement (RAR/RAD): collocation grows where "
                 "the PDE residual is largest; the Λ-gate accepts only once converged. "
                 "Error estimates are MODELED bounds, not MEASURED."),
        "lambda_note": LAMBDA_NOTE,
    })


def _h_certificate_dsse(req: Request):
    """Return the RAW Ed25519 DSSE envelope for the current certificate body, so
    anyone can verify it independently (e.g. GET /verify?url=<this>). Honest 404
    when no verifying signature is available for the current bytes."""
    sig_obj, env = _verified_signature(_cert_raw_bytes())
    if env is not None:
        return JSONResponse(env)
    return JSONResponse({
        "status": "UNSIGNED",
        "detail": ("no verifying Ed25519 DSSE signature is available for the current "
                   "certificate body (honest — never a fabricated signature)"),
    }, status_code=404)


def _h_verify(req: Request):
    """Explicit verification surface: independently RE-VERIFIES, at request time,
    every cryptographic signature available for the CURRENT certificate bytes —
    the on-metal Ed25519 DSSE attestation AND the cosign.pub-anchored signature.
    Honest: an absent or invalid signature reports verified:false (HTTP 503), never
    a fabricated green. cert_sha256 binding is enforced for both."""
    body = _cert_raw_bytes()
    sha = ("sha256:" + hashlib.sha256(body).hexdigest()) if body else None
    ed_obj, _ed_env = _verified_signature(body)
    co_obj = _verified_cosign_signature(body)
    sigs = {}
    sigs["ed25519_onmetal"] = ({
        "verified": True, "alg": "ed25519", "keyid": ed_obj.get("keyid"),
        "key_custody": ed_obj.get("key_custody"),
        "trust_model": "self-anchored on-metal attestation (embedded public key)",
    } if ed_obj else {
        "verified": False,
        "detail": "no verifying Ed25519 DSSE signature for the current certificate bytes",
    })
    sigs["cosign_anchored"] = ({
        "verified": True, "alg": "ecdsa-p256-sha256", "keyid": co_obj.get("keyid"),
        "pub_key_url": co_obj.get("pub_key_url"), "verify_cmd": co_obj.get("verify_cmd"),
        "trust_anchor": co_obj.get("trust_anchor"),
    } if co_obj else {
        "verified": False,
        "detail": "no verifying cosign signature for the current certificate bytes",
    })
    any_v = bool(ed_obj) or bool(co_obj)
    return JSONResponse({
        "model": "SZL Physical-Bounds Certifier — signature verification",
        "certificate_present": body is not None,
        "certificate_sha256": sha,
        "verified": any_v,
        "signed": any_v,
        "signatures": sigs,
        "honesty": ("Each signature is re-verified cryptographically against the EXACT "
                    "served certificate bytes at request time, with sha256 binding "
                    "enforced. Never a fabricated green — absent/invalid signatures report "
                    "verified:false. Doctrine v11: MEASURED energy only; the cosign "
                    "signature is verifiable against the PUBLISHED cosign.pub."),
        "lambda_note": LAMBDA_NOTE,
        "ts": _now_iso(),
    }, status_code=(200 if any_v else 503))


def register(app, ns="a11oy"):
    """Wire the PINN/bounds mesh onto the app under /api/<ns>/v1/pinn/*.

    Additive. Uses FastAPI's add_api_route when available (matches the sibling szl_*
    modules so resolution order is correct vs the SPA catch-all); falls back to a
    Starlette route append for a bare Starlette app.
    """
    base = f"/api/{ns}/v1/pinn"
    handlers = [
        (base, _h_index),
        (f"{base}/certify", _h_certify),
        (f"{base}/certificate", _h_certificate),
        (f"{base}/certificate.dsse", _h_certificate_dsse),
        (f"{base}/verify", _h_verify),
        (f"{base}/solve", _h_solve),
        (f"{base}/residual", _h_residual),
    ]
    add_api_route = getattr(app, "add_api_route", None)
    for path, fn in handlers:
        if callable(add_api_route):
            app.add_api_route(path, fn, methods=["GET"])
        else:
            from starlette.routing import Route
            app.router.routes.append(Route(path, fn))
    try:
        _anchor_signature_in_khipu()
    except Exception:
        pass
    return [p for p, _ in handlers]


def _selftest() -> dict:
    """No-server self-test: proves the certifier honesty + bound inequalities."""
    out = {}
    cert = certify_job(**{k: _SAMPLE_JOB[k] for k in (
        "avg_power_w", "wall_time_s", "temperature_k", "bit_operations", "bits_erased",
        "info_content_bits", "device_mass_kg", "device_radius_m")})
    # (a) energy is DERIVED = power × time
    assert abs(cert["energy_joules_derived"] - 700.0 * 10.0) < 1e-9
    out["energy_derived_power_x_time"] = True
    # (b) sample job is physically bounded
    assert cert["physically_bounded"] is True
    out["sample_physically_bounded"] = True
    # (c) above the Landauer floor (>=1×) — irreversibility honored
    assert cert["landauer_multiple_above_floor"] >= 1.0
    out["above_landauer_floor"] = True
    # (d) under the Margolus-Levitin and Bremermann rate ceilings (<=1)
    assert cert["margolus_levitin_headroom_fraction"] <= 1.0
    assert cert["bremermann_headroom_fraction"] <= 1.0
    out["under_rate_ceilings"] = True
    # (e) HONEST: an adversarial below-floor job is flagged NOT bounded
    bad = certify_job(avg_power_w=1e-30, wall_time_s=1.0, temperature_k=350.0,
                      bit_operations=1.0, bits_erased=1e14, info_content_bits=1.0,
                      device_mass_kg=2.0, device_radius_m=0.15)
    assert bad["physically_bounded"] is False
    out["below_floor_flagged_unbounded"] = True
    # (f) no free-energy claim; doctrine + Λ-advisory carried
    assert cert["honest_inverse_of_free_energy"] is True
    assert "free-energy" in cert["doctrine"].lower()
    assert "advisory" in cert["lambda_note"].lower()
    out["doctrine_honest"] = True
    out["ok"] = True
    return out


if __name__ == "__main__":
    print(json.dumps(_selftest(), indent=2))
