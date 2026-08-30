#!/usr/bin/env python3
"""Fail-closed materializer for the clean PR #1517 runtime-recovery successor."""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

REPOSITORY = os.environ.get("GITHUB_REPOSITORY", "szl-holdings/a11oy")
TARGET_BRANCH = "security/anatomy-product-origin-pin-20260830"
EXPECTED_TARGET_HEAD = "b8eb0bf7d606210f11fa7fb135a7dd4d9c86f352"
SOURCE_BRANCH = "codex/runtime-route-registry-successor-20260830-v2"
SOURCE_BASE = "0798d91a36306ae508d3a22cfce0171104a37025"
SOURCE_FINAL = "934cc4c12827408c4c5be5c95e9f7cb07befcfea"
PRODUCTION_FILES = (
    "a11oy_landing.html",
    "pages/console.html",
    "pages/landing.html",
    "serve.py",
)


def run(
    *args: str,
    check: bool = True,
    capture: bool = False,
    input_bytes: bytes | None = None,
) -> subprocess.CompletedProcess[bytes]:
    print("+", " ".join(args), flush=True)
    completed = subprocess.run(
        args,
        check=False,
        input=input_bytes,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.STDOUT if capture else None,
    )
    if capture and completed.stdout:
        sys.stdout.buffer.write(completed.stdout)
        sys.stdout.flush()
    if check and completed.returncode != 0:
        raise SystemExit(f"command failed ({completed.returncode}): {' '.join(args)}")
    return completed


def output(*args: str) -> str:
    completed = subprocess.run(args, check=True, stdout=subprocess.PIPE, text=True)
    return completed.stdout.strip()


def verify_remote_target() -> None:
    remote = output(
        "gh",
        "api",
        f"repos/{REPOSITORY}/git/ref/heads/{TARGET_BRANCH}",
        "--jq",
        ".object.sha",
    )
    if remote != EXPECTED_TARGET_HEAD:
        raise SystemExit(
            f"exact-head refusal: expected {EXPECTED_TARGET_HEAD}, observed {remote}"
        )


def checkout_exact_lineage() -> None:
    verify_remote_target()
    run(
        "git",
        "fetch",
        "--no-tags",
        "--depth=128",
        "origin",
        f"+refs/heads/{TARGET_BRANCH}:refs/remotes/origin/{TARGET_BRANCH}",
        f"+refs/heads/{SOURCE_BRANCH}:refs/remotes/origin/{SOURCE_BRANCH}",
    )
    if output("git", "rev-parse", f"refs/remotes/origin/{TARGET_BRANCH}") != EXPECTED_TARGET_HEAD:
        raise SystemExit("fetched target identity changed")
    if output("git", "rev-parse", f"refs/remotes/origin/{SOURCE_BRANCH}") != SOURCE_FINAL:
        raise SystemExit("reviewed recovery source identity changed")
    run("git", "cat-file", "-e", f"{SOURCE_BASE}^{{commit}}")
    run("git", "cat-file", "-e", f"{SOURCE_FINAL}^{{commit}}")
    run(
        "git",
        "checkout",
        "--force",
        "-B",
        "materialize-pr1517",
        f"refs/remotes/origin/{TARGET_BRANCH}",
    )
    if output("git", "rev-parse", "HEAD") != EXPECTED_TARGET_HEAD:
        raise SystemExit("local target checkout is not the exact reviewed head")


def apply_reviewed_frontend() -> None:
    patch = subprocess.run(
        (
            "git",
            "diff",
            "--binary",
            SOURCE_BASE,
            SOURCE_FINAL,
            "--",
            "a11oy_landing.html",
            "pages/console.html",
            "pages/landing.html",
        ),
        check=True,
        stdout=subprocess.PIPE,
    ).stdout
    if not patch:
        raise SystemExit("reviewed frontend recovery patch is empty")
    run("git", "apply", "--3way", "--whitespace=nowarn", input_bytes=patch)
    run("git", "reset", "--quiet")


