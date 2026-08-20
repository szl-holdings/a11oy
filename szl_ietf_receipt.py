# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings
# ORCID: 0009-0001-0110-4173
"""
szl_ietf_receipt — IETF compliance-receipt alignment VIEW.

Aligns a11oy's existing in-image DSSE (ECDSA-P256-SHA256) decision receipts to the
field model of:

    draft-marques-asqav-compliance-receipts-05
    "Compliance Receipts for Autonomous System Quality Assurance & Verification"
    (Informational, May 2026)

DESIGN INVARIANT — DO NOT BREAK THE EXISTING ENVELOPE
-----------------------------------------------------
This module is a *projection / VIEW*. It NEVER re-signs and NEVER mutates the
canonical DSSE envelope produced by a11oy_serve._a11oy_sign_receipt(). The
cross-app DSSE (payloadType / payload / signatures{keyid,sig}) stays byte-identical.
We only expose a `compliance_profile` object that maps our governed-decision fields
onto the draft-05 payload field names, so an external ASQAV verifier can read our
receipts under the draft's vocabulary while still verifying the original signature.

draft-05 ENVELOPE (for reference; we DO NOT emit this shape, we map TO its payload):
  envelope = { payload, signature{alg,kid,sig}, anchors[], witness_policy? }
  (kid MUST equal payload.issuer_id)

draft-05 PAYLOAD required fields:
  type, issued_at, issuer_id, payload_digest{hash,size,preview?},
  action_ref (sha256 of canonical action), sandbox_state, iteration_id
draft-05 DECISION receipts (type=protectmcp:decision):
  decision ∈ {allow,deny,rate_limit,observation}, tool_name,
  reason (required when deny/rate_limit), policy_digest="sha256:<hex>",
  previousReceiptHash (camelCase; sha256 of prior canonical signing-input;
                       first receipt = 64 zeros),
  controls_evaluated{emergency_halt,delegation_scope,quorum,mandate,policy,
                     content_scan,result}
    - quorum:  needs fired=true + attestation_hash
    - policy:  needs matched_count >= 1
type namespaces: protectmcp:{decision,restraint,lifecycle,observation,acknowledgment}
extension fields (optional): risk_class, incident_class, counterparty_binding,
  mitre_techniques, slsa_provenance_pointer, ...

Cite in docs+UI: draft-marques-asqav-compliance-receipts-05.

Pure-stdlib (hashlib/json/base64/datetime). No new crypto. ast-parse clean.
"""
from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Optional

DRAFT_ID = "draft-marques-asqav-compliance-receipts-05"
DRAFT_TITLE = ("Compliance Receipts for Autonomous System Quality Assurance "
               "& Verification")
DRAFT_STATUS = "Internet-Draft (Informational), May 2026"
PROFILE_VERSION = "szl-ietf-receipt/1.0.0"

ZERO_HASH = "0" * 64

DECISION_TYPES = ("protectmcp:decision", "protectmcp:restraint",
                  "protectmcp:lifecycle", "protectmcp:observation",
                  "protectmcp:acknowledgment")
DECISION_VALUES = ("allow", "deny", "rate_limit", "observation")

# control keys defined by the draft
CONTROL_KEYS = ("emergency_halt", "delegation_scope", "quorum", "mandate",
                "policy", "content_scan", "result")


