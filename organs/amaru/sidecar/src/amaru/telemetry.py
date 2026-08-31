"""
telemetry — structured JSON logging + optional OpenTelemetry spans for Amaru.

Two concerns live here so the rest of the runtime stays clean:

1. Structured logging. A single ``logging`` formatter emits one JSON object
   per line (timestamp, level, logger, message, plus any ``extra`` fields).
   This is the Python-stdlib equivalent of pino — no extra dependency, parses
   cleanly in any log pipeline. Configured once via :func:`configure_logging`.

2. Tracing. :func:`span` is a context manager that emits an OpenTelemetry span
   when ``opentelemetry-api`` is installed AND ``AMARU_OTEL_ENABLED`` is truthy,
   and otherwise degrades to a no-op (still logging start/finish at debug).
   This keeps OpenTelemetry strictly optional: the service runs with zero otel
   packages installed, and lights up spans the moment a collector is wired in.

Environment variables (see .env.example):
  AMARU_LOG_LEVEL     — root log level (default INFO)
  AMARU_LOG_FORMAT    — "json" (default) or "text"
  AMARU_OTEL_ENABLED  — "1"/"true" to emit OpenTelemetry spans (default off)
  AMARU_SERVICE_NAME  — service.name resource attribute (default "amaru")
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import time
from typing import Any, Iterator

_TRUTHY = {"1", "true", "yes", "on"}


def _env_truthy(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in _TRUTHY


class JsonLogFormatter(logging.Formatter):
    """Render each log record as a single-line JSON object.

    Standard ``LogRecord`` attributes are dropped; anything passed via the
    ``extra=`` kwarg (i.e. attributes not present on a vanilla record) is
    merged into the emitted object so callers can attach structured context.
    """

    _RESERVED = set(
        logging.makeLogRecord({}).__dict__.keys()
    ) | {"message", "asctime"}

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)
            ),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in self._RESERVED and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, separators=(",", ":"))


_CONFIGURED = False


def configure_logging() -> None:
    """Install the structured handler on the root logger exactly once.

    Idempotent: safe to call from module import and from ``main()``.
    """
    global _CONFIGURED
    if _CONFIGURED:
        return

    level_name = os.environ.get("AMARU_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    fmt = os.environ.get("AMARU_LOG_FORMAT", "json").strip().lower()

    handler = logging.StreamHandler()
    if fmt == "text":
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        )
    else:
        handler.setFormatter(JsonLogFormatter())

    root = logging.getLogger()
    # Replace any pre-existing handlers so we don't double-emit.
    root.handlers = [handler]
    root.setLevel(level)
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    configure_logging()
    return logging.getLogger(name)


# --- Tracing -----------------------------------------------------------------

_OTEL_ENABLED = _env_truthy("AMARU_OTEL_ENABLED", False)
_SERVICE_NAME = os.environ.get("AMARU_SERVICE_NAME", "amaru")
_tracer: Any = None
_provider: Any = None
_otel_init_log = logging.getLogger("amaru.otel")


def _init_otel() -> Any:
    """Stand up a real TracerProvider with an OTLP span exporter.

    Returns a tracer, or ``None`` if OpenTelemetry isn't installed (the
    runtime then runs with no-op spans). The OTLP endpoint is taken from the
    standard ``OTEL_EXPORTER_OTLP_ENDPOINT`` env var, honored natively by the
    exporter; ``AMARU_SERVICE_NAME`` sets the ``service.name`` resource.
    """
    global _provider
    try:  # pragma: no cover - exercised only when otel is installed
        from opentelemetry import trace as _ot_trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        provider = TracerProvider(
            resource=Resource.create({"service.name": _SERVICE_NAME})
        )
        # OTLP exporter is best-effort: if the exporter package is missing we
        # still register the provider so spans are produced (and can be picked
        # up by any other configured processor / console exporter).
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter,
            )

            provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
        except Exception as exc:  # noqa: BLE001
            _otel_init_log.warning(
                "otel.exporter_unavailable", extra={"err": str(exc)}
            )
        _ot_trace.set_tracer_provider(provider)
        _provider = provider
        return _ot_trace.get_tracer(_SERVICE_NAME)
    except Exception as exc:  # noqa: BLE001 — otel is strictly optional
        _otel_init_log.info("otel.unavailable", extra={"err": str(exc)})
        return None


if _OTEL_ENABLED:
    _tracer = _init_otel()


def otel_active() -> bool:
    """True when spans will be emitted to a real OpenTelemetry tracer."""
    return _tracer is not None


def instrument_fastapi(app: Any) -> bool:
    """Auto-instrument a FastAPI app for request-level spans.

    No-op (returns False) when tracing is disabled or the FastAPI
    instrumentation package isn't installed. When active, every HTTP request
    gets a server span in addition to the explicit operation spans we emit on
    /scheduler/tick and /receipts.
    """
    if not _OTEL_ENABLED or _tracer is None:
        return False
    try:  # pragma: no cover - needs otel + instrumentation installed
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app)
        _otel_init_log.info("otel.fastapi_instrumented", extra={"service": _SERVICE_NAME})
        return True
    except Exception as exc:  # noqa: BLE001
        _otel_init_log.warning("otel.fastapi_instrument_failed", extra={"err": str(exc)})
        return False


_span_log = logging.getLogger("amaru.span")


@contextlib.contextmanager
def span(name: str, **attributes: Any) -> Iterator[None]:
    """Emit an OpenTelemetry span for ``name`` if tracing is active.

    Always logs span start/finish (with duration_ms) at debug level so the
    operation is observable even without a collector. Attributes are attached
    to the otel span when active and always included in the structured log.
    """
    configure_logging()
    start = time.perf_counter()
    if _tracer is not None:  # pragma: no cover - needs otel installed
        with _tracer.start_as_current_span(name) as otel_span:
            for key, value in attributes.items():
                try:
                    otel_span.set_attribute(key, value)
                except Exception:  # noqa: BLE001
                    pass
            try:
                yield
            finally:
                dur_ms = round((time.perf_counter() - start) * 1000, 3)
                _span_log.debug(
                    "span.finish", extra={"span": name, "duration_ms": dur_ms, **attributes}
                )
    else:
        try:
            yield
        finally:
            dur_ms = round((time.perf_counter() - start) * 1000, 3)
            _span_log.debug(
                "span.finish", extra={"span": name, "duration_ms": dur_ms, **attributes}
            )