def merge_reviewed_server() -> None:
    with tempfile.TemporaryDirectory(prefix="pr1517-") as temp_dir:
        temp = Path(temp_dir)
        base_path = temp / "serve-base.py"
        reviewed_path = temp / "serve-reviewed.py"
        base_path.write_bytes(
            subprocess.run(
                ("git", "show", f"{SOURCE_BASE}:serve.py"),
                check=True,
                stdout=subprocess.PIPE,
            ).stdout
        )
        reviewed_path.write_bytes(
            subprocess.run(
                ("git", "show", f"{SOURCE_FINAL}:serve.py"),
                check=True,
                stdout=subprocess.PIPE,
            ).stdout
        )
        merge = run(
            "git",
            "merge-file",
            "--diff3",
            "-L",
            "CURRENT_TARGET",
            "-L",
            "SOURCE_BASE",
            "-L",
            "REVIEWED_RECOVERY",
            "serve.py",
            str(base_path),
            str(reviewed_path),
            check=False,
        )
        if merge.returncode != 1:
            raise SystemExit(
                f"expected exactly the audited single conflict; merge-file returned {merge.returncode}"
            )

    server = Path("serve.py")
    text = server.read_text(encoding="utf-8")
    conflict = re.compile(
        r"<<<<<<< CURRENT_TARGET\n"
        r"(?P<current>.*?)"
        r"\|\|\|\|\|\|\| SOURCE_BASE\n"
        r"(?P<base>.*?)"
        r"=======\n"
        r"(?P<reviewed>.*?)"
        r">>>>>>> REVIEWED_RECOVERY\n",
        re.DOTALL,
    )
    matches = list(conflict.finditer(text))
    if len(matches) != 1:
        raise SystemExit(f"expected one audited serve.py overlap, found {len(matches)}")
    match = matches[0]
    current = match.group("current")
    reviewed = match.group("reviewed")
    if match.group("base").strip() != '@app.get("/{full_path:path}")':
        raise SystemExit("audited source-base overlap changed")
    crawler_routes = (
        '@app.api_route("/robots.txt", methods=["GET", "HEAD"])',
        '@app.api_route("/sitemap.xml", methods=["GET", "HEAD"])',
    )
    for route in crawler_routes:
        if route not in current or route not in reviewed:
            raise SystemExit(f"crawler route changed inside audited overlap: {route}")
    old = '@app.get("/{full_path:path}")'
    new = '@app.api_route("/{full_path:path}", methods=["GET", "HEAD"])'
    if current.count(old) != 1 or reviewed.count(new) != 1:
        raise SystemExit("SPA fallback overlap changed")
    resolved = current.replace(old, new, 1)
    text = text[: match.start()] + resolved + text[match.end() :]
    for marker in (
        "<<<<<<< CURRENT_TARGET",
        "||||||| SOURCE_BASE",
        ">>>>>>> REVIEWED_RECOVERY",
    ):
        if marker in text:
            raise SystemExit(f"unresolved named merge marker: {marker}")
    server.write_text(text, encoding="utf-8")
    run("git", "reset", "--quiet")


def subtract_rejected_expansion() -> None:
    front = Path("a11oy_landing.html")
    text = front.read_text(encoding="utf-8")
    text = re.sub(
        r'\n[ \t]*<a class="card surface-card" href="/five-space" id="bind-five-space">.*?</a>\n',
        "\n",
        text,
        flags=re.DOTALL,
    )
    text = re.sub(
        r'\n[ \t]*<a href="/five-space">Five-space operator[^<]*</a>',
        "",
        text,
    )
    front.write_text(text, encoding="utf-8")

    landing = Path("pages/landing.html")
    text = landing.read_text(encoding="utf-8")
    text = re.sub(
        r'[ \t]*<a href="/five-space">Five-Space</a>[ \t]*\n?', "", text
    )
    landing.write_text(text, encoding="utf-8")

    server = Path("serve.py")
    text = server.read_text(encoding="utf-8")
    get_only = (
        'app.add_api_route("/investor", _investor_view_redirect, '
        'methods=["GET"], include_in_schema=False)'
    )
    get_head = (
        'app.add_api_route("/investor", _investor_view_redirect, '
        'methods=["GET", "HEAD"], include_in_schema=False)'
    )
    if get_only in text:
        text = text.replace(get_only, get_head, 1)
    elif get_head not in text:
        raise SystemExit("unknown /investor route shape")
    server.write_text(text, encoding="utf-8")

    forbidden = {
        front: ('id="bind-five-space"', 'href="/five-space"', "Five-space operator"),
        landing: ('href="/five-space"', ">Five-Space<"),
        Path("pages/console.html"): (
            'href="/five-space"',
            "Five-space operator",
            "Five-Space",
        ),
    }
    for path, needles in forbidden.items():
        body = path.read_text(encoding="utf-8")
        for needle in needles:
            if needle in body:
                raise SystemExit(f"rejected expansion remains in {path}: {needle}")


