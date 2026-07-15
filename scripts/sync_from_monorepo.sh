#!/usr/bin/env bash
# sync_from_monorepo.sh — szl-holdings/platform is the explicit source of truth
# for every vendored file in this flagship repo (STATUS.md open action, landed).
#
# Reads vendor.manifest.json (repo root): { monorepo, pin, files: { <local>: { source, header } } }
# `pin` MUST be a full 40-hex commit SHA for check/sync (deterministic, fail-loud);
# use `pin <ref>` to freeze one.
#
# Modes:
#   check                  verify every vendored file is byte-identical to monorepo@pin.
#                          For header:true entries the exact canonical 2-line attribution
#                          header (if present) is removed before comparison; anything
#                          header-shaped but non-canonical FAILS as tamper. Missing
#                          headers WARN — flip to --strict-headers after the first `sync`.
#   check --strict-headers same, but a missing attribution header is a FAILURE
#   sync                   refresh every vendored file from monorepo@pin and apply
#                          attribution headers to header-eligible files
#   pin <ref>              resolve <ref> (e.g. main) to a commit SHA and write it as pin
#
# Source resolution (no silent fallback — doctrine):
#   PLATFORM_DIR=<path to local platform checkout>  -> read files from disk, fail loud if absent
#   otherwise                                       -> fetch raw.githubusercontent.com at pin
#
# Exit codes: 0 clean · 1 drift/tamper/missing · 2 usage or manifest error
set -euo pipefail
cd "$(dirname "$0")/.."

exec python3 - "$@" <<'PY'
import hashlib, json, os, re, stat, sys, urllib.parse, urllib.request

MANIFEST = "vendor.manifest.json"
if not os.path.exists(MANIFEST):
    print(f"FATAL: {MANIFEST} not found at repo root", file=sys.stderr); sys.exit(2)
m = json.load(open(MANIFEST))
MONO, PIN, FILES = m["monorepo"], m["pin"], m["files"]

args = sys.argv[1:]
mode = args[0] if args else "check"
strict = "--strict-headers" in args

COMMENT = {  # extension -> (prefix, suffix)
    **{e: ("# ", "") for e in ("py sh bash yml yaml toml ps1 cfg ini editorconfig gitattributes txt").split()},
    **{e: ("// ", "") for e in ("js ts tsx jsx").split()},
    "css": ("/* ", " */"), "md": ("<!-- ", " -->"), "html": ("<!-- ", " -->"), "lean": ("-- ", ""),
}
DO_NOT_EDIT = "DO NOT EDIT HERE. Edit in the monorepo, then run scripts/sync_from_monorepo.sh sync."

def ext_of(p):
    b = os.path.basename(p)
    if b.startswith(".") and "." not in b[1:]: return b[1:]
    return b.rsplit(".", 1)[-1].lower() if "." in b else ""

def header_lines(src, pin, ext):
    pre, suf = COMMENT[ext]
    return [
        f"{pre}VENDORED FROM {MONO}@{pin} — {src}{suf}\n",
        f"{pre}{DO_NOT_EDIT}{suf}\n",
    ]

def header_applicable(upstream: bytes) -> bool:
    """Headers are only applied when they can round-trip byte-exactly:
    UTF-8 text, and not a degenerate one-line shebang file without newline."""
    try: t = upstream.decode("utf-8")
    except UnicodeDecodeError: return False
    if t.startswith("#!") and "\n" not in t: return False
    return True

def split_header(data: bytes, src: str, ext: str):
    """For header-eligible files only. Returns (body, status):
    status ∈ {"ok", "missing", "malformed"}. Only the exact canonical 2-line
    header (any hex pin) is removed; header-shaped-but-wrong = malformed (tamper)."""
    if ext not in COMMENT: return data, "missing"
    try: text = data.decode("utf-8")
    except UnicodeDecodeError: return data, "missing"
    lines = text.splitlines(keepends=True)
    i = 1 if lines and lines[0].startswith("#!") else 0
    if i >= len(lines) or "VENDORED FROM" not in lines[i]:
        return data, "missing"
    pre, suf = COMMENT[ext]
    exp1 = re.compile(
        r"^" + re.escape(pre) + r"VENDORED FROM " + re.escape(MONO)
        + r"@[0-9a-f]{7,40} — " + re.escape(src) + re.escape(suf) + r"$")
    l1 = lines[i].rstrip("\r\n")
    l2 = lines[i + 1].rstrip("\r\n") if i + 1 < len(lines) else None
    if not exp1.match(l1) or l2 != f"{pre}{DO_NOT_EDIT}{suf}":
        return data, "malformed"
    body = "".join(lines[:i]) + "".join(lines[i + 2:])
    return body.encode("utf-8"), "ok"

