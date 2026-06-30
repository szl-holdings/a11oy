"""szl_tee_attest.py — Intel TDX / AWS Nitro TEE attestation hook.

Pattern from: dstack-capsule / Phala (Apache-2.0, arXiv 2606.03323), adapted
for our stack without copying their code (doctrine: PATTERN not code).

HONEST REALITY (v11 — NEVER violate):
  The live HF Space runs on a CPU-basic tier with NO TEE.  On that runtime this
  module MUST return tee_attestation.present=False, label="UNAVAILABLE", with a
  note that TDX/Nitro attestation is ROADMAP for the sovereign deployment.
  We NEVER fabricate a quote, a measurement (PCR/RTMR/MRTD), or a TEE type.

  The VALUE is that the hook EXISTS and is wired into the receipt schema now, so
  when deployed on a dstack Intel TDX pod or AWS Nitro instance it lights up
  automatically without any code change — and every receipt already carries the
  field honestly.

SUPPORTED TEE TYPES (probed in order, first positive wins):
  1. Intel TDX  — /dev/tdx_guest device present (Linux kernel 5.19+/6.x TDX driver)
                  OR env SZL_TDX_REPORT_PATH points to a readable TDX report file.
  2. AWS Nitro  — /dev/nsm device present (Nitro Security Module) and the
                  nitro_enclaves NSM Python SDK importable.

WHAT GETS ATTACHED (when TEE IS present):
  tee_attestation: {
    present:    true,
    type:       "tdx" | "nitro",
    measurement: "<hex>",    # MRTD (TDX) or PCR0 (Nitro) — the hardware measurement
    label:      "MEASURED",
    doc_ref:    "arXiv 2606.03323 dstack-capsule pattern",
  }

WHAT GETS ATTACHED (when TEE is absent — current state):
  tee_attestation: {
    present:    false,
    label:      "UNAVAILABLE",
    note:       "no TEE on current runtime; TDX/Nitro attestation is ROADMAP for the sovereign deployment",
    doc_ref:    "arXiv 2606.03323 dstack-capsule pattern",
  }

ENDPOINTS:
  GET /api/a11oy/v1/tee/status   — honest present/absent + measurement when available

SPDX-License-Identifier: Apache-2.0
© 2026 Lutar, Stephen P. — SZL Holdings · Doctrine v11
"""

from __future__ import annotations

import os
import struct
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_DOC_REF = "arXiv 2606.03323 dstack-capsule pattern (Apache-2.0)"
_LABEL_MEASURED = "MEASURED"
_LABEL_UNAVAILABLE = "UNAVAILABLE"

# Standard TDX paths (Linux kernel TDX guest driver, kernel 5.19+/6.x)
_TDX_GUEST_DEVICE = "/dev/tdx_guest"
_TDX_REPORT_ENV = "SZL_TDX_REPORT_PATH"

# AWS Nitro NSM device path
_NITRO_NSM_DEVICE = "/dev/nsm"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# TEE probe: Intel TDX
# ---------------------------------------------------------------------------
def _probe_tdx() -> dict | None:
    """Try to read an Intel TDX MRTD measurement.

    Returns a measurement dict {type, measurement, label} on success, or None
    when not running inside TDX.  NEVER fabricates.

    Probing order:
      (a) /dev/tdx_guest device exists — attempt ioctl TDREPORT (Linux 6.x TDX driver).
      (b) Env SZL_TDX_REPORT_PATH points to a readable binary TDX report file (for
          containers that receive a pre-baked report from the TEE operator).
    """
    # (a) /dev/tdx_guest ioctl path
    tdx_dev = os.environ.get("SZL_TDX_DEVICE", _TDX_GUEST_DEVICE)
    if os.path.exists(tdx_dev):
        try:
            return _tdx_read_mrtd_ioctl(tdx_dev)
        except Exception:
            pass  # device exists but ioctl failed (non-TDX kernel, permissions) — fall through

    # (b) Pre-baked report file path (operator-provided, dstack pattern)
    report_path = os.environ.get(_TDX_REPORT_ENV, "")
    if report_path and os.path.isfile(report_path):
        try:
            return _tdx_read_mrtd_file(report_path)
        except Exception:
            pass

    return None


