#!/usr/bin/env python3
"""Fail-closed pin check for a vendored directory. Standard library only; run with `python3 -I -B`.

The pin file (default proofs/UPSTREAM_PIN.json, schema szl.upstream_pin/v1) records:
  upstream.repo, upstream.commit  GitHub repository and FULL 40-hex commit the copy was taken from
  vendored_prefix                 repository-relative directory holding the copy, ending in "/"
  files                           sha256 of EVERY file under the prefix (path relative to the prefix)
  local_deltas                    files that intentionally differ from upstream ("modified", with the upstream
                                  sha256) or do not exist upstream ("added"); each repeats its sha256 and
                                  gives a non-empty reason
  omitted_upstream                upstream files intentionally not vendored: upstream sha256 and reason

Local mode (default; no network) exits 1 if: the pin file is missing or malformed (bad JSON, duplicate
keys, unknown keys, wrong schema, short commit, unsafe paths, inconsistent deltas or omissions); the prefix
directory is missing; a pinned file is missing; an unpinned file exists under the prefix (extra); any file's
sha256 differs from the pin (changed, declared deltas included); or a symlink is found under the prefix.

--upstream also fetches https://codeload.github.com/<repo>/tar.gz/<commit> and exits 1 if: the archive
cannot be read or names a different commit; it contains links; a non-delta file is absent upstream or
differs from upstream; a "modified" delta is absent upstream, equals upstream, or its recorded upstream
sha256 is wrong; an "added" delta exists upstream; an upstream file is neither vendored nor a declared
omission; or a declared omission is absent upstream or has a different sha256.
--upstream-archive PATH reads a local .tar.gz instead (offline use and tests; it binds the commit only as
far as the archive's own pax header can, so the network mode is the authoritative one).

--generate writes a pin from the tree plus the upstream archive. It refuses (exit 1) when a delta or an
omission has no reason in --reasons (JSON object: path -> reason) or when --reasons names a path that is
neither, so every declaration stays deliberate and exact.

Exit 0 only when every check passed. Every failure, including bad usage, exits 1.
Hashes cover raw bytes: check out with LF line endings (core.autocrlf=false) or the check fails.

Usage:
  python3 -I -B vendored_pin_check.py [--pin proofs/UPSTREAM_PIN.json] [--root .] [--upstream | --upstream-archive X.tar.gz] [--json report.json]
  python3 -I -B vendored_pin_check.py --generate --repo OWNER/NAME --commit SHA40 --prefix DIR/ --reasons reasons.json --out PIN [--root .] [--upstream-archive X.tar.gz]
"""
import argparse, hashlib, json, os, re, sys, tarfile, time, urllib.request

SCHEMA = "szl.upstream_pin/v1"
TOP_KEYS = {"schema", "upstream", "vendored_prefix", "files", "local_deltas", "omitted_upstream", "generated_utc", "note"}
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


class Failures(list):
    def add(self, code, detail):
        self.append({"code": code, "detail": str(detail)})


def sha256(b):
    return hashlib.sha256(b).hexdigest()


def safe_rel(p):
    """Forward-slash relative path with no drive, backslash, slash at the start, '.', '..' or empty segment."""
    if not isinstance(p, str) or not p or "\\" in p or ":" in p or p.startswith("/") or "\x00" in p:
        return False
    return all(s not in ("", ".", "..") for s in p.split("/"))


def _reject_duplicates(pairs):
    keys = [k for k, _ in pairs]
    dup = sorted({k for k in keys if keys.count(k) > 1})
    if dup:  # guard:PIN_DUPLICATE_KEYS
        raise ValueError(f"duplicate JSON keys {dup}")
    return dict(pairs)


