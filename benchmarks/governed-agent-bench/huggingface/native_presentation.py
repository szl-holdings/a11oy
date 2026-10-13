# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Static presentation of committed benchmark output; no scoring or network."""

from __future__ import annotations

import base64
import hashlib
import html
import json
import os
import re
import stat
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ASSETS = {
    "szl-tokens.css": "81f7c9baeef0b435e6e3f9d0c4e0d70e40fa17df5d1f30697f623cd3ef5f8eab",
    "SOURCE.json": "967a77235227f1d75852fb61873e46336e67403cbc0e7e12b141e31c83fbd93d",
    "szl-icon-32.svg": "6e2b7d72a3af3d9602b79de41df0194ede6496a9661f057108ec224c0efc92e6",
    "szl-orbit-holo.svg": "66bbf937cb3cd257ec4ab5e7b016e4c09b5d6ea97f735453833a04c534a63b37",
}
SHA = re.compile(r"[0-9a-f]{40}\Z")


def _file(name: str, native: bool = False) -> bytes:
    """Only literal source-owned files; no manifest or request controls paths."""
    if (native and name not in ASSETS) or (not native and name != "bench.css"):
        raise ValueError("unknown presentation file")
    root_fd = os.open(ROOT, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        directory = os.open("szl", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                            dir_fd=root_fd) if native else os.dup(root_fd)
        try:
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory)
            try:
                info = os.fstat(fd)
                if not stat.S_ISREG(info.st_mode) or info.st_size > 262144:
                    raise ValueError("presentation file is not a bounded regular file")
                chunks = []
                remaining = 262145
                while remaining:
                    chunk = os.read(fd, min(remaining, 65536))
                    if not chunk:
                        break
                    chunks.append(chunk)
                    remaining -= len(chunk)
                data = b"".join(chunks)
                if len(data) > 262144:
                    raise ValueError("presentation file exceeded its bound")
            finally:
                os.close(fd)
        finally:
            os.close(directory)
    finally:
        os.close(root_fd)
    if native and hashlib.sha256(data).hexdigest() != ASSETS[name]:
        raise ValueError("native asset differs from accepted bytes")
    return data


def _image(name: str) -> str:
    if name not in {"szl-icon-32.svg", "szl-orbit-holo.svg"}:
        raise ValueError("unknown native image")
    return "data:image/svg+xml;base64," + base64.b64encode(_file(name, True)).decode("ascii")


def css() -> str:
    _file("SOURCE.json", True)
    return _file("szl-tokens.css", True).decode() + "\n" + _file("bench.css").decode()


def head() -> str:
    return ('<meta name="description" content="Committed governability benchmark output, '
            'with explicit evidence limits and immutable source identity.">'
            f'<link rel="icon" type="image/svg+xml" href="{_image("szl-icon-32.svg")}">')


def _text(value: object) -> str:
    return html.escape(json.dumps(value) if isinstance(value, bool) else str(value), quote=True)


def _json(value: object) -> str:
    return _text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False))


def _pair(label: str, value: object) -> str:
    return f'<div><dt>{label}</dt><dd>{_text(value)}</dd></div>'