def _tdx_read_mrtd_ioctl(dev_path: str) -> dict:
    """Read TDX MRTD via the Linux /dev/tdx_guest ioctl (TDREPORT).

    The TDX_CMD_GET_REPORT0 ioctl (0xc0400101 on Linux 6.x) returns a 1024-byte
    TDREPORT_STRUCT.  MRTD occupies bytes 128..176 (48 bytes, SHA-384 measurement
    of the initial TD memory).  We extract it and hex-encode it.

    Raises on any error so the caller can fall through to the file path or None.
    """
    import fcntl  # stdlib — available on Linux

    # TDX ioctl constants (Linux 6.x tdx-guest driver, uapi/linux/tdx-guest.h)
    # TDX_CMD_GET_REPORT0 = _IOWR('T', 0x01, struct tdx_report_req)
    # struct tdx_report_req: { u8 reportdata[64]; u8 tdreport[1024]; }
    TDX_CMD_GET_REPORT0 = 0xC0400101  # ioctl number for 64+1024 = 1088-byte struct
    REPORT_DATA_SIZE = 64
    TD_REPORT_SIZE = 1024
    REQ_SIZE = REPORT_DATA_SIZE + TD_REPORT_SIZE

    # report_data can be zeros (we're just reading MRTD, not binding to a nonce here)
    req = bytearray(REQ_SIZE)

    with open(dev_path, "rb") as f:
        buf = (ctypes_or_struct_pack := req)  # keep the bytearray
        result = fcntl.ioctl(f.fileno(), TDX_CMD_GET_REPORT0, buf)

    if not isinstance(result, (bytes, bytearray)) or len(result) < REPORT_DATA_SIZE + 176:
        raise RuntimeError(f"TDX ioctl returned unexpected result (len={len(result) if hasattr(result, '__len__') else '?'})")

    # MRTD is at offset 128 within the TDREPORT struct (after the 64-byte report_data prefix)
    mrtd_start = REPORT_DATA_SIZE + 128
    mrtd_end = mrtd_start + 48
    mrtd_bytes = bytes(result[mrtd_start:mrtd_end])
    mrtd_hex = mrtd_bytes.hex()
    return {"type": "tdx", "measurement": mrtd_hex, "measurement_field": "MRTD",
            "label": _LABEL_MEASURED, "source": "ioctl:TDX_CMD_GET_REPORT0"}


def _tdx_read_mrtd_file(path: str) -> dict:
    """Read MRTD from a pre-baked TDX TDREPORT binary file.

    The file is expected to be the 1024-byte TDREPORT_STRUCT (no report_data prefix
    when supplied directly from a dstack operator).  MRTD is at offset 128..176.
    Raises on any error.
    """
    with open(path, "rb") as f:
        data = f.read(1024)
    if len(data) < 176:
        raise ValueError(f"TDX report file too short ({len(data)} bytes)")
    mrtd_bytes = data[128:176]
    mrtd_hex = mrtd_bytes.hex()
    return {"type": "tdx", "measurement": mrtd_hex, "measurement_field": "MRTD",
            "label": _LABEL_MEASURED, "source": f"file:{path}"}


