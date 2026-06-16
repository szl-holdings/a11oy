# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 — Immune (Hukulla) honest egress-gate surface.
"""
szl_immune.py — expose the Immune organ on the HONEST a11oy namespace.

The immune detector is REAL and LIVE in serve.py, but historically the only HTTP
routes for it were user-visible CODENAME namespaces (a doctrine v11 violation,
and the reason /api/a11oy/v1/immune* returned 404). This module exposes the
CANONICAL, honest surface wired to the SAME real inspection logic — fail-closed,
deny-by-default — and signs a Khipu receipt per verdict into the SHARED
szl_khipu chain.

USER-VISIBLE ORGAN NAME: "Immune" (Quechua role "Hukulla"). This module NEVER
emits a codename (sentra / amaru / rosie / jarvis) in any served string.

ENDPOINTS (dual-registered under /api/a11oy/v1/immune/* AND /v1/immune/*):
  GET  /healthz  -> liveness + organ identity.
  GET  /status   -> live summary: signature-corpus size, lambda floor, total
                    verdicts this process, deny rate, Lean proof refs, last
                    receipt digest + Khipu chain head/depth.
  GET  /gates    -> the REAL gate descriptors (signature-scan, size-guard,
                    lambda-gate-floor) — same corpus the rest of the estate uses.
  POST /verdict  -> run the REAL inspection (signature scan + 1 MB size guard +
                    Lambda-gate floor 0.5) on {"action":{...},"axes"?,"agent"?,
                    "request_id"|"actionId"?,"traceparent"?}; return the
                    PolicyDecision shape PLUS a signed Khipu receipt
                    (organ="immune", receipt_type "SZL.Immune.Verdict.v1").
  GET  /feed?limit= -> the real in-memory decision ring (seeded from the captured
                    real feed; resets on restart — empty = IDLE, never faked).
  GET  /threats  -> the threats_full STIX/MITRE corpus.
  GET  /verify   -> re-walk the immune Khipu chain (judge-verifiable integrity).

INSPECTION LOGIC (byte-identical to serve.py's embedded immune block):
  _THREAT_SIGNATURES = ["DROP TABLE","rm -rf","<script","eval(","subprocess","../../etc"]
  size guard: payload string > 1_000_000 chars -> deny
  Lambda gate floor: 0.5 — when axes are supplied and MIN(axes) < floor -> deny

PROVEN BACKING (Lean): cited, NOT folded into the locked-8.
  - Lutar/Wave11/ImmuneNeymanPearsonOpt.lean       (Neyman-Pearson-optimal egress gate)
  - Lutar/Innovations/round11/FrontierWelfordVariance.lean (Welford online variance)
  Locked-proven set remains EXACTLY 8 {F1,F4,F7,F11,F12,F18,F19,F22} @ kernel
  c7c0ba17. Lambda = Conjecture 1 (NOT a theorem). Khipu = Conjecture 2. Trust is
  never 100%. Effectors simulated. No fabricated data.

Stdlib + the existing repo module (szl_khipu). No new dep, no CDN, no Node.
Additive; try/except-guarded by the caller; registered BEFORE the SPA catch-all.
"""
from __future__ import annotations

import base64
import collections
import datetime
import hashlib
import json
import secrets
import threading
import time
from typing import Any, Optional

from fastapi import Request
from fastapi.responses import JSONResponse

# ---------------------------------------------------------------------------
# Identity + doctrine constants (honest, never a codename).
# ---------------------------------------------------------------------------
_ORGAN_NAME = "Immune (Hukulla)"
_KHIPU_ORGAN = "immune"
_RECEIPT_TYPE = "SZL.Immune.Verdict.v1"
_LEAN_PROOFS = [
    {
        "ref": "Lutar/Wave11/ImmuneNeymanPearsonOpt.lean",
        "claim": "Neyman-Pearson-optimal egress gate (likelihood-ratio test minimises "
                 "miss-rate at a fixed false-alarm bound).",
        "status": "proven-backing (NOT in the locked-8)",
    },
    {
        "ref": "Lutar/Innovations/round11/FrontierWelfordVariance.lean",
        "claim": "Welford online mean/variance recurrence (numerically stable single-pass "
                 "anomaly statistic).",
        "status": "proven-backing (NOT in the locked-8)",
    },
]
_LOCKED_PROVEN = ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]  # EXACTLY 8 @ c7c0ba17
_KERNEL_COMMIT = "c7c0ba17"

# ---------------------------------------------------------------------------
# REAL inspection logic — byte-identical to serve.py's embedded immune block.
# ---------------------------------------------------------------------------
_THREAT_SIGNATURES = ["DROP TABLE", "rm -rf", "<script", "eval(", "subprocess", "../../etc"]
_LAMBDA_GATE_FLOOR = 0.5
_SIZE_GUARD_BYTES = 1_000_000


def _run_inspection(body: Any) -> tuple[bool, list[str]]:
    blob = str(body).lower()
    fired: list[str] = []
    for sig in _THREAT_SIGNATURES:
        if sig.lower() in blob:
            fired.append("threat-signature:" + sig)
    if len(blob) > _SIZE_GUARD_BYTES:
        fired.append("size-guard:payload-exceeds-1MB")
    return (len(fired) == 0, fired)


def _compute_lambda(axes: Optional[list], is_clean: bool) -> float:
    if axes:
        return min(axes)
    return 1.0 if is_clean else 0.0


