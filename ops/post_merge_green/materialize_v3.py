#!/usr/bin/env python3
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import re
import subprocess
import textwrap
import urllib.error
import urllib.request

EXPECTED_PATHS = [
    "CHANGELOG.md",
    "Dockerfile",
    "a11oy_landing.html",
    "a11oy_n25_organs.py",
    "tests/test_n25_organs_contract.py",
    "tools/readiness-harness/probe_runner.test.mjs",
]


def fail(message: str) -> "NoReturn":
    raise SystemExit(message)


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        fail(f"{path}: expected one exact replacement, observed {count}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


def request_json(url: str, token: str, *, data: bytes | None = None) -> dict:
    request = urllib.request.Request(
        url,
        data=data,
        method="POST" if data is not None else "GET",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "szl-post-merge-green-materializer-v3",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        detail = exc.read(1000).decode("utf-8", "replace")
        fail(f"GitHub HTTP {exc.code}: {detail}")


def verify_identity(repository: str, branch: str, base_sha: str, token: str) -> None:
    api = "https://api.github.com"
    branch_ref = request_json(
        f"{api}/repos/{repository}/git/ref/heads/{branch}", token
    )
    main_ref = request_json(
        f"{api}/repos/{repository}/git/ref/heads/main", token
    )
    if branch_ref.get("object", {}).get("sha") != base_sha:
        fail("target branch no longer equals the authorized base")
    if main_ref.get("object", {}).get("sha") != base_sha:
        fail("protected main moved; rebuild from the new exact base")
    local_sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], text=True
    ).strip()
    if local_sha != base_sha:
        fail("local checkout does not equal the authorized base")


