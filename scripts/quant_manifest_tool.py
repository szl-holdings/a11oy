#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 SZL Holdings — Doctrine v11. Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>
"""QUANT_MANIFEST generator — repair quantization drift (Codex v3 program).

Every quantized-model repository ships a QUANT_MANIFEST.json binding it to
its parent: parent repo, exact parent revision SHA (resolved LIVE, never
guessed), converter identity, quantization levels, and per-file SHA-256s from
the Hub itself. A parity-receipt section is scaffolded as BLOCKED until it is
measured: F16-vs-level agreement >= 0.95 on a frozen probe set, run on local
CUDA — never claimed from a cloud sandbox (program doctrine point 2).

Usage:
  python3 scripts/quant_manifest_tool.py --repo SZLHOLDINGS/SZL-Khipu-1.5B-GGUF \
      --parent SZLHOLDINGS/SZL-Khipu-1.5B [--converter llama-quantize] \
      [--write-pr] [--out /path/QUANT_MANIFEST.json]

Honesty: --write-pr opens a Hub PR adding the manifest (never overwrites a
public release). Without it, the manifest is written locally for review.
"""
from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

SCHEMA = "szl.quant-manifest/v1"
PARITY_THRESHOLD = 0.95


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _get_json(api, url: str):
    info = api.get_hf_file_metadata  # noqa: F841  (marker: api is HfApi)
    return None


def fetch_repo_state(session, repo_id: str) -> dict:
    """Live repo state from the Hub: revision + files with LFS sha256s."""
    r = session.get(f"https://huggingface.co/api/models/{repo_id}", timeout=45)
    if r.status_code != 200:
        raise SystemExit(f"repo {repo_id}: HTTP {r.status_code}")
    d = r.json()
    files = []
    for sib in d.get("siblings", []):
        name = sib.get("rfilename", "")
        if not name.endswith(".gguf"):
            continue
        lfs = sib.get("lfs") or {}
        files.append({
            "path": name,
            "size_bytes": lfs.get("size"),
            "sha256": lfs.get("sha256") or sib.get("blobId"),
            "sha256_source": "hub-lfs" if lfs.get("sha256") else "hub-blob-id",
        })
    return {"repo_id": repo_id, "revision": d.get("sha"), "gguf_files": files,
            "last_modified": d.get("lastModified")}


def build_manifest(quant: dict, parent: dict, converter: str, levels: list) -> dict:
    return {
        "schema": SCHEMA,
        "generated_at": _now(),
        "quant_repo": {
            "repo_id": quant["repo_id"],
            "revision": quant["revision"],
            "gguf_files": quant["gguf_files"],
        },
        "parent": {
            "repo_id": parent["repo_id"],
            "revision": parent["revision"],   # LIVE-resolved, never guessed
            "last_modified": parent["last_modified"],
            "note": ("parent revision resolved live at manifest generation; if the parent "
                     "advances past this revision the manifest is stale by definition "
                     "(PARENT_NEWER_THAN_QUANT) and must be regenerated."),
        },
        "converter": {"name": converter, "version": "UNSPECIFIED — set when the "
                      "quantization was actually performed"},
        "quantization_levels": levels,
        "parity_receipt": {
            "status": "BLOCKED",
            "threshold_agreement": PARITY_THRESHOLD,
            "probe_set": "FROZEN — define once, hash, and never regenerate per run",
            "requirement": ("F16 vs each level agreement >= 0.95 plus abstention parity, "
                            "measured on local CUDA hardware"),
            "never_claimed_from": "a cloud sandbox — no run is claimed until it happened",
        },
        "honesty": ("every SHA above is read from the Hub at generation time; the parity "
                    "receipt is BLOCKED until a real local run produces it."),
    }


def main() -> int:
    import requests
    import urllib3
    urllib3.disable_warnings()
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, help="quant repo id")
    ap.add_argument("--parent", required=True, help="parent (unquantized) repo id")
    ap.add_argument("--converter", default="llama-quantize")
    ap.add_argument("--levels", default="Q4_K_M")
    ap.add_argument("--out", default=None)
    ap.add_argument("--write-pr", action="store_true")
    args = ap.parse_args()

    S = requests.Session()
    S.verify = False
    S.headers.update({"user-agent": "Mozilla/5.0"})

    quant = fetch_repo_state(S, args.repo)
    parent = fetch_repo_state(S, args.parent)
    manifest = build_manifest(quant, parent, args.converter, args.levels.split(","))

    out = args.out or f"QUANT_MANIFEST.json"
    Path(out).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"manifest written: {out}")
    print(f"  quant rev : {quant['revision'][:12]} ({len(quant['gguf_files'])} gguf)")
    print(f"  parent rev: {parent['revision'][:12]} (live-resolved)")
    print(f"  parity    : BLOCKED pending local CUDA run (never claimed from a sandbox)")

    if args.write_pr:
        from huggingface_hub import HfApi, CommitOperationAdd
        api = HfApi()
        branch = "quant-manifest"
        api.create_branch(repo_id=args.repo, branch=branch, repo_type="model", exist_ok=True)
        api.create_commit(
            repo_id=args.repo, repo_type="model", revision=branch, create_pr=True,
            commit_message="quant: add QUANT_MANIFEST.json (parity receipt honestly BLOCKED)",
            commit_description=("binds this quant to its parent at the live-resolved revision "
                                "with per-file SHA-256s from the Hub; the parity receipt is "
                                "BLOCKED until a real local CUDA run measures F16-vs-level "
                                "agreement. never claimed from a cloud sandbox."),
            operations=[CommitOperationAdd(
                path_in_repo="QUANT_MANIFEST.json",
                path_or_fileobj=Path(out).read_bytes())],
        )
        print(f"  Hub PR opened on {args.repo} (branch {branch})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