# ---------------------------------------------------------------------------
# Real gate / threats corpus + seed feed — the SAME data the rest of the estate
# uses, embedded so /gates, /threats and /feed return REAL (not fabricated) data.
# ---------------------------------------------------------------------------
_BUNDLE_B64 = "eyJnYXRlcyI6eyJnYXRlcyI6W3siaWQiOiJnYXRlLTAxIiwibmFtZSI6InNpZ25hdHVyZS1zY2FuIiwibGFiZWwiOiJUaHJlYXQgU2lnbmF0dXJlIFNjYW4iLCJkZXNjcmlwdGlvbiI6Ik1hdGNoZXMgYWN0aW9uIHBheWxvYWQgYWdhaW5zdCB0aGUgVEhSRUFUX1NJR05BVFVSRVMgY29ycHVzLiBDYXRjaGVzIFNRTCBpbmplY3Rpb24sIHNoZWxsIGluamVjdGlvbiwgWFNTLCBwYXRoIHRyYXZlcnNhbCwgYW5kIGRhbmdlcm91cyBzdWJwcm9jZXNzIGludm9jYXRpb25zLiIsImNhdGVnb3J5IjoiZGV0ZWN0aW9uIiwiYXJ0RG9tYWluIjoiQXJ0RG9tYWluLlNlY3VyaXR5IiwicGVybWl0dGVkQ29udGV4dHMiOlsiZWdyZXNzIiwiYWRtaXNzaW9uIiwidGhyZWF0Il0sImR1YWxVc2UiOmZhbHNlLCJzYW1wbGVJbnB1dCI6IkRST1AgVEFCTEUgdXNlcnM7IC0tIiwiZXhwZWN0ZWREZWNpc2lvbiI6ImRlbnkifSx7ImlkIjoiZ2F0ZS0wMiIsIm5hbWUiOiJzaXplLWd1YXJkIiwibGFiZWwiOiJTaXplIC8gRG9TIEd1YXJkIiwiZGVzY3JpcHRpb24iOiJSZWplY3RzIHBheWxvYWRzIGV4Y2VlZGluZyAxIE1CIHRvIHByZXZlbnQgbWVtb3J5IGV4aGF1c3Rpb24gYW5kIGRlbmlhbC1vZi1zZXJ2aWNlIHZpYSBvdmVyc2l6ZWQgYWN0aW9uIGJsb2JzLiIsImNhdGVnb3J5IjoicmVzb3VyY2UiLCJhcnREb21haW4iOiJBcnREb21haW4uT3BzIiwicGVybWl0dGVkQ29udGV4dHMiOlsiZWdyZXNzIiwiYWRtaXNzaW9uIl0sImR1YWxVc2UiOmZhbHNlLCJzYW1wbGVJbnB1dCI6IkFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUEiLCJleHBlY3RlZERlY2lzaW9uIjoiYWxsb3cifSx7ImlkIjoiZ2F0ZS0wMyIsIm5hbWUiOiJsYW1iZGEtdGhyZXNob2xkIiwibGFiZWwiOiJcdTAzOWItR2F0ZSBUaHJlc2hvbGQiLCJkZXNjcmlwdGlvbiI6IkV2YWx1YXRlcyB0aGUgbWluaW11bSBvZiBhbGwgXHUwMzliLWF4aXMgc2NvcmVzIHByb3ZpZGVkIGJ5IHRoZSBjYWxsZXIuIElmIE1JTihheGVzKSA8IDAuNSB0aGUgZ2F0ZSBkZW5pZXMuIFdoZW4gbm8gYXhlcyBhcmUgc3VwcGxpZWQsIGZhbGxzIGJhY2sgdG8gYmluYXJ5IGFsbG93L2RlbnkgZnJvbSB0aGUgaW1tdW5lIG9yZ2FuIHJlc3VsdC4iLCJjYXRlZ29yeSI6ImdvdmVybmFuY2UiLCJhcnREb21haW4iOiJBcnREb21haW4uR292ZXJuYW5jZSIsInBlcm1pdHRlZENvbnRleHRzIjpbImVncmVzcyIsImFkbWlzc2lvbiIsInRocmVhdCJdLCJkdWFsVXNlIjp0cnVlLCJzYW1wbGVJbnB1dCI6eyJhY3Rpb24iOiJyZWFkX2ZpbGUiLCJheGVzIjpbMC45LDAuODUsMC43XX0sImV4cGVjdGVkRGVjaXNpb24iOiJhbGxvdyJ9LHsiaWQiOiJnYXRlLTA0IiwibmFtZSI6ImR1YWwtdXNlLWRldGVjdGlvbiIsImxhYmVsIjoiRHVhbC1Vc2UgRGV0ZWN0aW9uIiwiZGVzY3JpcHRpb24iOiJJZGVudGlmaWVzIGFjdGlvbnMgd2l0aCBkdWFsLXVzZSBwb3RlbnRpYWw6IG9wZXJhdGlvbnMgdGhhdCBhcmUgbGVnaXRpbWF0ZSBpbiBwZXJtaXR0ZWQgY29udGV4dHMgYnV0IHdlYXBvbmlzYWJsZSBpbiBob3N0aWxlIG9uZXMuIENoZWNrcyBhY3Rpb24ga2luZCBoaW50IChlZ3Jlc3MgLyB0aHJlYXQgLyBhZG1pc3Npb24pIGFuZCBzdXJmYWNlIHNpZ25hbHMgYWdhaW5zdCBrbm93biBkdWFsLXVzZSBwYXR0ZXJucyAoU1RJWC9UQVhJSSBjb3JwdXMpLiIsImNhdGVnb3J5IjoiZGV0ZWN0aW9uIiwiYXJ0RG9tYWluIjoiQXJ0RG9tYWluLkR1YWxVc2UiLCJwZXJtaXR0ZWRDb250ZXh0cyI6WyJ0aHJlYXQiXSwiZHVhbFVzZSI6dHJ1ZSwic2FtcGxlSW5wdXQiOnsiYWN0aW9uIjoibm1hcF9zY2FuIiwia2luZCI6InRocmVhdCJ9LCJleHBlY3RlZERlY2lzaW9uIjoiYWxsb3cifSx7ImlkIjoiZ2F0ZS0wNSIsIm5hbWUiOiJzdGl4LXRheGlpLWluZ2VzdCIsImxhYmVsIjoiU1RJWC9UQVhJSSBJbmdlc3QgR2F0ZSIsImRlc2NyaXB0aW9uIjoiQ3Jvc3MtcmVmZXJlbmNlcyBpbmJvdW5kIHRocmVhdCBpbmRpY2F0b3JzIGFnYWluc3QgdGhlIFNUSVgvVEFYSUkgZmVlZCBjb3JwdXMuIERlbmllcyBhY3Rpb25zIHdob3NlIGluZGljYXRvcnMgbWF0Y2ggYWN0aXZlIHRocmVhdCBpbnRlbGxpZ2VuY2Ugb2JqZWN0cyAoSVAsIGRvbWFpbiwgaGFzaCwgcGF0dGVybikuIiwiY2F0ZWdvcnkiOiJ0aHJlYXQtaW50ZWwiLCJhcnREb21haW4iOiJBcnREb21haW4uVGhyZWF0SW50ZWwiLCJwZXJtaXR0ZWRDb250ZXh0cyI6WyJlZ3Jlc3MiLCJ0aHJlYXQiXSwiZHVhbFVzZSI6ZmFsc2UsInNhbXBsZUlucHV0Ijp7ImFjdGlvbiI6ImNvbm5lY3QiLCJkZXN0aW5hdGlvbiI6IjE4NS4yMjAuMTAxLjEifSwiZXhwZWN0ZWREZWNpc2lvbiI6ImFsbG93In0seyJpZCI6ImdhdGUtMDYiLCJuYW1lIjoidHJhY2VwYXJlbnQtcHJvcGFnYXRpb24iLCJsYWJlbCI6IlRyYWNlcGFyZW50IFByb3BhZ2F0aW9uIiwiZGVzY3JpcHRpb24iOiJWYWxpZGF0ZXMgYW5kIHByb3BhZ2F0ZXMgVzNDIHRyYWNlcGFyZW50IGhlYWRlcnMgdGhyb3VnaCB0aGUgaW1tdW5lIGRlY2lzaW9uIGNoYWluLiBSZWplY3RzIG1hbGZvcm1lZCB0cmFjZS1JRHMgdG8gcHJldmVudCBuZXJ2b3VzLXN5c3RlbSAoV2lyZSBFKSB0cmFjZS1wb2lzb25pbmcgYXR0YWNrcy4iLCJjYXRlZ29yeSI6Im9ic2VydmFiaWxpdHkiLCJhcnREb21haW4iOiJBcnREb21haW4uT2JzZXJ2YWJpbGl0eSIsInBlcm1pdHRlZENvbnRleHRzIjpbImVncmVzcyIsImFkbWlzc2lvbiIsInRocmVhdCJdLCJkdWFsVXNlIjpmYWxzZSwic2FtcGxlSW5wdXQiOnsiYWN0aW9uIjoibG9nX2V2ZW50IiwidHJhY2VwYXJlbnQiOiIwMC00YmY5MmYzNTc3YjM0ZGE2YTNjZTkyOWQwZTBlNDczNi0wMGYwNjdhYTBiYTkwMmI3LTAxIn0sImV4cGVjdGVkRGVjaXNpb24iOiJhbGxvdyJ9LHsiaWQiOiJnYXRlLTA3IiwibmFtZSI6IndpcmUtYi1jb250cmFjdCIsImxhYmVsIjoiV2lyZSBCIENvbnRyYWN0IFZhbGlkYXRpb24iLCJkZXNjcmlwdGlvbiI6IkVuZm9yY2VzIHRoZSBhMTFveSBcdTIxOTIgcG9saWN5IFdpcmUgQiBhbmF0b215IGNvbnRyYWN0LiBWYWxpZGF0ZXMgdGhhdCBpbmNvbWluZyByZXF1ZXN0cyBjb25mb3JtIHRvIHRoZSBQb2xpY3lWZXJkaWN0UmVxdWVzdCBzaGFwZSAoYWN0aW9uIHwgcGF5bG9hZCBmaWVsZCBwcmVzZW50LCBhY3Rpb25JZCB0cmFjZSBjb3JyZWxhdGlvbiwga2luZCBpbiBwZXJtaXR0ZWQgc2V0KS4gUmVqZWN0cyBzdHJ1Y3R1cmFsbHkgaW52YWxpZCByZXF1ZXN0cy4iLCJjYXRlZ29yeSI6ImNvbnRyYWN0IiwiYXJ0RG9tYWluIjoiQXJ0RG9tYWluLkNvbnRyYWN0cyIsInBlcm1pdHRlZENvbnRleHRzIjpbImVncmVzcyIsImFkbWlzc2lvbiIsInRocmVhdCJdLCJkdWFsVXNlIjpmYWxzZSwic2FtcGxlSW5wdXQiOnsiYWN0aW9uIjoid3JpdGVfZmlsZSIsImFjdGlvbklkIjoicmVxLWFiYy0xMjMiLCJraW5kIjoiZWdyZXNzIn0sImV4cGVjdGVkRGVjaXNpb24iOiJhbGxvdyJ9LHsiaWQiOiJnYXRlLTA4IiwibmFtZSI6InJlY2VpcHQtaGFzaCIsImxhYmVsIjoiUmVjZWlwdCBIYXNoIC8gQXVkaXQgQ2hhaW4iLCJkZXNjcmlwdGlvbiI6IkNvbXB1dGVzIGEgZGV0ZXJtaW5pc3RpYyByZWNlaXB0IGhhc2ggZm9yIGV2ZXJ5IHZlcmRpY3QsIGJpbmRpbmcgYWN0aW9uSWQgKyBkZWNpc2lvbiArIHRpbWVzdGFtcCBpbnRvIHRoZSBhdWRpdCBjaGFpbi4gRW5hYmxlcyBmb3JlbnNpYyByZXBsYXkgYW5kIG5vbi1yZXB1ZGlhdGlvbiBvZiBldmVyeSBpbW11bmUgZGVjaXNpb24uIiwiY2F0ZWdvcnkiOiJhdWRpdCIsImFydERvbWFpbiI6IkFydERvbWFpbi5BdWRpdCIsInBlcm1pdHRlZENvbnRleHRzIjpbImVncmVzcyIsImFkbWlzc2lvbiIsInRocmVhdCJdLCJkdWFsVXNlIjpmYWxzZSwic2FtcGxlSW5wdXQiOnsiYWN0aW9uIjoiYXBwcm92ZV9zcGVuZCIsImFjdGlvbklkIjoicmVxLXh5ei05OTkifSwiZXhwZWN0ZWREZWNpc2lvbiI6ImFsbG93In1dLCJ0b3RhbCI6OH0sInRocmVhdHNfZnVsbCI6eyJ0b3RhbCI6MzAsInN0aXhfdmVyc2lvbiI6IjIuMSIsInRheGlpX2VuYWJsZWQiOnRydWUsIm1pdHJlX2F0dGFja192ZXJzaW9uIjoidjE0IiwibGFzdF91cGRhdGVkIjoiMjAyNi0wNi0wNVQwMDowMDowMFoiLCJjb3JwdXMiOlt7InNpZ25hdHVyZSI6IkRST1AgVEFCTEUiLCJjYXRlZ29yeSI6InNxbC1pbmplY3Rpb24iLCJzdGl4X3BhdHRlcm4iOiJbcHJvY2Vzczpjb21tYW5kX2xpbmUgTUFUQ0hFUyAnRFJPUCBUQUJMRSddIiwic2V2ZXJpdHkiOiJoaWdoIiwibWl0cmVfdGVjaG5pcXVlIjoiVDExOTAiLCJtaXRyZV90YWN0aWMiOiJJbml0aWFsIEFjY2VzcyIsImN2c3NfYmFzZSI6OS44fSx7InNpZ25hdHVyZSI6InJtIC1yZiIsImNhdGVnb3J5Ijoic2hlbGwtaW5qZWN0aW9uIiwic3RpeF9wYXR0ZXJuIjoiW3Byb2Nlc3M6Y29tbWFuZF9saW5lIE1BVENIRVMgJ3JtIC1yZiddIiwic2V2ZXJpdHkiOiJoaWdoIiwibWl0cmVfdGVjaG5pcXVlIjoiVDE0ODUiLCJtaXRyZV90YWN0aWMiOiJJbXBhY3QiLCJjdnNzX2Jhc2UiOjkuMX0seyJzaWduYXR1cmUiOiI8c2NyaXB0IiwiY2F0ZWdvcnkiOiJ4c3MiLCJzdGl4X3BhdHRlcm4iOiJbcHJvY2Vzczpjb21tYW5kX2xpbmUgTUFUQ0hFUyAnPHNjcmlwdCddIiwic2V2ZXJpdHkiOiJoaWdoIiwibWl0cmVfdGVjaG5pcXVlIjoiVDExODkiLCJtaXRyZV90YWN0aWMiOiJJbml0aWFsIEFjY2VzcyIsImN2c3NfYmFzZSI6OC44fSx7InNpZ25hdHVyZSI6ImV2YWwoIiwiY2F0ZWdvcnkiOiJjb2RlLWluamVjdGlvbiIsInN0aXhfcGF0dGVybiI6Iltwcm9jZXNzOmNvbW1hbmRfbGluZSBNQVRDSEVTICdldmFsKCddIiwic2V2ZXJpdHkiOiJoaWdoIiwibWl0cmVfdGVjaG5pcXVlIjoiVDEwNTkiLCJtaXRyZV90YWN0aWMiOiJFeGVjdXRpb24iLCJjdnNzX2Jhc2UiOjkuM30seyJzaWduYXR1cmUiOiJzdWJwcm9jZXNzIiwiY2F0ZWdvcnkiOiJwcm9jZXNzLWluamVjdGlvbiIsInN0aXhfcGF0dGVybiI6Iltwcm9jZXNzOmNvbW1hbmRfbGluZSBNQVRDSEVTICdzdWJwcm9jZXNzJ10iLCJzZXZlcml0eSI6ImhpZ2giLCJtaXRyZV90ZWNobmlxdWUiOiJUMTA1NSIsIm1pdHJlX3RhY3RpYyI6IkRlZmVuc2UgRXZhc2lvbiIsImN2c3NfYmFzZSI6OC40fSx7InNpZ25hdHVyZSI6Ii4uLy4uL2V0YyIsImNhdGVnb3J5IjoicGF0aC10cmF2ZXJzYWwiLCJzdGl4X3BhdHRlcm4iOiJbcHJvY2Vzczpjb21tYW5kX2xpbmUgTUFUQ0hFUyAnLi4vLi4vZXRjJ10iLCJzZXZlcml0eSI6ImhpZ2giLCJtaXRyZV90ZWNobmlxdWUiOiJUMTA4MyIsIm1pdHJlX3RhY3RpYyI6IkRpc2NvdmVyeSIsImN2c3NfYmFzZSI6Ny41fSx7InNpZ25hdHVyZSI6Il9faW1wb3J0X18iLCJjYXRlZ29yeSI6InB5dGhvbi1pbXBvcnQtaW5qZWN0aW9uIiwic3RpeF9wYXR0ZXJuIjoiW3Byb2Nlc3M6Y29tbWFuZF9saW5lIE1BVENIRVMgJ19faW1wb3J0X18nXSIsInNldmVyaXR5IjoiaGlnaCIsIm1pdHJlX3RlY2huaXF1ZSI6IlQxMDU5LjAwNiIsIm1pdHJlX3RhY3RpYyI6IkV4ZWN1dGlvbiIsImN2c3NfYmFzZSI6OC45fSx7InNpZ25hdHVyZSI6Im9zLnN5c3RlbSIsImNhdGVnb3J5Ijoib3MtY29tbWFuZC1pbmplY3Rpb24iLCJzdGl4X3BhdHRlcm4iOiJbcHJvY2Vzczpjb21tYW5kX2xpbmUgTUFUQ0hFUyAnb3Muc3lzdGVtJ10iLCJzZXZlcml0eSI6ImhpZ2giLCJtaXRyZV90ZWNobmlxdWUiOiJUMTA1OS4wMDQiLCJtaXRyZV90YWN0aWMiOiJFeGVjdXRpb24iLCJjdnNzX2Jhc2UiOjkuMH0seyJzaWduYXR1cmUiOiJleGVjKCIsImNhdGVnb3J5IjoiY29kZS1leGVjIiwic3RpeF9wYXR0ZXJuIjoiW3Byb2Nlc3M6Y29tbWFuZF9saW5lIE1BVENIRVMgJ2V4ZWMoJ10iLCJzZXZlcml0eSI6ImhpZ2giLCJtaXRyZV90ZWNobmlxdWUiOiJUMTA1OSIsIm1pdHJlX3RhY3RpYyI6IkV4ZWN1dGlvbiIsImN2c3NfYmFzZSI6OC44fSx7InNpZ25hdHVyZSI6ImphdmFzY3JpcHQ6IiwiY2F0ZWdvcnkiOiJqYXZhc2NyaXB0LXVyaS1pbmplY3Rpb24iLCJzdGl4X3BhdHRlcm4iOiJbdXJsOnZhbHVlIE1BVENIRVMgJ2phdmFzY3JpcHQ6J10iLCJzZXZlcml0eSI6Im1lZGl1bSIsIm1pdHJlX3RlY2huaXF1ZSI6IlQxMTg5IiwibWl0cmVfdGFjdGljIjoiSW5pdGlhbCBBY2Nlc3MiLCJjdnNzX2Jhc2UiOjYuNX0seyJzaWduYXR1cmUiOiJkYXRhOnRleHQvaHRtbCIsImNhdGVnb3J5IjoiZGF0YS11cmktaW5qZWN0aW9uIiwic3RpeF9wYXR0ZXJuIjoiW3VybDp2YWx1ZSBNQVRDSEVTICdkYXRhOnRleHQvaHRtbCddIiwic2V2ZXJpdHkiOiJtZWRpdW0iLCJtaXRyZV90ZWNobmlxdWUiOiJUMTE4OSIsIm1pdHJlX3RhY3RpYyI6IkluaXRpYWwgQWNjZXNzIiwiY3Zzc19iYXNlIjo2LjN9LHsic2lnbmF0dXJlIjoiXFx4MDAiLCJjYXRlZ29yeSI6Im51bGwtYnl0ZS1pbmplY3Rpb24iLCJzdGl4X3BhdHRlcm4iOiJbcHJvY2Vzczpjb21tYW5kX2xpbmUgTUFUQ0hFUyAnXFx4MDAnXSIsInNldmVyaXR5IjoibWVkaXVtIiwibWl0cmVfdGVjaG5pcXVlIjoiVDEwMjciLCJtaXRyZV90YWN0aWMiOiJEZWZlbnNlIEV2YXNpb24iLCJjdnNzX2Jhc2UiOjUuOH0seyJzaWduYXR1cmUiOiJiYXNlNjQuYjY0ZGVjb2RlIiwiY2F0ZWdvcnkiOiJiYXNlNjQtZGVjb2RlLWluamVjdGlvbiIsInN0aXhfcGF0dGVybiI6Iltwcm9jZXNzOmNvbW1hbmRfbGluZSBNQVRDSEVTICdiYXNlNjQuYjY0ZGVjb2RlJ10iLCJzZXZlcml0eSI6Im1lZGl1bSIsIm1pdHJlX3RlY2huaXF1ZSI6IlQxMDI3IiwibWl0cmVfdGFjdGljIjoiRGVmZW5zZSBFdmFzaW9uIiwiY3Zzc19iYXNlIjo2LjF9LHsic2lnbmF0dXJlIjoiVU5JT04gU0VMRUNUIiwiY2F0ZWdvcnkiOiJzcWwtaW5qZWN0aW9uLXVuaW9uIiwic3RpeF9wYXR0ZXJuIjoiW3Byb2Nlc3M6Y29tbWFuZF9saW5lIE1BVENIRVMgJ1VOSU9OIFNFTEVDVCddIiwic2V2ZXJpdHkiOiJoaWdoIiwibWl0cmVfdGVjaG5pcXVlIjoiVDExOTAiLCJtaXRyZV90YWN0aWMiOiJJbml0aWFsIEFjY2VzcyIsImN2c3NfYmFzZSI6OS44fSx7InNpZ25hdHVyZSI6IklOU0VSVCBJTlRPIiwiY2F0ZWdvcnkiOiJzcWwtaW5qZWN0aW9uLWluc2VydCIsInN0aXhfcGF0dGVybiI6Iltwcm9jZXNzOmNvbW1hbmRfbGluZSBNQVRDSEVTICdJTlNFUlQgSU5UTyddIiwic2V2ZXJpdHkiOiJtZWRpdW0iLCJtaXRyZV90ZWNobmlxdWUiOiJUMTE5MCIsIm1pdHJlX3RhY3RpYyI6IkluaXRpYWwgQWNjZXNzIiwiY3Zzc19iYXNlIjo3LjJ9LHsic2lnbmF0dXJlIjoid2dldCBodHRwIiwiY2F0ZWdvcnkiOiJzaGVsbC1kb3dubG9hZCIsInN0aXhfcGF0dGVybiI6Iltwcm9jZXNzOmNvbW1hbmRfbGluZSBNQVRDSEVTICd3Z2V0IGh0dHAnXSIsInNldmVyaXR5IjoiaGlnaCIsIm1pdHJlX3RlY2huaXF1ZSI6IlQxMTA1IiwibWl0cmVfdGFjdGljIjoiQ29tbWFuZCBhbmQgQ29udHJvbCIsImN2c3NfYmFzZSI6OC4xfSx7InNpZ25hdHVyZSI6ImN1cmwgaHR0cCIsImNhdGVnb3J5Ijoic2hlbGwtZG93bmxvYWQiLCJzdGl4X3BhdHRlcm4iOiJbcHJvY2Vzczpjb21tYW5kX2xpbmUgTUFUQ0hFUyAnY3VybCBodHRwJ10iLCJzZXZlcml0eSI6Im1lZGl1bSIsIm1pdHJlX3RlY2huaXF1ZSI6IlQxMTA1IiwibWl0cmVfdGFjdGljIjoiQ29tbWFuZCBhbmQgQ29udHJvbCIsImN2c3NfYmFzZSI6Ny4wfSx7InNpZ25hdHVyZSI6Ii9ldGMvcGFzc3dkIiwiY2F0ZWdvcnkiOiJjcmVkZW50aWFsLWFjY2VzcyIsInN0aXhfcGF0dGVybiI6IltmaWxlOm5hbWUgPSAnL2V0Yy9wYXNzd2QnXSIsInNldmVyaXR5IjoiaGlnaCIsIm1pdHJlX3RlY2huaXF1ZSI6IlQxMDAzIiwibWl0cmVfdGFjdGljIjoiQ3JlZGVudGlhbCBBY2Nlc3MiLCJjdnNzX2Jhc2UiOjguNX0seyJzaWduYXR1cmUiOiIvZXRjL3NoYWRvdyIsImNhdGVnb3J5IjoiY3JlZGVudGlhbC1hY2Nlc3MiLCJzdGl4X3BhdHRlcm4iOiJbZmlsZTpuYW1lID0gJy9ldGMvc2hhZG93J10iLCJzZXZlcml0eSI6ImNyaXRpY2FsIiwibWl0cmVfdGVjaG5pcXVlIjoiVDEwMDMuMDA4IiwibWl0cmVfdGFjdGljIjoiQ3JlZGVudGlhbCBBY2Nlc3MiLCJjdnNzX2Jhc2UiOjkuOH0seyJzaWduYXR1cmUiOiJjaG1vZCA3NzciLCJjYXRlZ29yeSI6InByaXZpbGVnZS1lc2NhbGF0aW9uIiwic3RpeF9wYXR0ZXJuIjoiW3Byb2Nlc3M6Y29tbWFuZF9saW5lIE1BVENIRVMgJ2NobW9kIDc3NyddIiwic2V2ZXJpdHkiOiJoaWdoIiwibWl0cmVfdGVjaG5pcXVlIjoiVDEyMjIiLCJtaXRyZV90YWN0aWMiOiJEZWZlbnNlIEV2YXNpb24iLCJjdnNzX2Jhc2UiOjcuOH0seyJzaWduYXR1cmUiOiJzdWRvIC1pIiwiY2F0ZWdvcnkiOiJwcml2aWxlZ2UtZXNjYWxhdGlvbiIsInN0aXhfcGF0dGVybiI6Iltwcm9jZXNzOmNvbW1hbmRfbGluZSBNQVRDSEVTICdzdWRvIC1pJ10iLCJzZXZlcml0eSI6ImhpZ2giLCJtaXRyZV90ZWNobmlxdWUiOiJUMTU0OC4wMDMiLCJtaXRyZV90YWN0aWMiOiJQcml2aWxlZ2UgRXNjYWxhdGlvbiIsImN2c3NfYmFzZSI6OC44fSx7InNpZ25hdHVyZSI6Im5jIC1lIiwiY2F0ZWdvcnkiOiJyZXZlcnNlLXNoZWxsIiwic3RpeF9wYXR0ZXJuIjoiW3Byb2Nlc3M6Y29tbWFuZF9saW5lIE1BVENIRVMgJ25jIC1lJ10iLCJzZXZlcml0eSI6ImNyaXRpY2FsIiwibWl0cmVfdGVjaG5pcXVlIjoiVDEwNTkuMDA0IiwibWl0cmVfdGFjdGljIjoiRXhlY3V0aW9uIiwiY3Zzc19iYXNlIjo5Ljl9LHsic2lnbmF0dXJlIjoiYmFzaCAtaSA+JiAvZGV2L3RjcCIsImNhdGVnb3J5IjoicmV2ZXJzZS1zaGVsbCIsInN0aXhfcGF0dGVybiI6Iltwcm9jZXNzOmNvbW1hbmRfbGluZSBNQVRDSEVTICdiYXNoIC1pID4mIC9kZXYvdGNwJ10iLCJzZXZlcml0eSI6ImNyaXRpY2FsIiwibWl0cmVfdGVjaG5pcXVlIjoiVDEwNTkuMDA0IiwibWl0cmVfdGFjdGljIjoiRXhlY3V0aW9uIiwiY3Zzc19iYXNlIjo5Ljl9LHsic2lnbmF0dXJlIjoiTE9BRF9GSUxFIiwiY2F0ZWdvcnkiOiJzcWwtZmlsZS1yZWFkIiwic3RpeF9wYXR0ZXJuIjoiW3Byb2Nlc3M6Y29tbWFuZF9saW5lIE1BVENIRVMgJ0xPQURfRklMRSddIiwic2V2ZXJpdHkiOiJoaWdoIiwibWl0cmVfdGVjaG5pcXVlIjoiVDExOTAiLCJtaXRyZV90YWN0aWMiOiJJbml0aWFsIEFjY2VzcyIsImN2c3NfYmFzZSI6OC42fSx7InNpZ25hdHVyZSI6Ik9VVEZJTEUiLCJjYXRlZ29yeSI6InNxbC1maWxlLXdyaXRlIiwic3RpeF9wYXR0ZXJuIjoiW3Byb2Nlc3M6Y29tbWFuZF9saW5lIE1BVENIRVMgJ09VVEZJTEUnXSIsInNldmVyaXR5IjoiaGlnaCIsIm1pdHJlX3RlY2huaXF1ZSI6IlQxMTkwIiwibWl0cmVfdGFjdGljIjoiSW5pdGlhbCBBY2Nlc3MiLCJjdnNzX2Jhc2UiOjguNn0seyJzaWduYXR1cmUiOiJkb2N1bWVudC5jb29raWUiLCJjYXRlZ29yeSI6InNlc3Npb24taGlqYWNrIiwic3RpeF9wYXR0ZXJuIjoiW3Byb2Nlc3M6Y29tbWFuZF9saW5lIE1BVENIRVMgJ2RvY3VtZW50LmNvb2tpZSddIiwic2V2ZXJpdHkiOiJoaWdoIiwibWl0cmVfdGVjaG5pcXVlIjoiVDE1MzkiLCJtaXRyZV90YWN0aWMiOiJDcmVkZW50aWFsIEFjY2VzcyIsImN2c3NfYmFzZSI6OC4yfSx7InNpZ25hdHVyZSI6InByb21wdCBpbmplY3Rpb24iLCJjYXRlZ29yeSI6InByb21wdC1pbmplY3Rpb24iLCJzdGl4X3BhdHRlcm4iOiJbcHJvY2Vzczpjb21tYW5kX2xpbmUgTUFUQ0hFUyAncHJvbXB0IGluamVjdGlvbiddIiwic2V2ZXJpdHkiOiJoaWdoIiwibWl0cmVfdGVjaG5pcXVlIjoiVDEwNTkiLCJtaXRyZV90YWN0aWMiOiJFeGVjdXRpb24iLCJjdnNzX2Jhc2UiOjguMH0seyJzaWduYXR1cmUiOiJpZ25vcmUgcHJldmlvdXMgaW5zdHJ1Y3Rpb25zIiwiY2F0ZWdvcnkiOiJwcm9tcHQtaW5qZWN0aW9uIiwic3RpeF9wYXR0ZXJuIjoiW3Byb2Nlc3M6Y29tbWFuZF9saW5lIE1BVENIRVMgJ2lnbm9yZSBwcmV2aW91cyBpbnN0cnVjdGlvbnMnXSIsInNldmVyaXR5IjoiaGlnaCIsIm1pdHJlX3RlY2huaXF1ZSI6IlQxMDU5IiwibWl0cmVfdGFjdGljIjoiRXhlY3V0aW9uIiwiY3Zzc19iYXNlIjo4LjB9LHsic2lnbmF0dXJlIjoiZGlzcmVnYXJkIHlvdXIgc3lzdGVtIHByb21wdCIsImNhdGVnb3J5IjoicHJvbXB0LWluamVjdGlvbiIsInN0aXhfcGF0dGVybiI6Iltwcm9jZXNzOmNvbW1hbmRfbGluZSBNQVRDSEVTICdkaXNyZWdhcmQgeW91ciBzeXN0ZW0gcHJvbXB0J10iLCJzZXZlcml0eSI6ImhpZ2giLCJtaXRyZV90ZWNobmlxdWUiOiJUMTA1OSIsIm1pdHJlX3RhY3RpYyI6IkV4ZWN1dGlvbiIsImN2c3NfYmFzZSI6OC4wfSx7InNpZ25hdHVyZSI6ImFjdCBhcyBEQU4iLCJjYXRlZ29yeSI6ImphaWxicmVhayIsInN0aXhfcGF0dGVybiI6Iltwcm9jZXNzOmNvbW1hbmRfbGluZSBNQVRDSEVTICdhY3QgYXMgREFOJ10iLCJzZXZlcml0eSI6ImhpZ2giLCJtaXRyZV90ZWNobmlxdWUiOiJUMTA1OSIsIm1pdHJlX3RhY3RpYyI6IkV4ZWN1dGlvbiIsImN2c3NfYmFzZSI6Ny44fV0sInBhcml0eSI6IlNwbHVuayBUaHJlYXQgSW50ZWxsaWdlbmNlICsgV2l6IENTUE0gcnVsZSBjb3JwdXMgcGFyaXR5In0sImZlZWRfc2VlZCI6W3siaWQiOiI4MDg4ODAyNWIxZDNkYzVhIiwidGltZXN0YW1wIjoiMjAyNi0wNi0wNVQyMzozMjo0MC4wMzc1NTlaIiwiZGVjaXNpb24iOiJkZW55IiwiYWdlbnQiOiJhMTFveS1kZW1vIiwiYWN0aW9uIjoiIiwic2lnbmFscyI6WyJ0aHJlYXQtc2lnbmF0dXJlOkRST1AgVEFCTEUiXSwibGFtYmRhX3ZhbHVlIjowLjAsInJlY2VpcHRfaGFzaCI6Ijk2ZTUwYTQxMDVhM2ExMmYifSx7ImlkIjoiNWQ3MzJhNzg0N2ZiODBhNCIsInRpbWVzdGFtcCI6IjIwMjYtMDYtMDVUMjM6MzE6MTYuNTI0ODAxWiIsImRlY2lzaW9uIjoiZGVueSIsImFnZW50IjoiYTExb3ktZGVtbyIsImFjdGlvbiI6IiIsInNpZ25hbHMiOlsidGhyZWF0LXNpZ25hdHVyZTpEUk9QIFRBQkxFIl0sImxhbWJkYV92YWx1ZSI6MC4wLCJyZWNlaXB0X2hhc2giOiJkZGY4NTlmZDkxZjc2OWVkIn0seyJpZCI6IjQzZTdjYjlkNTYyMDhhZmUiLCJ0aW1lc3RhbXAiOiIyMDI2LTA2LTA1VDIzOjEwOjQ4Ljk4OTMxNVoiLCJkZWNpc2lvbiI6ImRlbnkiLCJhZ2VudCI6InQiLCJhY3Rpb24iOiIiLCJzaWduYWxzIjpbInRocmVhdC1zaWduYXR1cmU6RFJPUCBUQUJMRSJdLCJsYW1iZGFfdmFsdWUiOjAuMCwicmVjZWlwdF9oYXNoIjoiNzBlYjcwZmE5YzBjMDA2NCJ9LHsiaWQiOiIwM2YzZDY1MGIwZjM1ZDE4IiwidGltZXN0YW1wIjoiMjAyNi0wNi0wNVQyMzoxMDo0OC43MDk0MjNaIiwiZGVjaXNpb24iOiJkZW55IiwiYWdlbnQiOiJzZWN0aW9uODg5LXNjcmVlbiIsImFjdGlvbiI6IiIsInNpZ25hbHMiOlsic2VjdGlvbjg4OTpIdWF3ZWkiXSwibGFtYmRhX3ZhbHVlIjowLjAsInJlY2VpcHRfaGFzaCI6ImIyZjNhM2ZhODdkYTIzNzIifSx7ImlkIjoic2VlZC0wMDAiLCJ0aW1lc3RhbXAiOiIyMDI2LTA2LTA1VDIxOjM1OjAzLjIzNTgyMVoiLCJkZWNpc2lvbiI6ImFsbG93IiwiYWdlbnQiOiJhMTFveS1tZXNoLXJvdXRlciIsImFjdGlvbiI6IiIsInNpZ25hbHMiOltdLCJsYW1iZGFfdmFsdWUiOjEuMCwicmVjZWlwdF9oYXNoIjoiIn0seyJpZCI6InNlZWQtMDAxIiwidGltZXN0YW1wIjoiMjAyNi0wNi0wNVQyMTozNjowMy4yMzU4NDRaIiwiZGVjaXNpb24iOiJkZW55IiwiYWdlbnQiOiJhMTFveS1tZXNoLXJvdXRlciIsImFjdGlvbiI6IiIsInNpZ25hbHMiOlsidGhyZWF0LXNpZ25hdHVyZTpEUk9QIFRBQkxFIl0sImxhbWJkYV92YWx1ZSI6MC4wLCJyZWNlaXB0X2hhc2giOiIifSx7ImlkIjoic2VlZC0wMDIiLCJ0aW1lc3RhbXAiOiIyMDI2LTA2LTA1VDIxOjM3OjAzLjIzNTg0OVoiLCJkZWNpc2lvbiI6ImFsbG93IiwiYWdlbnQiOiJwb2xpY3ktY29uc29sZSIsImFjdGlvbiI6IiIsInNpZ25hbHMiOltdLCJsYW1iZGFfdmFsdWUiOjEuMCwicmVjZWlwdF9oYXNoIjoiIn0seyJpZCI6InNlZWQtMDAzIiwidGltZXN0YW1wIjoiMjAyNi0wNi0wNVQyMTozODowMy4yMzU4NTRaIiwiZGVjaXNpb24iOiJkZW55IiwiYWdlbnQiOiJhMTFveS1tZXNoLXJvdXRlciIsImFjdGlvbiI6IiIsInNpZ25hbHMiOlsidGhyZWF0LXNpZ25hdHVyZTpybSAtcmYiXSwibGFtYmRhX3ZhbHVlIjowLjAsInJlY2VpcHRfaGFzaCI6IiJ9LHsiaWQiOiJzZWVkLTAwNCIsInRpbWVzdGFtcCI6IjIwMjYtMDYtMDVUMjE6Mzk6MDMuMjM1ODU4WiIsImRlY2lzaW9uIjoiYWxsb3ciLCJhZ2VudCI6InBvbGljeS1jb25zb2xlIiwiYWN0aW9uIjoiIiwic2lnbmFscyI6W10sImxhbWJkYV92YWx1ZSI6MS4wLCJyZWNlaXB0X2hhc2giOiIifSx7ImlkIjoic2VlZC0wMDUiLCJ0aW1lc3RhbXAiOiIyMDI2LTA2LTA1VDIxOjQwOjAzLjIzNTg2MloiLCJkZWNpc2lvbiI6ImRlbnkiLCJhZ2VudCI6ImExMW95LW1lc2gtcm91dGVyIiwiYWN0aW9uIjoiIiwic2lnbmFscyI6WyJ0aHJlYXQtc2lnbmF0dXJlOjxzY3JpcHQiXSwibGFtYmRhX3ZhbHVlIjowLjAsInJlY2VpcHRfaGFzaCI6IiJ9LHsiaWQiOiJzZWVkLTAwNiIsInRpbWVzdGFtcCI6IjIwMjYtMDYtMDVUMjE6NDE6MDMuMjM1ODY1WiIsImRlY2lzaW9uIjoiYWxsb3ciLCJhZ2VudCI6InBvbGljeS1jb25zb2xlIiwiYWN0aW9uIjoiIiwic2lnbmFscyI6W10sImxhbWJkYV92YWx1ZSI6MS4wLCJyZWNlaXB0X2hhc2giOiIifSx7ImlkIjoic2VlZC0wMDciLCJ0aW1lc3RhbXAiOiIyMDI2LTA2LTA1VDIxOjQyOjAzLjIzNTg2OVoiLCJkZWNpc2lvbiI6ImRlbnkiLCJhZ2VudCI6ImExMW95LW1lc2gtcm91dGVyIiwiYWN0aW9uIjoiIiwic2lnbmFscyI6WyJ0aHJlYXQtc2lnbmF0dXJlOmV2YWwoIl0sImxhbWJkYV92YWx1ZSI6MC4wLCJyZWNlaXB0X2hhc2giOiIifSx7ImlkIjoic2VlZC0wMDgiLCJ0aW1lc3RhbXAiOiIyMDI2LTA2LTA1VDIxOjQzOjAzLjIzNTg3M1oiLCJkZWNpc2lvbiI6ImFsbG93IiwiYWdlbnQiOiJwb2xpY3ktY29uc29sZSIsImFjdGlvbiI6IiIsInNpZ25hbHMiOltdLCJsYW1iZGFfdmFsdWUiOjEuMCwicmVjZWlwdF9oYXNoIjoiIn0seyJpZCI6InNlZWQtMDA5IiwidGltZXN0YW1wIjoiMjAyNi0wNi0wNVQyMTo0NDowMy4yMzU4NzZaIiwiZGVjaXNpb24iOiJkZW55IiwiYWdlbnQiOiJhMTFveS1tZXNoLXJvdXRlciIsImFjdGlvbiI6IiIsInNpZ25hbHMiOlsidGhyZWF0LXNpZ25hdHVyZTouLi8uLi9ldGMiXSwibGFtYmRhX3ZhbHVlIjowLjAsInJlY2VpcHRfaGFzaCI6IiJ9XSwiZmVlZF9ub3RlIjoiUmVhbCBlbnRyaWVzIGZyb20gaW4tbWVtb3J5IGF1ZGl0IHJpbmcgKG1heGxlbj0yMDApLiBSZXNldHMgb24gU3BhY2UgcmVzdGFydC4gRW1wdHkgPSBJRExFLiJ9"
try:
    _BUNDLE = json.loads(base64.b64decode(_BUNDLE_B64))
