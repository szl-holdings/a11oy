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

WHAT GETS ATTACHED (when TEE evidence is locally observed):
  tee_attestation: {
    schema:        "szl.tee-attestation/v2",
    present:       true,
    verified:      false,
    type:          "tdx" | "nitro",
    quote_digest:  "<sha256>",
    measurement:   "<hex>",
    verified_at:   null,
    verifier:      null,
    evidence_tier: "SAMPLE_UNVERIFIED",
    label:         "SAMPLE",
  }

WHAT GETS ATTACHED (when TEE is absent — current state):
  tee_attestation: {
    schema:        "szl.tee-attestation/v2",
    present:       false,
    verified:      false,
    label:         "UNAVAILABLE",
    evidence_tier: "UNAVAILABLE",
  }

Reading a report is not verification. This module never promotes locally parsed
evidence to MEASURED. A trusted verifier must validate the quote signature,
certificate chain, freshness, nonce, and reference measurements first.

HIGH-CONSEQUENCE RELEASE:
  The normalized verifier result must be sealed in a valid DSSE
  envelope with payload type application/vnd.szl.tee-verifier-result+json.
  The policy verifies that signature with the verifier-specific public key in
  SZL_TEE_VERIFIER_PUBLIC_KEYS_JSON, requires the verifier identity in
  SZL_TEE_TRUSTED_VERIFIERS, checks the current nonce and workload digest,
  enforces a five-minute freshness window, and matches the hardware measurement
  against SZL_TEE_REFERENCE_MEASUREMENTS. Missing config or evidence is BLOCK,
  never an inferred pass. The general receipt-signing key is not a TEE trust root.
  A live verifier adapter is configured with SZL_TEE_VERIFIER_URL plus the exact
  SZL_TEE_VERIFIER_ALLOWED_HOSTS allowlist. It receives the raw request-bound
  quote and must return the verifier-specific DSSE envelope. HTTPS certificate
  verification is mandatory and redirects are refused. External verification
  is explicit opt-in for authorized state-changing callers; GET/status/helper
  reads remain observation-only. Intel challenged requests call the official
  libtdx-attest Quote Generation Library, which obtains a same-host QGS-signed
  TD Quote; a local TDREPORT or configfs-TSM report is never relabeled as one.

ENDPOINTS:
  GET /api/a11oy/v1/tee/status   — honest present/absent + measurement when available

SPDX-License-Identifier: Apache-2.0
© 2026 Lutar, Stephen P. — SZL Holdings · Doctrine v11
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import secrets
import struct
from datetime import datetime, timezone
from typing import Mapping

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_DOC_REF = "arXiv 2606.03323 dstack-capsule pattern (Apache-2.0)"
_LABEL_MEASURED = "MEASURED"
_LABEL_SAMPLE = "SAMPLE"
_LABEL_UNAVAILABLE = "UNAVAILABLE"
_SCHEMA = "szl.tee-attestation/v2"
_VERIFIER_SCHEMA = "szl.tee-verifier-result/v1"
_VERIFIER_PAYLOAD_TYPE = "application/vnd.szl.tee-verifier-result+json"
_DEFAULT_MAX_AGE_SECONDS = 300

# Standard TDX paths (Linux kernel TDX guest driver, kernel 5.19+/6.x)
_TDX_GUEST_DEVICE = "/dev/tdx_guest"
_TDX_REPORT_ENV = "SZL_TDX_REPORT_PATH"
_MAX_TEE_EVIDENCE_BYTES = 1024 * 1024
_TDX_QUOTE_HEADER_SIZE = 48
_TDX_1_0_QUOTE_BODY_SIZE = 584
# Canonical packed layouts from Intel's public sgx_quote_5.h.
_TDX_V5_BODY_SIZES = {
    2: 584,  # TDX 1.0
    3: 648,  # TDX 1.5
    4: 885,  # TDX 1.5ex
}
_TDX_QUOTE_REPORT_DATA_OFFSET = 520
_TDX_TEE_TYPE = 0x00000081
_TDX_ECDSA_P256_ATTESTATION_KEY_TYPE = 2
_TDX_TDREPORT_SIZE = 1024
_TDX_TDREPORT_TYPE = 0x81
_TDX_TDREPORT_REPORTDATA_OFFSET = 128
_TDX_TDREPORT_REPORTDATA_SIZE = 64
_TDX_TDREPORT_TDINFO_OFFSET = 512
_TDX_TDINFO_MRTD_OFFSET = 16
_TDX_TDREPORT_MRTD_OFFSET = _TDX_TDREPORT_TDINFO_OFFSET + _TDX_TDINFO_MRTD_OFFSET
_TDX_TDREPORT_MRTD_SIZE = 48

