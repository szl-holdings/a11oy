"""Test-collection support for isolated file-module imports.

Only the universal frontend controller test uses importlib's low-level execution
path. Register that exact module name before execution so dataclass annotation
resolution sees the real module namespace. Normal repository imports are unchanged.
"""
from __future__ import annotations

import importlib.util
import sys

_ORIGINAL_MODULE_FROM_SPEC = importlib.util.module_from_spec


def _registered_module_from_spec(spec):
    module = _ORIGINAL_MODULE_FROM_SPEC(spec)
    if getattr(spec, "name", None) == "hf_universal_frontend_control":
        sys.modules[spec.name] = module
    return module


importlib.util.module_from_spec = _registered_module_from_spec