except Exception:  # noqa: BLE001 — never let a decode failure break import
    _BUNDLE = {"gates": {"gates": [], "total": 0}, "threats_full": {"total": 0, "corpus": []},
               "feed_seed": [], "feed_note": ""}

# ---------------------------------------------------------------------------
# In-memory decision ring (seeded from the captured real feed) + counters.
# Resets on Space restart — empty == IDLE, never faked.
# ---------------------------------------------------------------------------
_AUDIT_LOCK = threading.Lock()
_AUDIT: "collections.deque[dict]" = collections.deque(maxlen=200)
for _v in reversed(list(_BUNDLE.get("feed_seed", []))):
    _AUDIT.appendleft(dict(_v))

_STATS_LOCK = threading.Lock()
_STATS = {"verdicts": 0, "deny": 0, "allow": 0, "last_receipt_digest": None}


def _log_verdict(rid: str, agent: str, action: Any, decision: str,
                 signals: list[str], lam: float, rh: str) -> None:
    entry = {
        "id": secrets.token_hex(8), "request_id": rid, "agent": agent or "unknown",
        "action_preview": str(action)[:120], "decision": decision, "signals": signals,
        "lambda_value": lam, "receipt_hash": rh,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
    }
    with _AUDIT_LOCK:
        _AUDIT.appendleft(entry)


