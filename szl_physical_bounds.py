"""
szl_physical_bounds.py — single source of truth for the founder-captured
physical-bounds energy certificate (physical_bounds_certificate.json).

This module ONLY reads the certificate that already ships at the repo root /
image workdir. It NEVER hardcodes the numbers and NEVER fabricates a joule: if
the file is missing or unparseable at runtime the loaders return None and the
caller must serve an honest UNAVAILABLE.

DOCTRINE (non-negotiable):
  - The certificate is a FOUNDER-CAPTURED, POINT-IN-TIME reading (2026-06-14 on
    the sovereign GPU "betterwithage" / RTX 5050 Laptop over Tailscale). It is
    NOT a per-request live measurement. Every label this module emits says so
    explicitly, so no reader can mistake it for "this request measured joules".
  - measured.* fields are MEASURED (real nvidia-smi power.draw samples).
    energy_joules_derived is DERIVED (MEASURED power x MEASURED time).
    bit_operations / bits_erased / info_content are MODELED — those labels are
    preserved verbatim from the certificate, never upgraded.
  - Λ = Conjecture 1 (advisory). No free-energy / over-unity claim.
"""
import json
import os

# The honest freshness/provenance label. This is the ONE place the "not per-request
# live" caveat is spelled out, so both the endpoint and the govern receipt agree.
CAPTURED_DATE = "2026-06-14"
REFERENCE_LABEL = "MEASURED (founder-captured reference, %s; not per-request live)" % CAPTURED_DATE
ENDPOINT_PATH = "/api/a11oy/v1/energy/physical-bounds"


def _candidate_paths():
    """Ordered candidate locations for the shipped certificate. The flat repo /
    image workdir keeps it next to this module (/app/physical_bounds_certificate.json)."""
    here = os.path.dirname(os.path.abspath(__file__))
    seen = []
    for p in (
        os.environ.get("SZL_PHYSICAL_BOUNDS_CERT"),
        os.path.join(here, "physical_bounds_certificate.json"),
        os.path.join(os.getcwd(), "physical_bounds_certificate.json"),
        "/app/physical_bounds_certificate.json",
    ):
        if p and p not in seen:
            seen.append(p)
    return seen


def cert_path():
    """Return the first existing certificate path, or None if none is present."""
    for p in _candidate_paths():
        if os.path.isfile(p):
            return p
    return None


def load_certificate():
    """Read + parse the shipped certificate. Returns (cert_dict, path) on success,
    or (None, reason_str) if the file is missing or unparseable. NEVER fabricates."""
    path = cert_path()
    if path is None:
        return None, "physical_bounds_certificate.json not present at runtime"
    try:
        with open(path, "r", encoding="utf-8") as fh:
            cert = json.load(fh)
    except Exception as exc:  # unparseable / unreadable — honest, no fabrication
        return None, "physical_bounds_certificate.json unreadable: %s" % (type(exc).__name__,)
    if not isinstance(cert, dict):
        return None, "physical_bounds_certificate.json is not a JSON object"
    return cert, path


def physical_bounds_payload():
    """Normalized read-model for GET /api/a11oy/v1/energy/physical-bounds.

    Returns a dict with the top-level fields tests + clients assert on
    (label, energy_joules, avg_power_w, wall_time_s, landauer_multiple, source,
    captured, provenance) PLUS the full raw `certificate` (single source of
    truth). Returns None if the certificate cannot be read (caller serves 503).
    Numbers are READ FROM THE FILE — never hardcoded here."""
    cert, path_or_reason = load_certificate()
    if cert is None:
        return None
    measured = cert.get("measured", {}) or {}
    return {
        # Top-level MEASURED label comes straight from the certificate.
        "label": measured.get("label"),
        # DERIVED energy = MEASURED power x MEASURED time, read from the file.
        "energy_joules": cert.get("energy_joules_derived"),
        "avg_power_w": measured.get("avg_power_w_MEASURED"),
        "wall_time_s": measured.get("wall_time_s_MEASURED"),
        "temperature_k": measured.get("temperature_k_MEASURED"),
        "landauer_multiple": cert.get("landauer_multiple_above_floor"),
        "landauer_floor_joules": cert.get("landauer_floor_joules"),
        "source": measured.get("source"),
        "captured": CAPTURED_DATE,
        "provenance": {
            "source": measured.get("source"),
            "captured": CAPTURED_DATE,
            "freshness": "founder-captured point-in-time reading; NOT a per-request live measurement",
        },
        "honesty": (
            "MEASURED energy is a founder-captured reference reading (2026-06-14), "
            "DERIVED as MEASURED avg power x MEASURED wall time. It is NOT the joules of "
            "the current request. bit_operations / bits_erased / info_content stay MODELED. "
            "No number is fabricated; served from the shipped certificate."
        ),
        # The full certificate is the single source of truth (physics bounds,
        # attribution, MODELED workload descriptors, doctrine note).
        "certificate": cert,
    }


def energy_reference_block():
    """The founder-captured MEASURED reference to attach to a govern/infer energy
    block. Distinct from any per-request live joules: the label says exactly what
    this is. Returns None if the certificate cannot be read (caller keeps the
    per-request UNAVAILABLE — never fabricates a MEASURED)."""
    cert, _path_or_reason = load_certificate()
    if cert is None:
        return None
    measured = cert.get("measured", {}) or {}
    return {
        "label": REFERENCE_LABEL,
        "energy_joules": cert.get("energy_joules_derived"),
        "avg_power_w": measured.get("avg_power_w_MEASURED"),
        "wall_time_s": measured.get("wall_time_s_MEASURED"),
        "temperature_k": measured.get("temperature_k_MEASURED"),
        "landauer_multiple": cert.get("landauer_multiple_above_floor"),
        "source": measured.get("source"),
        "captured": CAPTURED_DATE,
        "endpoint": ENDPOINT_PATH,
        "note": (
            "Founder-captured point-in-time reading (2026-06-14), NOT this request's "
            "live joules. bit_operations/bits_erased/info_content remain MODELED."
        ),
    }


if __name__ == "__main__":
    import sys
    payload = physical_bounds_payload()
    if payload is None:
        print(json.dumps({"label": "UNAVAILABLE",
                          "reason": load_certificate()[1]}, indent=2))
        sys.exit(0)
    print(json.dumps(payload, indent=2, default=str))
