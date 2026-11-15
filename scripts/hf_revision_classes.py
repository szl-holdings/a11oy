#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Revision classes for public SZLHOLDINGS Hub rows, loaded fail-closed.

``docs/huggingface-revision-classes.v1.json`` classifies rows by
``(repoType, id)``; the same id can exist as a model and as a kernel.

- GOVERNED_EXACT: ``sha`` and ``lastModified`` stay exact in ``--check``.
  Required for every gated row and every model_release binding.
- SOURCE_TRACKED: the default for unlisted rows, identical to the ungated
  comparison that existed before these classes.
- APPEND_ONLY_EVIDENCE: reserved. No file-level append proof is implemented,
  so any entry using it is rejected instead of being half-checked.

Bindings are discovered by a fixed scan: every ``SZLHOLDINGS/<name>`` string in
``model_release/**/*.json`` must sit at a declared binding or reference-only
location. Each binding must be classed GOVERNED_EXACT and cited by its exact
location in that entry's ``policySource``. The four release sources in
``REQUIRED_BINDING_SOURCES`` and their namespaces are fixed in this file, and
only a ``COLLECTION`` kind may map to no namespace, so a policy-only edit
cannot unbind or re-namespace a release repository. Missing, unreadable or
invalid policy is an error, never a fallback to the default class.
"""
# No postponed annotations: the dataclasses must also build when this file is
# loaded by path (spec_from_file_location) without a sys.modules entry.
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import re
from types import MappingProxyType
from typing import Any, Iterator, Mapping

REPO_ROOT = Path(__file__).resolve().parents[1]
POLICY_RELATIVE = "docs/huggingface-revision-classes.v1.json"
SCHEMA = "szl.hf-revision-classes/v1"
SPDX_COMMENT = (
    "SPDX-License-Identifier: Apache-2.0; (c) 2026 Lutar, Stephen P. - "
    "SZL Holdings - ORCID 0009-0001-0110-4173"
)
GOVERNED_EXACT = "GOVERNED_EXACT"
APPEND_ONLY_EVIDENCE = "APPEND_ONLY_EVIDENCE"
SOURCE_TRACKED = "SOURCE_TRACKED"
CLASS_STATUS = {
    GOVERNED_EXACT: "ENFORCED",
    SOURCE_TRACKED: "DEFAULT",
    APPEND_ONLY_EVIDENCE: "RESERVED_UNUSED",
}
DEFAULT_POLICY_SOURCE = "default:SOURCE_TRACKED"
REPO_TYPES = ("model", "dataset", "space", "kernel")
PLURALS = {"models": "model", "datasets": "dataset", "spaces": "space", "kernels": "kernel"}
ORG_REPO = re.compile(r"SZLHOLDINGS/[A-Za-z0-9][A-Za-z0-9._-]{0,159}\Z")
SCAN_ROOT = "model_release"
NAMESPACE_KEYS = ("repoType", "repoTypeField", "repoTypeMap")
# The release files named by the design review, each with the namespace it
# must declare. The policy may add binding sources, but cannot drop or
# re-namespace one of these and so silently relax its repository.
REQUIRED_BINDING_SOURCES: Mapping[tuple[str, str], Mapping[str, Any]] = MappingProxyType({
    ("model_release/szl-nemo/release-manifest.json", "/hub/repository"): {"repoType": "model"},
    ("model_release/hf-promotion/promotion-manifest.json", "/candidates/*/canonical_target"): {
        "repoTypeField": "target_kind",
        "repoTypeMap": {"MODEL": "model"},
    },
    ("model_release/szl-forge-family.json", "/profiles/*/hf_target"): {"repoType": "model"},
    ("model_release/receipt-agent/release-manifest.json", "/hf_artifact_family/*/target_id"): {
        "repoTypeField": "artifact_type",
        "repoTypeMap": {
            "MODEL_ADAPTER": "model",
            "EVALUATION_DATASET": "dataset",
            "SCHEMA_DATASET": "dataset",
            "SPACE": "space",
            "COLLECTION": None,
        },
    },
})
# A Hub collection is not a repository namespace in the inventory. No other
# kind may map to no namespace, or a policy edit alone could unbind a repository.
UNNAMESPACED_KINDS = frozenset({"COLLECTION"})
MAX_POLICY_BYTES = 1024 * 1024
MAX_SCAN_FILES = 256
MAX_SCAN_FILE_BYTES = 4 * 1024 * 1024
TOP_LEVEL_KEYS = {
    "$comment", "schema", "defaultClass", "classes",
    "bindingSources", "referenceOnlySources", "entries",
}
ENTRY_KEYS = {"repoType", "id", "class", "policySource", "rationale"}


class RevisionClassError(ValueError):
    """The revision class policy cannot support a complete classification."""


@dataclass(frozen=True)
class Binding:
    repo_type: str
    repo_id: str
    ref: str


@dataclass(frozen=True)
class RevisionClasses:
    entries: Mapping[tuple[str, str], Mapping[str, Any]]
    bindings: tuple[Binding, ...]
    sha256: str
    path: str

    def _entry(self, repo_type: Any, repo_id: Any) -> Mapping[str, Any] | None:
        if not isinstance(repo_type, str) or not isinstance(repo_id, str):
            return None
        return self.entries.get((repo_type, repo_id))

    def class_of(self, repo_type: Any, repo_id: Any) -> str:
        entry = self._entry(repo_type, repo_id)
        return entry["class"] if entry is not None else SOURCE_TRACKED

    def policy_source(self, repo_type: Any, repo_id: Any) -> list[str]:
        entry = self._entry(repo_type, repo_id)
        return list(entry["policySource"]) if entry is not None else [DEFAULT_POLICY_SOURCE]

    def governed(self, repo_type: Any, repo_id: Any) -> bool:
        return self.class_of(repo_type, repo_id) == GOVERNED_EXACT

    def governed_keys(self) -> list[tuple[str, str]]:
        return sorted(key for key, entry in self.entries.items() if entry["class"] == GOVERNED_EXACT)


def _require(ok: bool, reason: str) -> None:
    if not ok:
        raise RevisionClassError(reason)


def _strict_json(raw: bytes, *, label: str) -> Any:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            _require(key not in result, f"{label} has a duplicate JSON key: {key}")
            result[key] = value
        return result

    def nonfinite(_: str) -> Any:
        raise RevisionClassError(f"{label} has a nonfinite JSON number")

    def finite(value: str) -> float:
        number = float(value)
        _require(math.isfinite(number), f"{label} has a nonfinite JSON number")
        return number

    try:
        return json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=pairs,
            parse_constant=nonfinite,
            parse_float=finite,
        )
    except RevisionClassError:
        raise
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise RevisionClassError(f"{label} is not valid JSON") from exc


def _read_regular(path: Path, *, limit: int, label: str) -> bytes:
    try:
        _require(not path.is_symlink() and path.is_file(), f"{label} must be a regular file")
        raw = path.read_bytes()
    except OSError as exc:
        raise RevisionClassError(f"{label} is unreadable") from exc
    _require(0 < len(raw) <= limit, f"{label} is empty or exceeds {limit} bytes")
    return raw


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _pointer_tokens(pointer: Any, *, label: str) -> tuple[str, ...]:
    _require(isinstance(pointer, str) and pointer.startswith("/") and len(pointer) > 1,
             f"{label} pointer must be a non-root JSON pointer")
    tokens = tuple(token.replace("~1", "/").replace("~0", "~") for token in pointer[1:].split("/"))
    _require(all(tokens), f"{label} pointer has an empty segment")
    return tokens


def _escape(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


def _walk(value: Any, path: tuple[str, ...] = ()) -> Iterator[tuple[tuple[str, ...], Any, Any]]:
    """Yield (path, string, containing object) for every string leaf."""
    if isinstance(value, dict):
        for key, child in value.items():
            # A repository id used as a key has no field to declare; refuse it.
            _require(ORG_REPO.fullmatch(key) is None,
                     f"SZLHOLDINGS repository id {key} is used as a JSON key under {SCAN_ROOT}/")
            if isinstance(child, str):
                yield path + (key,), child, value
            else:
                yield from _walk(child, path + (key,))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            if isinstance(child, str):
                yield path + (str(index),), child, None
            else:
                yield from _walk(child, path + (str(index),))


def _matches(pattern: tuple[str, ...], path: tuple[str, ...]) -> bool:
    return len(pattern) == len(path) and all(
        want == got or (want == "*" and got.isdigit()) for want, got in zip(pattern, path)
    )


def _required_namespace(path: str, tokens: tuple[str, ...]) -> Mapping[str, Any] | None:
    for (want, pointer), namespace in REQUIRED_BINDING_SOURCES.items():
        if want == path and _pointer_tokens(pointer, label="required source") == tokens:
            return namespace
    return None


def _sources(document: dict[str, Any], key: str, *, binding: bool) -> list[dict[str, Any]]:
    rows = document.get(key)
    _require(isinstance(rows, list), f"{key} must be a list")
    seen: set[tuple[str, tuple[str, ...]]] = set()
    result = []
    for index, row in enumerate(rows):
        label = f"{key}[{index}]"
        _require(isinstance(row, dict), f"{label} must be an object")
        allowed = {"path", "pointer", "rationale"}
        if binding:
            allowed |= set(NAMESPACE_KEYS)
        _require(set(row) <= allowed, f"{label} has unknown keys")
        path = row.get("path")
        _require(isinstance(path, str) and path.startswith(f"{SCAN_ROOT}/")
                 and path.endswith(".json") and ".." not in path.split("/")
                 and "\\" not in path, f"{label} path must be a {SCAN_ROOT}/ JSON file")
        tokens = _pointer_tokens(row.get("pointer"), label=label)
        _require(_text(row.get("rationale")), f"{label} requires a rationale")
        _require((path, tokens) not in seen, f"{label} duplicates another source")
        seen.add((path, tokens))
        if binding:
            fixed, field, mapping = row.get("repoType"), row.get("repoTypeField"), row.get("repoTypeMap")
            if "repoType" in row:
                # A binding without a namespace would be ambiguous between twins.
                _require(fixed in REPO_TYPES and field is None and mapping is None,
                         f"{label} needs exactly one fixed repoType or a repoTypeField map")
            else:
                _require(_text(field) and isinstance(mapping, dict) and mapping
                         and all(_text(k) and (v is None or v in REPO_TYPES) for k, v in mapping.items()),
                         f"{label} needs exactly one fixed repoType or a repoTypeField map")
                unnamespaced = sorted(k for k, v in mapping.items() if v is None and k not in UNNAMESPACED_KINDS)
                _require(not unnamespaced, f"{label} maps {unnamespaced} to no repository namespace; "
                                           f"only {sorted(UNNAMESPACED_KINDS)} may map to null")
            required = _required_namespace(path, tokens)
            if required is not None:
                declared = {name: row[name] for name in NAMESPACE_KEYS if name in row}
                _require(declared == required, f"{label} must declare the required namespace "
                                               f"{json.dumps(required, sort_keys=True)} for {path}#{row['pointer']}")
        result.append({**row, "tokens": tokens, "binding": binding})
    return result


def discover_bindings(document: dict[str, Any], *, root: Path) -> tuple[Binding, ...]:
    """Scan model_release JSON; every SZLHOLDINGS string must be declared."""
    bindings = _sources(document, "bindingSources", binding=True)
    references = _sources(document, "referenceOnlySources", binding=False)
    declared = {(row["path"], row["tokens"]) for row in bindings}
    missing = sorted(f"{path}#{pointer}" for path, pointer in REQUIRED_BINDING_SOURCES
                     if (path, _pointer_tokens(pointer, label="required source")) not in declared)
    _require(not missing, f"required binding sources are not declared: {missing}")
    scan_root = root / SCAN_ROOT
    _require(scan_root.is_dir() and not scan_root.is_symlink(), f"{SCAN_ROOT}/ is not a directory")
    files = sorted(scan_root.rglob("*.json"))
    _require(len(files) <= MAX_SCAN_FILES, f"{SCAN_ROOT}/ has more than {MAX_SCAN_FILES} JSON files")
    sources = bindings + references
    hits = [0] * len(sources)
    found: list[Binding] = []
    for file in files:
        relative = file.relative_to(root).as_posix()
        raw = _read_regular(file, limit=MAX_SCAN_FILE_BYTES, label=relative)
        value = _strict_json(raw, label=relative)
        for path, text, parent in _walk(value):
            if not ORG_REPO.fullmatch(text):
                continue
            pointer = "/" + "/".join(_escape(token) for token in path)
            owners = [index for index, row in enumerate(sources)
                      if row["path"] == relative and _matches(row["tokens"], path)]
            _require(owners, f"unreviewed SZLHOLDINGS repository reference {text} at "
                             f"{relative}#{pointer}; declare it as a binding or reference-only source")
            _require(len(owners) == 1, f"{relative}#{pointer} matches more than one source")
            hits[owners[0]] += 1
            owner = sources[owners[0]]
            if not owner["binding"]:
                continue
            repo_type = owner.get("repoType")
            if "repoType" not in owner:
                field = owner["repoTypeField"]
                kind = parent.get(field) if isinstance(parent, dict) else None
                _require(isinstance(kind, str) and kind in owner["repoTypeMap"],
                         f"{relative}#{pointer} has no mapped {field}")
                repo_type = owner["repoTypeMap"][kind]
                if repo_type is None:
                    # Collections are outside the repository namespaces in the inventory.
                    continue
            found.append(Binding(repo_type, text, f"{relative}#{pointer}"))
    stale = sorted(f"{row['path']}#{row['pointer']}" for row, hit in zip(sources, hits) if not hit)
    _require(not stale, f"declared sources match no SZLHOLDINGS reference: {stale}")
    return tuple(found)


def validate_document(document: Any, *, root: Path, sha256: str = "") -> RevisionClasses:
    _require(isinstance(document, dict), "revision classes must be a JSON object")
    _require(set(document) == TOP_LEVEL_KEYS, "revision classes have missing or unknown top-level keys")
    _require(document["$comment"] == SPDX_COMMENT, "revision classes require the SZL SPDX comment")
    _require(document["schema"] == SCHEMA, f"revision classes schema must be {SCHEMA}")
    _require(document["defaultClass"] == SOURCE_TRACKED, "defaultClass must be SOURCE_TRACKED")
    classes = document["classes"]
    _require(isinstance(classes, dict) and set(classes) == set(CLASS_STATUS),
             "classes must describe exactly the known revision classes")
    for name, status in CLASS_STATUS.items():
        row = classes[name]
        _require(isinstance(row, dict) and set(row) == {"status", "meaning"}
                 and row["status"] == status and _text(row["meaning"]),
                 f"class {name} must declare status {status} and a meaning")
    rows = document["entries"]
    _require(isinstance(rows, list), "entries must be a list")
    entries: dict[tuple[str, str], dict[str, Any]] = {}
    for index, row in enumerate(rows):
        label = f"entries[{index}]"
        _require(isinstance(row, dict) and set(row) == ENTRY_KEYS,
                 f"{label} must have exactly {sorted(ENTRY_KEYS)}")
        repo_type, repo_id, name = row["repoType"], row["id"], row["class"]
        _require(repo_type in REPO_TYPES, f"{label} repoType is unknown")
        _require(isinstance(repo_id, str) and ORG_REPO.fullmatch(repo_id) is not None,
                 f"{label} id must be an SZLHOLDINGS repository id")
        _require(name in CLASS_STATUS, f"{label} has unknown class {name!r}")
        _require(CLASS_STATUS[name] != "RESERVED_UNUSED",
                 f"{label} uses reserved class {name}; no append-only proof is implemented")
        sources = row["policySource"]
        _require(isinstance(sources, list) and sources and all(_text(item) for item in sources)
                 and len(set(sources)) == len(sources), f"{label} requires a non-empty policySource list")
        _require(_text(row["rationale"]), f"{label} requires a rationale")
        key = (repo_type, repo_id)
        _require(key not in entries, f"{label} duplicates ({repo_type}, {repo_id})")
        entries[key] = {**row, "policySource": tuple(sources)}
    bindings = discover_bindings(document, root=root)
    cited: dict[tuple[str, str], set[str]] = {}
    for binding in bindings:
        key = (binding.repo_type, binding.repo_id)
        cited.setdefault(key, set()).add(binding.ref)
        entry = entries.get(key)
        _require(entry is not None and entry["class"] == GOVERNED_EXACT,
                 f"bound {binding.repo_type} {binding.repo_id} ({binding.ref}) must be classed GOVERNED_EXACT")
        _require(binding.ref in entry["policySource"],
                 f"{binding.repo_type} {binding.repo_id} policySource must cite {binding.ref}")
    for key, entry in entries.items():
        for source in entry["policySource"]:
            if source.startswith(f"{SCAN_ROOT}/"):
                _require(source in cited.get(key, set()),
                         f"{key[0]} {key[1]} cites {source}, which is not a discovered binding")
    return RevisionClasses(entries=entries, bindings=bindings, sha256=sha256, path=POLICY_RELATIVE)


def load_revision_classes(path: Path | None = None, *, root: Path | None = None) -> RevisionClasses:
    """Load and validate the policy; every failure raises RevisionClassError."""
    root = REPO_ROOT if root is None else root
    path = root / POLICY_RELATIVE if path is None else path
    raw = _read_regular(path, limit=MAX_POLICY_BYTES, label=POLICY_RELATIVE)
    return validate_document(_strict_json(raw, label=POLICY_RELATIVE), root=root,
                             sha256=hashlib.sha256(raw).hexdigest())


def _rows(manifest: Any, *, label: str) -> Iterator[tuple[str, dict[str, Any]]]:
    inventory = manifest.get("inventory") if isinstance(manifest, dict) else None
    _require(isinstance(inventory, dict), f"{label} inventory must be an object")
    for plural, repo_type in PLURALS.items():
        rows = inventory.get(plural, [])
        _require(isinstance(rows, list), f"{label} inventory.{plural} must be a list")
        for row in rows:
            _require(isinstance(row, dict) and isinstance(row.get("id"), str),
                     f"{label} inventory.{plural} rows must be objects with an id")
            yield repo_type, row


def validate_manifest_coverage(classes: RevisionClasses, manifest: Any, *, label: str) -> None:
    """Every gated row must be explicitly GOVERNED_EXACT."""
    for repo_type, row in _rows(manifest, label=label):
        if row.get("gated") not in (None, False) and not classes.governed(repo_type, row["id"]):
            raise RevisionClassError(
                f"{label} gated {repo_type} {row['id']} must be classed GOVERNED_EXACT in {POLICY_RELATIVE}"
            )


def governed_changes(classes: RevisionClasses, old: Any, new: Any) -> list[dict[str, Any]]:
    """List GOVERNED_EXACT or gated rows whose presence, sha or lastModified differ."""
    def index(manifest: Any, label: str) -> dict[tuple[str, str], dict[str, Any]]:
        return {(repo_type, row["id"]): row for repo_type, row in _rows(manifest, label=label)}

    before, after = index(old, "tracked manifest"), index(new, "candidate")
    keys = set(classes.governed_keys())
    keys |= {key for key, row in {**before, **after}.items() if row.get("gated") not in (None, False)}
    changes = []
    for repo_type, repo_id in sorted(keys):
        first, second = before.get((repo_type, repo_id)), after.get((repo_type, repo_id))
        if first is None and second is None:
            continue
        if first is None or second is None:
            change, fields = ("ADDED" if first is None else "REMOVED"), ["presence"]
        else:
            fields = [field for field in ("sha", "lastModified", "gated") if first.get(field) != second.get(field)]
            if not fields:
                continue
            change = "REVISION_CHANGED"
        changes.append({
            "repoType": repo_type, "id": repo_id, "class": classes.class_of(repo_type, repo_id),
            "policySource": classes.policy_source(repo_type, repo_id), "change": change, "fields": fields,
        })
    return changes