def validate(pin):
    """Return a list of (code, detail) problems; an empty list means the pin is well formed."""
    P = []
    if not isinstance(pin, dict):  # guard:PIN_NOT_OBJECT
        return [("PIN_NOT_OBJECT", "top level must be a JSON object")]
    unknown = sorted(set(pin) - TOP_KEYS)
    if unknown:  # guard:PIN_UNKNOWN_KEYS
        P.append(("PIN_UNKNOWN_KEYS", unknown))
    if pin.get("schema") != SCHEMA:  # guard:PIN_SCHEMA
        P.append(("PIN_SCHEMA", f"schema must be {SCHEMA}"))
    up = pin.get("upstream")
    up = up if isinstance(up, dict) else {}
    if set(up) != {"repo", "commit"} or not REPO_RE.match(str(up.get("repo", ""))):  # guard:PIN_REPO
        P.append(("PIN_REPO", "upstream must be exactly {repo: owner/name, commit}"))
    if not HEX40.match(str(up.get("commit", ""))):  # guard:PIN_COMMIT
        P.append(("PIN_COMMIT", "upstream.commit must be a full 40-hex commit"))
    pre = pin.get("vendored_prefix")
    if not (isinstance(pre, str) and pre.endswith("/") and safe_rel(pre[:-1])):  # guard:PIN_PREFIX
        P.append(("PIN_PREFIX", "vendored_prefix must be a safe relative directory ending in '/'"))
    files = pin.get("files")
    if not isinstance(files, dict) or not files:  # guard:PIN_FILES
        P.append(("PIN_FILES", "files must be a non-empty object"))
        files = {}
    bad = sorted(k for k, v in files.items() if not safe_rel(k) or not isinstance(v, str) or not HEX64.match(v))
    if bad:  # guard:PIN_FILE_ENTRY
        P.append(("PIN_FILE_ENTRY", f"unsafe path or non-sha256 value: {bad[:5]}"))
    deltas = pin.get("local_deltas")
    if not isinstance(deltas, dict):  # guard:PIN_DELTAS
        P.append(("PIN_DELTAS", "local_deltas must be an object"))
        deltas = {}
    for k, v in sorted(deltas.items()):
        v = v if isinstance(v, dict) else {}
        reason = v.get("reason")
        if v.get("kind") not in ("modified", "added") or not isinstance(reason, str) or not reason.strip() or set(v) - {"kind", "sha256", "upstream_sha256", "reason"}:  # guard:PIN_DELTA_FIELDS
            P.append(("PIN_DELTA_FIELDS", f"{k}: needs kind modified|added, sha256 and a non-empty reason"))
        if k not in files or v.get("sha256") != files.get(k):  # guard:PIN_DELTA_PINNED
            P.append(("PIN_DELTA_PINNED", f"{k}: a delta must be a pinned file with the same sha256"))
        if (v.get("kind") == "modified") != bool(HEX64.match(str(v.get("upstream_sha256") or ""))):  # guard:PIN_DELTA_UPSTREAM_HASH
            P.append(("PIN_DELTA_UPSTREAM_HASH", f"{k}: a modified delta needs upstream_sha256; an added delta must not have one"))
    om = pin.get("omitted_upstream")
    if not isinstance(om, dict):  # guard:PIN_OMISSIONS
        P.append(("PIN_OMISSIONS", "omitted_upstream must be an object"))
        om = {}
    for k, v in sorted(om.items()):
        v = v if isinstance(v, dict) else {}
        reason = v.get("reason")
        if not safe_rel(k) or not HEX64.match(str(v.get("upstream_sha256", ""))) or not isinstance(reason, str) or not reason.strip() or set(v) - {"upstream_sha256", "reason"}:  # guard:PIN_OMISSION_FIELDS
            P.append(("PIN_OMISSION_FIELDS", f"{k}: needs a safe path, upstream_sha256 and a non-empty reason"))
        if k in files:  # guard:PIN_OMISSION_OVERLAP
            P.append(("PIN_OMISSION_OVERLAP", f"{k}: listed as both vendored and omitted"))
    return P


def load_pin(path, fails):
    if not os.path.isfile(path):  # guard:PIN_MISSING
        fails.add("PIN_MISSING", path)
        return None
    pin, err = None, None
    try:
        with open(path, "rb") as fh:
            pin = json.loads(fh.read().decode("utf-8"), object_pairs_hook=_reject_duplicates)
    except ValueError as e:
        err = e
    if err is not None:  # guard:PIN_JSON
        fails.add("PIN_DUPLICATE_KEYS" if "duplicate JSON keys" in str(err) else "PIN_JSON", err)
        return None
    problems = validate(pin)
    for code, detail in problems:
        fails.add(code, detail)
    return None if problems else pin


def read_tree(root, prefix, fails):
    """Map path-relative-to-prefix -> bytes for every regular file under root/prefix; flags links and absence."""
    base = os.path.join(root, *prefix.rstrip("/").split("/"))
    if not os.path.isdir(base):  # guard:TREE_MISSING
        fails.add("TREE_MISSING", prefix)
        return None
    out = {}
    for dp, dn, fn in os.walk(base):
        for name in sorted(dn):
            if os.path.islink(os.path.join(dp, name)):  # guard:SYMLINK_DIR
                fails.add("SYMLINK", os.path.relpath(os.path.join(dp, name), base).replace(os.sep, "/"))
        dn[:] = sorted(x for x in dn if not os.path.islink(os.path.join(dp, x)))
        for name in sorted(fn):
            p = os.path.join(dp, name)
            rel = os.path.relpath(p, base).replace(os.sep, "/")
            if os.path.islink(p):  # guard:SYMLINK_FILE
                fails.add("SYMLINK", rel)
                continue
            with open(p, "rb") as fh:
                out[rel] = fh.read()
    return out


