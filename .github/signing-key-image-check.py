#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings
#
# Signing-key image guard.
#
# a11oy signs its release/decision receipts with a PERSISTENT ECDSA P-256
# (secp256r1) key that a11oy_signing_key.py::load_signing_key() reads from a
# mounted Secret. a11oy_dev1_endpoints.py imports that loader. This Dockerfile
# never uses `COPY . .`, so if `COPY a11oy_signing_key.py ...` is ever dropped,
# the module is absent from the image, the import fails, the loader never runs,
# and serve.py silently falls back to a THROWAWAY in-process key that changes on
# every pod restart — which breaks offline verification of every receipt a11oy
# ever signed. This was the live state before this guard.
#
# This check fails the build if EITHER of the two things that keep the loader in
# the image is missing:
#   1. the Dockerfile does not COPY a11oy_signing_key.py into the image, OR
#   2. a11oy_signing_key.py is absent / does not expose a working load_signing_key
#      (importable and returns a usable ECDSA P-256 key, not an error).
#
# Modes:
#   (default)     run the real check against this repo (used by the static CI job).
#   --self-test   feed the Dockerfile-COPY parser pristine + broken fixtures and
#                 assert it PASSES / FAILS (catches a neutered parser that would go
#                 green while guarding nothing). No Docker required.

import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODULE = "a11oy_signing_key.py"


def err(msg):
    print("::error::" + msg)
    return 1


def _logical_lines(text):
    """Yield Dockerfile instructions, joining trailing-backslash continuations."""
    buf = ""
    for raw in text.splitlines():
        line = raw.rstrip("\n")
        stripped = line.strip()
        if not buf and (not stripped or stripped.startswith("#")):
            continue
        if line.rstrip().endswith("\\"):
            buf += line.rstrip()[:-1] + " "
            continue
        buf += line
        yield buf
        buf = ""
    if buf:
        yield buf


def dockerfile_copies_module(dockerfile_text, module=MODULE):
    """True if the Dockerfile has a COPY whose source is `module`.

    Ignores `COPY --from=...` (those sources live in another build stage, not the
    repo) and tolerates --chown/--chmod/--link flags and JSON-array form.
    """
    for line in _logical_lines(dockerfile_text):
        m = re.match(r"^\s*COPY\s+(.*)$", line, re.IGNORECASE)
        if not m:
            continue
        rest = m.group(1).strip()
        # JSON-array form: COPY ["src", "dst"]
        if rest.startswith("["):
            toks = re.findall(r'"([^"]*)"', rest)
        else:
            toks = rest.split()
        # Drop flag tokens; --from copies are not from the repo.
        toks = [t for t in toks if not t.startswith("-")]
        if any(t.startswith("--from") for t in rest.split()):
            continue
        if len(toks) < 2:
            continue
        sources = toks[:-1]  # last token is the destination
        for s in sources:
            base = os.path.basename(s.rstrip("/"))
            if base == module or s == module or s == "./" + module:
                return True
    return False


def run_repo_check():
    df = os.path.join(REPO, "Dockerfile")
    if not os.path.isfile(df):
        return err("Dockerfile not found at %s" % df)
    with open(df, "r", encoding="utf-8") as fh:
        dockerfile_text = fh.read()

    if not dockerfile_copies_module(dockerfile_text):
        return err(
            "Dockerfile does not COPY %s into the image. Without it the "
            "load_signing_key import fails and a11oy falls back to an EPHEMERAL "
            "per-boot signing key. Add: COPY %s ./%s"
            % (MODULE, MODULE, MODULE)
        )

    mod_path = os.path.join(REPO, MODULE)
    if not os.path.isfile(mod_path):
        return err(
            "%s is missing from the repo — the Dockerfile COPY would break a "
            "fresh `docker build`." % MODULE
        )

    # The loader must import cleanly and actually produce a usable ECDSA P-256
    # key. (With no Secret mounted it returns a freshly generated ephemeral key —
    # that is fine HERE; the point is that the loader code path works at all. The
    # chart guard separately proves a PERSISTENT key is provisioned + mounted.)
    sys.path.insert(0, REPO)
    try:
        import a11oy_signing_key  # noqa: E402
    except Exception as e:  # pragma: no cover - exercised in CI
        return err("import a11oy_signing_key failed: %r" % (e,))
    if not hasattr(a11oy_signing_key, "load_signing_key"):
        return err("a11oy_signing_key has no load_signing_key()")
    try:
        priv, pub_pem, source, load_err = a11oy_signing_key.load_signing_key()
    except Exception as e:  # pragma: no cover
        return err("load_signing_key() raised: %r" % (e,))
    if load_err:
        return err("load_signing_key() reported an error: %s" % load_err)
    if priv is None or not pub_pem:
        return err(
            "load_signing_key() returned no usable key (source=%r) — cryptography "
            "missing or the loader is broken" % source
        )

    print("OK: Dockerfile COPYs %s and load_signing_key() returns a usable "
          "ECDSA P-256 key (source=%s)" % (MODULE, source))
    return 0


# ── self-test ─────────────────────────────────────────────────────────────────
def _self_test():
    passed = failed = 0

    def case(label, expect, got):
        nonlocal passed, failed
        if expect == got:
            passed += 1
            print("ok   - %s" % label)
        else:
            failed += 1
            print("FAIL - %s (expected %s, got %s)" % (label, expect, got))

    case("per-file COPY detected", True,
         dockerfile_copies_module("COPY a11oy_signing_key.py ./a11oy_signing_key.py"))
    case("COPY with --chown detected", True,
         dockerfile_copies_module("COPY --chown=1000:1000 a11oy_signing_key.py ."))
    case("JSON-array COPY detected", True,
         dockerfile_copies_module('COPY ["a11oy_signing_key.py", "./"]'))
    case("subdir source basename match", True,
         dockerfile_copies_module("COPY src/a11oy_signing_key.py ./a11oy_signing_key.py"))
    case("missing COPY not detected", False,
         dockerfile_copies_module("COPY serve.py ./serve.py\nCOPY other.py ./"))
    case("--from copy is ignored (not from repo)", False,
         dockerfile_copies_module("COPY --from=build a11oy_signing_key.py ./"))
    case("commented COPY is ignored", False,
         dockerfile_copies_module("# COPY a11oy_signing_key.py ./a11oy_signing_key.py"))
    case("continuation-line COPY detected", True,
         dockerfile_copies_module("COPY \\\n  a11oy_signing_key.py \\\n  ./a11oy_signing_key.py"))

    print("\n%d passed, %d failed" % (passed, failed))
    return 1 if failed else 0


if __name__ == "__main__":
    if "--self-test" in sys.argv[1:]:
        sys.exit(_self_test())
    sys.exit(run_repo_check())