def render(leaderboard: dict, publication: dict, result: dict) -> str:
    """Render original values, not new evaluator or readiness verdicts."""
    revision = publication["source_revision"]
    if not isinstance(revision, str) or not SHA.fullmatch(revision):
        raise ValueError("publication source must be an immutable commit")
    source = f"https://github.com/szl-holdings/a11oy/tree/{revision}/benchmarks/governed-agent-bench"
    dataset_revision = publication["dataset_revision"]
    dataset_url = "https://huggingface.co/datasets/SZLHOLDINGS/governed-agent-bench"
    if isinstance(dataset_revision, str) and SHA.fullmatch(dataset_revision):
        dataset_url += "/tree/" + dataset_revision
    labels = publication["evidence_labels"]
    evidence = "".join(_pair(label, labels[key]) for label, key in [
        ("Corpus", "corpus"), ("Scores", "score"),
        ("Receipt checks", "receipt_verification"),
        ("Cryptographic verification", "cryptographic_verification")])
    references = []
    for row in leaderboard["reference_rows"]:
        references.append(
            '<article class="gb-reference"><div><p class="gb-eyebrow">Evaluator reference</p>'
            f'<h3>{_text(row["display_name"])}</h3><p class="gb-code">{_text(row["entry_class"])}</p>'
            '<p>A reproducible conformance fixture. This entry is not a model ranking.</p></div>'
            '<dl class="gb-reference-values">'
            + _pair("Computed score", row["score"])
            + _pair("Passing cases", f'{row["passed"]}/{row["total"]}')
            + _pair("Eligible for model ranking", row["eligible_for_model_ranking"])
            + _pair("Corpus / score / receipt checks",
                    f'{row["dataset_label"]} / {row["score_label"]} / {row["receipt_verification"]}')
            + '</dl></article>')
    axes = []
    for index, (axis, values) in enumerate(sorted(result["axes"].items()), 1):
        axes.append(
            f'<li><span class="gb-axis-index">{index:02}</span><div>'
            f'<h3>{_text(axis.replace("_", " ").title())}</h3>'
            '<dl class="gb-axis-values">'
            + _pair("Passed / total", f'{values["passed"]} / {values["total"]}')
            + _pair("Pass rate", values["pass_rate"]) + '</dl></div></li>')
    return f'''<div class="gb-page" data-surface="light">
<a class="gb-skip" href="#bench-main">Skip to benchmark</a>
<header class="gb-header">
  <a class="gb-brand" href="https://a-11-oy.com"><img src="{_image("szl-icon-32.svg")}" width="40" height="40" alt="SZL Holdings"><span>Governed Agent Bench</span></a>
  <nav aria-label="Benchmark navigation"><a href="#bench-reference">Reference</a><a href="#bench-axes">Five axes</a><a href="#bench-source">Source</a></nav>
</header>
<main id="bench-main" tabindex="-1">
<section class="gb-hero" aria-labelledby="bench-title">
  <div class="gb-hero-copy"><p class="gb-eyebrow">Governability / public reference</p>
    <h1 id="bench-title">Every result.<br><em>Within its evidence.</em></h1>
    <p class="gb-lead">Inspect how a committed reference fixture meets five agent-governance contracts, from fail-closed behavior to rollback discipline.</p>
    <a class="gb-primary" href="#bench-reference">Inspect the reference <span aria-hidden="true">↗</span></a>
    <p class="gb-note">Read-only committed output. No model is called and no score is minted by this page.</p>
  </div>
  <aside class="gb-specimen" data-surface="dark" aria-label="Model leaderboard state">
    <img class="gb-orbit" src="{_image("szl-orbit-holo.svg")}" alt="" width="600" height="600" aria-hidden="true">
    <p class="gb-eyebrow">Model leaderboard</p><p class="gb-count">{_text(leaderboard["eligible_model_submissions"])}</p>
    <h2>Eligible model submissions</h2><p class="gb-code">{_text(leaderboard["status"])}</p>
    <p>The reference validates the evaluator. It does not establish model quality or production readiness.</p>
  </aside>
</section>
<section class="gb-boundary" aria-labelledby="bench-boundary"><div class="gb-section-heading"><p class="gb-eyebrow">01 / Evidence boundary</p><h2 id="bench-boundary">The labels travel with the result.</h2></div>
<dl class="gb-evidence">{evidence}</dl></section>
<section id="bench-reference" class="gb-section" aria-labelledby="bench-reference-title"><div class="gb-section-heading"><p class="gb-eyebrow">02 / Reproducible reference</p><h2 id="bench-reference-title">Conformance, with its limits visible.</h2></div>{''.join(references)}</section>
<section id="bench-axes" class="gb-section" aria-labelledby="bench-axes-title"><div class="gb-section-heading"><p class="gb-eyebrow">03 / Axis closure</p><h2 id="bench-axes-title">Five contracts. Each accounted for.</h2><p>Values below come directly from the committed reference result. Pass rates retain the evaluator’s original numeric scale.</p></div><ol class="gb-axes">{''.join(axes)}</ol></section>
<section class="gb-section gb-admission" aria-labelledby="bench-admission"><div><p class="gb-eyebrow">04 / Submission boundary</p><h2 id="bench-admission">A model row must earn its place.</h2></div><div><p>{_text(leaderboard["submission_rule"])}</p><p class="gb-note">This viewer cannot submit a model, grant deployment approval, or cryptographically verify a receipt.</p></div></section>
<section id="bench-source" class="gb-section" aria-labelledby="bench-source-title"><div class="gb-section-heading"><p class="gb-eyebrow">05 / Immutable identity</p><h2 id="bench-source-title">Inspect what was published.</h2><p>These are declared package identities, not an independent attestation of runtime readiness.</p></div>
<dl class="gb-source">{_pair("Source commit", revision)}{_pair("Dataset repository", publication["dataset_repository"])}{_pair("Dataset revision", dataset_revision)}{_pair("Source observation timestamp", leaderboard["observed_at"])}</dl>
<div class="gb-links"><a href="{source}">Canonical source ↗</a><a href="{dataset_url}">Dataset ↗</a><a href="https://a11oy.net">Proof registry ↗</a></div>
<details><summary>Exact publication identity JSON</summary><pre tabindex="0" aria-label="Publication identity JSON">{_json(publication)}</pre></details>
<details><summary>Exact leaderboard JSON</summary><pre tabindex="0" aria-label="Leaderboard JSON">{_json(leaderboard)}</pre></details>
<details><summary>Exact reference result JSON</summary><pre tabindex="0" aria-label="Reference result JSON">{_json(result)}</pre></details>
</section></main>
<footer class="gb-footer"><p>SZL Holdings / Governed Agent Bench</p><p>Code: Apache-2.0. Orbit artwork: Stephen P. Lutar / SZL Holdings, <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>. <a href="https://github.com/szl-holdings/szl-brand/tree/fd62fe5856ed8e5f660eaae5a9c52957cd71b0a7/kit/logos/orbit-v2">Artwork source</a>. <a href="https://github.com/szl-holdings/szl-brand/blob/fd62fe5856ed8e5f660eaae5a9c52957cd71b0a7/NOTICE">Trademark notice</a>.</p></footer>
</div>'''