def patch_sources() -> None:
    docker = Path("Dockerfile")
    docker_text = docker.read_text(encoding="utf-8")
    copy_line = "COPY a11oy_n25_organs.py ./a11oy_n25_organs.py\n"
    if copy_line not in docker_text:
        marker = "COPY a11oy_landing.html ./a11oy_landing.html\n"
        if docker_text.count(marker) != 1:
            fail("Dockerfile: landing COPY marker is not unique")
        docker.write_text(
            docker_text.replace(marker, marker + copy_line, 1),
            encoding="utf-8",
        )

    replace_once(
        "a11oy_landing.html",
        "Factory organs execute on this origin. Honesty LIVE. Public Hub admission false. GPU tune UNAVAILABLE. Not 25 public Spaces. Proof RECORD is a11oy.net/factory/.",
        "Factory organs execute on this origin with per-organ SIMULATED, MODELED, MEASURED, or UNAVAILABLE evidence classes. Public Hub admission false. GPU tune UNAVAILABLE. Not 25 public Spaces. Proof RECORD is a11oy.net/factory/.",
    )
    replace_once(
        "a11oy_n25_organs.py",
        '        "honesty": "LIVE",\n        "evidence_class": organ["evidence_class"],',
        '        "honesty": organ["evidence_class"],\n        "evidence_class": organ["evidence_class"],',
    )
    replace_once(
        "a11oy_n25_organs.py",
        '        "honesty": "LIVE",\n        "count": 25,',
        '        "honesty": "PER_ORGAN_EVIDENCE_CLASS",\n        "count": 25,',
    )
    replace_once(
        "a11oy_n25_organs.py",
        '| {"honesty": "LIVE", "run": f"POST /api/a11oy/v1/organs/{o[\'id\']}"}',
        '| {"honesty": o["evidence_class"], "run": f"POST /api/a11oy/v1/organs/{o[\'id\']}"}',
    )
    replace_once(
        "a11oy_n25_organs.py",
        '        "note": "N1–N25 execute on the product origin. Not 25 public Spaces. GPU tune remains UNAVAILABLE.",',
        '        "note": "N1–N25 execute on the product origin with per-organ evidence classes. Not 25 public Spaces. GPU tune remains UNAVAILABLE.",',
    )
    replace_once(
        "a11oy_n25_organs.py",
        '<p class="banner">LIVE on a-11-oy.com. Honesty LIVE. Public Hub admission false. GPU tune UNAVAILABLE. Formulas never grant authority. Not 25 public Spaces.</p>',
        '<p class="banner">Route served from a-11-oy.com. Each organ retains its explicit SIMULATED, MODELED, MEASURED, or UNAVAILABLE evidence class. Public Hub admission false. GPU tune UNAVAILABLE. Formulas never grant authority. Not 25 public Spaces.</p>',
    )
    replace_once(
        "a11oy_n25_organs.py",
        '<p>Twenty-five category organs execute here. Receipts are hashed in this runtime. Proof copy lives on a11oy.net.</p>',
        '<p>Twenty-five bounded demonstration organs execute here. Each response exposes its own evidence class. Receipts are SHA-256 integrity records from this process, not signed production receipts. Proof copy lives on a11oy.net.</p>',
    )

    probe = Path("tools/readiness-harness/probe_runner.test.mjs")
    probe_text = probe.read_text(encoding="utf-8")
    pattern = re.compile(
        r'test\("router-stats schema requires live observed process counters", \(\) => \{.*?\n\}\);\n\n(?=test\("router counter evidence)',
        re.S,
    )
    replacement = textwrap.dedent(
        '''\
        test("router-stats schema requires truthful modeled tier-display signals", () => {
          const modeled = {
            state: "MODELED",
            mode: "modeled",
            catalog_state: "LIVE",
            throughput_state: "MODELED",
            routes: [{ tier: "T0", model: "alpha", modeled_load: 0 }],
            servedThisWindow: 0,
            tiers: ["T0"],
            source: "szl_brain.TIERS",
            doctrine: "v11",
            honesty: "Deterministic tier-display signals; not QPS or observed traffic.",
          };
          assert.equal(validateSchema("router_stats", modeled).ok, true);
          assert.equal(validateSchema("router_stats", { ...modeled, state: "LIVE" }).ok, false);
          assert.equal(validateSchema("router_stats", { ...modeled, throughput_state: "OBSERVED" }).ok, false);
          assert.equal(validateSchema("router_stats", { ...modeled, source: "szl_llm_registry.router_stats_snapshot" }).ok, false);
          assert.equal(validateSchema("router_stats", { ...modeled, routes: [] }).ok, false);
          assert.equal(validateSchema("router_stats", { ...modeled, servedThisWindow: -1 }).ok, false);
          assert.equal(validateSchema("router_stats", { ...modeled, servedThisWindow: 0.5 }).ok, false);
        });

        '''
    )
    probe_text, count = pattern.subn(replacement, probe_text, count=1)
    if count != 1:
        fail(
            "probe_runner.test.mjs: expected one legacy router-schema test, "
            f"observed {count}"
        )
    probe.write_text(probe_text, encoding="utf-8")

    test_path = Path("tests/test_n25_organs_contract.py")
    if test_path.exists():
        fail(f"refusing to replace existing {test_path}")
    test_path.write_text(
        textwrap.dedent(
            '''\
            from __future__ import annotations

            import copy
            import unittest

            import a11oy_n25_organs as organs


            class N25OrgansContractTests(unittest.TestCase):
                def test_catalog_is_complete_unique_and_evidence_scoped(self) -> None:
                    self.assertEqual(len(organs.ORGANS), 25)
                    self.assertEqual(len({row["id"] for row in organs.ORGANS}), 25)
                    self.assertEqual(
                        {row["id"] for row in organs.ORGANS},
                        {f"N{i}" for i in range(1, 26)},
                    )
                    allowed = {"SIMULATED", "MODELED", "MEASURED", "UNAVAILABLE"}
                    self.assertTrue(
                        all(row["evidence_class"] in allowed for row in organs.ORGANS)
                    )
                    catalog = organs.catalog()
                    self.assertEqual(
                        catalog["honesty"], "PER_ORGAN_EVIDENCE_CLASS"
                    )
                    self.assertFalse(catalog["admitted_public"])
                    self.assertEqual(catalog["count"], 25)
                    self.assertTrue(
                        all(
                            row["honesty"] == row["evidence_class"]
                            for row in catalog["items"]
                        )
                    )

                def test_receipt_honesty_matches_each_organ_evidence_class(self) -> None:
                    for row in organs.ORGANS:
                        with self.subTest(row=row["id"]):
                            receipt = organs.run_organ(row["id"], "")
                            self.assertEqual(
                                receipt["honesty"], row["evidence_class"]
                            )
                            self.assertEqual(
                                receipt["evidence_class"], row["evidence_class"]
                            )
                            self.assertFalse(receipt["formula_grants_authority"])

                def test_tune_remains_denied_and_unavailable(self) -> None:
                    receipt = organs.run_organ("N11", "sha256:example")
                    self.assertEqual(receipt["status"], "DENIED")
                    self.assertEqual(receipt["honesty"], "UNAVAILABLE")
                    self.assertEqual(receipt["output"]["gpu"], "UNAVAILABLE")
                    self.assertEqual(receipt["output"]["job"], "not-queued")

                def test_guard_and_sandbox_fail_closed(self) -> None:
                    guarded = organs.run_organ("N3", "weapon targeting private-data")
                    self.assertEqual(guarded["status"], "DENIED")
                    sandbox = organs.run_organ(
                        "N21", "__import__('os').system('id')"
                    )
                    self.assertEqual(sandbox["status"], "DENIED")
                    self.assertIsNone(sandbox["output"].get("value"))

                def test_hash_binds_the_complete_receipt_body(self) -> None:
                    receipt = organs.run_organ("N25", "tool=quote resource=lyte")
                    body = {
                        key: value
                        for key, value in receipt.items()
                        if key != "hash"
                    }
                    self.assertEqual(
                        receipt["hash"], organs._sha(organs._canonical(body))
                    )
                    tampered = copy.deepcopy(body)
                    tampered["output"]["allow"] = not tampered["output"]["allow"]
                    self.assertNotEqual(
                        receipt["hash"], organs._sha(organs._canonical(tampered))
                    )

                def test_unknown_organ_is_rejected(self) -> None:
                    with self.assertRaises(KeyError):
                        organs.run_organ("N26", "")


            if __name__ == "__main__":
                unittest.main()
            '''
        ),
        encoding="utf-8",
    )

    changelog = Path("CHANGELOG.md")
    changelog_text = changelog.read_text(encoding="utf-8")
    marker = "## [Unreleased]\n"
    if changelog_text.count(marker) != 1:
        fail("CHANGELOG Unreleased marker is not unique")
    entry = textwrap.dedent(
        '''\
        ## [Unreleased]

        ### Fixed - N1–N25 post-merge runtime and evidence relock
        - The N1–N25 module is copied into the canonical runtime image, every
          receipt and catalog row preserves its per-organ evidence class, and
          public copy no longer describes simulated or modeled organs as a
          blanket LIVE capability. Focused safety, denial, and integrity tests
          are included. The router schema regression now matches the existing
          truthful MODELED tier-display contract.
        '''
    )
    changelog.write_text(
        changelog_text.replace(marker, entry, 1), encoding="utf-8"
    )