def resolve_ref(ref):
    req = urllib.request.Request(
        f"https://api.github.com/repos/{MONO}/commits/{ref}",
        headers={"Accept": "application/vnd.github.sha", "User-Agent": "sync-from-monorepo"})
    tok = os.environ.get("GITHUB_TOKEN")
    if tok: req.add_header("Authorization", f"Bearer {tok}")
    return urllib.request.urlopen(req, timeout=30).read().decode().strip()

def fetch_source(path, pin):
    pdir = os.environ.get("PLATFORM_DIR")
    if pdir:
        full = os.path.join(pdir, path)
        if not os.path.exists(full):
            print(f"FATAL: PLATFORM_DIR set but {full} missing — refusing network fallback", file=sys.stderr)
            sys.exit(1)
        return open(full, "rb").read()
    url = f"https://raw.githubusercontent.com/{MONO}/{pin}/{urllib.parse.quote(path)}"
    req = urllib.request.Request(url, headers={"User-Agent": "sync-from-monorepo"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()

if mode == "pin":
    ref = next((a for a in args[1:] if not a.startswith("-")), None)
    if not ref: print("usage: sync_from_monorepo.sh pin <ref>", file=sys.stderr); sys.exit(2)
    sha = resolve_ref(ref)
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        print(f"FATAL: resolved '{ref}' to non-SHA '{sha}'", file=sys.stderr); sys.exit(2)
    m["pin"] = sha
    json.dump(m, open(MANIFEST, "w"), indent=2); open(MANIFEST, "a").write("\n")
    print(f"pinned {MONO}@{sha} (from {ref})"); sys.exit(0)

if mode not in ("check", "sync"):
    print(f"unknown mode: {mode}", file=sys.stderr); sys.exit(2)

if not re.fullmatch(r"[0-9a-f]{40}", str(PIN)):
    print(f"FATAL: manifest pin '{PIN}' is not a full 40-hex commit SHA. "
          f"Run scripts/sync_from_monorepo.sh pin main to freeze one "
          f"(doctrine: checks must be deterministic — no moving refs).", file=sys.stderr)
    sys.exit(2)
pin = PIN

fails, warns = 0, 0
for local, entry in sorted(FILES.items()):
    src, want_header = entry["source"], entry.get("header", False)
    try:
        upstream = fetch_source(src, pin)
    except Exception as e:
        print(f"FAIL  {local}: cannot fetch {src}@{pin[:12]}: {e}"); fails += 1; continue

    if mode == "sync":
        out = upstream
        applied = want_header and header_applicable(upstream)
        if want_header and not applied:
            print(f"NOTE  {local}: header:true but not header-applicable (binary or "
                  f"one-line shebang) — syncing verbatim, no header")
        if applied:
            ext = ext_of(local)
            body = upstream.decode("utf-8")
            lines = body.splitlines(keepends=True)
            if lines and lines[0].startswith("#!"):
                first = lines[0] if lines[0].endswith("\n") else lines[0] + "\n"
                out = (first + "".join(header_lines(src, pin, ext)) + "".join(lines[1:])).encode("utf-8")
            else:
                out = ("".join(header_lines(src, pin, ext)) + body).encode("utf-8")
        prev_mode = os.stat(local).st_mode if os.path.exists(local) else None
        os.makedirs(os.path.dirname(local) or ".", exist_ok=True)
        open(local, "wb").write(out)
        if prev_mode: os.chmod(local, stat.S_IMODE(prev_mode))
        print(f"SYNCED {local} <- {src}@{pin[:12]}{' (+header)' if applied else ''}")
        continue

    # check
    if not os.path.exists(local):
        print(f"FAIL  {local}: missing locally (source {src})"); fails += 1; continue
    data = open(local, "rb").read()
    up_sha = hashlib.sha256(upstream).hexdigest()
    if not want_header:
        if hashlib.sha256(data).hexdigest() != up_sha:
            print(f"FAIL  {local}: DRIFT from {src}@{pin[:12]} — edit the monorepo, not the flagship"); fails += 1
        continue
    body, status = split_header(data, src, ext_of(local))
    if status == "malformed":
        print(f"FAIL  {local}: header-shaped lines that do not match the canonical attribution "
              f"header — tamper-shaped, refusing to strip"); fails += 1; continue
    if hashlib.sha256(body).hexdigest() != up_sha:
        print(f"FAIL  {local}: DRIFT from {src}@{pin[:12]} — edit the monorepo, not the flagship"); fails += 1; continue
    if status == "missing" and header_applicable(upstream):
        msg = f"{local}: byte-identical but missing attribution header (run sync)"
        if strict: print(f"FAIL  {msg}"); fails += 1
        else: print(f"WARN  {msg}"); warns += 1

total = len(FILES)
print(f"\n{mode}: {total} vendored files · {fails} failures · {warns} warnings · monorepo={MONO}@{pin[:12]}")
sys.exit(1 if fails else 0)
PY
