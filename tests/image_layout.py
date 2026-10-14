#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Project the runtime image's /app tree from the Dockerfile COPY set.

Tests that run from the source checkout see files the image never ships (the
homepage stylesheet 404 came from a route that read ``console/assets`` while
the image installs ``console/`` at ``static/``).  This module derives the exact
installed layout so a test can boot the app against it instead.

Fail closed: any Dockerfile or .dockerignore construct this projection does
not model raises ``LayoutError`` rather than producing a partial tree.
"""
import os
import posixpath
import re
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

RUNTIME_STAGE = "runtime"
RUNTIME_ROOT = "/app"


class LayoutError(ValueError):
    pass


def _logical_lines(text):
    lines, buf = [], ""
    for raw in text.splitlines():
        if not buf and (not raw.strip() or raw.lstrip().startswith("#")):
            continue
        if buf and raw.lstrip().startswith("#"):
            continue
        if raw.rstrip().endswith("\\"):
            buf += raw.rstrip()[:-1] + " "
            continue
        lines.append(buf + raw)
        buf = ""
    if buf:
        raise LayoutError("dangling line continuation")
    return lines


def runtime_copies(dockerfile_text):
    """Return [(sources, destination)] for every COPY in the runtime stage."""
    stage, workdir, copies, heredoc = None, None, [], None
    for line in _logical_lines(dockerfile_text):
        if heredoc is not None:
            if line.strip() == heredoc:
                heredoc = None
            continue
        parts = line.strip().split(None, 1)
        instruction = parts[0].upper()
        arguments = parts[1] if len(parts) > 1 else ""
        if instruction == "RUN":
            marker = re.search(r"<<-?'?\"?([A-Za-z_][A-Za-z0-9_]*)", arguments)
            if marker:
                heredoc = marker.group(1)
            continue
        if instruction == "FROM":
            tokens = arguments.split()
            stage = tokens[2] if len(tokens) == 3 and tokens[1].upper() == "AS" else None
            workdir = None
            continue
        if stage != RUNTIME_STAGE:
            continue
        if instruction == "WORKDIR":
            workdir = arguments.strip()
        elif instruction == "ADD":
            raise LayoutError("ADD is not modelled: " + line)
        elif instruction == "COPY":
            if workdir != RUNTIME_ROOT:
                raise LayoutError("runtime COPY before WORKDIR " + RUNTIME_ROOT)
            if arguments.startswith("[") or any(c in arguments for c in "\"'*?["):
                raise LayoutError("COPY form is not modelled: " + line)
            tokens = arguments.split()
            if any(t.startswith("--") for t in tokens) or len(tokens) < 2:
                raise LayoutError("COPY flags are not modelled: " + line)
            *sources, destination = tokens
            if len(sources) > 1 and not destination.endswith("/"):
                raise LayoutError("multi-source COPY needs a directory destination: " + line)
            target = posixpath.normpath(posixpath.join(workdir, destination))
            copies.append(([s[2:] if s.startswith("./") else s for s in sources],
                           target + "/" if destination.endswith("/") else target))
    if heredoc is not None:
        raise LayoutError("unterminated heredoc")
    if not copies:
        raise LayoutError("runtime stage has no COPY instructions")
    return copies


def _ignore_regex(pattern):
    pattern = pattern.strip("/")
    out, i = "", 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out += "(?:.*/)?"
            i += 3
        elif pattern.startswith("**", i):
            out += ".*"
            i += 2
        elif pattern[i] == "*":
            out += "[^/]*"
            i += 1
        elif pattern[i] == "?":
            out += "[^/]"
            i += 1
        else:
            out += re.escape(pattern[i])
            i += 1
    return re.compile(out + r"\Z")


def dockerignore_matcher(text):
    regexes = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("!") or "[" in line or "\\" in line:
            raise LayoutError(".dockerignore construct is not modelled: " + line)
        regexes.append(_ignore_regex(line))

    def ignored(path):
        parts = path.split("/")
        prefixes = ["/".join(parts[:n]) for n in range(1, len(parts) + 1)]
        return any(rx.match(p) for rx in regexes for p in prefixes)

    return ignored


def tracked_files(root):
    out = subprocess.run(["git", "-C", str(root), "ls-files", "-z"],
                         check=True, capture_output=True).stdout
    return sorted(p for p in out.decode("utf-8").split("\0") if p)


def installed_layout(root):
    """Map each installed path (relative to /app) to its repo source path."""
    root = Path(root)
    copies = runtime_copies((root / "Dockerfile").read_text(encoding="utf-8"))
    ignored = dockerignore_matcher((root / ".dockerignore").read_text(encoding="utf-8"))
    context = [p for p in tracked_files(root) if not ignored(p) and (root / p).is_file()]
    context_set = set(context)
    layout = {}
    for sources, destination in copies:
        for source in sources:
            source = source.rstrip("/")
            if source in context_set:
                if destination.endswith("/"):
                    target = posixpath.join(destination, posixpath.basename(source))
                else:
                    target = destination
                matches = [(source, target)]
            else:
                prefix = source + "/"
                matches = [(p, posixpath.join(destination, p[len(prefix):]))
                           for p in context if p.startswith(prefix)]
                if not matches:
                    raise LayoutError("COPY source missing from build context: " + source)
            for path, target in matches:
                target = posixpath.normpath(target)
                if not target.startswith(RUNTIME_ROOT + "/"):
                    continue  # build-only inputs such as /tmp/requirements-runtime.txt
                layout[target[len(RUNTIME_ROOT) + 1:]] = path
    return layout


def materialize(root, layout, destination):
    """Copy (never link) the installed tree so the app cannot mutate the checkout."""
    root, destination = Path(root), Path(destination)
    for installed, source in layout.items():
        target = destination / installed
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / source, target)
    return destination


SAME_ORIGIN_HOSTS = frozenset({"a-11-oy.com", "www.a-11-oy.com"})
_LINK_RELS = frozenset({"stylesheet", "icon", "shortcut", "apple-touch-icon", "mask-icon",
                        "preload", "modulepreload", "prefetch", "manifest"})
_SRC_ATTRS = {"script": ("src",), "img": ("src", "srcset"), "source": ("src", "srcset"),
              "iframe": ("src",), "video": ("src", "poster"), "audio": ("src",),
              "embed": ("src",), "object": ("data",), "input": ("src",), "track": ("src",)}
_SCRIPT_SRC = re.compile(r"""\.src\s*=\s*(["'])([^"']+)\1""")
_CONTENT_TYPES = {".css": "text/css", ".js": "javascript", ".mjs": "javascript",
                  ".svg": "image/svg+xml", ".html": "text/html", ".png": "image/png",
                  ".json": "json", ".woff2": "font/woff2"}


def _same_origin_path(url):
    url = (url or "").strip()
    if not url or url.startswith(("#", "data:", "blob:", "javascript:", "mailto:")):
        return None
    parts = urlsplit(url)
    if parts.scheme or parts.netloc:
        if parts.scheme not in ("http", "https", "") or parts.hostname not in SAME_ORIGIN_HOSTS:
            return None
    if not parts.path.startswith("/"):
        raise LayoutError("relative subresource URL is ambiguous on the front door: " + url)
    return parts.path + ("?" + parts.query if parts.query else "")


class _Subresources(HTMLParser):
    """Every URL the browser fetches while rendering the page (not navigations)."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.urls, self._in_script = [], False

    def _add(self, value, srcset=False):
        candidates = [c.strip().split()[0] for c in value.split(",") if c.strip()] if srcset else [value]
        for candidate in candidates:
            path = _same_origin_path(candidate)
            if path is not None:
                self.urls.append(path)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "link" and set((attrs.get("rel") or "").lower().split()) & _LINK_RELS:
            self._add(attrs.get("href"))
        for name in _SRC_ATTRS.get(tag, ()):
            if attrs.get(name):
                self._add(attrs[name], srcset=name == "srcset")
        if tag == "meta" and (attrs.get("property") or attrs.get("name") or "").lower() in (
                "og:image", "twitter:image"):
            self._add(attrs.get("content"))
        self._in_script = tag == "script" and not attrs.get("src")

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self._in_script = False

    def handle_endtag(self, tag):
        if tag == "script":
            self._in_script = False

    def handle_data(self, data):
        if self._in_script:
            for _, url in _SCRIPT_SRC.findall(data):
                self._add(url)


def subresource_paths(html):
    parser = _Subresources()
    parser.feed(html)
    parser.close()
    return sorted(set(parser.urls))


def _insert_only(original, served, max_insertions=16, anchor=64):
    """True when ``served`` is ``original`` plus a few insertions (HTML middleware).

    Linear: walk the common run, and at each divergence resume at the next
    occurrence of the following ``anchor`` original bytes.  Any deletion or
    replacement leaves an anchor that cannot be found, so it fails.
    """
    i = j = insertions = 0
    while i < len(original):
        while i < len(original) and j < len(served) and original[i] == served[j]:
            i += 1
            j += 1
        if i == len(original):
            break
        resume = served.find(original[i:i + anchor], j + 1)
        insertions += 1
        if resume < 0 or insertions > max_insertions:
            return False
        j = resume
    return True


def asset_verdict(url, status, content_type, body, layout, source_root):
    """Explain why ``url`` is not served from the installed file it names, or None.

    The installed file must sit at the URL path (or a mount root above it) and
    the response must be that file's bytes (read from the COPY source, which is
    what COPY installs); HTML documents may only gain insertions.  An SPA
    fallback, a JSON 404 or a path absent from the COPY set all fail.
    """
    if status != 200:
        return "HTTP %s" % status
    rel = urlsplit(url).path.lstrip("/")
    if not rel or rel.endswith("/"):
        rel += "index.html"
    suffix = "." + rel.rsplit(".", 1)[-1] if "." in rel.rsplit("/", 1)[-1] else ""
    expected_type = _CONTENT_TYPES.get(suffix)
    if expected_type and expected_type not in (content_type or "").lower():
        return "content-type %r is not %s" % (content_type, expected_type)
    candidates = [p for p in layout if p == rel or p.endswith("/" + rel)]
    if not candidates:
        return "no installed file for /%s in the Dockerfile COPY set" % rel
    for candidate in candidates:
        data = (Path(source_root) / layout[candidate]).read_bytes()
        if body == data or (expected_type == "text/html" and _insert_only(data, body)):
            return None
    return "body is not the installed bytes of " + ", ".join(sorted(candidates))


def child_main(argv):
    """Run inside the materialized tree: boot serve.py and probe the front door.

    argv: [removed_relpath]. Phase two deletes that installed file and probes
    again so the parent can prove the verdict is sensitive to the image tree.
    """
    import base64
    import json
    import sys

    import serve
    from starlette.testclient import TestClient

    client = TestClient(serve.app, raise_server_exceptions=False)

    def probe(path):
        response = client.get(path)
        return {"status": response.status_code,
                "content_type": response.headers.get("content-type"),
                "body": base64.b64encode(response.content).decode("ascii")}

    report = {"static_dir": str(serve.STATIC_DIR), "front_door": probe("/"), "assets": {}}
    html = base64.b64decode(report["front_door"]["body"]).decode("utf-8", "replace")
    report["subresources"] = subresource_paths(html)
    for path in report["subresources"]:
        report["assets"][path] = probe(path)
    removed = argv[0]
    os.remove(removed)
    report["after_removal"] = {path: probe(path) for path in report["subresources"]}
    sys.stdout.write("\n@@IMAGE-LAYOUT-REPORT@@" + json.dumps(report) + "\n")
    sys.stdout.flush()