def run_qualification() -> None:
    commands = [
        ["python3", "-m", "py_compile", "a11oy_n25_organs.py", "tests/test_n25_organs_contract.py"],
        ["python3", "-m", "unittest", "tests/test_n25_organs_contract.py", "-v"],
        ["node", "--test", "tools/readiness-harness/probe_runner.test.mjs"],
        ["python3", "tools/readiness-harness/gen_tabs_matrix.py", "--check"],
    ]
    for command in commands:
        subprocess.run(command, check=True)

    checks = {
        "Dockerfile": "COPY a11oy_n25_organs.py ./a11oy_n25_organs.py",
        "a11oy_n25_organs.py": "PER_ORGAN_EVIDENCE_CLASS",
    }
    for path, needle in checks.items():
        if needle not in Path(path).read_text(encoding="utf-8"):
            fail(f"{path}: required contract is absent: {needle}")
    if "Factory organs execute on this origin. Honesty LIVE." in Path(
        "a11oy_landing.html"
    ).read_text(encoding="utf-8"):
        fail("landing still carries the blanket LIVE claim")
    if "Honesty LIVE. Public Hub admission false." in Path(
        "a11oy_n25_organs.py"
    ).read_text(encoding="utf-8"):
        fail("organs page still carries the blanket LIVE claim")

    changed = set(
        subprocess.check_output(
            ["git", "diff", "--name-only"], text=True
        ).splitlines()
    )
    changed.update(
        subprocess.check_output(
            ["git", "ls-files", "--others", "--exclude-standard"], text=True
        ).splitlines()
    )
    if changed != set(EXPECTED_PATHS):
        fail(
            "unexpected changed-path set: "
            + json.dumps({"expected": EXPECTED_PATHS, "actual": sorted(changed)})
        )


