# SPDX-License-Identifier: Apache-2.0
"""Honesty contract for the public CI overclaim counter."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_landing_exposes_evidence_backed_overclaim_counter() -> None:
    landing = (ROOT / "a11oy_landing.html").read_text(encoding="utf-8")

    assert "Overclaims caught by CI" in landing
    assert 'id="hs-overclaim-sample">source unavailable<' in landing
    assert "Mean time to correction:" not in landing
    assert 'class="k gray" id="hs-overclaims">—<' in landing
    assert 'id="hs-overclaim-time">—<' in landing
    assert 'id="hs-overclaims">1<' not in landing
    assert 'id="hs-overclaim-time">10h 51m 38s<' not in landing
    assert "docs/OVERCLAIM_LEDGER.md" in landing
    assert (
        "https://raw.githubusercontent.com/szl-holdings/platform/main/"
        "docs/overclaim-ledger.json"
    ) in landing
    assert (
        "https://raw.githubusercontent.com/szl-holdings/platform/main/"
        "docs/overclaim-ledger.evidence.json"
    ) in landing
    assert "crypto.subtle.digest" in landing
    assert "digest !== pinnedDigest" in landing
    assert 'grayChip("SAMPLE · SNAPSHOT 2026-07-25 · SOURCE UNAVAILABLE")' in landing
    assert 'grayChip("MEASURED · SNAPSHOT "+observed+" · DIGEST OK")' in landing


def test_counter_requires_explicit_snapshot_and_one_sample_labels() -> None:
    landing = (ROOT / "a11oy_landing.html").read_text(encoding="utf-8")

    assert 'manifest.maturity !== "MEASURED"' in landing
    assert 'manifest.snapshot.state !== "SNAPSHOT"' in landing
    assert 'd.snapshot.state !== "SNAPSHOT"' in landing
    assert "d.snapshot.exhaustive !== false" in landing
    assert "sampleSize !== 1" in landing
    assert 'd.metrics.aggregation !== "single_observation"' in landing
    assert 'key.toLowerCase().includes("mean")' in landing


def test_every_unavailable_path_clears_and_sample_labels_the_figures() -> None:
    landing = (ROOT / "a11oy_landing.html").read_text(encoding="utf-8")

    assert "function showUnavailableOverclaimMetrics()" in landing
    assert 'count.textContent = "—"' in landing
    assert 'count.classList.remove("proof")' in landing
    assert 'count.classList.add("gray")' in landing
    assert '$("hs-overclaim-time").textContent = "—"' in landing
    assert '$("hs-overclaim-sample").textContent = "source unavailable"' in landing
    assert "catch (_) {\n      showUnavailableOverclaimMetrics();" in landing
    assert '$("hs-overclaim-sample").textContent = "n="+sampleSize' in landing
