#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Fail-closed static preview for an exact, reviewed Platform A11oy build.

Taxonomy: services/.  The router serves only a digest-bound, zero-effector
candidate tree.  It owns no credential, provider client, signer, scheduler, or
write path and cannot change the root application or its API routes.
"""

import hashlib
import json
import mimetypes
import os
import posixpath
import re
import stat
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from types import MappingProxyType
from typing import Mapping
from urllib.parse import urlsplit

from fastapi.responses import Response
from starlette.routing import Route, WebSocketRoute


PREFIX = "/preview/platform-a11oy"
SCHEMA = "szl.platform-static-candidate/v1"
SOURCE_REPOSITORY = "https://github.com/szl-holdings/platform"
BASE_PATH = PREFIX + "/"
STATE = "CANDIDATE_DEMO"
REVIEWED_ROUTES = ("/", "/security-agents")
UNKNOWN_ROUTE_POLICY = "not_found"

MANIFEST_LIMIT = 64 * 1024
FILE_LIMIT = 2 * 1024 * 1024
TOTAL_LIMIT = 16 * 1024 * 1024
FILE_COUNT_LIMIT = 256
INVENTORY_ENTRY_LIMIT = 512
DIRECTORY_DEPTH_LIMIT = 8
REQUEST_PATH_LIMIT = 1024
_REVISION = re.compile(r"[0-9a-f]{40}\Z")
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_FINGERPRINTED_ASSET = re.compile(
    r"assets/[A-Za-z0-9_.-]+-[A-Za-z0-9_-]{8,}\.(?:css|js)\Z"
)
_CSP = (
    "default-src 'none'; "
    "script-src https://a-11-oy.com/preview/platform-a11oy/ "
    "https://szlholdings-a11oy.hf.space/preview/platform-a11oy/; "
    "script-src-attr 'none'; "
    "style-src 'unsafe-inline' https://a-11-oy.com/preview/platform-a11oy/ "
    "https://szlholdings-a11oy.hf.space/preview/platform-a11oy/; "
    "img-src data:; "
    "font-src 'none'; "
    "connect-src 'none'; "
    "media-src 'none'; "
    "frame-src 'none'; "
    "child-src 'none'; "
    "worker-src 'none'; "
    "object-src 'none'; "
    "base-uri 'none'; "
    "form-action 'none'; "
    "manifest-src 'none'; "
    "frame-ancestors 'self' https://huggingface.co https://*.hf.space "
    "https://*.huggingface.co"
)
_PERMISSIONS_POLICY = "camera=(), microphone=(), geolocation=(), payment=(), usb=()"


@dataclass(frozen=True)
class BoundFile:
    path: str
    sha256: str
    size: int


@dataclass(frozen=True)
class BoundBundle:
    source_revision: str
    manifest_sha256: str
    manifest_bytes: bytes
    files: Mapping[str, BoundFile]
    payloads: Mapping[str, bytes]
    reviewed_routes: tuple[str, ...]
    unknown_route_policy: str


class BundleUnavailable(ValueError):
    """The candidate tree is absent or does not match its immutable contract."""


def _canonical_relative_path(value: object) -> str:
    if not isinstance(value, str) or not value or len(value) > 512:
        raise BundleUnavailable("invalid candidate path")
    if value.startswith("/") or "\\" in value or "\x00" in value or "%" in value:
        raise BundleUnavailable("invalid candidate path")
    segments = value.split("/")
    if any(segment in {"", ".", ".."} for segment in segments):
        raise BundleUnavailable("invalid candidate path")
    return value


def _request_path(value: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) > REQUEST_PATH_LIMIT
        or "\\" in value
        or "\x00" in value
        or "%" in value
    ):
        raise BundleUnavailable("invalid request path")
    if not value:
        return ""
    segments = value.split("/")
    if any(segment in {"", ".", ".."} for segment in segments):
        raise BundleUnavailable("invalid request path")
    return value


def _css_without_comments_or_strings(text: str) -> str:
    """Remove inert CSS text while preserving token concatenation semantics."""
    output: list[str] = []
    index = 0
    while index < len(text):
        if text.startswith("/*", index):
            end = text.find("*/", index + 2)
            if end < 0:
                raise BundleUnavailable("candidate CSS comment is unterminated")
            index = end + 2
            continue
        if text[index] in {'\"', "'"}:
            quote = text[index]
            index += 1
            while index < len(text):
                character = text[index]
                if character == quote:
                    index += 1
                    break
                if character in "\r\n\f":
                    raise BundleUnavailable("candidate CSS string is invalid")
                if character == "\\":
                    index += 1
                    if index >= len(text):
                        raise BundleUnavailable("candidate CSS string is invalid")
                    if text[index] == "\r" and index + 1 < len(text) and text[index + 1] == "\n":
                        index += 2
                    else:
                        index += 1
                    continue
                index += 1
            else:
                raise BundleUnavailable("candidate CSS string is unterminated")
            output.append(" ")
            continue
        output.append(text[index])
        index += 1
    return "".join(output)


def _consume_css_name(text: str, start: int) -> tuple[str, int]:
    """Decode one CSS name, including its standards-defined escapes."""
    decoded: list[str] = []
    index = start
    while index < len(text):
        character = text[index]
        if character.isalnum() or character in {"-", "_"} or ord(character) >= 128:
            decoded.append(character)
            index += 1
            continue
        if character != "\\":
            break
        index += 1
        if index >= len(text) or text[index] in "\r\n\f":
            raise BundleUnavailable("candidate CSS escape is invalid")
        if text[index] in "0123456789abcdefABCDEF":
            end = index
            while end < len(text) and end - index < 6 and text[end] in "0123456789abcdefABCDEF":
                end += 1
            codepoint = int(text[index:end], 16)
            if codepoint == 0 or codepoint > 0x10FFFF or 0xD800 <= codepoint <= 0xDFFF:
                decoded.append("\ufffd")
            else:
                decoded.append(chr(codepoint))
            index = end
            if index < len(text) and text[index].isspace():
                if text[index] == "\r" and index + 1 < len(text) and text[index + 1] == "\n":
                    index += 2
                else:
                    index += 1
            continue
        decoded.append(text[index])
        index += 1
    return "".join(decoded), index


def _validate_css_has_no_fetch_primitives(text: str) -> None:
    """Reject every CSS construct that can name a browser-loaded resource."""
    lexical = _css_without_comments_or_strings(text)
    index = 0
    while index < len(lexical):
        if lexical[index] == "@":
            name, end = _consume_css_name(lexical, index + 1)
            if name.casefold() == "import":
                raise BundleUnavailable("candidate CSS imports are forbidden")
            index = max(end, index + 1)
            continue
        character = lexical[index]
        if character.isalnum() or character in {"-", "_", "\\"} or ord(character) >= 128:
            name, end = _consume_css_name(lexical, index)
            cursor = end
            while cursor < len(lexical) and lexical[cursor].isspace():
                cursor += 1
            if lexical[cursor : cursor + 1] == "(" and name.casefold() in {
                "url",
                "image-set",
                "-webkit-image-set",
            }:
                raise BundleUnavailable("candidate CSS resource loads are forbidden")
            index = max(end, index + 1)
            continue
        index += 1


def _open_root(root: Path) -> int:
    try:
        metadata = root.lstat()
    except OSError as error:
        raise BundleUnavailable("candidate root unavailable") from error
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
        raise BundleUnavailable("candidate root unavailable")
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        return os.open(root, flags)
    except OSError as error:
        raise BundleUnavailable("candidate root unavailable") from error


def _read_regular_file(root: Path, relative: str, limit: int) -> bytes:
    """Read a regular file beneath root without following any symlink."""
    relative = _canonical_relative_path(relative)
    root_fd = _open_root(root)
    opened = [root_fd]
    try:
        parent_fd = root_fd
        segments = relative.split("/")
        directory_flags = (
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
        )
        for segment in segments[:-1]:
            next_fd = os.open(segment, directory_flags, dir_fd=parent_fd)
            opened.append(next_fd)
            parent_fd = next_fd
        # Opening a FIFO for reading can otherwise block application startup
        # before fstat gets a chance to reject the non-regular node.
        file_flags = (
            os.O_RDONLY
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_NONBLOCK", 0)
        )
        file_fd = os.open(segments[-1], file_flags, dir_fd=parent_fd)
        opened.append(file_fd)
        metadata = os.fstat(file_fd)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > limit:
            raise BundleUnavailable("candidate file unavailable")
        chunks = []
        remaining = limit + 1
        while remaining:
            chunk = os.read(file_fd, min(remaining, 64 * 1024))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        payload = b"".join(chunks)
        if len(payload) > limit or len(payload) != metadata.st_size:
            raise BundleUnavailable("candidate file unavailable")
        return payload
    except (OSError, ValueError) as error:
        if isinstance(error, BundleUnavailable):
            raise
        raise BundleUnavailable("candidate file unavailable") from error
    finally:
        for descriptor in reversed(opened):
            try:
                os.close(descriptor)
            except OSError:
                pass


def _physical_files(root: Path) -> set[str]:
    """Inventory regular files and reject links or special filesystem nodes."""
    files: set[str] = set()
    entries_seen = 0
    stack = [(root, "", 0)]
    while stack:
        directory, prefix, depth = stack.pop()
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    entries_seen += 1
                    if entries_seen > INVENTORY_ENTRY_LIMIT:
                        raise BundleUnavailable("candidate inventory exceeds bound")
                    relative = f"{prefix}/{entry.name}" if prefix else entry.name
                    _canonical_relative_path(relative)
                    if entry.is_symlink():
                        raise BundleUnavailable("candidate links are forbidden")
                    if entry.is_dir(follow_symlinks=False):
                        if depth >= DIRECTORY_DEPTH_LIMIT:
                            raise BundleUnavailable("candidate inventory exceeds depth bound")
                        stack.append((Path(entry.path), relative, depth + 1))
                    elif entry.is_file(follow_symlinks=False):
                        files.add(relative)
                    else:
                        raise BundleUnavailable("candidate special files are forbidden")
        except BundleUnavailable:
            raise
        except OSError as error:
            raise BundleUnavailable("candidate inventory unavailable") from error
    return files


def _resolve_resource_reference(
    reference: str,
    *,
    source_path: str,
    declared: set[str],
    allow_data: bool = False,
) -> str | None:
    """Resolve one browser-loaded resource to an exact manifest member."""
    reference = reference.strip()
    if not reference:
        raise BundleUnavailable("candidate resource reference invalid")
    if reference.startswith("#"):
        return None
    if reference.lower().startswith("data:"):
        if allow_data:
            return None
        raise BundleUnavailable("candidate data resource is not permitted here")

    try:
        parsed = urlsplit(reference)
    except (UnicodeError, ValueError) as error:
        raise BundleUnavailable("candidate resource reference invalid") from error
    if parsed.scheme or parsed.netloc:
        raise BundleUnavailable("candidate external resource is forbidden")
    if not parsed.path:
        raise BundleUnavailable("candidate resource reference invalid")
    if parsed.path.startswith(BASE_PATH):
        relative = parsed.path[len(BASE_PATH) :]
    elif parsed.path.startswith("/"):
        raise BundleUnavailable("candidate resource escaped its base path")
    else:
        relative = posixpath.normpath(
            posixpath.join(posixpath.dirname(source_path), parsed.path)
        )
    relative = _canonical_relative_path(relative)
    if relative not in declared:
        raise BundleUnavailable("candidate resource is absent from the manifest")
    return relative


class _IndexResourceParser(HTMLParser):
    """Collect only resource-bearing HTML attributes; navigation links are inert."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.references: list[tuple[str, bool]] = []
        self.inline_css: list[str] = []
        self._style_depth = 0

    def handle_startendtag(self, tag: str, attrs) -> None:
        if tag.lower() == "style":
            raise BundleUnavailable("candidate self-closing style is invalid")
        self.handle_starttag(tag, attrs)

    def handle_starttag(self, tag: str, attrs) -> None:
        values: dict[str, str] = {}
        seen_attributes: set[str] = set()
        for name, value in attrs:
            normalized = name.casefold()
            if normalized in seen_attributes:
                raise BundleUnavailable("candidate duplicate HTML attribute is forbidden")
            seen_attributes.add(normalized)
            if value is not None:
                values[normalized] = value
        tag = tag.lower()
        if tag in {"svg", "image", "use", "feimage", "applet", "portal", "fencedframe"}:
            raise BundleUnavailable("candidate active embedded element is forbidden")
        if any(
            attribute in values
            for attribute in (
                "background",
                "imagesizes",
                "imagesrcset",
                "ping",
                "srcdoc",
                "xlink:href",
            )
        ):
            raise BundleUnavailable("candidate active resource attribute is forbidden")
        if "style" in values:
            self.inline_css.append(values["style"])
        if tag == "style":
            self._style_depth += 1
            return
        if tag == "base":
            raise BundleUnavailable("candidate HTML base element is forbidden")
        if tag == "meta" and values.get("http-equiv", "").lower() == "refresh":
            raise BundleUnavailable("candidate HTML refresh is forbidden")
        if tag == "script":
            source = values.get("src")
            if source is None:
                raise BundleUnavailable("candidate inline script is forbidden")
            self.references.append((source, False))
            return
        if tag == "link":
            rel = {item.lower() for item in values.get("rel", "").split()}
            forbidden = {
                "apple-touch-icon",
                "dns-prefetch",
                "manifest",
                "mask-icon",
                "preconnect",
                "prefetch",
                "prerender",
            }
            if rel.intersection(forbidden):
                raise BundleUnavailable("candidate resource hint is forbidden")
            if rel.intersection({"stylesheet", "preload", "modulepreload", "icon"}):
                href = values.get("href")
                if href is None:
                    raise BundleUnavailable("candidate resource link is invalid")
                self.references.append((href, "icon" in rel))
            elif "href" in values:
                raise BundleUnavailable("candidate link relation is outside the reviewed contract")
            return
        attribute = {
            "audio": "src",
            "embed": "src",
            "iframe": "src",
            "img": "src",
            "input": "src",
            "object": "data",
            "source": "src",
            "track": "src",
            "video": "src",
        }.get(tag)
        if attribute and attribute in values:
            self.references.append((values[attribute], tag in {"img", "input"}))
        if tag == "video" and "poster" in values:
            self.references.append((values["poster"], True))
        if "srcset" in values:
            raise BundleUnavailable("candidate srcset is outside the reviewed contract")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "style":
            if self._style_depth == 0:
                raise BundleUnavailable("candidate CSS style element is invalid")
            self._style_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._style_depth:
            self.inline_css.append(data)

    def validate_closed(self) -> None:
        if self._style_depth:
            raise BundleUnavailable("candidate CSS style element is unclosed")



