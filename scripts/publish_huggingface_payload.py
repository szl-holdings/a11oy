#!/usr/bin/env python3
"""Plan, or explicitly apply, the fixed A11oy model payload without deleting files.

Uses the existing HF_TOKEN credential. A successful apply means immutable bytes
were read back; it grants no model, Space, or runtime qualification.
"""

from __future__ import annotations

import argparse
import contextlib
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tempfile
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
TARGET = "SZLHOLDINGS/a11oy-v19-substrate"
REPO_TYPE = "model"
HUB = "https://huggingface.co"
GITHUB = "https://api.github.com/repos/szl-holdings/a11oy"
# These existing provider/BOM files are outside this payload writer's body set.
# Their presence is not an ownership assertion: retain their exact parent bytes.
PRESERVE = frozenset({".gitattributes", "bom/model-bom.cdx.json"})
MAX_FILES = 256
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_TOTAL_BYTES = 16 * 1024 * 1024


class PublishError(ValueError):
    """A safe, credential-free explanation of a failed publication contract."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise PublishError(message)


def sha(value: str) -> str:
    require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{40}", value) is not None,
            "An exact lowercase 40-character commit revision is required.")
    return value


def safe_path(value: str) -> str:
    require(isinstance(value, str) and bool(value) and "\\" not in value
            and "\x00" not in value and not any(ord(c) < 32 for c in value),
            "A repository path is malformed.")
    path = PurePosixPath(value)
    require(not path.is_absolute() and path.as_posix() == value
            and all(part not in ("", ".", "..") for part in value.split("/")),
            "A repository path is not a contained POSIX path.")
    return value


def fingerprint(path: str, content: bytes) -> dict:
    return {"path": path, "size": len(content),
            "sha256": hashlib.sha256(content).hexdigest()}


def snapshot(folder: Path) -> dict[str, bytes]:
    require(folder.is_dir() and not folder.is_symlink(), "The prepared folder is missing or a symlink.")
    files = {}
    for path in sorted(folder.rglob("*")):
        require(not path.is_symlink(), "The payload contains a symlink.")
        if path.is_dir():
            continue
        require(path.is_file(), "The payload contains a non-regular file.")
        name = safe_path(path.relative_to(folder).as_posix())
        require(path.stat().st_size <= MAX_FILE_BYTES, "A payload file exceeds the byte limit.")
        files[name] = path.read_bytes()
    require(0 < len(files) <= MAX_FILES, "The payload file count is outside the fixed limit.")
    require(sum(map(len, files.values())) <= MAX_TOTAL_BYTES, "The payload exceeds the byte limit.")
    require(not (files.keys() & PRESERVE), "The payload attempts to overwrite a preserved remote file.")
    return files


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise PublishError("Canonical source evidence redirected; publication is refused.")


def github_json(suffix: str) -> dict:
    request = urllib.request.Request(
        GITHUB + suffix,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "szl-a11oy-payload-publisher"},
    )
    with urllib.request.build_opener(NoRedirect()).open(request, timeout=20) as response:
        body = response.read(1024 * 1024 + 1)
    require(len(body) <= 1024 * 1024, "Canonical source evidence exceeds the byte limit.")
    value = json.loads(body)
    require(isinstance(value, dict), "Canonical source evidence is malformed.")
    return value


def canonical_source(root: Path = ROOT) -> str:
    def git(*args: str) -> str:
        return subprocess.check_output(["git", *args], cwd=root, text=True,
                                       stderr=subprocess.DEVNULL).strip()

    require(Path(git("rev-parse", "--show-toplevel")).resolve() == root.resolve(),
            "The publisher must run from the canonical repository checkout.")
    revision = sha(git("rev-parse", "HEAD"))
    require(not git("status", "--porcelain", "--untracked-files=normal"),
            "The canonical source checkout is not clean.")
    require(all(line.startswith("H ") for line in git("ls-files", "-v").splitlines()),
            "Index flags conceal or omit tracked source; use an ordinary complete checkout.")
    # Ignored additions inside copied source trees cannot enter merely because
    # ordinary git status omits them. These trees have no symlink payload inputs.
    source_trees = ("huggingface", "docs", "deploy")
    require(not git("ls-files", "--others", "--", *source_trees),
            "A copied source tree contains an untracked or ignored file.")
    require(not any(line.startswith("120000 ") for line in
                    git("ls-files", "--stage", "--", *source_trees).splitlines()),
            "A copied source tree contains a symlink.")
    main = github_json("/git/ref/heads/main")
    require(main.get("object", {}).get("sha") == revision,
            "The checkout is not the currently observed canonical main revision.")
    commit = github_json("/git/commits/" + revision)
    require(commit.get("sha") == revision
            and commit.get("verification", {}).get("verified") is True
            and commit.get("verification", {}).get("reason") == "valid",
            "The canonical source commit has no valid native signature evidence.")
    return revision


def canonical_payload(folder: Path, source_revision: str, root: Path = ROOT) -> dict[str, bytes]:
    import prepare_huggingface_payload as prepare

    actual = snapshot(folder)
    (root / "dist").mkdir(exist_ok=True)
    prior_root, prior_output = prepare.REPO_ROOT, prepare.OUT_DIR
    try:
        with tempfile.TemporaryDirectory(prefix="hf-publish-check-", dir=root / "dist") as temporary:
            prepare.REPO_ROOT = root
            prepare.OUT_DIR = Path(temporary) / "payload"
            with contextlib.redirect_stdout(io.StringIO()):
                require(prepare.main() == 0, "The canonical payload stager failed.")
            expected = snapshot(prepare.OUT_DIR)
    finally:
        prepare.REPO_ROOT, prepare.OUT_DIR = prior_root, prior_output
    require(actual == expected, "Prepared bytes differ from the existing canonical stager projection.")
    metadata = json.loads(expected["a11oy-metadata.json"])
    require(metadata.get("sourceCommit") == source_revision, "The payload source revision differs.")
    card = re.match(br"\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)", expected["README.md"], re.S)
    require(card is not None and b"license: apache-2.0" in card.group(1).splitlines()
            and b"Apache License" in expected["LICENSE"]
            and b"Version 2.0" in expected["LICENSE"],
            "The payload card and canonical Apache-2.0 license do not match.")
    return expected


def remote_state(api, revision: str) -> tuple[str, dict[str, int]]:
    info = api.repo_info(repo_id=TARGET, repo_type=REPO_TYPE, revision=revision,
                         files_metadata=True, timeout=20)
    require(info.id == TARGET and info.private is False and info.gated is False,
            "The fixed existing target must remain public and ungated.")
    observed = sha(info.sha)
    require(isinstance(info.siblings, list) and len(info.siblings) <= MAX_FILES + len(PRESERVE),
            "The remote file inventory is missing or too large.")
    files = {}
    for entry in info.siblings:
        path = safe_path(entry.rfilename)
        require(path not in files, "The remote file inventory contains a duplicate.")
        require(type(entry.size) is int and 0 <= entry.size <= MAX_FILE_BYTES,
                "A remote file size is missing or exceeds the byte limit.")
        files[path] = entry.size
    require(sum(files.values()) <= MAX_TOTAL_BYTES, "The remote inventory exceeds the byte limit.")
    return observed, files


def reconcile(api, expected_revision: str, payload: dict[str, bytes], source_revision: str,
              *, read_file, operation_factory, check_source, apply: bool = False) -> dict:
    parent = sha(expected_revision)
    sha(source_revision)
    observed, remote = remote_state(api, "main")
    require(observed == parent, "The target advanced from the explicitly selected parent.")
    require(not (payload.keys() & PRESERVE), "The payload collides with a preserved remote file.")
    unknown = remote.keys() - payload.keys() - PRESERVE
    require(not unknown, "Unmanaged remote paths require separate source review: " + ", ".join(sorted(unknown)))
    retained = {}
    for path in sorted(remote.keys() & PRESERVE):
        content = read_file(path, parent, remote[path])
        require(len(content) == remote[path], "A preserved parent file has an unexpected byte count.")
        retained[path] = content
    result = {
        "schema": "szl.a11oy.hf-payload-publication.v1",
        "observed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "mode": "APPLY" if apply else "PLAN", "repo_id": TARGET, "repo_type": REPO_TYPE,
        "source_revision": source_revision, "expected_parent": parent,
        "payload": [fingerprint(path, payload[path]) for path in sorted(payload)],
        "preserved": [fingerprint(path, retained[path]) for path in sorted(retained)],
        "deleted_paths": [], "verified": False, "runtime_qualification": "UNCHANGED",
    }
    if not apply:
        return result
    require(check_source() == source_revision, "The canonical source changed before the commit.")
    observed, _ = remote_state(api, "main")
    require(observed == parent, "The target advanced before the parent-bound commit.")
    commit = api.create_commit(
        repo_id=TARGET, repo_type=REPO_TYPE, revision="main", parent_commit=parent,
        operations=[operation_factory(path_in_repo=path, path_or_fileobj=payload[path])
                    for path in sorted(payload)],
        commit_message="publish source-bound a11oy operational payload " + source_revision,
    )
    committed = sha(commit.oid)
    try:
        observed, final_files = remote_state(api, committed)
        expected = {**payload, **retained}
        require(observed == committed and final_files.keys() == expected.keys(),
                "The immutable committed file set does not match the plan.")
        for path in sorted(expected):
            require(final_files[path] == len(expected[path])
                    and read_file(path, committed, final_files[path]) == expected[path],
                    "The immutable committed bytes differ for " + path)
    except Exception as error:
        raise PublishError("Commit " + committed + " exists but immutable readback is unverified.") from error
    result.update(commit=committed, verified=True,
                  verified_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                  immutable_url=HUB + "/" + TARGET + "/tree/" + committed)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-id", default=TARGET, choices=[TARGET])
    parser.add_argument("--repo-type", default=REPO_TYPE, choices=[REPO_TYPE])
    parser.add_argument("--folder", default="dist/huggingface/a11oy")
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--apply", action="store_true", help="perform the one parent-bound additive commit")
    args = parser.parse_args()
    try:
        sha(args.expected_revision)
        token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_HUB_TOKEN")
        require(bool(token), "HF_TOKEN is missing; use the existing publisher credential.")
        from huggingface_hub import CommitOperationAdd, HfApi, hf_hub_download

        source_revision = canonical_source()
        folder = (ROOT / args.folder).resolve()
        require(folder == ROOT / "dist" / "huggingface" / "a11oy", "Only the canonical prepared folder is accepted.")
        payload = canonical_payload(folder, source_revision)
        api = HfApi(endpoint=HUB, token=token)

        def read_file(path: str, revision: str, size: int) -> bytes:
            local = Path(hf_hub_download(repo_id=TARGET, repo_type=REPO_TYPE, filename=path,
                                        revision=revision, token=token, endpoint=HUB,
                                        force_download=True, etag_timeout=20))
            require(local.stat().st_size == size, "A downloaded immutable file has an unexpected size.")
            return local.read_bytes()

        result = reconcile(api, args.expected_revision, payload, source_revision,
                           read_file=read_file, operation_factory=CommitOperationAdd,
                           check_source=canonical_source, apply=args.apply)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except PublishError as error:
        print("Publication refused or unverified: " + str(error))
        return 1
    except Exception as error:
        # Third-party exceptions may contain request details. Do not echo them or
        # treat a post-commit readback failure as evidence that no commit occurred.
        print("Publication unavailable or unverified (" + type(error).__name__ + "). No success receipt was produced.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