def check_local(pin, tree, fails):
    files = pin["files"]
    for rel in sorted(set(files) | set(tree)):
        if rel not in tree:  # guard:FILE_MISSING
            fails.add("FILE_MISSING", rel)
        elif rel not in files:  # guard:FILE_EXTRA
            fails.add("FILE_EXTRA", f"{rel}: under the prefix but not pinned")
        elif sha256(tree[rel]) != files[rel]:  # guard:FILE_CHANGED
            fails.add("FILE_CHANGED", f"{rel}: sha256 {sha256(tree[rel])[:12]} != pinned {files[rel][:12]}")


def read_archive(fileobj):
    """(commit from the pax header, {path: bytes}, [link members]) for a GitHub-style source archive."""
    files, links = {}, []
    with tarfile.open(fileobj=fileobj, mode="r|gz") as tf:
        for m in tf:
            rel = m.name.split("/", 1)[1] if "/" in m.name else ""
            if not rel:
                continue
            if m.issym() or m.islnk():
                links.append(rel)
            elif m.isfile():
                files[rel] = tf.extractfile(m).read()
        commit = (tf.pax_headers or {}).get("comment")
    return commit, files, links


def fetch_upstream(repo, commit, archive, fails):
    data, err = None, None
    try:
        if archive:
            with open(archive, "rb") as fh:
                data = read_archive(fh)
        else:
            url = f"https://codeload.github.com/{repo}/tar.gz/{commit}"
            with urllib.request.urlopen(url, timeout=300) as r:
                data = read_archive(r)
    except Exception as e:
        err = f"{type(e).__name__}: {e}"
    if data is None:  # guard:UPSTREAM_FETCH
        fails.add("UPSTREAM_FETCH", err)
        return None
    got, files, links = data
    if got != commit:  # guard:UPSTREAM_COMMIT
        fails.add("UPSTREAM_COMMIT", f"archive names commit {got!r}, pin says {commit}")
        return None
    if links:  # guard:UPSTREAM_LINKS
        fails.add("UPSTREAM_LINKS", f"links are not supported: {sorted(links)[:5]}")
    return files


def check_upstream(pin, up, fails):
    files, deltas, om = pin["files"], pin["local_deltas"], pin["omitted_upstream"]
    for rel in sorted(files):
        d = deltas.get(rel)
        if d is None:
            if rel not in up:  # guard:UPSTREAM_MISSING
                fails.add("UPSTREAM_MISSING", f"{rel}: not in upstream and not declared as an added delta")
            elif sha256(up[rel]) != files[rel]:  # guard:UPSTREAM_DIFFERS
                fails.add("UPSTREAM_DIFFERS", f"{rel}: differs from upstream and is not a declared delta")
        elif d["kind"] == "modified":
            if rel not in up:  # guard:DELTA_MODIFIED_ABSENT
                fails.add("DELTA_MODIFIED_ABSENT", f"{rel}: declared modified but absent upstream")
            elif sha256(up[rel]) == files[rel]:  # guard:DELTA_EQUALS_UPSTREAM
                fails.add("DELTA_EQUALS_UPSTREAM", f"{rel}: declared modified but equals upstream")
            elif sha256(up[rel]) != d["upstream_sha256"]:  # guard:DELTA_UPSTREAM_HASH
                fails.add("DELTA_UPSTREAM_HASH", f"{rel}: recorded upstream_sha256 is not upstream's")
        elif rel in up:  # guard:DELTA_ADDED_EXISTS
            fails.add("DELTA_ADDED_EXISTS", f"{rel}: declared added but exists upstream")
    for rel in sorted(set(up) - set(files)):
        if rel not in om:  # guard:UNDECLARED_OMISSION
            fails.add("UNDECLARED_OMISSION", f"{rel}: upstream file neither vendored nor declared omitted")
    for rel in sorted(om):
        if rel not in up:  # guard:OMISSION_ABSENT
            fails.add("OMISSION_ABSENT", f"{rel}: declared omitted but absent upstream")
        elif sha256(up[rel]) != om[rel]["upstream_sha256"]:  # guard:OMISSION_HASH
            fails.add("OMISSION_HASH", f"{rel}: recorded upstream_sha256 is not upstream's")