def _asset_references(path: str, payload: bytes, declared: set[str]) -> set[str]:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise BundleUnavailable("candidate text asset is not UTF-8") from error

    references: list[tuple[str, bool]] = []
    if path == "index.html":
        parser = _IndexResourceParser()
        try:
            parser.feed(text)
            parser.close()
            parser.validate_closed()
        except (ValueError, AssertionError) as error:
            raise BundleUnavailable("candidate HTML is invalid") from error
        references.extend(parser.references)
        for inline_css in parser.inline_css:
            _validate_css_has_no_fetch_primitives(inline_css)

    if path.endswith(".css"):
        _validate_css_has_no_fetch_primitives(text)
    if path.endswith(".js"):
        if "sourceMappingURL=" in text:
            raise BundleUnavailable("candidate source map reference is forbidden")

    resolved: set[str] = set()
    for reference, allow_data in references:
        target = _resolve_resource_reference(
            reference,
            source_path=path,
            declared=declared,
            allow_data=allow_data,
        )
        if target is not None:
            resolved.add(target)
    return resolved


def _validate_static_assets(payloads: Mapping[str, bytes]) -> None:
    """Validate exact static bytes without interpreting JavaScript semantics.

    The manifest digest and per-file hashes bind the complete reviewed build.
    Path-scoped CSP sources enforce its runtime namespace.  A bespoke JavaScript
    lexer would be a weaker security boundary because ECMAScript tokenization is
    context-sensitive; browser execution is instead checked by the source build's
    network trace and the deployment verifier fetches every manifest member.
    """
    declared = set(payloads)
    entry_references = _asset_references("index.html", payloads["index.html"], declared)
    if not any(path.endswith(".js") for path in entry_references):
        raise BundleUnavailable("candidate index has no declared JavaScript entry")
    if not any(path.endswith(".css") for path in entry_references):
        raise BundleUnavailable("candidate index has no declared stylesheet entry")
    for path, payload in payloads.items():
        if path != "index.html":
            _asset_references(path, payload, declared)


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    document: dict[str, object] = {}
    for key, value in pairs:
        if key in document:
            raise BundleUnavailable("candidate manifest contains duplicate fields")
        document[key] = value
    return document


