"""a11oy.intoto_binding — production binding to the maintained
in-toto-attestation package (T-16).

Law: never hand-roll the envelope you intend to defend in diligence.
This module prefers the official bindings and falls back — explicitly and
visibly — to the local demo signer when the package is unavailable.
"""
from __future__ import annotations

import json
from typing import Any

BACKEND = "demo-local-signer"
_statement_pb2 = None
_Struct = None

try:
    import importlib.metadata
    from in_toto_attestation.v1 import statement_pb2 as _statement_pb2  # type: ignore
    from google.protobuf.struct_pb2 import Struct as _Struct  # type: ignore
    BACKEND = "in-toto-attestation/" + importlib.metadata.version("in-toto-attestation")
except Exception:  # noqa: BLE001
    BACKEND = "demo-local-signer"


def available() -> bool:
    return _statement_pb2 is not None and _Struct is not None


def backend() -> str:
    return BACKEND


def envelope_statement(predicate: dict, subject_name: str, subject_sha256: str) -> Any:
    """Build a real in-toto v1 Statement protobuf if bindings are present.

    Raises RuntimeError (honestly) when the package is absent — callers must
    then record the signing scheme as the demo fallback and never imply the
    official in-toto binding was used.
    """
    if not available():
        raise RuntimeError(
            "in-toto-attestation not installed; production binding unavailable. "
            "pip install in-toto-attestation. The demo signer records its scheme honestly."
        )
    st = _statement_pb2.Statement()
    subject = st.subject.add()
    subject.name = subject_name
    subject.digest["sha256"] = subject_sha256
    st.predicate_type = "https://szl.dev/GovernedAction/v1"
    s = _Struct()
    s.update(json.loads(json.dumps(predicate)))
    st.predicate.CopyFrom(s)
    return st
