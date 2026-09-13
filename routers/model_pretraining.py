# SPDX-License-Identifier: Apache-2.0
"""Read-only pre-training model view over the existing public estate manifest.

This is a projection, not another inventory writer or admission authority.
Metadata hints, declared source pointers and unperformed checks stay distinct.
No model, tokenizer, trainer, credential or remote service is loaded by a request.
"""
import hashlib
import json
import math
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response

ROOT = Path(__file__).resolve().parents[1]
SOURCE_MANIFEST = ROOT / "docs" / "huggingface-ecosystem-manifest.json"
MANIFEST = ROOT / "routers" / "data" / "model-pretraining-snapshot.json"
PAGE_ROOT = ROOT / "pages"
SCHEMA = "szl.model-pretraining-view/v1"
MAX_BYTES = 8 * 1024 * 1024
MAX_MODELS = 2000
REPO = re.compile(r"SZLHOLDINGS/[A-Za-z0-9][A-Za-z0-9._-]{0,159}\Z")
SHA = re.compile(r"[0-9a-f]{40}\Z")
AUTHORITY = {"training": False, "inference": False, "publication": False,
             "promotion": False, "deletion": False, "toolExecution": False}
CATEGORIES = {
    "ADAPTER_HINT": "Verify exact base and adapter; evaluate before retraining.",
    "CHECKPOINT_HINT": "Verify actual weight artifacts and task evaluation.",
    "GGUF_HINT": "Verify parent and conversion; evaluate exported bytes.",
    "CLASSICAL_MODEL_HINT": "Inspect the CPU task, data lineage and evaluation.",
    "KERNEL_OR_SOFTWARE_HINT": "Verify software, numerical and runtime contracts; not LLM SFT.",
    "RECIPE_OR_PLACEHOLDER_HINT": "Inspect the task and admitted data before proposing training.",
    "UNCLASSIFIED": "Inspect the exact artifact and source; do not guess its type.",
}
HEADERS = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
           "Referrer-Policy": "no-referrer"}
PAGE_HEADERS = {**HEADERS, "Content-Security-Policy": (
    "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; "
    "img-src 'self'; base-uri 'none'; form-action 'none'; object-src 'none'; "
    "frame-ancestors 'self' https://huggingface.co https://*.hf.space https://*.huggingface.co"
), "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()"}


class CatalogError(ValueError):
    """The existing snapshot is missing, inconsistent, or outside this view's scope."""


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                      separators=(",", ":")).encode("utf-8")


def require(ok: bool) -> None:
    if not ok:
        raise CatalogError("model_inventory_invalid")


def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in out)
        out[key] = value
    return out


def timestamp(value: Any) -> datetime:
    require(isinstance(value, str) and len(value) <= 64)
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(result.tzinfo is not None and result.utcoffset() is not None)
    return result.astimezone(timezone.utc)


def decode_json(raw: bytes) -> Any:
    """Decode bounded strict JSON, including numeric-overflow rejection."""
    require(type(raw) is bytes and 0 < len(raw) <= MAX_BYTES)
    def reject_constant(_: str) -> None:
        raise CatalogError("nonfinite_inventory")
    def finite_float(raw_number: str) -> float:
        number = float(raw_number)
        require(math.isfinite(number))
        return number
    return json.loads(raw, object_pairs_hook=unique, parse_constant=reject_constant,
                      parse_float=finite_float)