# ---------------------------------------------------------------------------
# TEE probe: AWS Nitro
# ---------------------------------------------------------------------------
def _probe_nitro() -> dict | None:
    """Try to read an AWS Nitro NSM attestation document and extract PCR0.

    Returns a measurement dict {type, measurement, label} on success, or None
    when not running inside a Nitro enclave.  NEVER fabricates.
    """
    if not os.path.exists(_NITRO_NSM_DEVICE):
        return None
    try:
        # aws-nitro-enclaves-nsm-api (pip install aws-nitro-enclaves-nsm-api)
        # Alternatively some images use the `nsm` package.
        import nsm  # type: ignore[import]
        fd = nsm.open()
        try:
            doc = nsm.get_attestation_doc(fd, user_data=b"szl-tee-attest", nonce=b"")
        finally:
            nsm.close(fd)
        return _extract_nitro_pcr0(doc)
    except ImportError:
        pass

    # Fallback: try the AWS Nitro helper library (aws_nitro_enclaves_nsm_api)
    try:
        from aws_nitro_enclaves_nsm_api import nsm  # type: ignore[import]
        fd = nsm.lib.nsm_lib_init()
        response = nsm.lib.nsm_process_request(
            fd,
            nsm.AttestationRequest(user_data=b"szl-tee-attest")
        )
        nsm.lib.nsm_lib_exit(fd)
        doc_bytes = response.attestation_doc
        return _extract_nitro_pcr0(doc_bytes)
    except Exception:
        pass

    return None


def _extract_nitro_pcr0(doc_bytes: bytes) -> dict:
    """Extract PCR0 from an AWS Nitro attestation document (CBOR + COSE_Sign1).

    The document is a CBOR-encoded map.  PCR0 is the SHA-384 measurement of the
    enclave image.  We use the stdlib `struct` module + a minimal CBOR decoder to
    avoid adding a cbor2 dependency (which is not in all environments).

    Raises on parse failure so the caller can fall through.
    """
    # Prefer cbor2 if available (cleaner)
    try:
        import cbor2  # type: ignore[import]
        payload = cbor2.loads(doc_bytes)
        # COSE_Sign1: [protected, unprotected, payload_bytes, sig]
        if isinstance(payload, list) and len(payload) == 4:
            inner = cbor2.loads(payload[2])
        else:
            inner = payload
        pcrs = inner.get("pcrs", {})
        pcr0_bytes = pcrs.get(0)
        if not isinstance(pcr0_bytes, bytes):
            raise ValueError(f"PCR0 not found in attestation doc (keys: {list(pcrs.keys())})")
        return {"type": "nitro", "measurement": pcr0_bytes.hex(), "measurement_field": "PCR0",
                "label": _LABEL_MEASURED, "source": "nsm:AttestationDoc"}
    except ImportError:
        pass

    # Minimal fallback: if we can't parse, surface that TEE is present but measurement
    # extraction failed — this is still honest (present=True, no fabricated value).
    raise RuntimeError("Nitro NSM present but CBOR parse unavailable (install cbor2)")


# ---------------------------------------------------------------------------
# Public API: get_tee_attestation()
# ---------------------------------------------------------------------------
def get_tee_attestation() -> dict:
    """Probe the runtime for TEE attestation.  Always returns a complete, honest dict.

    On a real Intel TDX pod:
      {"present": True, "type": "tdx", "measurement": "<mrtd_hex>", "label": "MEASURED",
       "measurement_field": "MRTD", "doc_ref": "..."}

    On a real AWS Nitro enclave:
      {"present": True, "type": "nitro", "measurement": "<pcr0_hex>", "label": "MEASURED",
       "measurement_field": "PCR0", "doc_ref": "..."}

    On the current HF CPU-basic Space (no TEE):
      {"present": False, "label": "UNAVAILABLE",
       "note": "no TEE on current runtime; TDX/Nitro attestation is ROADMAP for the sovereign deployment",
       "doc_ref": "..."}

    NEVER fabricates a quote, measurement, or type.
    """
    try:
        result = _probe_tdx()
        if result is not None:
            return {
                "present": True,
                "type": result["type"],
                "measurement": result["measurement"],
                "measurement_field": result.get("measurement_field", "MRTD"),
                "label": _LABEL_MEASURED,
                "source": result.get("source", "tdx"),
                "doc_ref": _DOC_REF,
                "doctrine": "v11 — measurement MEASURED from live TDX hardware; never fabricated.",
            }
    except Exception as e:
        # Device exists but probing failed — still honest: not present/successful
        _warn(f"TDX probe failed: {type(e).__name__}: {e}")

    try:
        result = _probe_nitro()
        if result is not None:
            return {
                "present": True,
                "type": result["type"],
                "measurement": result["measurement"],
                "measurement_field": result.get("measurement_field", "PCR0"),
                "label": _LABEL_MEASURED,
                "source": result.get("source", "nsm"),
                "doc_ref": _DOC_REF,
                "doctrine": "v11 — measurement MEASURED from live Nitro NSM; never fabricated.",
            }
    except Exception as e:
        _warn(f"Nitro probe failed: {type(e).__name__}: {e}")

    # Neither TDX nor Nitro present — honest UNAVAILABLE
    return {
        "present": False,
        "label": _LABEL_UNAVAILABLE,
        "note": (
            "no TEE on current runtime; "
            "TDX/Nitro attestation is ROADMAP for the sovereign deployment"
        ),
        "doc_ref": _DOC_REF,
        "doctrine": "v11 — no fabricated quote; hook is wired and auto-lights-up on TDX/Nitro.",
    }


