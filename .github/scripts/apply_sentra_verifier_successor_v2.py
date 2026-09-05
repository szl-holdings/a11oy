#!/usr/bin/env python3
"""Apply the Sentra receipt-verifier repair without restoring stale tests."""
from __future__ import annotations

import subprocess
from pathlib import Path

SIGNED_SOURCE = "02d6d2c846a07fdbec2caffd16c1a4cf64d378e3"
IMPLEMENTATION = "scripts/hf_publish_vertical_flagships_v4_impl.py"
TEST_PATH = Path("tests/test_hf_publish_vertical_flagships_v4.py")

PUBLIC_VERIFY_ANCHOR = 'SYNC_WORKFLOW = Path(".github/workflows/hf-sync.yml")\n'
PUBLIC_VERIFY_LINE = 'PUBLIC_VERIFY = Path("szl_public_verify.py")\n'
OLD_RENDERER_ASSERTION = (
    "    assert '\"sentra\":' in text and \"assurance admission graph\" in text "
    "and \"ASSURANCE EVIDENCE QUEUE\" in text\n"
)
NEW_RENDERER_ASSERTION = (
    "    assert '\"sentra\":' in text and \"receipt verification graph\" in text "
    "and \"VERIFICATION EVIDENCE QUEUE\" in text\n"
)
DISCLOSURE_ANCHOR = "\ndef test_disclosures_remain_accessible_on_counsel_and_narrow_terra() -> None:\n"
SENTRA_TEST = '''

def test_sentra_binds_to_the_read_only_public_verifier_contract() -> None:
    module = load_implementation()
    sentra = next(row for row in module.FLAGSHIPS if row["slug"] == "sentra")
    verifier = PUBLIC_VERIFY.read_text(encoding="utf-8")

    assert sentra["upstream"] == (
        "https://szlholdings-a11oy.hf.space/api/a11oy/v1/verify/receipt"
    )
    assert sentra["workflow"] == (
        "RECEIPT",
        "SIGNATURE",
        "DIGEST",
        "CHAIN",
        "VERDICT",
    )
    assert sentra["lens"] == "receipt"
    assert sentra["labels"] == (
        "Verifier contract",
        "Integrity checks",
        "Evidence verdict",
    )
    assert 'app.add_api_route(f"{p}/receipt", _verify_manifest, methods=["GET"]' in verifier
    assert '"schema": "szl.public-receipt-verifier/manifest/v1"' in verifier
    assert "vert/cyber/feed" not in sentra["upstream"]

    panel = domain_html()["sentra"]
    assert "performs no admission or approval" in panel
    assert "PASS requires an actual caller-supplied receipt" in panel
'''
OLD_CARD = '        "Admission, receipt verification, and evidence assurance",\n'
NEW_CARD = '        "Public receipt verification and assurance evidence",\n'


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def main() -> int:
    subprocess.run(
        ["git", "checkout", SIGNED_SOURCE, "--", IMPLEMENTATION],
        check=True,
    )
    text = TEST_PATH.read_text(encoding="utf-8")
    if PUBLIC_VERIFY_LINE in text or "test_sentra_binds_to_the_read_only_public_verifier_contract" in text:
        raise SystemExit("Sentra focused assertions already exist")
    text = replace_once(
        text,
        PUBLIC_VERIFY_ANCHOR,
        PUBLIC_VERIFY_ANCHOR + PUBLIC_VERIFY_LINE,
        "PUBLIC_VERIFY declaration",
    )
    text = replace_once(
        text,
        OLD_RENDERER_ASSERTION,
        NEW_RENDERER_ASSERTION,
        "Sentra renderer assertion",
    )
    text = replace_once(
        text,
        DISCLOSURE_ANCHOR,
        SENTRA_TEST + DISCLOSURE_ANCHOR,
        "Sentra verifier test insertion",
    )
    text = replace_once(text, OLD_CARD, NEW_CARD, "Sentra card copy assertion")
    TEST_PATH.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