def load_bundle(
    root: Path,
    *,
    expected_source_revision: str,
    expected_manifest_sha256: str,
) -> BoundBundle:
    """Validate the manifest, complete inventory, and every declared byte."""
    if (
        not _REVISION.fullmatch(expected_source_revision)
        or expected_source_revision == "0" * 40
    ):
        raise BundleUnavailable("invalid expected source revision")
    if (
        not _DIGEST.fullmatch(expected_manifest_sha256)
        or expected_manifest_sha256 == "0" * 64
    ):
        raise BundleUnavailable("invalid expected manifest digest")

    manifest_bytes = _read_regular_file(root, "source.json", MANIFEST_LIMIT)
    manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
    if manifest_sha256 != expected_manifest_sha256:
        raise BundleUnavailable("candidate manifest digest mismatch")
    try:
        manifest = json.loads(manifest_bytes, object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, ValueError) as error:
        raise BundleUnavailable("candidate manifest invalid") from error
    if not isinstance(manifest, dict):
        raise BundleUnavailable("candidate manifest invalid")

    expected_keys = {
        "schema",
        "state",
        "source_repository",
        "source_revision",
        "base_path",
        "production_ready",
        "runtime_api_binding",
        "effectors",
        "unknown_route_policy",
        "reviewed_routes",
        "files",
    }
    if set(manifest) != expected_keys:
        raise BundleUnavailable("candidate manifest fields invalid")
    if (
        manifest["schema"] != SCHEMA
        or manifest["state"] != STATE
        or manifest["source_repository"] != SOURCE_REPOSITORY
        or manifest["source_revision"] != expected_source_revision
        or manifest["base_path"] != BASE_PATH
        or manifest["production_ready"] is not False
        or manifest["runtime_api_binding"] != "UNAVAILABLE"
        or type(manifest["effectors"]) is not int
        or manifest["effectors"] != 0
        or manifest["unknown_route_policy"] != UNKNOWN_ROUTE_POLICY
        or manifest["reviewed_routes"] != list(REVIEWED_ROUTES)
    ):
        raise BundleUnavailable("candidate manifest contract mismatch")

    rows = manifest["files"]
    if not isinstance(rows, list) or not 1 <= len(rows) <= FILE_COUNT_LIMIT:
        raise BundleUnavailable("candidate file inventory invalid")
    files: dict[str, BoundFile] = {}
    total_size = 0
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"path", "sha256", "size"}:
            raise BundleUnavailable("candidate file record invalid")
        relative = _canonical_relative_path(row["path"])
        digest = row["sha256"]
        size = row["size"]
        if (
            relative == "source.json"
            or relative in files
            or (relative != "index.html" and not _FINGERPRINTED_ASSET.fullmatch(relative))
            or not isinstance(digest, str)
            or not _DIGEST.fullmatch(digest)
            or type(size) is not int
            or not 0 <= size <= FILE_LIMIT
        ):
            raise BundleUnavailable("candidate file record invalid")
        total_size += size
        if total_size > TOTAL_LIMIT:
            raise BundleUnavailable("candidate tree exceeds bound")
        files[relative] = BoundFile(relative, digest, size)
    if "index.html" not in files:
        raise BundleUnavailable("candidate index missing")

    physical = _physical_files(root)
    if physical != set(files) | {"source.json"}:
        raise BundleUnavailable("candidate inventory mismatch")

    payloads: dict[str, bytes] = {}
    for relative, record in files.items():
        payload = _read_regular_file(root, relative, FILE_LIMIT)
        if len(payload) != record.size or hashlib.sha256(payload).hexdigest() != record.sha256:
            raise BundleUnavailable("candidate file digest mismatch")
        payloads[relative] = payload
    _validate_static_assets(payloads)

    return BoundBundle(
        source_revision=expected_source_revision,
        manifest_sha256=manifest_sha256,
        manifest_bytes=manifest_bytes,
        files=MappingProxyType(dict(files)),
        payloads=MappingProxyType(dict(payloads)),
        reviewed_routes=REVIEWED_ROUTES,
        unknown_route_policy=UNKNOWN_ROUTE_POLICY,
    )