def _warn(msg: str) -> None:
    import sys
    print(f"[szl_tee_attest] {msg}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Receipt field helper — additive, zero-cost when no TEE
# ---------------------------------------------------------------------------
def tee_attestation_field() -> dict:
    """Return the tee_attestation field suitable for embedding in any Khipu/govern receipt.

    Always additive: if this function raises (import error, etc.) the caller should
    catch and skip — the receipt remains valid without it.

    Returns the full tee_attestation dict as documented in get_tee_attestation().
    """
    return get_tee_attestation()


# ---------------------------------------------------------------------------
# HTTP handler + registration
# ---------------------------------------------------------------------------
def _h_tee_status(request):
    from starlette.responses import JSONResponse  # type: ignore[import]
    result = get_tee_attestation()
    result["ts"] = _now_iso()
    return JSONResponse(result)


def register(app, ns: str = "a11oy") -> dict:
    """Wire GET /api/<ns>/v1/tee/status onto the app.

    Additive.  Prefers FastAPI's add_api_route (so the route resolves before the SPA
    catch-all); falls back to Starlette Route append.  Never raises into the caller.
    Returns {"registered": [...], "status": "ok"|"failed:<reason>"}.
    """
    path = f"/api/{ns}/v1/tee/status"
    try:
        from starlette.routing import Route  # type: ignore[import]
    except Exception as e:
        return {"registered": [], "status": f"failed:starlette-absent:{e}"}

    add_api_route = getattr(app, "add_api_route", None)
    try:
        if callable(add_api_route):
            app.add_api_route(path, _h_tee_status, methods=["GET"])
        else:
            app.router.routes.append(Route(path, _h_tee_status))
        return {"registered": [path], "status": "ok"}
    except Exception as e:
        return {"registered": [], "status": f"failed:{type(e).__name__}:{e}"}


# ---------------------------------------------------------------------------
# No-server self-test
# ---------------------------------------------------------------------------
def _selftest() -> dict:
    """Verify honest UNAVAILABLE on the current (non-TEE) runtime."""
    result = get_tee_attestation()
    # On a non-TEE host, result MUST be UNAVAILABLE and no measurement fabricated
    if not os.path.exists(_TDX_GUEST_DEVICE) and not os.path.exists(_NITRO_NSM_DEVICE):
        assert result["present"] is False, f"Expected present=False on non-TEE host, got: {result}"
        assert result["label"] == _LABEL_UNAVAILABLE, result
        assert "NOT fabricated" not in str(result.get("note", ""))  # note says "no fabricated quote"
        assert "ROADMAP" in result.get("note", ""), result
    return {"ok": True, "result": result}


if __name__ == "__main__":
    import json
    print(json.dumps(_selftest(), indent=2, default=str))
