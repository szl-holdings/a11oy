"""
szl_logging.py — Structured JSON logging for SZL Holdings flagships.
Doctrine v11 LOCKED 749/14/163 | SLSA L1 honest
Signed-off-by: Yachay <yachay@szlholdings.ai>
Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
"""
import logging
import json
import time
import sys
from datetime import datetime, timezone


class SZLJSONFormatter(logging.Formatter):
    """JSON log formatter with trace_id, level, timestamp for OpenTelemetry compatibility."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "doctrine": "v11",
            "trace_id": getattr(record, "trace_id", ""),
        }
        if record.exc_info:
            log_entry["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)


def configure_szl_logging(app_name: str = "szl", level: str = "INFO") -> logging.Logger:
    """Configure structured JSON logging for a SZL flagship app."""
    logger = logging.getLogger(app_name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(SZLJSONFormatter())
        logger.addHandler(handler)

    return logger


# Default logger for import convenience
szl_logger = configure_szl_logging("szl-flagship")