def _headers(
    cache_control: str,
    *,
    bundle: BoundBundle | None = None,
    unavailable: bool = False,
) -> dict[str, str]:
    headers = {
        "Cache-Control": cache_control,
        "Content-Security-Policy": _CSP,
        "Permissions-Policy": _PERMISSIONS_POLICY,
        "Referrer-Policy": "no-referrer",
        "X-Content-Type-Options": "nosniff",
        "X-Robots-Tag": "noindex, nofollow, noarchive",
        "X-SZL-Candidate-State": "UNAVAILABLE" if unavailable else STATE,
    }
    if bundle is not None and not unavailable:
        headers["X-SZL-Platform-Source-Revision"] = bundle.source_revision
        headers["X-SZL-Candidate-Manifest-SHA256"] = bundle.manifest_sha256
    return headers


def _response(
    payload: bytes,
    *,
    status_code: int,
    media_type: str,
    headers: dict[str, str],
    head: bool,
) -> Response:
    headers = {**headers, "Content-Length": str(len(payload))}
    return Response(
        content=b"" if head else payload,
        status_code=status_code,
        media_type=media_type,
        headers=headers,
    )


def _json(
    document: dict[str, object],
    *,
    status_code: int,
    headers: dict[str, str],
    head: bool,
) -> Response:
    payload = json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return _response(
        payload,
        status_code=status_code,
        media_type="application/json",
        headers=headers,
        head=head,
    )