def create_verified_commit(
    repository: str, branch: str, base_sha: str, token: str
) -> str:
    additions = [
        {
            "path": rel,
            "contents": base64.b64encode(Path(rel).read_bytes()).decode("ascii"),
        }
        for rel in EXPECTED_PATHS
    ]
    mutation = """
    mutation Materialize($input: CreateCommitOnBranchInput!) {
      createCommitOnBranch(input: $input) { commit { oid url } }
    }
    """
    variables = {
        "input": {
            "branch": {
                "repositoryNameWithOwner": repository,
                "branchName": branch,
            },
            "expectedHeadOid": base_sha,
            "message": {
                "headline": "fix(runtime): relock N1-N25 packaging and evidence states",
                "body": (
                    "Copy the merged N1-N25 module into the runtime image, replace blanket LIVE "
                    "claims with per-organ evidence classes, add safety and integrity regressions, "
                    "and align the router schema test with the admitted MODELED contract.\n\n"
                    "No provider mutation, direct protected-main write, force push, secret read, "
                    "capability promotion, or evidence-threshold weakening.\n\n"
                    "Signed-off-by: Lutar, Stephen P. <stephenlutar2@gmail.com>"
                ),
            },
            "fileChanges": {"additions": additions},
        }
    }
    result = request_json(
        "https://api.github.com/graphql",
        token,
        data=json.dumps({"query": mutation, "variables": variables}).encode(
            "utf-8"
        ),
    )
    if result.get("errors"):
        fail("; ".join(str(row.get("message")) for row in result["errors"]))
    commit = result["data"]["createCommitOnBranch"]["commit"]
    oid = str(commit.get("oid") or "")
    if not re.fullmatch(r"[0-9a-f]{40}", oid):
        fail("GitHub did not return a valid commit OID")

    commit_json = request_json(
        f"https://api.github.com/repos/{repository}/commits/{oid}", token
    )
    verification = commit_json.get("commit", {}).get("verification", {})
    parents = commit_json.get("parents", [])
    if verification.get("verified") is not True:
        fail("created commit is not GitHub-verified")
    if len(parents) != 1 or parents[0].get("sha") != base_sha:
        fail("created commit does not have the exact authorized parent")
    branch_ref = request_json(
        f"https://api.github.com/repos/{repository}/git/ref/heads/{branch}", token
    )
    if branch_ref.get("object", {}).get("sha") != oid:
        fail("target branch did not advance to the verified commit")
    return oid


def main() -> int:
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    branch = os.environ.get("TARGET_BRANCH", "")
    base_sha = os.environ.get("TARGET_BASE", "")
    token = os.environ.get("GH_TOKEN", "")
    if repository != "szl-holdings/a11oy":
        fail("refusing unexpected repository")
    if not branch.startswith("fix/post-merge-green-"):
        fail("refusing unexpected target branch")
    if not re.fullmatch(r"[0-9a-f]{40}", base_sha):
        fail("invalid TARGET_BASE")
    if not token:
        fail("GH_TOKEN is required")

    verify_identity(repository, branch, base_sha, token)
    patch_sources()
    run_qualification()
    oid = create_verified_commit(repository, branch, base_sha, token)
    print(json.dumps({"state": "VERIFIED_COMMIT_CREATED", "base": base_sha, "head": oid}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