def verify_contracts() -> None:
    required = {
        "a11oy_landing.html": (
            '<a href="/console">Command</a>',
            "loadKernelLocked",
            "timed out",
            "https://a11oy.net",
        ),
        "pages/landing.html": (
            "https://huggingface.co/spaces/SZLHOLDINGS/killinchu",
            "UNAVAILABLE",
        ),
        "pages/console.html": (
            'id="szl-series-a-cards"',
            "go('investor')",
            "u.searchParams.set('view', view)",
            "Verify on a11oy.net",
            "function emptyUnknown(kind, detail)",
            "locked_formula_count===8",
            'id="cnt-locked"',
            "from /honest locked_formula_count",
            "catalog:true",
            "LOCKED-PROVEN (catalog)",
            '["Home"',
            '["Operate"',
            '["Build"',
            '["Observe"',
            '["Govern"',
            '["Research"',
            '["More"',
        ),
        "serve.py": (
            '"szl_command_bar.js": _VENDOR_JS_CT',
            '"szl_command_bar.css": _VENDOR_CSS_CT',
            '"status": "ABSENT"',
            "orange-cloud",
            "a11oy_khipu_chat.register(app)",
            '"/estate"',
            '"/investor"',
            '@app.api_route("/robots.txt", methods=["GET", "HEAD"])',
            '@app.api_route("/sitemap.xml", methods=["GET", "HEAD"])',
            '@app.api_route("/{full_path:path}", methods=["GET", "HEAD"])',
        ),
    }
    for name, needles in required.items():
        body = Path(name).read_text(encoding="utf-8")
        for needle in needles:
            if needle not in body:
                raise SystemExit(f"missing recovery contract in {name}: {needle}")

    console = Path("pages/console.html").read_text(encoding="utf-8")
    if "tier_counts['LOCKED-PROVEN']" in console:
        raise SystemExit("kernel chip still reads the genome catalog count")
    landing = Path("pages/landing.html").read_text(encoding="utf-8")
    if 'href="https://szlholdings-killinchu.hf.space/' in landing:
        raise SystemExit("direct Killinchu hf.space product link remains")
    server = Path("serve.py").read_text(encoding="utf-8")
    investor = (
        'app.add_api_route("/investor", _investor_view_redirect, '
        'methods=["GET", "HEAD"], include_in_schema=False)'
    )
    if investor not in server:
        raise SystemExit("/investor is not registered for GET and HEAD")

    run("git", "diff", "--check")
    marker_check = subprocess.run(
        (
            "grep",
            "-nE",
            r"^(<<<<<<<|>>>>>>>)( |$)",
            *PRODUCTION_FILES,
        ),
        stdout=subprocess.PIPE,
        text=True,
    )
    if marker_check.returncode == 0:
        print(marker_check.stdout)
        raise SystemExit("generic merge marker remains")
    if marker_check.returncode not in (0, 1):
        raise SystemExit("merge-marker scan failed")
    changed = tuple(
        sorted(
            row
            for row in output("git", "diff", "--name-only", "HEAD").splitlines()
            if row
        )
    )
    if changed != tuple(sorted(PRODUCTION_FILES)):
        raise SystemExit(f"exact four-file diff fence failed: {changed!r}")


def run_regression_gates() -> None:
    run(
        sys.executable,
        "-m",
        "pip",
        "install",
        "--require-hashes",
        "-r",
        ".github/requirements/ci-core.txt",
    )
    run(sys.executable, "-m", "py_compile", "serve.py")
    run(
        sys.executable,
        "-m",
        "pytest",
        "tests/test_demo_critical_routes.py",
        "tests/test_frontier_now_control_plane.py",
        "tests/test_holographic_static_route_runtime.py",
        "tests/test_khipu_gguf_voter.py",
        "tests/test_khipu_chat_proxy.py",
        "tests/test_khipu_console_panel.py",
        "tests/test_v4_agent_voters.py",
        "tests/test_identity_lock.py",
        "test_canonical_domain.py",
        "-q",
    )
    run(
        sys.executable,
        "-m",
        "pytest",
        "tests/test_frontier_model_admission.py",
        "tests/test_model_intel_frontier_estate.py",
        "tests/test_demo_critical_routes.py",
        "tests/test_series_a_estate.py",
        "tests/test_holographic_command_bar.py",
        "-q",
    )
    run(
        sys.executable,
        "model_release/frontier-qualification/frontier_admission_guard.py",
        "audit",
    )
    run(sys.executable, "-m", "pytest", "tests/test_zero_cdn_guard.py", "-q")
    run(
        sys.executable,
        "-m",
        "pytest",
        "tests/test_readiness_blocker_repairs.py",
        "-q",
    )
    run(
        sys.executable,
        "-m",
        "pytest",
        "tests/test_dockerfile_layer_budget.py",
        "-q",
    )