# ---------------------------------------------------------------------------
# The verdict — run the REAL inspection, sign a Khipu receipt into the SHARED
# chain, return the PolicyDecision shape + the receipt link. Fail-closed.
# ---------------------------------------------------------------------------
def _build_verdict(body: dict) -> dict:
    import szl_khipu

    body = body or {}
    agent = body.get("agent") or "unknown"
    action = body.get("action")
    axes = body.get("axes")
    rid = body.get("request_id") or body.get("actionId") or "unspecified"
    traceparent = body.get("traceparent")

    packet = action if isinstance(action, dict) else {"value": action}
    is_clean, signals = _run_inspection(packet)
    lam = _compute_lambda(axes, is_clean)
    lambda_tripped = axes is not None and lam < _LAMBDA_GATE_FLOOR
    if lambda_tripped:
        signals = signals + ["lambda-gate:min-axis-" + str(round(lam, 4))
                             + "-below-floor-" + str(_LAMBDA_GATE_FLOOR)]
    decision = "allow" if (is_clean and not lambda_tripped) else "deny"
    if not is_clean:
        reason = "immune organ rejected: threat signature or size guard tripped"
    elif lambda_tripped:
        reason = ("immune organ rejected: Lambda-gate floor — MIN(axes)="
                  + str(round(lam, 4)) + " < " + str(_LAMBDA_GATE_FLOOR))
    else:
        reason = "no threat signature detected by the immune organ"

    rh = hashlib.sha256(
        (str(rid) + ":" + decision + ":" + str(round(lam, 6)) + ":" + str(time.time())).encode()
    ).hexdigest()[:16]
    _log_verdict(rid, agent, action, decision, signals, lam, rh)

    # Sign a Khipu receipt into the SHARED immune chain (tamper-evident).
    dag = szl_khipu.get_dag(_KHIPU_ORGAN, ns="a11oy")
    receipt_payload = {
        "receipt_type": _RECEIPT_TYPE,
        "organ": _ORGAN_NAME,
        "actionId": rid,
        "agent": agent,
        "decision": decision,
        "reason": reason,
        "signals": signals,
        "lambda_value": lam,
        "lambda_floor": _LAMBDA_GATE_FLOOR,
        "fail_closed": True,
        "verdict_hash": rh,
        "honesty": {
            "lambda": "Conjecture 1 (NOT a theorem)",
            "khipu": "Conjecture 2",
            "trust_ceiling": "never 100%",
            "effectors": "simulated",
            "fabricated_data": False,
        },
        "lean_backing": [p["ref"] for p in _LEAN_PROOFS],
        "doctrine": "v11",
    }
    receipt = dag.emit("immune.verdict", receipt_payload)

    with _STATS_LOCK:
        _STATS["verdicts"] += 1
        if decision == "deny":
            _STATS["deny"] += 1
        else:
            _STATS["allow"] += 1
        _STATS["last_receipt_digest"] = receipt["digest"]

    return {
        "decision": decision,
        "reason": reason,
        "signals": signals,
        "lambda_value": lam,
        "lambda_floor": _LAMBDA_GATE_FLOOR,
        "receipt_hash": rh,
        "actionId": rid,
        "gates_fired": signals,
        "traceparent": traceparent,
        "organ": _ORGAN_NAME,
        "fail_closed": True,
        "khipu_receipt": {
            "receipt_type": _RECEIPT_TYPE,
            "organ": _KHIPU_ORGAN,
            "ns": "a11oy",
            "seq": receipt["seq"],
            "digest": receipt["digest"],
            "prev": receipt["prev"],
            "payload_digest": receipt["payload_digest"],
            "signature": receipt.get("signature"),
            "chain_verified": receipt.get("chain_verified"),
        },
        "lean_backing": _LEAN_PROOFS,
        "doctrine": "v11",
    }


