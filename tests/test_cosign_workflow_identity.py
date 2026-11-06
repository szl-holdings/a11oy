#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Exercise release verification arguments offline; no signatures are minted."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
IMAGE = "ghcr.io/szl-holdings/a11oy@sha256:" + "a" * 64


def invoke_verification(tmp_path, workflow_ref, exit_code=0):
    workflow = yaml.safe_load((ROOT / ".github/workflows/cosign.yml").read_text())
    steps = workflow["jobs"]["sign"]["steps"]
    step = next(step for step in steps if step.get("name") == "Verify signature")
    script = step["run"].replace("${{ steps.img.outputs.ref }}", IMAGE)
    script = script.replace("${{ github.repository }}", "szl-holdings/a11oy")
    recorder = tmp_path / "cosign"
    recorder.write_text(
        f"#!{sys.executable}\n"
        "import json, os, pathlib, sys\n"
        "pathlib.Path(os.environ['ARGV_LOG']).write_text(json.dumps(sys.argv[1:]))\n"
        "sys.exit(int(os.environ['VERIFY_EXIT']))\n"
    )
    recorder.chmod(0o755)
    log = tmp_path / "args.json"
    # No runner credentials or network are needed by this command-argument test.
    env = {"PATH": str(tmp_path) + os.pathsep + os.defpath,
           "ARGV_LOG": str(log), "VERIFY_EXIT": str(exit_code)}
    if workflow_ref is not None:
        env["GITHUB_WORKFLOW_REF"] = workflow_ref
    result = subprocess.run(["/bin/bash", "-c", script], env=env,
                            capture_output=True, text=True, timeout=5)
    return result, json.loads(log.read_text()) if log.exists() else None


@pytest.mark.parametrize("tag", ["v1.2.3", "v1.2.3-rc.1", "v1.2.3+build.5"])
def test_release_verification_requires_exact_workflow_and_tag(tmp_path, tag):
    ref = f"szl-holdings/a11oy/.github/workflows/cosign.yml@refs/tags/{tag}"
    result, argv = invoke_verification(tmp_path, ref)
    assert result.returncode == 0, result.stderr
    assert argv == ["verify", "--certificate-identity=https://github.com/" + ref,
                    "--certificate-oidc-issuer=https://token.actions.githubusercontent.com", IMAGE]


@pytest.mark.parametrize("workflow_ref", [None, ""])
def test_missing_workflow_identity_fails_before_cosign(tmp_path, workflow_ref):
    result, argv = invoke_verification(tmp_path, workflow_ref)
    assert result.returncode != 0
    assert argv is None


def test_verification_failure_is_not_masked(tmp_path):
    ref = "szl-holdings/a11oy/.github/workflows/cosign.yml@refs/tags/v1.2.3"
    result, argv = invoke_verification(tmp_path, ref, exit_code=7)
    assert result.returncode == 7
    assert argv[-1] == IMAGE
