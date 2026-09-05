#!/usr/bin/env python3
"""One-shot transformer for the private-security credential fallback repair.

This file is temporary branch-only machinery. It patches exactly three permanent
files and is deleted before the resulting pull request is opened.
"""
from __future__ import annotations

from pathlib import Path


SCRIPT_PATH = Path(".github/scripts/private_security_posture.py")
WORKFLOW_PATH = Path(".github/workflows/private-security-posture.yml")
TESTS_PATH = Path("tests/test_private_security_posture.py")


def replace_once(text: str, old: str, new: str, *, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one target, found {count}")
    return text.replace(old, new, 1)


def patch_controller() -> None:
    text = SCRIPT_PATH.read_text(encoding="utf-8")

    token_marker = "\n\ndef utc_now() -> str:\n"
    token_support = '''

SECURITY_TOKEN_ENV_NAMES = (
    "SZL_SECURITY_TOKEN",
    "SZL_SECURITY_TOKEN_1",
    "SZL_SECURITY_TOKEN_2",
    "SZL_SECURITY_TOKEN_3",
    "SZL_SECURITY_TOKEN_4",
    "SZL_SECURITY_TOKEN_5",
    "SZL_SECURITY_TOKEN_6",
    "GITHUB_TOKEN",
)


def security_token_candidates(
    environ: Mapping[str, str] | None = None,
) -> list[str]:
    """Return distinct nonempty credentials in declared priority order.

    Credentials and source names remain process-local and are never added to
    receipts, logs, issues, or artifacts. Digest-based deduplication prevents
    retrying aliases that resolve to the same underlying token.
    """
    source = os.environ if environ is None else environ
    tokens: list[str] = []
    fingerprints: set[bytes] = set()
    for name in SECURITY_TOKEN_ENV_NAMES:
        token = str(source.get(name) or "").strip()
        if not token:
            continue
        fingerprint = hashlib.sha256(token.encode("utf-8")).digest()
        if fingerprint in fingerprints:
            continue
        fingerprints.add(fingerprint)
        tokens.append(token)
    return tokens
'''
    text = replace_once(
        text,
        token_marker,
        token_support + token_marker,
        label="token candidate insertion",
    )

    fallback_marker = "\n\ndef build_receipt(\n"
    fallback_support = '''


def collect_family_with_fallback(
    clients: Iterable[Any], repository: str, spec: FamilySpec
) -> dict[str, Any]:
    """Use the first credential that can observe this alert family."""
    fallback: dict[str, Any] = {
        "status": "UNAVAILABLE",
        "reason": "TOKEN_UNAVAILABLE",
        "http_status": None,
        "open_count": None,
        "severity": None,
        "pages_observed": 0,
    }
    for client in clients:
        result = collect_family(client, repository, spec)
        fallback = result
        if result.get("status") == "OBSERVED":
            return result
    return fallback


def collect_status_with_fallback(
    clients: Iterable[Any], collector: Any, *args: Any
) -> dict[str, Any]:
    """Retry a status collector without exposing credential identity."""
    fallback: dict[str, Any] = {
        "status": "UNAVAILABLE",
        "reason": "TOKEN_UNAVAILABLE",
    }
    for client in clients:
        result = collector(client, *args)
        fallback = result
        if result.get("status") == "OBSERVED":
            return result
    return fallback


def collect_governance_with_fallback(
    clients: Iterable[Any], repository: str, default_branch: str
) -> dict[str, Any]:
    """Merge independently observable governance families across credentials."""
    branch: dict[str, Any] = {
        "status": "UNAVAILABLE",
        "reason": "TOKEN_UNAVAILABLE",
    }
    rulesets: dict[str, Any] = {
        "status": "UNAVAILABLE",
        "reason": "TOKEN_UNAVAILABLE",
        "count": None,
    }
    for client in clients:
        result = collect_governance(client, repository, default_branch)
        candidate_branch = result.get("branch_protection")
        if (
            branch.get("status") != "OBSERVED"
            and isinstance(candidate_branch, Mapping)
        ):
            branch = dict(candidate_branch)
        candidate_rulesets = result.get("rulesets")
        if (
            rulesets.get("status") != "OBSERVED"
            and isinstance(candidate_rulesets, Mapping)
        ):
            rulesets = dict(candidate_rulesets)
        if (
            branch.get("status") == "OBSERVED"
            and rulesets.get("status") == "OBSERVED"
        ):
            break
    return {
        "default_branch": default_branch,
        "branch_protection": branch,
        "rulesets": rulesets,
    }
'''
    text = replace_once(
        text,
        fallback_marker,
        fallback_support + fallback_marker,
        label="fallback helper insertion",
    )

    old_main = '''    token = os.environ.get("SZL_SECURITY_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
    client = GitHubClient(token)
    family_results = {
        spec.name: collect_family(client, repository, spec) for spec in FAMILIES
    }
    receipt = build_receipt(
        repository=repository,
        revision=revision,
        default_branch=args.default_branch,
        families=family_results,
        features=collect_repository_features(client, repository),
        governance=collect_governance(client, repository, args.default_branch),
        workflows=collect_workflow_evidence(client, repository),
    )
    if args.apply:
        receipt["incident_action"] = synchronize_issue(client, repository, receipt)
'''
    new_main = '''    tokens = security_token_candidates()
    if not tokens:
        raise SystemExit("security posture credential unavailable")
    clients = [GitHubClient(token) for token in tokens]
    family_results = {
        spec.name: collect_family_with_fallback(clients, repository, spec)
        for spec in FAMILIES
    }
    receipt = build_receipt(
        repository=repository,
        revision=revision,
        default_branch=args.default_branch,
        families=family_results,
        features=collect_status_with_fallback(
            clients, collect_repository_features, repository
        ),
        governance=collect_governance_with_fallback(
            clients, repository, args.default_branch
        ),
        workflows=collect_status_with_fallback(
            clients, collect_workflow_evidence, repository
        ),
    )
    if args.apply:
        issue_token = os.environ.get("SZL_SECURITY_TOKEN_5") or tokens[-1]
        receipt["incident_action"] = synchronize_issue(
            GitHubClient(issue_token), repository, receipt
        )
'''
    text = replace_once(text, old_main, new_main, label="main credential flow")
    SCRIPT_PATH.write_text(text, encoding="utf-8")


def patch_workflow() -> None:
    text = WORKFLOW_PATH.read_text(encoding="utf-8")
    old = '''      # A managed organization credential may expose alert families that the
      # repository GITHUB_TOKEN cannot. Every family independently reports
      # OBSERVED or UNAVAILABLE; a fallback token never implies zero alerts.
      SZL_SECURITY_TOKEN: ${{ secrets.SZL_ORG_ADMIN_TOKEN || secrets.ORG_ADMIN_TOKEN || secrets.SZL_GITHUB_TOKEN || secrets.GH_PAT || github.token }}
'''
    new = '''      # Credentials are tried independently per alert family. An under-scoped
      # earlier token cannot hide a later authorized observation. Credential
      # identity and raw private-alert data are never persisted.
      SZL_SECURITY_TOKEN_1: ${{ secrets.SZL_ORG_ADMIN_TOKEN }}
      SZL_SECURITY_TOKEN_2: ${{ secrets.ORG_ADMIN_TOKEN }}
      SZL_SECURITY_TOKEN_3: ${{ secrets.SZL_GITHUB_TOKEN }}
      SZL_SECURITY_TOKEN_4: ${{ secrets.GH_PAT }}
      SZL_SECURITY_TOKEN_5: ${{ github.token }}
'''
    WORKFLOW_PATH.write_text(
        replace_once(text, old, new, label="workflow credential block"),
        encoding="utf-8",
    )


def patch_tests() -> None:
    text = TESTS_PATH.read_text(encoding="utf-8")
    class_marker = "\n\nclass ReceiptBoundaryTests(unittest.TestCase):\n"
    fallback_tests = '''

    def test_token_candidates_preserve_priority_and_deduplicate_aliases(self):
        candidates = posture.security_token_candidates(
            {
                "SZL_SECURITY_TOKEN_1": " alpha ",
                "SZL_SECURITY_TOKEN_2": "alpha",
                "SZL_SECURITY_TOKEN_4": "beta",
                "GITHUB_TOKEN": "beta",
            }
        )
        self.assertEqual(candidates, ["alpha", "beta"])

    def test_family_fallback_retries_after_an_under_scoped_credential(self):
        endpoint = "/repos/szl-holdings/a11oy/code-scanning/alerts?state=open"
        denied = FakeClient(
            pages={endpoint: posture.PostureError("HTTP_403", status=403)}
        )
        observed = FakeClient(
            pages={endpoint: [[{"rule": {"security_severity_level": "critical"}}]]}
        )
        result = posture.collect_family_with_fallback(
            [denied, observed], "szl-holdings/a11oy", posture.FAMILIES[1]
        )
        self.assertEqual(result["status"], "OBSERVED")
        self.assertEqual(result["open_count"], 1)
        self.assertEqual(result["severity"]["critical"], 1)
        self.assertEqual(len(denied.calls), 1)
        self.assertEqual(len(observed.calls), 1)

    def test_status_fallback_uses_a_later_authorized_credential(self):
        endpoint = ("GET", "/repos/szl-holdings/a11oy")
        denied = FakeClient(
            requests={endpoint: posture.PostureError("HTTP_403", status=403)}
        )
        observed = FakeClient(
            requests={
                endpoint: {
                    "security_and_analysis": {
                        "advanced_security": {"status": "enabled"}
                    }
                }
            }
        )
        result = posture.collect_status_with_fallback(
            [denied, observed],
            posture.collect_repository_features,
            "szl-holdings/a11oy",
        )
        self.assertEqual(result["status"], "OBSERVED")
        self.assertEqual(result["features"], {"advanced_security": "enabled"})

    def test_governance_fallback_merges_independently_visible_subfamilies(self):
        branch_path = "/repos/szl-holdings/a11oy/branches/main/protection"
        ruleset_path = "/repos/szl-holdings/a11oy/rulesets?includes_parents=true"
        ruleset_only = FakeClient(
            requests={
                ("GET", branch_path): posture.PostureError("HTTP_403", status=403),
                ("GET", ruleset_path): [
                    {
                        "id": 42,
                        "name": "protected-main",
                        "enforcement": "active",
                        "target": "branch",
                        "source_type": "Organization",
                    }
                ],
            }
        )
        branch_only = FakeClient(
            requests={
                ("GET", branch_path): {
                    "required_status_checks": {"contexts": ["ci"]},
                    "required_pull_request_reviews": {
                        "required_approving_review_count": 0
                    },
                },
                ("GET", ruleset_path): posture.PostureError("HTTP_403", status=403),
            }
        )
        result = posture.collect_governance_with_fallback(
            [ruleset_only, branch_only], "szl-holdings/a11oy", "main"
        )
        self.assertEqual(result["branch_protection"]["status"], "OBSERVED")
        self.assertEqual(result["rulesets"]["status"], "OBSERVED")
        self.assertEqual(result["rulesets"]["count"], 1)
'''
    text = replace_once(
        text,
        class_marker,
        fallback_tests + class_marker,
        label="fallback tests insertion",
    )

    required_anchor = '            "secrets.SZL_GITHUB_TOKEN",\n'
    required_replacement = '''            "secrets.SZL_GITHUB_TOKEN",
            "secrets.SZL_ORG_ADMIN_TOKEN",
            "secrets.ORG_ADMIN_TOKEN",
            "secrets.GH_PAT",
            "SZL_SECURITY_TOKEN_1",
            "SZL_SECURITY_TOKEN_5",
'''
    text = replace_once(
        text,
        required_anchor,
        required_replacement,
        label="workflow required-token contract",
    )

    forbidden_anchor = '            "branches-ignore",\n'
    forbidden_replacement = '''            "branches-ignore",
            "SZL_SECURITY_TOKEN: ${{",
'''
    text = replace_once(
        text,
        forbidden_anchor,
        forbidden_replacement,
        label="collapsed-token negative contract",
    )
    TESTS_PATH.write_text(text, encoding="utf-8")


def main() -> int:
    patch_controller()
    patch_workflow()
    patch_tests()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