# AWS Nitro NSM device path
_NITRO_NSM_DEVICE = "/dev/nsm"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_hex(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


# ---------------------------------------------------------------------------
# TEE probe: Intel TDX
# ---------------------------------------------------------------------------
def _request_binding(
    nonce: str | None,
    workload_digest: str | None,
) -> tuple[bytes, bytes, bytes] | None:
    """Validate and frame one attestation request without inventing evidence."""
    if nonce is None and workload_digest is None:
        return None
    if (
        not _valid_hex(nonce, minimum=64, maximum=64)
        or not _valid_hex(workload_digest, minimum=64, maximum=128)
    ):
        raise ValueError("nonce/workload digest must be bounded hexadecimal values")
    nonce_bytes = bytes.fromhex(nonce)
    workload_bytes = bytes.fromhex(workload_digest)
    report_data = hashlib.sha512(
        b"szl-tee-request-v1\0"
        + len(nonce_bytes).to_bytes(2, "big")
        + nonce_bytes
        + len(workload_bytes).to_bytes(2, "big")
        + workload_bytes
    ).digest()
    return nonce_bytes, workload_bytes, report_data


def _probe_tdx(
    nonce: str | None = None,
    workload_digest: str | None = None,
) -> dict | None:
    """Try to read an Intel TDX MRTD measurement.

    Returns a measurement dict {type, measurement, label} on success, or None
    when not running inside TDX.  NEVER fabricates.

    Probing order:
      (a) /dev/tdx_guest device exists — attempt ioctl TDREPORT (Linux 6.x TDX driver).
      (b) Env SZL_TDX_REPORT_PATH points to a readable binary TDX report file (for
          containers that receive a pre-baked report from the TEE operator).
    """
    binding = _request_binding(nonce, workload_digest)
    if binding is not None:
        # A request-bound remote attestation requires a signed TD Quote from the
        # platform Quote Generation Service. Intel's libtdx_attest QGL performs
        # that conversion through the configured vsock/configfs/TDCall channel.
        # Reading configfs outblob directly can yield only a local TDREPORT, and
        # GET_REPORT0 is never a valid fallback for a challenged request.
        try:
            return _tdx_read_quote_qgl(binding[2])
        except Exception:
            return None

    # (a) /dev/tdx_guest ioctl path
    tdx_dev = os.environ.get("SZL_TDX_DEVICE", _TDX_GUEST_DEVICE)
    if os.path.exists(tdx_dev):
        try:
            return _tdx_read_mrtd_ioctl(tdx_dev)
        except Exception:
            pass  # device exists but ioctl failed (non-TDX kernel, permissions) — fall through

    # (b) Pre-baked report file path (operator-provided, dstack pattern).
    # Never associate a cached file with a fresh challenge it did not receive.
    report_path = os.environ.get(_TDX_REPORT_ENV, "")
    if report_path and os.path.isfile(report_path):
        try:
            return _tdx_read_mrtd_file(report_path)
        except Exception:
            pass

    return None


def _load_tdx_attest_library():
    """Load Intel's in-guest Quote Generation Library without a shell helper."""
    import ctypes
    import ctypes.util

    candidates = [
        ctypes.util.find_library("tdx_attest"),
        "libtdx_attest.so.1",
        "libtdx_attest.so",
    ]
    errors: list[str] = []
    for candidate in candidates:
        if not candidate:
            continue
        try:
            return ctypes.CDLL(candidate)
        except OSError as exc:
            errors.append(type(exc).__name__)
    detail = ",".join(errors) if errors else "not-found"
    raise RuntimeError(f"Intel libtdx-attest is unavailable ({detail})")


def _tdx_quote_layout(quote: bytes) -> tuple[int, int, int]:
    """Validate a QGL result and return (version, report-data offset, sig offset)."""
    if not isinstance(quote, bytes) or len(quote) > _MAX_TEE_EVIDENCE_BYTES:
        raise RuntimeError("TDX QGL returned invalid or oversized evidence")
    if len(quote) < _TDX_QUOTE_HEADER_SIZE + _TDX_1_0_QUOTE_BODY_SIZE + 4:
        raise RuntimeError("TDX QGL result is too short to be a signed TD Quote")
    version, att_key_type, tee_type = struct.unpack_from("<HHI", quote, 0)
    if version not in {4, 5}:
        raise RuntimeError("TDX QGL returned an unsupported Quote version")
    if att_key_type != _TDX_ECDSA_P256_ATTESTATION_KEY_TYPE:
        raise RuntimeError("TDX QGL returned an unsupported attestation key type")
    if tee_type != _TDX_TEE_TYPE:
        raise RuntimeError("TDX QGL result is not an Intel TDX Quote")
    if quote[8:12] != b"\0" * 4:
        raise RuntimeError("TDX Quote reserved header bytes are nonzero")

    if version == 4:
        report_data_offset = (
            _TDX_QUOTE_HEADER_SIZE + _TDX_QUOTE_REPORT_DATA_OFFSET
        )
        signature_length_offset = (
            _TDX_QUOTE_HEADER_SIZE + _TDX_1_0_QUOTE_BODY_SIZE
        )
    else:
        body_type, body_size = struct.unpack_from(
            "<HI", quote, _TDX_QUOTE_HEADER_SIZE
        )
        expected_body_size = _TDX_V5_BODY_SIZES.get(body_type)
        if expected_body_size is None:
            raise RuntimeError("TDX Quote v5 has an unsupported body type")
        if body_size != expected_body_size:
            raise RuntimeError(
                "TDX Quote v5 body size does not match its body type"
            )
        report_data_offset = (
            _TDX_QUOTE_HEADER_SIZE + 6 + _TDX_QUOTE_REPORT_DATA_OFFSET
        )
        signature_length_offset = _TDX_QUOTE_HEADER_SIZE + 6 + body_size

    if signature_length_offset + 4 > len(quote):
        raise RuntimeError("TDX Quote omits its signature length")
    signature_length = struct.unpack_from(
        "<I", quote, signature_length_offset
    )[0]
    if signature_length < 64:
        raise RuntimeError("TDX Quote omits remotely verifiable signature data")
    if signature_length_offset + 4 + signature_length != len(quote):
        raise RuntimeError("TDX Quote signature length does not match its buffer")
    if report_data_offset + 64 > signature_length_offset:
        raise RuntimeError("TDX Quote omits its REPORTDATA binding")
    return version, report_data_offset, signature_length_offset


def _tdx_qgl_quote_bytes(report_data: bytes) -> bytes:
    """Use Intel libtdx-attest to obtain the QGS-produced TD Quote."""
    import ctypes

    if not isinstance(report_data, bytes) or len(report_data) != 64:
        raise ValueError("TDX Quote REPORTDATA must be exactly 64 bytes")

    class _TdxReportData(ctypes.Structure):
        _pack_ = 1
        _fields_ = [("d", ctypes.c_uint8 * 64)]

    class _TdxUuid(ctypes.Structure):
        _pack_ = 1
        _fields_ = [("d", ctypes.c_uint8 * 16)]

    library = _load_tdx_attest_library()
    get_quote = library.tdx_att_get_quote
    free_quote = library.tdx_att_free_quote
    get_quote.argtypes = [
        ctypes.POINTER(_TdxReportData),
        ctypes.POINTER(_TdxUuid),
        ctypes.c_uint32,
        ctypes.POINTER(_TdxUuid),
        ctypes.POINTER(ctypes.POINTER(ctypes.c_uint8)),
        ctypes.POINTER(ctypes.c_uint32),
        ctypes.c_uint32,
    ]
    get_quote.restype = ctypes.c_uint32
    free_quote.argtypes = [ctypes.POINTER(ctypes.c_uint8)]
    free_quote.restype = ctypes.c_uint32

    report = _TdxReportData()
    ctypes.memmove(report.d, report_data, len(report_data))
    selected_key = _TdxUuid()
    quote_pointer = ctypes.POINTER(ctypes.c_uint8)()
    quote_size = ctypes.c_uint32(0)
    result = get_quote(
        ctypes.byref(report),
        None,
        0,
        ctypes.byref(selected_key),
        ctypes.byref(quote_pointer),
        ctypes.byref(quote_size),
        0,
    )
    if result != 0:
        raise RuntimeError(f"Intel TDX Quote Generation Library failed (0x{result:04x})")
    if not quote_pointer:
        raise RuntimeError("Intel TDX Quote Generation Library returned no Quote")
    try:
        if not 0 < quote_size.value <= _MAX_TEE_EVIDENCE_BYTES:
            raise RuntimeError(
                "Intel TDX Quote Generation Library returned no bounded Quote"
            )
        return ctypes.string_at(quote_pointer, quote_size.value)
    finally:
        free_result = free_quote(quote_pointer)
        if free_result != 0:
            raise RuntimeError(
                f"Intel TDX Quote buffer release failed (0x{free_result:04x})"
            )


def _tdx_read_quote_qgl(report_data: bytes) -> dict:
    """Generate and structurally validate a request-bound QGS-signed TD Quote."""
    if not isinstance(report_data, bytes) or len(report_data) != 64:
        raise ValueError("TDX Quote REPORTDATA must be exactly 64 bytes")
    quote = _tdx_qgl_quote_bytes(report_data)
    version, report_data_offset, _signature_offset = _tdx_quote_layout(quote)
    if quote[report_data_offset : report_data_offset + 64] != report_data:
        raise RuntimeError("TDX Quote REPORTDATA does not match this request")
    return {
        "type": "tdx",
        "measurement": None,
        "measurement_field": "MRTD",
        "quote_digest": _sha256_hex(quote),
        "quote_bytes": quote,
        "source": "intel-libtdx-attest:qgs",
        "evidence_format": f"TDQUOTE_V{version}",
        "request_binding_digest": report_data.hex(),
    }


def _parse_tdx_tdreport(report: bytes) -> tuple[bytes, bytes]:
    """Validate one TDX 1.0 TDREPORT and return (REPORTDATA, MRTD).

    Intel TDX ABI 1.0 defines a 1024-byte TDREPORT_STRUCT:
    REPORTMACSTRUCT.REPORTDATA is at 128..192, while TDINFO.MRTD is at
    TDINFO offset 16, or absolute report bytes 528..576. The four-byte
    REPORTTYPE header must be TDX type 0x81, subtype 0, version 0, reserved 0.
    """
    if not isinstance(report, bytes) or len(report) != _TDX_TDREPORT_SIZE:
        length = len(report) if isinstance(report, bytes) else "non-bytes"
        raise ValueError(
            f"TDX report must be exactly {_TDX_TDREPORT_SIZE} bytes ({length})"
        )
    report_type, subtype, version, reserved = report[:4]
    if report_type != _TDX_TDREPORT_TYPE:
        raise ValueError("TDX report has a non-TDX REPORTTYPE")
    if subtype != 0:
        raise ValueError("TDX report has an unsupported REPORTTYPE subtype")
    if version != 0:
        raise ValueError("TDX report has an unsupported REPORTTYPE version")
    if reserved != 0:
        raise ValueError("TDX report has nonzero REPORTTYPE reserved data")
    reportdata = report[
        _TDX_TDREPORT_REPORTDATA_OFFSET:
        _TDX_TDREPORT_REPORTDATA_OFFSET + _TDX_TDREPORT_REPORTDATA_SIZE
    ]
    mrtd = report[
        _TDX_TDREPORT_MRTD_OFFSET:
        _TDX_TDREPORT_MRTD_OFFSET + _TDX_TDREPORT_MRTD_SIZE
    ]
    return reportdata, mrtd


def _tdx_read_mrtd_ioctl(
    dev_path: str,
    report_data: bytes | None = None,
) -> dict:
    """Read TDX MRTD via the Linux /dev/tdx_guest ioctl (TDREPORT).

    The TDX_CMD_GET_REPORT0 ioctl (0xc0400101 on Linux 6.x) returns a 1024-byte
    TDREPORT_STRUCT. REPORTMACSTRUCT.REPORTDATA occupies bytes 128..192 and
    TDINFO.MRTD occupies bytes 528..576. We validate the REPORTTYPE header,
    verify REPORTDATA when supplied, and extract the distinct MRTD field.

    Raises on any error so the caller can fall through to the file path or None.
    """
    import fcntl  # stdlib — available on Linux

    # TDX ioctl constants (Linux 6.x tdx-guest driver, uapi/linux/tdx-guest.h)
    # TDX_CMD_GET_REPORT0 = _IOWR('T', 0x01, struct tdx_report_req)
    # struct tdx_report_req: { u8 reportdata[64]; u8 tdreport[1024]; }
    TDX_CMD_GET_REPORT0 = 0xC0400101  # ioctl number for 64+1024 = 1088-byte struct
    REPORT_DATA_SIZE = 64
    TD_REPORT_SIZE = _TDX_TDREPORT_SIZE
    REQ_SIZE = REPORT_DATA_SIZE + TD_REPORT_SIZE

    req = bytearray(REQ_SIZE)
    if report_data is not None:
        if len(report_data) != REPORT_DATA_SIZE:
            raise ValueError("TDX REPORT_DATA must be exactly 64 bytes")
        req[:REPORT_DATA_SIZE] = report_data

    with open(dev_path, "rb") as f:
        fcntl.ioctl(f.fileno(), TDX_CMD_GET_REPORT0, req, True)

    raw_report = bytes(req[REPORT_DATA_SIZE:])
    returned_report_data, mrtd_bytes = _parse_tdx_tdreport(raw_report)
    if report_data is not None and returned_report_data != report_data:
        raise ValueError("TDX TDREPORT REPORTDATA does not match the ioctl request")
    mrtd_hex = mrtd_bytes.hex()
    return {
        "type": "tdx",
        "measurement": mrtd_hex,
        "measurement_field": "MRTD",
        "quote_digest": _sha256_hex(raw_report),
        "source": "ioctl:TDX_CMD_GET_REPORT0",
        "request_binding_digest": report_data.hex() if report_data is not None else None,
        "evidence_format": "TDREPORT_LOCAL_ONLY",
    }


def _tdx_read_mrtd_file(path: str) -> dict:
    """Read MRTD from a pre-baked TDX TDREPORT binary file.

    The file must be exactly one 1024-byte TDREPORT_STRUCT. REPORTDATA is at
    128..192 and MRTD is the distinct TDINFO field at 528..576. The report type,
    subtype, version, and reserved header byte are validated before extraction.
    """
    with open(path, "rb") as f:
        data = f.read(_TDX_TDREPORT_SIZE + 1)
    _report_data, mrtd_bytes = _parse_tdx_tdreport(data)
    mrtd_hex = mrtd_bytes.hex()
    return {
        "type": "tdx",
        "measurement": mrtd_hex,
        "measurement_field": "MRTD",
        "quote_digest": _sha256_hex(data),
        "source": "file:operator-provided",
        "request_binding_digest": None,
        "evidence_format": "TDREPORT_LOCAL_ONLY",
    }


# ---------------------------------------------------------------------------
# TEE probe: AWS Nitro
# ---------------------------------------------------------------------------
def _probe_nitro(
    nonce: str | None = None,
    workload_digest: str | None = None,
) -> dict | None:
    """Try to read an AWS Nitro NSM attestation document and extract PCR0.

    Returns a measurement dict {type, measurement, label} on success, or None
    when not running inside a Nitro enclave.  NEVER fabricates.
    """
    if not os.path.exists(_NITRO_NSM_DEVICE):
        return None
    binding = _request_binding(nonce, workload_digest)
    nonce_bytes = binding[0] if binding is not None else b""
    workload_bytes = binding[1] if binding is not None else b"szl-tee-attest"
    try:
        # aws-nitro-enclaves-nsm-api (pip install aws-nitro-enclaves-nsm-api)
        # Alternatively some images use the `nsm` package.
        import nsm  # type: ignore[import]
        fd = nsm.open()
        try:
            doc = nsm.get_attestation_doc(
                fd,
                user_data=workload_bytes,
                nonce=nonce_bytes,
            )
        finally:
            nsm.close(fd)
        return _extract_nitro_pcr0(
            doc,
            expected_nonce=nonce_bytes,
            expected_user_data=workload_bytes,
        )
    except ImportError:
        pass

    # Fallback: try the AWS Nitro helper library (aws_nitro_enclaves_nsm_api)
    try:
        from aws_nitro_enclaves_nsm_api import nsm  # type: ignore[import]
        fd = nsm.lib.nsm_lib_init()
        try:
            response = nsm.lib.nsm_process_request(
                fd,
                nsm.AttestationRequest(
                    user_data=workload_bytes,
                    nonce=nonce_bytes,
                )
            )
            doc_bytes = response.attestation_doc
        finally:
            nsm.lib.nsm_lib_exit(fd)
        return _extract_nitro_pcr0(
            doc_bytes,
            expected_nonce=nonce_bytes,
            expected_user_data=workload_bytes,
        )
    except Exception:
        pass

    return None


def _extract_nitro_pcr0(
    doc_bytes: bytes,
    *,
    expected_nonce: bytes | None = None,
    expected_user_data: bytes | None = None,
) -> dict:
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
        nonce_matches = (
            expected_nonce is None or inner.get("nonce") == expected_nonce
        )
        user_data_matches = (
            expected_user_data is None
            or inner.get("user_data") == expected_user_data
        )
        return {
            "type": "nitro",
            "measurement": pcr0_bytes.hex(),
            "measurement_field": "PCR0",
            "quote_digest": _sha256_hex(doc_bytes),
            "quote_bytes": doc_bytes,
            "source": "nsm:AttestationDoc",
            "request_binding_observed": bool(nonce_matches and user_data_matches),
        }
    except ImportError:
        pass

    # Minimal fallback: if we can't parse, surface that TEE is present but measurement
    # extraction failed — this is still honest (present=True, no fabricated value).
    raise RuntimeError("Nitro NSM present but CBOR parse unavailable (install cbor2)")


def _submit_to_verifier(
    result: dict,
    *,
    nonce: str,
    workload_digest: str,
) -> tuple[dict | None, str]:
    """Submit raw request-bound evidence to an operator-approved HTTPS verifier.

    The adapter returns a DSSE envelope; authentication and evidence equality
    are enforced locally afterward. Redirects are disabled so an allowed URL
    cannot redirect the quote to another host.
    """
    from urllib import error, parse, request

    url = os.environ.get("SZL_TEE_VERIFIER_URL", "").strip()
    if not url:
        return None, "external verifier URL is not configured"
    parsed = parse.urlsplit(url)
    allowed_hosts = {
        item.strip().lower()
        for item in os.environ.get(
            "SZL_TEE_VERIFIER_ALLOWED_HOSTS", ""
        ).split(",")
        if item.strip()
    }
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
        or parsed.hostname.lower() not in allowed_hosts
    ):
        return None, "external verifier URL is not an allowed HTTPS endpoint"
    quote_bytes = result.get("quote_bytes")
    if not isinstance(quote_bytes, bytes) or not quote_bytes:
        return None, "raw request-bound quote is unavailable"
    request_body = json.dumps(
        {
            "schema": "szl.tee-verifier-request/v1",
            "tee_type": result.get("type"),
            "quote": base64.b64encode(quote_bytes).decode("ascii"),
            "quote_digest": result.get("quote_digest"),
            "measurement": result.get("measurement"),
            "measurement_field": result.get("measurement_field"),
            "nonce": nonce,
            "workload_digest": workload_digest,
            "request_binding_digest": result.get("request_binding_digest"),
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    if len(request_body) > 256 * 1024:
        return None, "verifier request exceeds the bounded evidence limit"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "a11oy-tee-verifier-adapter/1",
    }
    bearer_token = os.environ.get("SZL_TEE_VERIFIER_BEARER_TOKEN", "")
    if bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"

    class _NoRedirect(request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    req = request.Request(url, data=request_body, headers=headers, method="POST")
    try:
        response = request.build_opener(_NoRedirect).open(req, timeout=5.0)
        with response:
            if response.status != 200:
                return None, f"external verifier returned HTTP {response.status}"
            raw = response.read(1024 * 1024 + 1)
    except (error.HTTPError, error.URLError, TimeoutError, OSError):
        return None, "external verifier request failed"
    if len(raw) > 1024 * 1024:
        return None, "external verifier response exceeds the bounded limit"
    try:
        decoded = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeError):
        return None, "external verifier response is malformed"
    envelope = (
        decoded.get("verifier_envelope")
        if isinstance(decoded, dict) and "verifier_envelope" in decoded
        else decoded
    )
    if not isinstance(envelope, dict):
        return None, "external verifier response lacks a DSSE envelope"
    return envelope, "external verifier returned a candidate envelope"


def _verified_attestation(
    result: dict,
    envelope: dict,
    *,
    nonce: str,
    workload_digest: str,
) -> tuple[dict | None, str]:
    """Promote only a verifier-authenticated result bound to the raw evidence."""
    payload, reason = _authenticated_verifier_payload(
        {"verifier_envelope": envelope},
        configured_verifier_public_keys(),
    )
    if payload is None:
        return None, reason
    verifier = payload.get("verifier")
    if verifier not in configured_trusted_verifiers():
        return None, "authenticated verifier is not in the operator allowlist"
    verified_at = _parse_utc(payload.get("verified_at"))
    age_seconds = (
        (datetime.now(timezone.utc) - verified_at).total_seconds()
        if verified_at is not None
        else None
    )
    if not (
        age_seconds is not None
        and 0 <= age_seconds <= _DEFAULT_MAX_AGE_SECONDS
    ):
        return None, "authenticated verifier result is stale or future-dated"
    verified_measurement = payload.get("measurement")
    if _is_debug_measurement(payload.get("tee_type"), verified_measurement):
        return None, "authenticated verifier reported a debug-mode measurement"
    local_measurement = result.get("measurement")
    if not (
        payload.get("tee_type") == result.get("type")
        and payload.get("quote_digest") == result.get("quote_digest")
        and _valid_hex(verified_measurement, minimum=64, maximum=256)
        and (
            local_measurement is None
            or verified_measurement == local_measurement
        )
        and payload.get("nonce") == nonce
        and payload.get("workload_digest") == workload_digest
        and payload.get("quote_signature_verified") is True
        and payload.get("certificate_chain_verified") is True
    ):
        return None, "authenticated verifier result does not match the request evidence"
    reference_measurements = configured_reference_measurements()
    if verified_measurement.lower() not in reference_measurements:
        return None, "authenticated measurement is not in the operator allowlist"
    return {
        "schema": _SCHEMA,
        "present": True,
        "verified": True,
        "type": result["type"],
        "quote_digest": result["quote_digest"],
        "measurement": verified_measurement,
        "measurement_field": result.get("measurement_field"),
        "request_nonce": nonce,
        "workload_digest": workload_digest,
        "request_binding_digest": result.get("request_binding_digest"),
        "request_binding_observed": result.get("request_binding_observed"),
        "verified_at": payload["verified_at"],
        "verifier": verifier,
        "verifier_envelope": envelope,
        "evidence_tier": "MEASURED_VERIFIED",
        "label": _LABEL_MEASURED,
        "source": result.get("source"),
        "note": "raw quote authenticated by the configured external verifier",
        "doc_ref": _DOC_REF,
        "doctrine": "v11 - MEASURED requires authenticated, request-bound verifier evidence.",
    }, "external verifier evidence authenticated"


# ---------------------------------------------------------------------------
# Public API: get_tee_attestation()
# ---------------------------------------------------------------------------
def _observed_attestation(
    result: dict,
    *,
    nonce: str | None = None,
    workload_digest: str | None = None,
) -> dict:
    """Normalize locally read evidence without claiming signature verification."""
    request_bound = bool(
        result.get("request_binding_digest")
        or result.get("request_binding_observed") is True
    )
    return {
        "schema": _SCHEMA,
        "present": True,
        "verified": False,
        "type": result["type"],
        "quote_digest": result["quote_digest"],
        "measurement": result["measurement"],
        "measurement_field": result.get("measurement_field"),
        "verified_at": None,
        "verifier": None,
        "evidence_tier": "SAMPLE_UNVERIFIED",
        "label": _LABEL_SAMPLE,
        "source": result.get("source"),
        "request_nonce": nonce if request_bound else None,
        "workload_digest": workload_digest if request_bound else None,
        "request_binding_digest": result.get("request_binding_digest"),
        "request_binding_observed": result.get("request_binding_observed"),
        "note": (
            "hardware evidence was read locally, but its signature and certificate chain "
            "were not verified; high-consequence release remains blocked"
        ),
        "doc_ref": _DOC_REF,
        "doctrine": "v11 - observation is not verification; no MEASURED claim emitted.",
    }


def _attestation_from_probe(
    result: dict,
    *,
    nonce: str | None,
    workload_digest: str | None,
    verify_external: bool,
) -> dict:
    """Verify request-bound probe evidence when a live adapter is configured."""
    request_bound = bool(
        result.get("request_binding_digest")
        or result.get("request_binding_observed") is True
    )
    if (
        verify_external
        and request_bound
        and isinstance(nonce, str)
        and isinstance(workload_digest, str)
    ):
        envelope, adapter_reason = _submit_to_verifier(
            result,
            nonce=nonce,
            workload_digest=workload_digest,
        )
        if envelope is not None:
            verified, verifier_reason = _verified_attestation(
                result,
                envelope,
                nonce=nonce,
                workload_digest=workload_digest,
            )
            if verified is not None:
                return verified
            adapter_reason = verifier_reason
    elif not verify_external:
        adapter_reason = "external verification disabled for read-only observation"
    else:
        adapter_reason = "probe evidence is not bound to the current request"
    observed = _observed_attestation(
        result,
        nonce=nonce,
        workload_digest=workload_digest,
    )
    observed["verifier_note"] = adapter_reason
    return observed


def get_tee_attestation(
    *,
    nonce: str | None = None,
    workload_digest: str | None = None,
    verify_external: bool = False,
) -> dict:
    """Probe the runtime for TEE attestation.  Always returns a complete, honest dict.

    On an Intel TDX pod where a TDREPORT is readable but not externally verified:
      {"present": True, "verified": False, "type": "tdx",
       "measurement": "<mrtd_hex>", "label": "SAMPLE", ...}

    On an AWS Nitro enclave where an attestation document is readable but its
    signature and certificate chain have not been validated:
      {"present": True, "verified": False, "type": "nitro",
       "measurement": "<pcr0_hex>", "label": "SAMPLE", ...}

    On the current HF CPU-basic Space (no TEE):
      {"present": False, "label": "UNAVAILABLE",
       "note": "no TEE on current runtime; TDX/Nitro attestation is ROADMAP for the sovereign deployment",
       "doc_ref": "..."}

    NEVER fabricates a quote, measurement, or type. External verification is
    explicit opt-in for an authorized state-changing caller. The safe default
    is observation-only: it suppresses both a request-bound quote challenge and
    the remote verifier transaction for every GET/status/helper caller.
    """
    probe_nonce = nonce if verify_external else None
    probe_workload_digest = workload_digest if verify_external else None
    try:
        result = _probe_tdx(
            nonce=probe_nonce,
            workload_digest=probe_workload_digest,
        )
        if result is not None:
            return _attestation_from_probe(
                result,
                nonce=nonce,
                workload_digest=workload_digest,
                verify_external=verify_external,
            )
    except Exception as e:
        # Device exists but probing failed — still honest: not present/successful
        _warn(f"TDX probe failed: {type(e).__name__}: {e}")

    try:
        result = _probe_nitro(
            nonce=probe_nonce,
            workload_digest=probe_workload_digest,
        )
        if result is not None:
            return _attestation_from_probe(
                result,
                nonce=nonce,
                workload_digest=workload_digest,
                verify_external=verify_external,
            )
    except Exception as e:
        _warn(f"Nitro probe failed: {type(e).__name__}: {e}")

    # Neither TDX nor Nitro present — honest UNAVAILABLE
    return {
        "schema": _SCHEMA,
        "present": False,
        "verified": False,
        "type": None,
        "quote_digest": None,
        "measurement": None,
        "measurement_field": None,
        "request_nonce": nonce,
        "workload_digest": workload_digest,
        "verified_at": None,
        "verifier": None,
        "evidence_tier": "UNAVAILABLE",
        "label": _LABEL_UNAVAILABLE,
        "note": (
            "no TEE on current runtime; "
            "TDX/Nitro attestation is ROADMAP for the sovereign deployment"
        ),
        "doc_ref": _DOC_REF,
        "doctrine": "v11 — no fabricated quote; hook is wired and auto-lights-up on TDX/Nitro.",
    }


def configured_reference_measurements() -> frozenset[str]:
    """Return the operator-configured measurement allowlist.

    This is public policy data, not a secret. An absent or malformed allowlist
    stays empty so high-consequence release fails closed.
    """
    raw = os.environ.get("SZL_TEE_REFERENCE_MEASUREMENTS", "")
    values = {
        item.strip().lower()
        for item in raw.split(",")
        if _valid_hex(item.strip(), minimum=64, maximum=128)
    }
    return frozenset(values)


def configured_trusted_verifiers() -> frozenset[str]:
    """Return verifier identities authorized to seal normalized TEE results."""
    raw = os.environ.get("SZL_TEE_TRUSTED_VERIFIERS", "")
    return frozenset(
        item.strip()
        for item in raw.split(",")
        if item.strip() and len(item.strip()) <= 128
    )


def configured_verifier_public_keys() -> dict[str, str]:
    """Return verifier identity -> P-256 public key policy.

    This is public trust-root configuration, not a signing secret. Malformed
    JSON, non-string entries, or implausible identities/PEMs are ignored so a
    high-consequence request fails closed instead of falling back to the
    repository-wide receipt key.
    """
    raw = os.environ.get("SZL_TEE_VERIFIER_PUBLIC_KEYS_JSON", "")
    if not raw:
        return {}
    try:
        decoded = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    if not isinstance(decoded, dict):
        return {}
    return {
        identity: pem
        for identity, pem in decoded.items()
        if (
            isinstance(identity, str)
            and 0 < len(identity) <= 128
            and isinstance(pem, str)
            and "-----BEGIN PUBLIC KEY-----" in pem
            and "-----END PUBLIC KEY-----" in pem
        )
    }


def _valid_hex(value: object, *, minimum: int, maximum: int) -> bool:
    return (
        isinstance(value, str)
        and minimum <= len(value) <= maximum
        and len(value) % 2 == 0
        and re.fullmatch(r"[0-9a-fA-F]+", value) is not None
    )


def _is_debug_measurement(tee_type: object, measurement: object) -> bool:
    """Identify evidence values that explicitly denote an unsafe debug enclave."""
    return bool(
        tee_type == "nitro"
        and _valid_hex(measurement, minimum=96, maximum=96)
        and set(str(measurement).lower()) == {"0"}
    )


def _parse_utc(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _authenticated_verifier_payload(
    attestation: dict,
    verifier_public_keys: Mapping[str, str],
) -> tuple[dict | None, str]:
    """Cryptographically verify and decode the trusted verifier result.

    The untrusted payload identity only selects from an externally configured
    verifier-specific public-key map. It cannot reuse the general receipt
    signing key or introduce a key from the envelope itself.
    """
    envelope = attestation.get("verifier_envelope")
    if not isinstance(envelope, dict):
        return None, "authenticated verifier envelope is absent"
    if envelope.get("_dsse") != "DSSEv1":
        return None, "verifier envelope is not DSSEv1"
    if envelope.get("payloadType") != _VERIFIER_PAYLOAD_TYPE:
        return None, "verifier envelope payload type is not trusted"
    try:
        body = base64.b64decode(envelope.get("payload", ""), validate=True)
        payload = json.loads(body.decode("utf-8"))
    except (TypeError, ValueError, UnicodeError):
        return None, "verifier envelope payload is malformed"
    if not isinstance(payload, dict):
        return None, "verifier envelope payload is not a mapping"
    if payload.get("schema") != _VERIFIER_SCHEMA:
        return None, "verifier envelope schema is not trusted"
    if payload.get("verdict") != "VERIFIED":
        return None, "trusted verifier did not issue a VERIFIED verdict"
    verifier = payload.get("verifier")
    if not isinstance(verifier, str) or not verifier:
        return None, "verifier identity is absent"
    pem = verifier_public_keys.get(verifier)
    if not isinstance(pem, str):
        return None, "verifier-specific public key is not configured"
    signatures = envelope.get("signatures")
    if not isinstance(signatures, list) or not signatures:
        return None, "verifier envelope signature is absent"
    try:
        from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ec

        public_key = serialization.load_pem_public_key(pem.encode("utf-8"))
        if (
            not isinstance(public_key, ec.EllipticCurvePublicKey)
            or not isinstance(public_key.curve, ec.SECP256R1)
        ):
            return None, "verifier public key is not ECDSA P-256"
        payload_type = _VERIFIER_PAYLOAD_TYPE.encode("utf-8")
        to_verify = (
            b"DSSEv1 "
            + str(len(payload_type)).encode("ascii")
            + b" "
            + payload_type
            + b" "
            + str(len(body)).encode("ascii")
            + b" "
            + body
        )
        for signature in signatures:
            if not isinstance(signature, dict) or signature.get("keyid") != verifier:
                continue
            try:
                signature_bytes = base64.b64decode(
                    signature.get("sig", ""), validate=True
                )
                public_key.verify(
                    signature_bytes,
                    to_verify,
                    ec.ECDSA(hashes.SHA256()),
                )
                break
            except (TypeError, ValueError, InvalidSignature):
                continue
        else:
            return None, "verifier envelope signature is invalid"
    except (TypeError, ValueError, UnsupportedAlgorithm):
        return None, "verifier public key could not be loaded"
    return payload, "authenticated verifier envelope passed"


def evaluate_attestation_policy(
    attestation: dict,
    *,
    high_consequence: bool,
    expected_nonce: str | None = None,
    expected_workload_digest: str | None = None,
    reference_measurements: set[str] | frozenset[str] | None = None,
    trusted_verifiers: set[str] | frozenset[str] | None = None,
    verifier_public_keys: Mapping[str, str] | None = None,
    max_age_seconds: int = _DEFAULT_MAX_AGE_SECONDS,
    now: datetime | None = None,
) -> dict:
    """Fail closed when a high-consequence action lacks verified hardware evidence.

    A high-consequence ALLOW requires a cryptographically authenticated verifier
    result, a fresh timestamp, exact request binding, and a measurement in the
    operator's explicit allowlist. Truthy metadata alone can never release work.
    """
    required = bool(high_consequence)
    current_time = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    configured_references = (
        configured_reference_measurements()
        if reference_measurements is None
        else reference_measurements
    )
    references = {
        value.lower()
        for value in configured_references
        if _valid_hex(value, minimum=64, maximum=128)
    }
    verifier_allowlist = (
        configured_trusted_verifiers()
        if trusted_verifiers is None
        else frozenset(trusted_verifiers)
    )
    public_keys = (
        configured_verifier_public_keys()
        if verifier_public_keys is None
        else dict(verifier_public_keys)
    )
    payload, verifier_reason = _authenticated_verifier_payload(
        attestation,
        public_keys,
    )
    verified_at = _parse_utc(payload.get("verified_at")) if payload else None
    age_seconds = (
        (current_time - verified_at).total_seconds()
        if verified_at is not None
        else None
    )
    fresh = (
        age_seconds is not None
        and 0 <= age_seconds <= max(1, int(max_age_seconds))
    )
    quote_digest = attestation.get("quote_digest")
    measurement = attestation.get("measurement")
    debug_mode = _is_debug_measurement(attestation.get("type"), measurement)
    outer_contract = (
        attestation.get("schema") == _SCHEMA
        and attestation.get("present") is True
        and attestation.get("verified") is True
        and attestation.get("label") == _LABEL_MEASURED
        and attestation.get("evidence_tier") == "MEASURED_VERIFIED"
        and attestation.get("type") in {"tdx", "nitro", "sev-snp", "nvidia-gpu"}
        and _valid_hex(quote_digest, minimum=64, maximum=64)
        and _valid_hex(measurement, minimum=64, maximum=128)
    )
    authenticated = payload is not None
    trusted_verifier = bool(
        payload
        and isinstance(payload.get("verifier"), str)
        and payload["verifier"] in verifier_allowlist
    )
    vendor_verification = bool(
        payload
        and payload.get("quote_signature_verified") is True
        and payload.get("certificate_chain_verified") is True
    )
    evidence_matches = bool(
        payload
        and payload.get("tee_type") == attestation.get("type")
        and payload.get("quote_digest") == quote_digest
        and payload.get("measurement") == measurement
        and payload.get("verified_at") == attestation.get("verified_at")
        and payload.get("verifier") == attestation.get("verifier")
    )
    request_bound = bool(
        payload
        and isinstance(expected_nonce, str)
        and expected_nonce
        and isinstance(expected_workload_digest, str)
        and expected_workload_digest
        and payload.get("nonce") == expected_nonce
        and payload.get("workload_digest") == expected_workload_digest
    )
    reference_match = bool(
        isinstance(measurement, str)
        and not debug_mode
        and references
        and measurement.lower() in references
    )
    verified = bool(
        outer_contract
        and authenticated
        and trusted_verifier
        and vendor_verification
        and evidence_matches
        and fresh
        and request_bound
        and not debug_mode
        and reference_match
    )
    allowed = (not required) or verified
    checks = {
        "outer_contract": outer_contract,
        "authenticated_verifier": authenticated,
        "trusted_verifier": trusted_verifier,
        "quote_and_certificate_verified": vendor_verification,
        "fresh": fresh,
        "request_bound": request_bound,
        "not_debug_mode": not debug_mode,
        "reference_measurement": reference_match,
        "evidence_matches_envelope": evidence_matches,
    }
    if verified:
        reason = "authenticated, fresh, request-bound evidence matches an allowed measurement"
    elif not required:
        reason = "verified hardware evidence is not required for this modeled, non-consequential read"
    else:
        failed = [name for name, passed in checks.items() if not passed]
        reason = (
            "high-consequence release blocked: "
            + ", ".join(failed)
            + f"; verifier={verifier_reason}"
        )
    return {
        "schema": "szl.attestation-policy/v1",
        "high_consequence": required,
        "verified_evidence": verified,
        "allowed": allowed,
        "verdict": "ALLOW" if allowed else "BLOCK",
        "reason": reason,
        "checks": checks,
        "verified_at": verified_at.isoformat() if verified_at else None,
        "age_seconds": round(age_seconds, 6) if age_seconds is not None else None,
        "max_age_seconds": max(1, int(max_age_seconds)),
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

    Additive.  Uses routes.insert(0, ...) to front-move so this route wins over
    the generic /api/a11oy/{path:path} Node proxy catch-all (same proven pattern
    as szl_compliance, szl_e8, etc. in serve.py).  Never raises into the caller.
    Returns {"registered": [...], "status": "ok"|"failed:<reason>"}.
    """
    path = f"/api/{ns}/v1/tee/status"
    try:
        from starlette.routing import Route  # type: ignore[import]
    except Exception as e:
        return {"registered": [], "status": f"failed:starlette-absent:{e}"}

    try:
        # Front-insert so this route beats the /api/a11oy/{path:path} Node proxy
        # catch-all.  add_api_route appends (loses to pre-registered catch-all);
        # insert(0, ...) is the canonical pattern in this codebase.
        _r = Route(path, _h_tee_status, methods=["GET"])
        app.router.routes.insert(0, _r)
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