def parse_manifest(raw: bytes) -> dict[str, Any]:
    """Reject partial, malformed and wrong-visibility observations, not as zero."""
    try:
        value = decode_json(raw)
        require(type(value) is dict and type(value.get("schemaVersion")) is int
                and value["schemaVersion"] == 2 and value.get("org") == "SZLHOLDINGS")
        timestamp(value["observedAt"])
        scope = value["inventoryScope"]
        require(scope["visibility"] == "public-only" and scope["authenticated"] is False
                and scope["privateAssetsIncluded"] is False)
        models, count = value["inventory"]["models"], value["counts"]["models"]
        require(type(models) is list and type(count) is int and 0 <= count <= MAX_MODELS
                and count == len(models))
        seen: set[str] = set()
        for item in models:
            require(type(item) is dict)
            identity = item.get("id")
            require(isinstance(identity, str) and REPO.fullmatch(identity) is not None
                    and identity not in seen and ".." not in identity)
            seen.add(identity)
            require(item.get("repoType") == "model" and item.get("private") is False)
            require(isinstance(item.get("sha"), str) and SHA.fullmatch(item["sha"]) is not None)
            timestamp(item["lastModified"])
            tags = item.get("tags")
            require(type(tags) is list and len(tags) <= 512 and all(
                isinstance(tag, str) and 0 < len(tag) <= 512 for tag in tags))
            require(type(item.get("gated")) is bool or item.get("gated") in ("auto", "manual"))
            require(type(item.get("disabled")) is bool)
            license_id = item.get("license")
            require(license_id is None or (isinstance(license_id, str) and len(license_id) <= 256))
        return value
    except (KeyError, TypeError, ValueError, UnicodeError, RecursionError, OverflowError) as exc:
        raise CatalogError("model_inventory_invalid") from exc


def build_projection(raw: bytes) -> bytes:
    """Derive only needed public model metadata from the existing inventory.

    No second author list is maintained. CI checks these bytes against the
    canonical manifest; the image already copies routers/data, not all docs.
    """
    value = parse_manifest(raw)
    fields = ("id", "repoType", "private", "sha", "lastModified", "tags", "gated",
              "disabled", "license")
    snapshot = {
        "schemaVersion": 2, "org": value["org"], "observedAt": value["observedAt"],
        "inventoryScope": {k: value["inventoryScope"][k] for k in
                           ("visibility", "authenticated", "privateAssetsIncluded")},
        "counts": {"models": len(value["inventory"]["models"])},
        "inventory": {"models": [{k: item.get(k) for k in fields}
            for item in value["inventory"]["models"]]},
    }
    return canonical({"schema": "szl.model-pretraining-input/v1",
        "sourceManifestPath": "docs/huggingface-ecosystem-manifest.json",
        "sourceManifestSha256": hashlib.sha256(raw).hexdigest(), "snapshot": snapshot}) + b"\n"


def decode_projection(raw: bytes) -> tuple[bytes, str]:
    """Check the packaged projection schema; the source digest is build-declared.

    Runtime does not possess/re-hash the complete original docs manifest. This
    method never turns that declared source digest into a signature/attestation.
    """
    try:
        value = decode_json(raw)
        require(type(value) is dict and set(value) == {
            "schema", "sourceManifestPath", "sourceManifestSha256", "snapshot"})
        require(value["schema"] == "szl.model-pretraining-input/v1")
        require(value["sourceManifestPath"] == "docs/huggingface-ecosystem-manifest.json")
        require(isinstance(value["sourceManifestSha256"], str)
                and re.fullmatch(r"[a-f0-9]{64}", value["sourceManifestSha256"]) is not None)
        snapshot = canonical(value["snapshot"])
        parse_manifest(snapshot)
        return snapshot, value["sourceManifestSha256"]
    except (KeyError, TypeError, ValueError, UnicodeError, RecursionError, OverflowError) as exc:
        raise CatalogError("model_projection_invalid") from exc


def category(tags: list[str]) -> str:
    lowered = {tag.casefold() for tag in tags}
    # Explicit not-a-checkpoint/reference markers win over nominal model tags.
    if lowered.intersection({"not-a-checkpoint", "not-a-model", "test-fixture", "surrogate"}):
        return "KERNEL_OR_SOFTWARE_HINT"
    if lowered.intersection({"kernel", "kernels", "software"}):
        return "KERNEL_OR_SOFTWARE_HINT"
    if "logistic-regression" in lowered:
        return "CLASSICAL_MODEL_HINT"
    if lowered.intersection({"no-weights", "curriculum-only", "roadmap", "alias"}):
        return "RECIPE_OR_PLACEHOLDER_HINT"
    if "gguf" in lowered or "llama.cpp" in lowered:
        return "GGUF_HINT"
    if "peft" in lowered or any(tag.startswith("base_model:adapter:") for tag in lowered):
        return "ADAPTER_HINT"
    if "transformers" in lowered and lowered.intersection({"safetensors", "text-generation", "image-text-to-text"}):
        return "CHECKPOINT_HINT"
    return "UNCLASSIFIED"


