"""rosie.console.telemetry — structured JSON logging + optional OTel spans.

Two stdlib-only capabilities, no required runtime dependency:

1. :class:`JsonLogFormatter` / :func:`configure_logging` — one JSON object per
   log line (ts, level, logger, msg + any structured ``extra`` fields).
   Configurable via ROSIE_LOG_LEVEL and ROSIE_LOG_FORMAT (json|text).

2. :func:`span` — a context manager that emits a real OpenTelemetry span when
   the optional ``opentelemetry-api`` package is installed AND
   ROSIE_OTEL_ENABLED is truthy; otherwise it degrades to a no-op that still
   logs a debug line with the operation's duration. The service runs with zero
   otel packages installed and lights up tracing the moment a collector is
   wired in.

SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import time
from typing import Any, Iterator

SERVICE_NAME = "rosie"

# ---------------------------------------------------------------------------
# Structured JSON logging
# ---------------------------------------------------------------------------

# Standard LogRecord attributes we never want to duplicate into the JSON body;
# anything else passed via ``extra=`` is merged in as a structured field.
_RESERVED = set(logging.makeLogRecord({}).__dict__.keys()) | {"message", "asctime"}


class JsonLogFormatter(logging.Formatter):
    """Format a LogRecord as a single-line JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


_configured = False


def configure_logging(force: bool = False) -> logging.Logger:
    """Configure the ``rosie`` logger from the environment (idempotent).

    Reads:
        ROSIE_LOG_LEVEL  — DEBUG/INFO/WARNING/... (default INFO)
        ROSIE_LOG_FORMAT — "json" (default) or "text"

    Args:
        force: Reconfigure even if already configured (used by tests).

    Returns:
        The configured ``rosie`` logger.
    """
    global _configured
    logger = logging.getLogger(SERVICE_NAME)
    if _configured and not force:
        return logger

    level = os.environ.get("ROSIE_LOG_LEVEL", "INFO").upper()
    fmt = os.environ.get("ROSIE_LOG_FORMAT", "json").lower()

    handler = logging.StreamHandler()
    if fmt == "text":
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    else:
        handler.setFormatter(JsonLogFormatter())

    logger.handlers.clear()
    logger.addHandler(handler)
    logger.setLevel(getattr(logging, level, logging.INFO))
    logger.propagate = False
    _configured = True
    return logger


def get_logger() -> logging.Logger:
    """Return the configured ``rosie`` logger (configures on first call)."""
    return configure_logging()


# ---------------------------------------------------------------------------
# Optional OpenTelemetry spans (graceful degradation)
# ---------------------------------------------------------------------------


def _otel_enabled() -> bool:
    return os.environ.get("ROSIE_OTEL_ENABLED", "").strip().lower() in ("1", "true", "yes", "on")


def otel_active() -> bool:
    """True iff OTel is both enabled by env and importable."""
    if not _otel_enabled():
        return False
    try:
        import opentelemetry.trace  # noqa: F401
    except ImportError:
        return False
    return True


@contextlib.contextmanager
def span(name: str, **attributes: Any) -> Iterator[Any]:
    """Context manager wrapping a consequential operation in a span.

    When OTel is enabled and installed, emits a real span named
    ``rosie.span.<name>`` with the given attributes. Otherwise it is a no-op
    that still emits a debug log line with ``duration_ms`` on exit, so the
    operation is observable even with zero otel packages installed.

    Args:
        name:        Span name suffix (prefixed with ``rosie.span.``).
        attributes:  Span attributes / structured log fields.

    Yields:
        The active OTel span object, or None in the degraded path.
    """
    span_name = f"rosie.span.{name}"
    start = time.perf_counter()

    if otel_active():
        from opentelemetry import trace

        tracer = trace.get_tracer(SERVICE_NAME)
        with tracer.start_as_current_span(span_name) as otel_span:
            for key, value in attributes.items():
                try:
                    otel_span.set_attribute(key, value)
                except (TypeError, ValueError):
                    otel_span.set_attribute(key, str(value))
            yield otel_span
        return

    # Degraded no-op path: still time and log the operation.
    try:
        yield None
    finally:
        duration_ms = round((time.perf_counter() - start) * 1000, 3)
        get_logger().debug(
            "span", extra={"span": span_name, "duration_ms": duration_ms, **attributes}
        )