def create_responder(
    root: Path,
    *,
    expected_source_revision: str,
    expected_manifest_sha256: str,
):
    root = Path(root)
    try:
        bundle = load_bundle(
            root,
            expected_source_revision=expected_source_revision,
            expected_manifest_sha256=expected_manifest_sha256,
        )
    except BundleUnavailable:
        bundle = None

    def respond(candidate_path: str, *, head: bool, method: str = "GET") -> Response:
        if method not in {"GET", "HEAD"}:
            headers = _headers(
                "no-store, no-transform",
                bundle=bundle,
                unavailable=bundle is None,
            )
            headers["Allow"] = "GET, HEAD"
            return _json(
                {"state": "METHOD_NOT_ALLOWED"},
                status_code=405,
                headers=headers,
                head=False,
            )
        if bundle is None:
            return _json(
                {
                    "effectors": 0,
                    "reason": "platform candidate bundle unavailable",
                    "state": "UNAVAILABLE",
                },
                status_code=503,
                headers=_headers("no-store, no-transform", unavailable=True),
                head=head,
            )

        try:
            relative = _request_path(candidate_path)
        except BundleUnavailable:
            return _json(
                {"state": "NOT_FOUND"},
                status_code=404,
                headers=_headers("no-store, no-transform", bundle=bundle),
                head=head,
            )

        if relative == "source.json":
            return _response(
                bundle.manifest_bytes,
                status_code=200,
                media_type="application/json",
                headers=_headers("no-store, no-transform", bundle=bundle),
                head=head,
            )
        if relative in bundle.files:
            payload = bundle.payloads[relative]
            media_type = mimetypes.guess_type(relative)[0] or "application/octet-stream"
            return _response(
                payload,
                status_code=200,
                media_type=media_type,
                headers=_headers("no-store, no-transform", bundle=bundle),
                head=head,
            )

        route = "/" + relative if relative else "/"
        if route in bundle.reviewed_routes:
            payload = bundle.payloads["index.html"]
            return _response(
                payload,
                status_code=200,
                media_type="text/html",
                headers=_headers("no-store, no-transform", bundle=bundle),
                head=head,
            )

        return _json(
            {"state": "NOT_FOUND"},
            status_code=404,
            headers=_headers("no-store, no-transform", bundle=bundle),
            head=head,
        )

    return respond


