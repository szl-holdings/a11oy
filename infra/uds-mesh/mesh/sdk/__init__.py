"""UDS-Mesh Python SDK — Λ-signed cross-organ OTEL span emission with BLS batch receipts."""
from .mesh import (  # noqa: F401
    LAMBDA_FLOOR_MESH,
    ORGANS,
    SPAN_NAMES,
    MeshEmitter,
    MeshSpan,
    TraceContext,
    verify_batch,
)

__version__ = "0.1.0"
