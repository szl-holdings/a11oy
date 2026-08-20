#!/usr/bin/env python3
"""
check_weight_guard.py — the executable core of a pinned-download weight guard.

The root Dockerfile fetches pinned, size/sha256-verified weights for the
local-model ("alloy") demo tier (today: ONE GGUF — Qwen2.5-Coder-0.5B-Instruct
Q4_K_M; tomorrow possibly an ONNX export, a tokenizer blob, etc). History: the
GGUF fetch USED to be a single best-effort `hf_hub_download(...) || echo`, so a
transient download failure silently shipped an image with NO model and the alloy
demo tier degraded to the honest tower-side label with no red signal.

This module is the GENERIC guard logic for ANY such pinned download weight,
lifted OUT of the workflow YAML so it can be exercised by an offline
negative-fixture self-test (scripts/check_weight_guard.test.sh) — the same
`*.py` + `*.test.sh` convention the other a11oy script guards use. A guard that
never fails when it should can rot into a no-op; the self-test proves this one
still goes RED on a deliberately broken input.

ONE engine, MANY weights. Each weight is identified by a Dockerfile ARG prefix
(`--arg-prefix`, default the GGUF weight's prefix so the existing GGUF guard is
behavior-identical). For a prefix `P` the engine reads five pinned ARGs:

    ARG P_REPO=...      huggingface repo id
    ARG P_FILE=...      filename within the repo
    ARG P_REV=...       exact 40-hex commit revision
    ARG P_SHA256=...    64-hex sha256 of the file bytes
    ARG P_SIZE=...      integer byte count

and bounds the fetch region between `ARG P_REPO=` and `ENV P=` (the ENV that
records the on-disk weight path). Guarding a NEW download weight is therefore a
DECLARATIVE change — add those five pins + the `ENV P=` line to the Dockerfile
and point a thin workflow at this script with `--arg-prefix P` — not a whole new
copy of this logic.

Three invariants, each a subcommand:

  assert-fail-closed --dockerfile <f> [--arg-prefix P]
      Static check that the Dockerfile fetch region for this weight stays
      fail-closed: no best-effort `|| echo` / `|| true` / `|| :` mask was
      reintroduced (the original silent-degrade bug), and the fetch still exits
      non-zero on failure (a `sys.exit(1)` on the unverified path). Network-free.

  parse --dockerfile <f> [--arg-prefix P]
      Parse the five pinned ARGs and shape-check them (rev = 40-hex commit,
      sha = 64-hex, size = integer) so a malformed bump fails closed here instead
      of during a 25-minute image build. Prints `key=value` lines to stdout (for
      `>> $GITHUB_OUTPUT`); info to stderr. Network-free.

  verify --file <f> --size <n> --sha256 <hex>
      The lockstep integrity check: a file passes ONLY if its size AND sha256
      both match. This is what keeps rev/size/sha in lockstep — change any one
      without the matching bytes and verify mismatches. Network-free; this is the
      exact predicate the live download path below uses.

  fetch --dockerfile <f> [--arg-prefix P]
      The real guard action: parse + shape-check, then download the weight at the
      pinned revision (OUTSIDE the image build, UNMASKED, with retries) and run
      `verify`. Requires huggingface_hub. This is the only subcommand that touches
      the network.

Exit codes:
  0 — ok / verified
  1 — a guard invariant was violated (mask reintroduced, malformed pin, weight
      missing or integrity mismatch)
  2 — usage / configuration error
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
import time

# The GGUF weight's ARG prefix — the default so the existing GGUF guard is
# behavior-identical when no --arg-prefix is passed.
DEFAULT_ARG_PREFIX = "A11OY_ALLOY_GGUF"

# A best-effort mask on the fetch — the original silent-degrade bug.
MASK = re.compile(r"\|\|[ \t]*(echo|true|:)")

# The trailing `rm -rf .../.cache ... || true` cleanup line legitimately uses
# `|| true`; exclude it so only the FETCH itself is policed.
CACHE_CLEANUP = re.compile(r"rm -rf .*/\.cache")


class Pins:
    """The five pinned ARG names + the fetch-region boundaries for a prefix."""

    def __init__(self, prefix: str) -> None:
        self.prefix = prefix
        self.repo = "%s_REPO" % prefix
        self.file = "%s_FILE" % prefix
        self.rev = "%s_REV" % prefix
        self.sha = "%s_SHA256" % prefix
        self.size = "%s_SIZE" % prefix
        # Region: from the first pinned ARG to the ENV that records the on-disk
        # weight path. Mirrors the awk window the inline guard used.
        self.region_start = re.compile(r"ARG[ \t]+" + re.escape(self.repo) + r"=")
        self.region_end = re.compile(r"^ENV[ \t]+" + re.escape(prefix) + r"=")


def read_text(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except OSError as e:
        sys.stderr.write("::error::Could not read '%s': %s\n" % (path, e))
        sys.exit(2)


def arg_value(text: str, name: str) -> str:
    """Value of the first `ARG <name>=<value>` (no surrounding whitespace)."""
    m = re.search(r"ARG[ \t]+" + re.escape(name) + r"=([^\s]+)", text)
    return m.group(1) if m else ""


def fetch_region(text: str, pins: Pins) -> str:
    """The Dockerfile fetch region for this weight, or '' if not locatable."""
    out: list[str] = []
    started = False
    for line in text.splitlines():
        if pins.region_start.search(line):
            started = True
        if started:
            out.append(line)
        if started and pins.region_end.match(line):
            break
    return "\n".join(out)


# --------------------------------------------------------------------------
# assert-fail-closed
# --------------------------------------------------------------------------
def cmd_assert_fail_closed(text: str, pins: Pins) -> int:
    region = fetch_region(text, pins)
    if not region:
        sys.stderr.write(
            "::error::Could not locate the %s fetch region (ARG "
            "%s ... ENV %s) in the Dockerfile. Update this guard "
            "in lockstep with the pin block.\n"
            % (pins.prefix, pins.repo, pins.prefix)
        )
        return 1

    # Police only the FETCH itself; the cache-cleanup line may use `|| true`.
    fetch_lines = [ln for ln in region.splitlines() if not CACHE_CLEANUP.search(ln)]
    fetch = "\n".join(fetch_lines)

    masked = [ln for ln in fetch_lines if MASK.search(ln)]
    if masked:
        sys.stderr.write(
            "::error::The Dockerfile %s fetch reintroduced a best-effort "
            "'|| echo'/'|| true' mask. That silently ships a model-less image "
            "(the original demo-tier degrade bug). The weight fetch MUST fail "
            "closed.\n" % pins.prefix
        )
        for ln in masked:
            sys.stderr.write("    %s\n" % ln.strip())
        return 1

    if "sys.exit(1)" not in fetch:
        sys.stderr.write(
            "::error::The Dockerfile %s fetch no longer exits non-zero on "
            "failure (expected a 'sys.exit(1)' on the unverified path). It must "
            "fail the build loudly when the weight cannot be verified.\n"
            % pins.prefix
        )
        return 1

    print("OK: Dockerfile %s fetch is unmasked and fails closed." % pins.prefix)
    return 0


# --------------------------------------------------------------------------
# parse
# --------------------------------------------------------------------------
def parse_pins(text: str, pins: Pins) -> dict:
    """Parse + shape-check the five pinned ARGs. Exits 1 on any problem."""
    repo = arg_value(text, pins.repo)
    fname = arg_value(text, pins.file)
    rev = arg_value(text, pins.rev)
    sha = arg_value(text, pins.sha)
    size = arg_value(text, pins.size)

    if not (repo and fname and rev and sha and size):
        sys.stderr.write(
            "::error::Could not parse all five pinned %s ARGs (%s/%s/%s/%s/%s) "
            "from the Dockerfile. If the pin block moved or changed shape, update "
            "this guard in lockstep.\n"
            % (pins.prefix, pins.repo, pins.file, pins.rev, pins.sha, pins.size)
        )
        sys.exit(1)

    if not re.fullmatch(r"[0-9a-f]{40}", rev):
        sys.stderr.write(
            "::error::%s='%s' is not a 40-hex commit revision. A loose pin (e.g. "
            "a branch/tag) lets the weight move under the digest — pin the exact "
            "commit sha.\n" % (pins.rev, rev)
        )
        sys.exit(1)
    if not re.fullmatch(r"[0-9a-f]{64}", sha):
        sys.stderr.write(
            "::error::%s='%s' is not a 64-hex sha256 digest.\n" % (pins.sha, sha)
        )
        sys.exit(1)
    if not re.fullmatch(r"[0-9]+", size):
        sys.stderr.write(
            "::error::%s='%s' is not an integer byte count.\n" % (pins.size, size)
        )
        sys.exit(1)

    return {"repo": repo, "file": fname, "rev": rev, "sha": sha, "size": size}


def cmd_parse(text: str, pins: Pins) -> int:
    parsed = parse_pins(text, pins)
    # key=value to STDOUT (for `>> $GITHUB_OUTPUT`); human note to STDERR.
    print("repo=%s" % parsed["repo"])
    print("file=%s" % parsed["file"])
    print("rev=%s" % parsed["rev"])
    print("sha=%s" % parsed["sha"])
    print("size=%s" % parsed["size"])
    sys.stderr.write(
        "Parsed %s/%s @ %s (size %s, sha256 %s)\n"
        % (parsed["repo"], parsed["file"], parsed["rev"], parsed["size"], parsed["sha"])
    )
    return 0


# --------------------------------------------------------------------------
# verify (the lockstep predicate)
# --------------------------------------------------------------------------
def verify_file(path: str, want_size: int, want_sha: str):
    """Return None if the file matches BOTH size and sha256, else a reason str."""
    if not path or not os.path.exists(path):
        return "missing"
    sz = os.path.getsize(path)
    if sz != want_size:
        return "size %d != expected %d" % (sz, want_size)
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    got = h.hexdigest()
    if got != want_sha.lower():
        return "sha256 %s != expected %s" % (got, want_sha.lower())
    return None


def cmd_verify(path: str, want_size: int, want_sha: str) -> int:
    reason = verify_file(path, want_size, want_sha)
    if reason is None:
        print("OK: %s matches the pinned size (%d) and sha256." % (path, want_size))
        return 0
    sys.stderr.write(
        "::error::Integrity check failed for %s: %s. rev/size/sha256 must move in "
        "lockstep — a bump to any one without the matching bytes fails closed.\n"
        % (path, reason)
    )
    return 1


# --------------------------------------------------------------------------
# fetch (the only networked subcommand)
# --------------------------------------------------------------------------
def cmd_fetch(text: str, pins: Pins) -> int:
    parsed = parse_pins(text, pins)
    try:
        from huggingface_hub import hf_hub_download
    except ImportError as e:
        sys.stderr.write(
            "::error::huggingface_hub is required for 'fetch': %s\n" % e
        )
        return 2

    repo = parsed["repo"]
    fname = parsed["file"]
    rev = parsed["rev"]
    want_sha = parsed["sha"].lower()
    want_size = int(parsed["size"])
    dest = os.path.abspath("weight-guard-dl")
    os.makedirs(dest, exist_ok=True)

    last = None
    for attempt in range(1, 7):
        try:
            p = hf_hub_download(
                repo_id=repo, filename=fname, revision=rev, local_dir=dest
            )
            last = verify_file(p, want_size, want_sha)
            if last is None:
                print(
                    "[weight-guard] %s verified present: %s (%d bytes, sha256 ok, "
                    "rev %s)" % (pins.prefix, fname, want_size, rev[:12]),
                    flush=True,
                )
                return 0
            print(
                "[weight-guard] attempt %d: integrity check failed: %s"
                % (attempt, last),
                flush=True,
            )
            try:
                os.remove(p)
            except OSError:
                pass
        except Exception as e:  # noqa: BLE001 — surface any fetch failure as RED
            last = "%s: %s" % (type(e).__name__, str(e)[:200])
            print(
                "[weight-guard] attempt %d: download failed: %s" % (attempt, last),
                flush=True,
            )
        time.sleep(min(60, 5 * attempt))

    sys.stderr.write(
        "::error::The pinned %s weight could NOT be obtained and verified after "
        "retries: %s. The Dockerfile would ship a model-less image (or, if a "
        "'|| echo' mask is reintroduced, do so silently). Fix the pin so "
        "rev/size/sha256 point at a present, matching weight.\n" % (pins.prefix, last)
    )
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    def add_prefix(p):
        p.add_argument(
            "--arg-prefix",
            default=DEFAULT_ARG_PREFIX,
            help="Dockerfile ARG prefix identifying the weight "
            "(default %(default)s — the GGUF weight).",
        )

    p_assert = sub.add_parser(
        "assert-fail-closed",
        help="static check that the Dockerfile fetch stays fail-closed",
    )
    p_assert.add_argument("--dockerfile", default="Dockerfile")
    add_prefix(p_assert)

    p_parse = sub.add_parser(
        "parse", help="parse + shape-check the five pinned ARGs"
    )
    p_parse.add_argument("--dockerfile", default="Dockerfile")
    add_prefix(p_parse)

    p_verify = sub.add_parser(
        "verify", help="lockstep size+sha256 verify of a local file"
    )
    p_verify.add_argument("--file", required=True)
    p_verify.add_argument("--size", required=True, type=int)
    p_verify.add_argument("--sha256", required=True)

    p_fetch = sub.add_parser(
        "fetch", help="download the pinned weight (unmasked) and verify it"
    )
    p_fetch.add_argument("--dockerfile", default="Dockerfile")
    add_prefix(p_fetch)

    args = parser.parse_args()

    if args.cmd == "assert-fail-closed":
        return cmd_assert_fail_closed(read_text(args.dockerfile), Pins(args.arg_prefix))
    if args.cmd == "parse":
        return cmd_parse(read_text(args.dockerfile), Pins(args.arg_prefix))
    if args.cmd == "verify":
        return cmd_verify(args.file, args.size, args.sha256)
    if args.cmd == "fetch":
        return cmd_fetch(read_text(args.dockerfile), Pins(args.arg_prefix))
    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    sys.exit(main())