def safe_source(value: Any) -> str | None:
    """Accept only existing declared organization source pointers, never arbitrary URLs."""
    if (not isinstance(value, str) or len(value) > 1024
            or any(ord(char) <= 32 or ord(char) == 127 for char in value)):
        return None
    try:
        parsed = urlsplit(value)
        parts = parsed.path.split("/")
        if (parsed.scheme != "https" or parsed.netloc != "github.com" or parsed.query
                or parsed.fragment or parsed.username or parsed.password or parsed.port
                or len(parts) < 3 or parts[1] != "szl-holdings"
                or any(not re.fullmatch(r"[A-Za-z0-9._-]+", part) or part in (".", "..")
                       for part in parts[2:])):
            return None
        return value
    except ValueError:
        return None


def declared_source_cards() -> tuple[list[dict[str, Any]], str]:
    """Reuse the established A11oy catalog without querying its network functions."""
    try:
        from a11oy_model_intel import SERIES_A_CARDS
        if not isinstance(SERIES_A_CARDS, tuple):
            return [], "UNAVAILABLE"
        return list(SERIES_A_CARDS), "EXISTING_SERIES_A_CATALOG_SUBSET"
    except (ImportError, AttributeError, OSError, ValueError, TypeError):
        return [], "UNAVAILABLE"


def project(raw: bytes, cards: list[dict[str, Any]], *, now: datetime,
            product_revision: str | None = None) -> dict[str, Any]:
    value = parse_manifest(raw)
    require(now.tzinfo is not None and now.utcoffset() is not None)
    observed = timestamp(value["observedAt"])
    age = (now.astimezone(timezone.utc) - observed).total_seconds()
    require(math.isfinite(age))
    sources: dict[str, list[str | None]] = {}
    for card in cards:
        if isinstance(card, dict) and card.get("hub_kind") == "model" and isinstance(card.get("hub_id"), str):
            sources.setdefault(card["hub_id"], []).append(safe_source(card.get("github")))
    rows = []
    for item in sorted(value["inventory"]["models"], key=lambda row: row["id"].casefold()):
        identity = item["id"]
        hints = category(item["tags"])
        pointers = sources.get(identity, [])
        source_url = pointers[0] if len(pointers) == 1 else None
        source_state = ("AMBIGUOUS" if len(pointers) > 1 else
                        "DECLARED_POINTER_ONLY" if source_url else "NOT_RESOLVED_BY_THIS_CATALOG")
        rows.append({
            "id": identity, "categoryHint": hints, "categoryIsVerified": False,
            "hubRevision": item["sha"], "hubRevisionState": "RECORDED_SNAPSHOT_NOT_LIVE",
            "hubUrl": f"https://huggingface.co/{identity}/tree/{item['sha']}",
            "sourceUrl": source_url, "sourceState": source_state,
            "sourceBytesVerified": False, "weightsVerified": False,
            "evaluationVerified": False, "publicationVerified": False,
            "runtimeVerified": False, "trainingAllowed": False,
            "gated": item["gated"], "disabled": item["disabled"],
            "licenseReported": item.get("license"), "licenseReview": "NOT_PERFORMED",
            "nextAction": CATEGORIES[hints],
        })
    source = product_revision if isinstance(product_revision, str) and SHA.fullmatch(product_revision) else None
    return {
        "schema": SCHEMA, "available": True, "state": "PRETRAINING_REVIEW_NOT_ALIGNMENT",
        "inventoryScope": value["inventoryScope"], "observedAt": value["observedAt"],
        "snapshotAgeSeconds": round(max(age, 0)),
        "snapshotFreshness": "CLOCK_SKEW" if age < 0 else "STALE_SNAPSHOT" if age > 86400 else "SNAPSHOT_NOT_LIVE",
        "manifestPath": "docs/huggingface-ecosystem-manifest.json",
        "manifestSha256": hashlib.sha256(raw).hexdigest(),
        "productSourceRevisionReported": source, "productSourceIndependentlyAttested": False,
        "models": rows, "returned": len(rows), "categoryCounts": dict(Counter(r["categoryHint"] for r in rows)),
        "sourcePointersDeclared": sum(r["sourceState"] == "DECLARED_POINTER_ONLY" for r in rows),
        "wholeOrganizationInventoryVerified": False, "sourceAlignmentVerified": False,
        "trainingAllowed": False, "authority": dict(AUTHORITY),
        "bounds": [
            "Existing public metadata snapshot, not a current authenticated organization census.",
            "Tags classify inspection work only; they do not establish loadable or trained weights.",
            "A declared GitHub link does not verify source bytes or reproduce a model.",
            "No training, model inference, external mutation or promotion is available through this view.",
        ],
    }