def materialize_verified_commit() -> str:
    verify_remote_target()
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        raise SystemExit("GitHub token is unavailable")
    additions = [
        {
            "path": path,
            "contents": base64.b64encode(Path(path).read_bytes()).decode("ascii"),
        }
        for path in PRODUCTION_FILES
    ]
    mutation = """
    mutation Materialize($input: CreateCommitOnBranchInput!) {
      createCommitOnBranch(input: $input) { commit { oid url } }
    }
    """
    variables = {
        "input": {
            "branch": {
                "repositoryNameWithOwner": REPOSITORY,
                "branchName": TARGET_BRANCH,
            },
            "expectedHeadOid": EXPECTED_TARGET_HEAD,
            "message": {
                "headline": "fix(runtime): restore verified route and console contracts",
                "body": (
                    "Restore the four reviewed runtime surfaces at the exact security-PR head. "
                    "This recovers Khipu, investor and estate routes, KANCHAY command chrome, "
                    "honest Lean-8 and Killinchu labeling, and dual-origin proof links while "
                    "retaining the current crawler, sitemap, signer, and security-pin guards.\n\n"
                    "The rejected Five-Space product-door expansion is explicitly absent. "
                    "No protected-main write, force push, deployment, DNS mutation, secret change, "
                    "or evidence-class weakening is claimed.\n\n"
                    "Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>"
                ),
            },
            "fileChanges": {"additions": additions},
        }
    }
    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": mutation, "variables": variables}).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "szl-pr1517-runtime-recovery-v3",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            result = json.load(response)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"GitHub GraphQL HTTP {exc.code}: {body}") from exc
    if result.get("errors"):
        raise SystemExit("; ".join(str(row.get("message")) for row in result["errors"]))
    commit_sha = str(result["data"]["createCommitOnBranch"]["commit"]["oid"])
    if not re.fullmatch(r"[0-9a-f]{40}", commit_sha):
        raise SystemExit(f"invalid successor OID: {commit_sha!r}")

    commit_json = json.loads(
        output("gh", "api", f"repos/{REPOSITORY}/commits/{commit_sha}")
    )
    if not commit_json["commit"]["verification"]["verified"]:
        raise SystemExit("successor commit is not GitHub-verified")
    parents = commit_json.get("parents", [])
    if len(parents) != 1 or parents[0].get("sha") != EXPECTED_TARGET_HEAD:
        raise SystemExit("successor parent is not the exact reviewed head")
    changed = tuple(sorted(row["filename"] for row in commit_json.get("files", [])))
    if changed != tuple(sorted(PRODUCTION_FILES)):
        raise SystemExit(f"successor changed an unexpected file set: {changed!r}")
    remote = output(
        "gh",
        "api",
        f"repos/{REPOSITORY}/git/ref/heads/{TARGET_BRANCH}",
        "--jq",
        ".object.sha",
    )
    if remote != commit_sha:
        raise SystemExit("target branch did not advance to the verified successor")
    return commit_sha


def write_summary(commit_sha: str) -> None:
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return
    with Path(summary_path).open("a", encoding="utf-8") as handle:
        handle.write("## PR #1517 clean runtime successor\n\n")
        handle.write(f"- target branch: `{TARGET_BRANCH}`\n")
        handle.write(f"- verified successor: `{commit_sha}`\n")
        handle.write(f"- exact parent: `{EXPECTED_TARGET_HEAD}`\n")
        handle.write(f"- reviewed source final: `{SOURCE_FINAL}`\n")
        handle.write("- changed production files: 4\n")
        handle.write("- rejected Five-Space product-door expansion: absent\n")
        handle.write("- protected `main` mutation: none\n")


def main() -> None:
    checkout_exact_lineage()
    apply_reviewed_frontend()
    merge_reviewed_server()
    subtract_rejected_expansion()
    verify_contracts()
    run_regression_gates()
    commit_sha = materialize_verified_commit()
    write_summary(commit_sha)
    print(f"verified successor materialized: {commit_sha}")


if __name__ == "__main__":
    main()