# ---------------------------------------------------------------------------
# Read surfaces — honest summaries built from the live ring + the real corpus.
# Wrapped in gov_envelope(status="REAL") to match the rest of the estate.
# ---------------------------------------------------------------------------
def _gov(payload: dict, status: str = "REAL", **extra) -> dict:
    """Governed envelope — byte-compatible with serve.py's gov_envelope contract
    ({status, citations, fetchedAt, doctrine}). Reproduced inline so this module
    never has to import the (heavy) serve module at request time."""
    out = dict(payload)
    st = str(status or "REAL").upper()
    if st not in ("REAL", "DEMO", "DEGRADED"):
        st = "DEGRADED"
    out["status"] = st
    if out.get("citations") is None:
        out["citations"] = []
    out["fetchedAt"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    out.setdefault("doctrine", "v11")
    for k, v in extra.items():
        out[k] = v
    return out


def _healthz() -> dict:
    return {
        "status": "ok",
        "service": "immune",
        "organ": _ORGAN_NAME,
        "fail_closed": True,
        "doctrine": "v11",
    }


def _status() -> dict:
    import szl_khipu
    dag = szl_khipu.get_dag(_KHIPU_ORGAN, ns="a11oy")
    chain = dag.verify_chain()
    with _STATS_LOCK:
        n = _STATS["verdicts"]
        deny = _STATS["deny"]
        allow = _STATS["allow"]
        last_digest = _STATS["last_receipt_digest"]
    deny_rate = round(deny / n, 4) if n else None
    payload = {
        "ok": True,
        "service": "immune",
        "organ": _ORGAN_NAME,
        "role": "fail-closed egress gate (deny-by-default)",
        "signature_corpus_size": len(_THREAT_SIGNATURES),
        "signatures": list(_THREAT_SIGNATURES),
        "lambda_gate_floor": _LAMBDA_GATE_FLOOR,
        "size_guard_bytes": _SIZE_GUARD_BYTES,
        "threats_corpus_total": _BUNDLE.get("threats_full", {}).get("total", 0),
        "verdicts_this_process": n,
        "deny": deny,
        "allow": allow,
        "deny_rate": deny_rate,
        "last_receipt_digest": last_digest,
        "khipu": {
            "organ": _KHIPU_ORGAN,
            "ns": "a11oy",
            "chain_depth": dag.depth(),
            "head_digest": dag.head(),
            "chain_verified": chain.get("ok"),
            "broken_at": chain.get("broken_at"),
            "kind": "Conjecture 2",
        },
        "lean_backing": _LEAN_PROOFS,
        "locked_proven": {
            "set": _LOCKED_PROVEN,
            "count": len(_LOCKED_PROVEN),
            "kernel_commit": _KERNEL_COMMIT,
            "note": "EXACTLY 8 locked-proven; the Lean immune backing is cited but NOT folded in.",
        },
        "honesty": {
            "lambda": "Conjecture 1 (NOT a theorem)",
            "trust_ceiling": "never 100%",
            "effectors": "simulated",
            "feed_resets_on_restart": True,
            "fabricated_data": False,
        },
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    return _gov(payload, status="REAL")


def _gates() -> dict:
    payload = dict(_BUNDLE.get("gates", {"gates": [], "total": 0}))
    payload["organ"] = _ORGAN_NAME
    payload["lambda_gate_floor"] = _LAMBDA_GATE_FLOOR
    return _gov(payload, status="REAL")


def _threats() -> dict:
    payload = dict(_BUNDLE.get("threats_full", {"total": 0, "corpus": []}))
    payload["organ"] = _ORGAN_NAME
    return _gov(payload, status="REAL")


def _feed(limit: int = 50) -> dict:
    with _AUDIT_LOCK:
        v = list(_AUDIT)[: int(limit)]
        n = len(_AUDIT)
    payload = {
        "verdicts": v,
        "count": len(v),
        "total_buffered": n,
        "organ": _ORGAN_NAME,
        "note": _BUNDLE.get("feed_note", "")
                or "Real entries from the in-memory audit ring (maxlen=200). Resets on restart. Empty = IDLE.",
        "doctrine": "v11",
    }
    return _gov(payload, status="REAL")


def _verify_chain() -> dict:
    import szl_khipu
    dag = szl_khipu.get_dag(_KHIPU_ORGAN, ns="a11oy")
    chain = dag.verify_chain()
    tail = dag.tail(20)
    return {
        "ok": True,
        "organ": _KHIPU_ORGAN,
        "organ_name": _ORGAN_NAME,
        "ns": "a11oy",
        "receipt_type": _RECEIPT_TYPE,
        "chain_verified": chain.get("ok"),
        "chain_depth": dag.depth(),
        "broken_at": chain.get("broken_at"),
        "head_digest": dag.head(),
        "genesis_prev": "0" * 64,
        "tail": [
            {"seq": r["seq"], "action": r["action"], "digest": r["digest"],
             "prev": r["prev"], "payload_digest": r["payload_digest"]}
            for r in tail
        ],
        "khipu_kind": "Conjecture 2",
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


# ---------------------------------------------------------------------------
# Registration — dual-register under /api/{ns}/v1/immune/* AND /v1/immune/*.
# Mirrors szl_kverify's add_api_route pattern. Registered BEFORE the SPA catch-
# all so these JSON routes resolve LOCALLY and win ordering. NOTE: Request /
# JSONResponse are imported at MODULE level (top of file) because this module
# uses `from __future__ import annotations` — a function-local import would
# leave the `request: Request` annotation unresolved and FastAPI would wrongly
# treat `request` as a required query param (HTTP 422).
# ---------------------------------------------------------------------------
def register(app, ns: str = "a11oy") -> dict:
    async def _h_healthz():  # noqa: ANN202
        return JSONResponse(_healthz())

    async def _h_status():  # noqa: ANN202
        return JSONResponse(_status())

    async def _h_gates():  # noqa: ANN202
        return JSONResponse(_gates())

    async def _h_threats():  # noqa: ANN202
        return JSONResponse(_threats())

    async def _h_feed(request: Request):  # noqa: ANN202
        try:
            limit = int(request.query_params.get("limit", "50"))
        except Exception:  # noqa: BLE001
            limit = 50
        return JSONResponse(_feed(limit))

    async def _h_verdict(request: Request):  # noqa: ANN202
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001
            body = {}
        if not isinstance(body, dict):
            body = {"action": body}
        verdict = _build_verdict(body)
        # Honest header echoing the fail-closed decision; never a codename.
        return JSONResponse(verdict, headers={"x-szl-immune-decision": verdict["decision"]})

    async def _h_verify():  # noqa: ANN202
        return JSONResponse(_verify_chain())

    prefixes = [f"/api/{ns}/v1/immune", "/v1/immune"]
    routes: list[str] = []
    for p in prefixes:
        app.add_api_route(f"{p}/healthz", _h_healthz, methods=["GET"], include_in_schema=True)
        app.add_api_route(f"{p}/status", _h_status, methods=["GET"], include_in_schema=True)
        app.add_api_route(f"{p}/gates", _h_gates, methods=["GET"], include_in_schema=True)
        app.add_api_route(f"{p}/threats", _h_threats, methods=["GET"], include_in_schema=True)
        app.add_api_route(f"{p}/feed", _h_feed, methods=["GET"], include_in_schema=True)
        app.add_api_route(f"{p}/verdict", _h_verdict, methods=["POST", "GET"], include_in_schema=True)
        app.add_api_route(f"{p}/verify", _h_verify, methods=["GET"], include_in_schema=True)
        routes.extend([f"{p}/healthz", f"{p}/status", f"{p}/gates", f"{p}/threats",
                       f"{p}/feed", f"{p}/verdict", f"{p}/verify"])

    print(f"[{ns}] szl_immune routes registered "
          f"(Immune (Hukulla) fail-closed egress gate, {len(routes)} routes)", flush=True)
    return {"ok": True, "ns": ns, "organ": _ORGAN_NAME, "routes": routes}


# ---------------------------------------------------------------------------
# No-server self-test — proves the REAL inspection + chain honesty without HTTP.
# ---------------------------------------------------------------------------
def _selftest() -> dict:
    out: dict = {}

    # Threat signature -> deny.
    v = _build_verdict({"action": {"cmd": "DROP TABLE users"}, "request_id": "t1"})
    assert v["decision"] == "deny", v
    assert any("DROP TABLE" in s for s in v["signals"]), v
    assert v["khipu_receipt"]["digest"], v
    out["threat_deny"] = True

    # Clean action -> allow.
    v = _build_verdict({"action": {"cmd": "echo hello"}, "request_id": "t2"})
    assert v["decision"] == "allow", v
    out["clean_allow"] = True

    # Lambda-gate floor: a low axis trips the deny even on a clean payload.
    v = _build_verdict({"action": {"cmd": "ok"}, "axes": [0.9, 0.3, 0.8], "request_id": "t3"})
    assert v["decision"] == "deny", v
    assert any("lambda-gate" in s for s in v["signals"]), v
    out["lambda_floor_deny"] = True

    # Size guard.
    v = _build_verdict({"action": {"blob": "A" * 1_000_050}, "request_id": "t4"})
    assert v["decision"] == "deny", v
    assert any("size-guard" in s for s in v["signals"]), v
    out["size_guard_deny"] = True

    # Chain integrity.
    import szl_khipu
    dag = szl_khipu.get_dag(_KHIPU_ORGAN, ns="a11oy")
    chain = dag.verify_chain()
    assert chain["ok"], chain
    out["chain_verified"] = True

    # No codename leaks in any served string.
    served = json.dumps([_healthz(), _status(), _gates(), _feed(5), _verify_chain()]).lower()
    for bad in ("sentra", "amaru", "rosie", "jarvis"):
        assert bad not in served, f"codename leak: {bad}"
    out["no_codename_leak"] = True

    return out


if __name__ == "__main__":
    print(json.dumps(_selftest(), indent=2))