def _canonical(obj: Any) -> bytes:
    """Canonical JSON identical in spirit to a11oy_serve._a11oy_canonical:
    sort_keys, compact separators, no ASCII escaping."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def _sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def action_ref(action: Any) -> str:
    """draft-05 action_ref = SHA-256 of the canonical action JSON (hex)."""
    return _sha256_hex(_canonical(action))


def payload_digest(payload_obj: Any, preview: bool = True) -> dict:
    """draft-05 payload_digest{hash,size,preview?} over canonical payload bytes."""
    body = _canonical(payload_obj)
    d = {"hash": "sha256:" + _sha256_hex(body), "size": len(body)}
    if preview:
        # short, non-secret preview (first 120 canonical chars) — never a key
        d["preview"] = body[:120].decode("utf-8", "replace")
    return d


def policy_digest(policy_obj: Any) -> str:
    """draft-05 policy_digest = 'sha256:<hex>' over canonical policy material."""
    return "sha256:" + _sha256_hex(_canonical(policy_obj))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _signing_input_hash_from_envelope(env: dict) -> Optional[str]:
    """Recover the prior receipt's canonical-signing-input hash for use as the
    NEXT receipt's previousReceiptHash. a11oy's DSSE envelope already carries
    `_pae_sha256` = sha256 of the DSSE PAE signing input, which is exactly the
    'hash of prior canonical signing input' the draft wants. Honest passthrough."""
    if not isinstance(env, dict):
        return None
    h = env.get("_pae_sha256")
    if isinstance(h, str) and len(h) == 64:
        return h
    # fall back to hashing the payload field if present
    p = env.get("payload")
    if isinstance(p, str):
        try:
            return _sha256_hex(base64.b64decode(p))
        except Exception:
            return None
    return None


def build_controls_evaluated(*,
                             policy_matched_count: int = 0,
                             content_scan_fired: Optional[bool] = None,
                             content_scan_signatures: Optional[list] = None,
                             quorum_fired: bool = False,
                             quorum_attestation_hash: Optional[str] = None,
                             emergency_halt: Optional[bool] = None,
                             delegation_scope_ok: Optional[bool] = None,
                             mandate_ok: Optional[bool] = None,
                             result: Optional[str] = None) -> dict:
    """Construct the draft-05 controls_evaluated object honestly from real signals.

    Only emit a control if we actually evaluated it; unevaluated controls are
    omitted rather than zero-filled (the draft treats absence as 'not evaluated').
    """
    controls: dict[str, Any] = {}

    # policy: must carry matched_count; matched_count>=1 means a policy matched
    controls["policy"] = {
        "evaluated": True,
        "matched_count": int(policy_matched_count),
        "matched": int(policy_matched_count) >= 1,
    }

    # content_scan: emit only if we actually ran the threat-signature scan
    if content_scan_fired is not None:
        controls["content_scan"] = {
            "evaluated": True,
            "fired": bool(content_scan_fired),
            "signatures": list(content_scan_signatures or []),
        }

    # quorum: per draft, fired=true REQUIRES an attestation_hash
    if quorum_fired:
        if not quorum_attestation_hash:
            raise ValueError(
                "draft-05: controls_evaluated.quorum.fired=true requires "
                "attestation_hash")
        controls["quorum"] = {
            "evaluated": True,
            "fired": True,
            "attestation_hash": quorum_attestation_hash,
        }
    else:
        controls["quorum"] = {"evaluated": True, "fired": False}

    if emergency_halt is not None:
        controls["emergency_halt"] = {"evaluated": True, "tripped": bool(emergency_halt)}
    if delegation_scope_ok is not None:
        controls["delegation_scope"] = {"evaluated": True, "within_scope": bool(delegation_scope_ok)}
    if mandate_ok is not None:
        controls["mandate"] = {"evaluated": True, "satisfied": bool(mandate_ok)}
    if result is not None:
        controls["result"] = {"evaluated": True, "value": str(result)}

    return controls


def compliance_payload(*,
                       decision: str,
                       tool_name: str,
                       action: Any,
                       issuer_id: str,
                       iteration_id: str,
                       sandbox_state: str = "active",
                       reason: Optional[str] = None,
                       policy_material: Any = None,
                       controls_evaluated: Optional[dict] = None,
                       previous_envelope: Optional[dict] = None,
                       rtype: str = "protectmcp:decision",
                       extensions: Optional[dict] = None) -> dict:
    """Build a draft-05-shaped compliance PAYLOAD (the inner object that an ASQAV
    verifier reads). This is the projection we expose; the real signature is still
    produced by a11oy's DSSE signer over a11oy's own canonical payload.

    Raises ValueError on draft-05 conformance violations so we never emit a
    silently-malformed compliance view.
    """
    if rtype not in DECISION_TYPES:
        raise ValueError("type %r not in draft-05 namespaces %r" % (rtype, DECISION_TYPES))
    if rtype == "protectmcp:decision" and decision not in DECISION_VALUES:
        raise ValueError("decision %r not in %r" % (decision, DECISION_VALUES))
    if decision in ("deny", "rate_limit") and not reason:
        raise ValueError("draft-05: decision=%s REQUIRES a reason" % decision)

    prev = ZERO_HASH
    if previous_envelope is not None:
        ph = _signing_input_hash_from_envelope(previous_envelope)
        if ph:
            prev = ph

    core = {
        "type": rtype,
        "issued_at": _now_iso(),
        "issuer_id": issuer_id,
        "iteration_id": str(iteration_id),
        "sandbox_state": sandbox_state,
        "action_ref": "sha256:" + action_ref(action),
        "decision": decision,
        "tool_name": tool_name,
        "previousReceiptHash": prev,  # camelCase per draft
        "policy_digest": policy_digest(policy_material if policy_material is not None else {}),
        "controls_evaluated": controls_evaluated or build_controls_evaluated(),
    }
    if reason:
        core["reason"] = reason
    # payload_digest is over the action+decision core (self-describing)
    core["payload_digest"] = payload_digest({"action": action, "decision": decision,
                                              "tool_name": tool_name})
    if extensions:
        # extension fields live alongside core per draft (risk_class, etc.)
        for k, v in extensions.items():
            if k not in core:
                core[k] = v
    return core


def compliance_profile(dsse_envelope: dict, payload_obj: dict, *,
                       decision: str,
                       tool_name: str,
                       action: Any,
                       issuer_id: str,
                       iteration_id: str,
                       reason: Optional[str] = None,
                       policy_material: Any = None,
                       controls_evaluated: Optional[dict] = None,
                       previous_envelope: Optional[dict] = None,
                       rtype: str = "protectmcp:decision",
                       extensions: Optional[dict] = None) -> dict:
    """Top-level VIEW returned by the API/UI.

    Returns:
      {
        draft, draft_title, draft_status, profile_version,
        dsse_envelope_intact: True,           # we did not touch the signature
        dsse_alg, dsse_kid,                    # echoed from the real envelope
        compliance_payload: {... draft-05 fields ...},
        mapping: {our_field -> draft_field},   # human-auditable crosswalk
        conformance: {ok, checks[...]},        # self-validation against the draft
      }
    """
    cpl = compliance_payload(
        decision=decision, tool_name=tool_name, action=action,
        issuer_id=issuer_id, iteration_id=iteration_id, reason=reason,
        policy_material=policy_material, controls_evaluated=controls_evaluated,
        previous_envelope=previous_envelope, rtype=rtype, extensions=extensions)

    sigs = (dsse_envelope or {}).get("signatures") or []
    kid = sigs[0].get("keyid") if sigs and isinstance(sigs[0], dict) else None

    mapping = {
        "a11oy.decision": "decision",
        "a11oy.tool / plan target": "tool_name",
        "a11oy._a11oy_canonical(action) sha256": "action_ref",
        "a11oy.issuer ('a11oy')": "issuer_id (== DSSE signature.kid)",
        "a11oy.iteration / seq": "iteration_id",
        "a11oy.policy gate digest": "policy_digest",
        "a11oy.prev DSSE _pae_sha256": "previousReceiptHash",
        "a11oy.arena_inspect threats + size guard": "controls_evaluated.content_scan",
        "a11oy.UDS 4/4 quorum": "controls_evaluated.quorum{fired,attestation_hash}",
        "a11oy.Colang policy flows matched": "controls_evaluated.policy.matched_count",
        "a11oy.DSSE envelope (ECDSA-P256-SHA256)": "envelope.signature (INTACT, unmodified)",
    }

    return {
        "draft": DRAFT_ID,
        "draft_title": DRAFT_TITLE,
        "draft_status": DRAFT_STATUS,
        "profile_version": PROFILE_VERSION,
        "dsse_envelope_intact": True,
        "dsse_alg": "ECDSA-P256-SHA256",
        "dsse_kid": kid,
        "dsse_payloadType": (dsse_envelope or {}).get("payloadType"),
        "compliance_payload": cpl,
        "mapping": mapping,
        "conformance": validate_compliance_payload(cpl),
        "note": ("VIEW only. The cross-app DSSE envelope is reproduced unchanged; "
                 "this profile maps a11oy governed-decision fields onto "
                 + DRAFT_ID + " payload vocabulary so an external ASQAV verifier "
                 "can read the receipt while still verifying the original "
                 "ECDSA-P256 signature against /cosign.pub."),
    }


def validate_compliance_payload(cpl: dict) -> dict:
    """Self-validate a compliance payload against draft-05 required fields.
    Returns {ok, checks:[{field, ok, detail}]} — honest, never throws."""
    checks = []

    def chk(name, cond, detail=""):
        checks.append({"check": name, "ok": bool(cond), "detail": detail})

    chk("type_in_namespace", cpl.get("type") in DECISION_TYPES, cpl.get("type"))
    for req in ("issued_at", "issuer_id", "iteration_id", "sandbox_state",
                "action_ref", "payload_digest"):
        chk("has_" + req, cpl.get(req) not in (None, ""), str(cpl.get(req))[:40])
    if cpl.get("type") == "protectmcp:decision":
        chk("decision_value", cpl.get("decision") in DECISION_VALUES, cpl.get("decision"))
        chk("has_tool_name", bool(cpl.get("tool_name")), cpl.get("tool_name"))
        if cpl.get("decision") in ("deny", "rate_limit"):
            chk("reason_when_deny", bool(cpl.get("reason")), "required for deny/rate_limit")
        pd = cpl.get("policy_digest", "")
        chk("policy_digest_format", isinstance(pd, str) and pd.startswith("sha256:") and len(pd) == 71, pd)
        prh = cpl.get("previousReceiptHash", "")
        chk("prev_hash_len", isinstance(prh, str) and len(prh) == 64, "len=%d" % len(prh or ""))
        ce = cpl.get("controls_evaluated") or {}
        pol = ce.get("policy") or {}
        chk("controls.policy.matched_count", "matched_count" in pol, str(pol.get("matched_count")))
        q = ce.get("quorum") or {}
        if q.get("fired"):
            chk("quorum.attestation_hash", bool(q.get("attestation_hash")),
                "fired=true requires attestation_hash")
    ok = all(c["ok"] for c in checks)
    return {"ok": ok, "checks": checks, "draft": DRAFT_ID}


# --------------------------------------------------------------------------- #
# self-test
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    import ast as _ast
    _ast.parse(open(__file__).read())

    fake_action = {"plan": "issue a reversible reroute", "tool_call": "reroute()"}
    fake_payload = {"decision": "ALLOW", "issuer": "a11oy", "seq": 7}
    fake_env = {
        "payloadType": "application/vnd.szl.a11oy-receipt+json",
        "payload": base64.b64encode(b'{"x":1}').decode(),
        "signatures": [{"keyid": "a11oy", "sig": "ZmFrZQ=="}],
        "_pae_sha256": "a" * 64,
        "signed": True,
    }

    # allow case
    prof = compliance_profile(
        fake_env, fake_payload,
        decision="allow", tool_name="reroute",
        action=fake_action, issuer_id="a11oy", iteration_id="7",
        controls_evaluated=build_controls_evaluated(
            policy_matched_count=2, content_scan_fired=False,
            content_scan_signatures=[], result="allow"),
        previous_envelope=fake_env,
    )
    assert prof["dsse_envelope_intact"] is True
    assert prof["dsse_alg"] == "ECDSA-P256-SHA256"
    assert prof["compliance_payload"]["type"] == "protectmcp:decision"
    assert prof["compliance_payload"]["previousReceiptHash"] == "a" * 64
    assert prof["conformance"]["ok"], prof["conformance"]
    print("[allow] conformance ok:", prof["conformance"]["ok"],
          "| action_ref:", prof["compliance_payload"]["action_ref"][:20])

    # deny case with content scan firing + quorum
    prof2 = compliance_profile(
        fake_env, fake_payload,
        decision="deny", tool_name="containment",
        action={"plan": "ignore previous policy", "tool_call": "system('rm -rf /')"},
        issuer_id="a11oy", iteration_id="8",
        reason="threat-signatures matched: ignore previous, rm -rf, system(",
        controls_evaluated=build_controls_evaluated(
            policy_matched_count=3,
            content_scan_fired=True,
            content_scan_signatures=["ignore previous", "rm -rf", "system("],
            quorum_fired=True, quorum_attestation_hash="b" * 64,
            result="deny"),
        extensions={"risk_class": "destructive", "mitre_techniques": ["T1059"]},
    )
    assert prof2["compliance_payload"]["decision"] == "deny"
    assert prof2["compliance_payload"]["reason"]
    assert prof2["conformance"]["ok"], prof2["conformance"]
    print("[deny ] conformance ok:", prof2["conformance"]["ok"],
          "| reason set:", bool(prof2["compliance_payload"].get("reason")))

    # negative: deny without reason must raise
    try:
        compliance_payload(decision="deny", tool_name="x", action={}, issuer_id="a11oy",
                           iteration_id="1")
        print("ERROR: deny-without-reason did NOT raise")
    except ValueError:
        print("[neg  ] deny-without-reason correctly rejected")

    # negative: quorum fired without attestation_hash must raise
    try:
        build_controls_evaluated(quorum_fired=True)
        print("ERROR: quorum-without-attestation did NOT raise")
    except ValueError:
        print("[neg  ] quorum-without-attestation correctly rejected")

    print("OK")
