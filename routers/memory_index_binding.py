# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
"""Immutable adapter-to-generation binding for the Memory Covenant worker."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Protocol

from routers.memory_index_worker import (
    IndexAdapter,
    IndexEvent,
    WorkerConfig,
    WorkerContractError,
    run_once,
)

IDENTITY_SCHEMA = "szl.memory-index-generation/v1"
METRICS = {"cosine", "euclidean", "dot"}
NORMALIZATIONS = {"none", "l2", "provider-defined"}


class BoundIndexAdapter(IndexAdapter, Protocol):
    def identity(self) -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class AdapterIdentity:
    provider: str
    model: str
    revision: str
    dimension: int
    metric: str
    normalization: str

    @classmethod
    def parse(cls, value: Mapping[str, Any]) -> "AdapterIdentity":
        if not isinstance(value, Mapping):
            raise WorkerContractError("adapter identity must be one object")
        expected = {"provider", "model", "revision", "dimension", "metric", "normalization"}
        if set(value) != expected:
            raise WorkerContractError("adapter identity fields do not match the closed contract")
        for field in ("provider", "model", "revision"):
            item = value[field]
            if not isinstance(item, str) or not item or len(item) > 256:
                raise WorkerContractError(f"adapter identity {field} is invalid")
        dimension = value["dimension"]
        if isinstance(dimension, bool) or not isinstance(dimension, int) or not 1 <= dimension <= 65536:
            raise WorkerContractError("adapter identity dimension is invalid")
        metric = value["metric"]
        normalization = value["normalization"]
        if metric not in METRICS:
            raise WorkerContractError("adapter identity metric is invalid")
        if normalization not in NORMALIZATIONS:
            raise WorkerContractError("adapter identity normalization is invalid")
        return cls(
            provider=value["provider"],
            model=value["model"],
            revision=value["revision"],
            dimension=dimension,
            metric=metric,
            normalization=normalization,
        )

    def payload(self) -> dict[str, Any]:
        return {
            "schema": IDENTITY_SCHEMA,
            "provider": self.provider,
            "model": self.model,
            "revision": self.revision,
            "dimension": self.dimension,
            "metric": self.metric,
            "normalization": self.normalization,
        }

    def digest(self) -> str:
        body = json.dumps(
            self.payload(),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        return hashlib.sha256(body).hexdigest()


def generation_identity_digest(value: Mapping[str, Any]) -> str:
    """Canonical digest written into ``memory_index_generations.identity_digest``."""
    return AdapterIdentity.parse(value).digest()


def run_bound_once(
    connect_factory: Callable[[], Any],
    adapter: BoundIndexAdapter,
    config: WorkerConfig,
) -> dict[str, Any]:
    """Run one batch only when reviewed adapter identity matches the generation."""
    try:
        identity_value = adapter.identity()
    except Exception as exc:
        raise WorkerContractError("adapter identity could not be read") from exc
    identity = AdapterIdentity.parse(identity_value)
    digest = identity.digest()
    if digest != config.generation_identity_digest:
        raise WorkerContractError("adapter identity digest does not match worker generation")
    result = run_once(connect_factory, adapter, config)
    result["adapter_identity"] = {
        "schema": IDENTITY_SCHEMA,
        "provider": identity.provider,
        "model": identity.model,
        "revision": identity.revision,
        "dimension": identity.dimension,
        "metric": identity.metric,
        "normalization": identity.normalization,
        "identity_digest": digest,
    }
    result["binding"] = "EXACT_ADAPTER_TO_ACTIVE_GENERATION"
    return result