class _CandidateEndpoint:
    """ASGI endpoint that fully owns its path for every HTTP method."""

    def __init__(self, responder, fixed_path: str | None) -> None:
        self._responder = responder
        self._fixed_path = fixed_path

    async def __call__(self, scope, receive, send) -> None:
        method = str(scope.get("method", ""))
        candidate_path = self._fixed_path
        if candidate_path is None:
            candidate_path = str(scope.get("path_params", {}).get("candidate_path", ""))
        response = self._responder(
            candidate_path,
            head=method == "HEAD",
            method=method,
        )
        await response(scope, receive, send)


async def _reject_candidate_websocket(websocket) -> None:
    """Close every WebSocket handshake in the candidate-owned namespace."""
    await websocket.close(code=1008, reason="platform candidate is static")


def register(
    app,
    root: Path,
    *,
    expected_source_revision: str,
    expected_manifest_sha256: str,
) -> dict[str, object]:
    """Register the static preview namespace ahead of every prior route."""
    registration = getattr(app.state, "platform_candidate_preview", None)
    # Registration identity must not inspect or follow the candidate tree.  A
    # broken or cyclic symlink is an unavailable bundle, not an application
    # startup failure; the fd-relative loader below remains responsible for
    # rejecting every symlink with O_NOFOLLOW.
    identity = (
        os.path.abspath(os.fspath(root)),
        expected_source_revision,
        expected_manifest_sha256,
    )
    if registration is not None:
        if registration["identity"] != identity:
            raise RuntimeError("platform candidate preview already registered differently")
        return registration["result"]

    owned_paths = {PREFIX, PREFIX + "/{candidate_path:path}"}
    collisions = [
        route.path
        for route in app.router.routes
        if isinstance(getattr(route, "path", None), str)
        and (
            route.path in owned_paths
            or route.path.startswith(PREFIX + "/")
        )
    ]
    if collisions:
        raise RuntimeError("platform candidate preview route collision")

    responder = create_responder(
        root,
        expected_source_revision=expected_source_revision,
        expected_manifest_sha256=expected_manifest_sha256,
    )
    prior = list(app.router.routes)

    added = [
        Route(
            PREFIX,
            _CandidateEndpoint(responder, ""),
            methods=None,
            include_in_schema=False,
            name="platform_candidate_preview_root",
        ),
        Route(
            PREFIX + "/{candidate_path:path}",
            _CandidateEndpoint(responder, None),
            methods=None,
            include_in_schema=False,
            name="platform_candidate_preview_path",
        ),
        WebSocketRoute(
            PREFIX,
            _reject_candidate_websocket,
            name="platform_candidate_preview_websocket_root",
        ),
        WebSocketRoute(
            PREFIX + "/{candidate_path:path}",
            _reject_candidate_websocket,
            name="platform_candidate_preview_websocket_path",
        ),
    ]
    # The preview claims its complete prefix.  Put its exact root and catch-all
    # ahead of every prior route so dynamic patterns cannot shadow source.json
    # or an asset-shaped path.  Existing routes keep their relative order.
    app.router.routes[:] = added + prior
    result = {"module": "routers.platform_candidate_preview", "routes": len(added), "read_only": True}
    app.state.platform_candidate_preview = {"identity": identity, "result": result}
    return result
