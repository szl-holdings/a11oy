# SPDX-License-Identifier: Apache-2.0
"""Offline tests for the research-layer primary project registry."""

import json
import threading
from urllib.parse import urlparse

import pytest

from research import a11oy_primary_project_registry as registry


class _Response:
    def __init__(self, payload):
        self._raw = json.dumps(payload).encode("utf-8")
        self.closed = False

    def read(self, limit=-1):
        return self._raw if limit < 0 else self._raw[:limit]

    def close(self):
        self.closed = True


class _GitHubOpener:
    """Small deterministic stand-in for the two GitHub API endpoints."""

    def __init__(self, *, stars=123, spdx="Apache-2.0"):
        self.stars = stars
        self.spdx = spdx
        self.calls = []
        self._lock = threading.Lock()

    def __call__(self, request, timeout):
        with self._lock:
            self.calls.append((request.full_url, timeout))
        if "/commits/" in request.full_url:
            return _Response({"sha": "a" * 40})
        return _Response({
            "stargazers_count": self.stars,
            "default_branch": "main",
            "license": {"spdx_id": self.spdx},
        })


@pytest.fixture(autouse=True)
def _empty_live_cache():
    registry.clear_cache()
    yield
    registry.clear_cache()


def test_registry_covers_ten_fields_with_primary_sources_and_honest_attribution():
    payload = registry.info()
    items = registry.projects()

    assert payload["field_count"] == 10
    assert payload["project_count"] == len(items) == 51
    assert payload["ranking"] == "NONE"
    assert payload["scope"] == "projects_and_organizations_only"
    assert all(field["project_count"] >= 5 for field in payload["fields"])

    allowed_primary_hosts = {
        "arxiv.org",
        "dev.risczero.com",
        "docs.mlcommons.org",
        "genai.owasp.org",
        "github.com",
        "slsa.dev",
    }
    for item in items:
        assert set((
            "project",
            "organization",
            "canonical_repo_url",
            "license_expected",
            "primary_paper_docs",
            "szl_adaptation",
            "attribution",
        )).issubset(item)
        repo = urlparse(item["canonical_repo_url"])
        assert repo.scheme == "https" and repo.netloc == "github.com"
        assert len(repo.path.strip("/").split("/")) == 2
        assert item["license_expected"]
        assert item["szl_adaptation_status"] == "DECLARED"
        assert item["attribution"] == "STUDIED_NOT_COPIED"
        assert item["primary_paper_docs"]
        assert all(urlparse(url).netloc in allowed_primary_hosts
                   for url in item["primary_paper_docs"])
        assert "stars" not in item, "live stars must never be stored in the static registry"


def test_offline_snapshot_is_deterministic_and_never_opens_network(monkeypatch):
    def forbidden_network(*_args, **_kwargs):
        raise AssertionError("offline snapshot attempted network I/O")

    monkeypatch.setattr(registry, "urlopen", forbidden_network)
    first = registry.snapshot()
    second = registry.snapshot()

    assert first == second
    assert json.loads(json.dumps(first))["project_count"] == 51
    assert first["live_metadata_requested"] is False
    assert first["live_metadata_summary"] == {"MEASURED": 0, "UNAVAILABLE": 51}
    for item in first["projects"]:
        observed = item["live_metadata"]
        assert observed["label"] == "UNAVAILABLE"
        assert observed["freshness"] == "UNAVAILABLE"
        assert observed["stars"] is None
        assert observed["license"] is None
        assert observed["revision"] is None
        assert observed["fetched_at"] is None
        assert observed["stars_label"] == "UNAVAILABLE"
        assert observed["license_label"] == "UNAVAILABLE"
        assert observed["revision_label"] == "UNAVAILABLE"
        assert observed["fetched_at_label"] == "UNAVAILABLE"


