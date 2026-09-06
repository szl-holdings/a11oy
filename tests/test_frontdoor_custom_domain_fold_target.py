# SPDX-License-Identifier: Apache-2.0
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_custom_domain_fold_keeps_full_mobile_cta_contract() -> None:
    """The Flow-shell override must not shrink the landing page's 52px CTA."""

    landing = (ROOT / "a11oy_landing.html").read_text(encoding="utf-8")
    flow = (ROOT / "console/assets/szl-flow.css").read_text(encoding="utf-8")

    inline_contract = (
        ".cta-row .btn{width:100%;min-height:52px;border-radius:6px;"
        "white-space:normal;text-align:center}"
    )
    durable_override = (
        '@media(max-width:480px){html[data-szl-shell-owner="homepage"] '
        ".cta-row .btn{min-height:52px}}"
    )

    assert inline_contract in landing
    assert durable_override in flow
    assert 'html[data-szl-shell-owner="homepage"] .cta-row .btn{min-height:45px}' not in flow