def register(app: FastAPI) -> dict[str, Any]:
    """Attach a read-only subview to the existing HF-tooling product route group."""
    api = "/api/a11oy/v1/models/pretraining"
    files = {"/frontier-tooling/models": ("model-pretraining.html", "text/html"),
             "/frontier-tooling/models/": ("model-pretraining.html", "text/html"),
             "/frontier-tooling/models/assets/view.js": ("model-pretraining.js", "text/javascript"),
             "/frontier-tooling/models/assets/view.css": ("model-pretraining.css", "text/css")}
    intended = {api, *files}
    old = [r for r in app.routes if getattr(r, "path", None) in intended]
    if old:
        if (len(old) == len(intended) and {r.path for r in old} == intended
                and all(getattr(r.endpoint, "__module__", None) == __name__
                        and r.methods == {"GET", "HEAD"} for r in old)):
            return {"state": "READ_ONLY", "alreadyRegistered": True}
        raise RuntimeError("MODEL_PRETRAINING_ROUTE_COLLISION")

    def send(request: Request, body: bytes, media: str, status: int = 200) -> Response:
        headers = PAGE_HEADERS if media == "text/html" else HEADERS
        return Response(b"" if request.method == "HEAD" else body, status_code=status,
                        media_type=media, headers={**headers, "Content-Length": str(len(body))})

    @app.api_route(api, methods=["GET", "HEAD"])
    def catalog(request: Request) -> Response:
        try:
            with MANIFEST.open("rb") as stream:
                raw = stream.read(MAX_BYTES + 1)
            from routers.hf_tooling_evidence import runtime_source
            revision, _ = runtime_source()
            snapshot, source_digest = decode_projection(raw)
            cards, card_state = declared_source_cards()
            body = project(snapshot, cards, now=datetime.now(timezone.utc), product_revision=revision)
            body["manifestSha256"] = source_digest
            body["manifestDigestState"] = "BUILD_DERIVED_SOURCE_DIGEST_NOT_REHASHED_AT_RUNTIME"
            body["projectionSha256"] = hashlib.sha256(raw).hexdigest()
            body["sourcePointerCatalogState"] = card_state
            return send(request, canonical(body), "application/json")
        except (OSError, CatalogError):
            return send(request, canonical({"schema": SCHEMA, "available": False,
                "state": "UNAVAILABLE", "returned": None, "models": [],
                "trainingAllowed": False, "sourceAlignmentVerified": False,
                "authority": dict(AUTHORITY)}), "application/json", status=503)

    def file_handler(filename: str, media: str):
        def read(request: Request) -> Response:
            try:
                body = (PAGE_ROOT / filename).read_bytes()
            except OSError:
                raise HTTPException(503, "Model view unavailable") from None
            return send(request, body, media)
        return read
    for i, (path, (filename, media)) in enumerate(files.items()):
        app.add_api_route(path, file_handler(filename, media), methods=["GET", "HEAD"],
                          name=f"model_pretraining_file_{i}", include_in_schema=False)
    return {"state": "READ_ONLY", "trainingAllowed": False, "routes": sorted(intended)}