def generate(a, fails):
    for name, val, ok in (("--repo", a.repo, REPO_RE.match(a.repo or "")), ("--commit", a.commit, HEX40.match(a.commit or "")),
                          ("--prefix", a.prefix, a.prefix and a.prefix.endswith("/") and safe_rel(a.prefix[:-1])), ("--out", a.out, a.out)):
        if not ok:
            fails.add("USAGE", f"{name} is missing or invalid: {val!r}")
    if fails:
        return None
    reasons = {}
    if a.reasons:
        with open(a.reasons, "rb") as fh:
            reasons = json.loads(fh.read().decode("utf-8"), object_pairs_hook=_reject_duplicates)
    tree = read_tree(a.root, a.prefix, fails)
    up = fetch_upstream(a.repo, a.commit, a.upstream_archive, fails)
    if tree is None or up is None or fails:
        return None
    files = {k: sha256(v) for k, v in sorted(tree.items())}
    deltas, om, unexplained = {}, {}, []
    for k in sorted(tree):
        if k not in up:
            deltas[k] = {"kind": "added", "sha256": files[k], "reason": reasons.get(k, "")}
        elif up[k] != tree[k]:
            deltas[k] = {"kind": "modified", "sha256": files[k], "upstream_sha256": sha256(up[k]), "reason": reasons.get(k, "")}
    for k in sorted(set(up) - set(tree)):
        om[k] = {"upstream_sha256": sha256(up[k]), "reason": reasons.get(k, "")}
    unexplained = sorted(k for k, v in list(deltas.items()) + list(om.items()) if not str(v["reason"]).strip())
    if unexplained:  # guard:GEN_REASON_REQUIRED
        fails.add("GEN_REASON_REQUIRED", f"{len(unexplained)} delta/omission path(s) need a reason: {unexplained[:10]}")
    stale = sorted(set(reasons) - set(deltas) - set(om))
    if stale:  # guard:GEN_STALE_REASON
        fails.add("GEN_STALE_REASON", f"--reasons names paths that are neither deltas nor omissions: {stale[:10]}")
    if fails:
        return None
    pin = {"schema": SCHEMA, "upstream": {"repo": a.repo, "commit": a.commit}, "vendored_prefix": a.prefix,
           "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "note": a.note or "",
           "files": files, "local_deltas": deltas, "omitted_upstream": om}
    for code, detail in validate(pin):
        fails.add(code, detail)
    if fails:
        return None
    with open(a.out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(pin, indent=1, sort_keys=False, ensure_ascii=False) + "\n")
    return pin


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        print(json.dumps({"status": "FAIL", "failures": [{"code": "USAGE", "detail": message}]}))
        sys.exit(1)


def main(argv):
    ap = _Parser(description="Fail-closed vendored-copy pin check.")
    ap.add_argument("--pin", default="proofs/UPSTREAM_PIN.json")
    ap.add_argument("--root", default=".")
    ap.add_argument("--upstream", action="store_true")
    ap.add_argument("--upstream-archive", dest="upstream_archive")
    ap.add_argument("--json", dest="json_out")
    ap.add_argument("--generate", action="store_true")
    ap.add_argument("--repo"); ap.add_argument("--commit"); ap.add_argument("--prefix")
    ap.add_argument("--reasons"); ap.add_argument("--out"); ap.add_argument("--note")
    a = ap.parse_args(argv)
    fails = Failures()
    summary = {}
    try:
        if a.generate:
            pin = generate(a, fails)
            if pin is not None:
                summary = {"mode": "generate", "out": a.out, "files": len(pin["files"]), "local_deltas": len(pin["local_deltas"]), "omitted_upstream": len(pin["omitted_upstream"])}
        else:
            pin_path = a.pin if os.path.isabs(a.pin) else os.path.join(a.root, a.pin)
            pin = load_pin(pin_path, fails)
            if pin is not None:
                tree = read_tree(a.root, pin["vendored_prefix"], fails)
                if tree is not None:
                    check_local(pin, tree, fails)
                    summary = {"mode": "local", "files_pinned": len(pin["files"]), "files_on_disk": len(tree), "local_deltas": len(pin["local_deltas"]),
                               "omitted_upstream": len(pin["omitted_upstream"]), "upstream": pin["upstream"], "vendored_prefix": pin["vendored_prefix"]}
                if a.upstream or a.upstream_archive:
                    up = fetch_upstream(pin["upstream"]["repo"], pin["upstream"]["commit"], a.upstream_archive, fails)
                    if up is not None:
                        check_upstream(pin, up, fails)
                        summary.update({"mode": "local+upstream", "upstream_files": len(up), "upstream_source": a.upstream_archive and "archive" or "codeload"})
    except Exception as e:
        fails.add("INTERNAL_ERROR", f"{type(e).__name__}: {e}")
    status = "FAIL" if fails else "PASS"
    report = {"status": status, "failures": list(fails), "summary": summary}
    if a.json_out:
        with open(a.json_out, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(report, fh, indent=1)
    print(status, json.dumps(summary, sort_keys=True))
    for f in fails[:50]:
        print(f"  {f['code']}: {f['detail']}")
    if len(fails) > 50:
        print(f"  ... {len(fails) - 50} more")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