def test_live_fetch_gets_values_and_revision_from_github_then_uses_fresh_cache():
    opener = _GitHubOpener(stars=456, spdx="MIT")
    url = "https://github.com/example/project"

    first = registry.fetch_github_metadata(
        url, opener=opener, timeout_s=2.5, ttl_s=60, now=1_700_000_000,
    )
    assert first == {
        "label": "MEASURED",
        "freshness": "LIVE",
        "source": "GitHub REST API",
        "source_url": "https://api.github.com/repos/example/project",
        "stars": 456,
        "stars_label": "MEASURED",
        "license": "MIT",
        "license_label": "MEASURED",
        "revision": "a" * 40,
        "revision_label": "MEASURED",
        "default_branch": "main",
        "fetched_at": "2023-11-14T22:13:20Z",
        "fetched_at_label": "MEASURED",
        "reason": None,
    }
    assert len(opener.calls) == 2
    assert all(timeout == 2.5 for _, timeout in opener.calls)

    first["stars"] = -1  # caller mutation must not corrupt the cache
    cached = registry.fetch_github_metadata(
        url, opener=opener, timeout_s=2.5, ttl_s=60, now=1_700_000_010,
    )
    assert cached["stars"] == 456
    assert cached["label"] == "MEASURED"
    assert cached["freshness"] == "CACHE_FRESH"
    assert cached["cache_age_s"] == 10.0
    assert cached["fetched_at"] == "2023-11-14T22:13:20Z"
    assert len(opener.calls) == 2, "fresh cache must avoid both GitHub requests"


def test_expired_cache_is_not_presented_as_current():
    opener = _GitHubOpener()
    url = "https://github.com/example/expiry"

    registry.fetch_github_metadata(url, opener=opener, ttl_s=10, now=1000)
    refreshed = registry.fetch_github_metadata(url, opener=opener, ttl_s=10, now=1011)

    assert refreshed["freshness"] == "LIVE"
    assert refreshed["fetched_at"] == "1970-01-01T00:16:51Z"
    assert len(opener.calls) == 4


@pytest.mark.parametrize("failure", [
    TimeoutError("bounded timeout"),
    ValueError("malformed response"),
])
def test_live_failure_is_honest_unavailable_with_no_fabricated_values(failure):
    def broken(_request, timeout):
        assert timeout == 1.0
        raise failure

    observed = registry.fetch_github_metadata(
        "https://github.com/example/down",
        opener=broken,
        timeout_s=1.0,
        now=1234,
    )

    assert observed["label"] == "UNAVAILABLE"
    assert observed["freshness"] == "UNAVAILABLE"
    assert observed["stars"] is None
    assert observed["license"] is None
    assert observed["revision"] is None
    assert observed["fetched_at"] is None
    assert all(observed[key] == "UNAVAILABLE" for key in (
        "stars_label", "license_label", "revision_label", "fetched_at_label",
    ))
    assert str(failure) in observed["reason"]


def test_missing_live_spdx_is_labeled_unavailable_without_losing_revision():
    opener = _GitHubOpener(spdx="NOASSERTION")
    observed = registry.fetch_github_metadata(
        "https://github.com/example/no-license", opener=opener, now=2000,
    )

    assert observed["label"] == "MEASURED"
    assert observed["stars_label"] == "MEASURED"
    assert observed["license"] is None
    assert observed["license_label"] == "UNAVAILABLE"
    assert observed["revision"] == "a" * 40


def test_snapshot_payload_filters_fields_and_deduplicates_cross_field_repos():
    opener = _GitHubOpener(stars=9)
    payload = registry.snapshot(
        fetch_live=True,
        fields=("reasoning_math", "biomed_science"),
        opener=opener,
        max_workers=4,
        now=3000,
    )

    assert payload["live_metadata_requested"] is True
    assert payload["selected_fields"] == ["reasoning_math", "biomed_science"]
    assert payload["snapshot_project_count"] == len(payload["projects"]) == 10
    assert payload["live_metadata_summary"] == {"MEASURED": 10, "UNAVAILABLE": 0}
    # DeepSeek-R1 appears in both selected fields but is fetched once (two API calls).
    unique_repos = {item["canonical_repo_url"] for item in payload["projects"]}
    assert payload["unique_repository_count"] == len(unique_repos)
    assert len(opener.calls) == len(unique_repos) * 2
    assert all(item["live_metadata"]["revision"] == "a" * 40
               for item in payload["projects"])


def test_invalid_repo_and_fetch_controls_are_rejected():
    with pytest.raises(ValueError, match="github.com"):
        registry.fetch_github_metadata("https://example.com/org/repo")
    with pytest.raises(ValueError, match="subpath"):
        registry.fetch_github_metadata("https://github.com/org/repo/issues")
    with pytest.raises(ValueError, match="timeout_s"):
        registry.fetch_github_metadata("https://github.com/org/repo", timeout_s=0)
    with pytest.raises(ValueError, match="ttl_s"):
        registry.fetch_github_metadata("https://github.com/org/repo", ttl_s=-1)
    with pytest.raises(ValueError, match="unknown field"):
        registry.snapshot(fields=("not-a-field",))
