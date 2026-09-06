#!/usr/bin/env python3
"""Apply the Sentra receipt-verifier repair onto the current publisher."""
from __future__ import annotations

from pathlib import Path

IMPLEMENTATION_PATH = Path("scripts/hf_publish_vertical_flagships_v4_impl.py")
TEST_PATH = Path("tests/test_hf_publish_vertical_flagships_v4.py")

OLD_SENTRA_ENTRY = """    {
        "slug": "sentra",
        "title": "Sentra",
        "vertical": "ASSURANCE COMMAND",
        "short": "Admission, receipt verification, and evidence assurance",
        "source": "https://github.com/szl-holdings/a11oy/blob/main/scripts/hf_publish_vertical_flagships_v4_impl.py",
        "upstream": f"{A11OY}/api/a11oy/v1/vert/cyber/feed",
        "workflow": ("EVIDENCE", "ADMISSION", "VERIFY", "REVIEW", "RECEIPT"),
        "lens": "attack",
        "labels": ("Admission graph", "Verification chain", "Evidence queue"),
    },
"""
NEW_SENTRA_ENTRY = """    {
        "slug": "sentra",
        "title": "Sentra",
        "vertical": "ASSURANCE COMMAND",
        "short": "Public receipt verification and assurance evidence",
        "source": "https://github.com/szl-holdings/a11oy/blob/main/scripts/hf_publish_vertical_flagships_v4_impl.py",
        "upstream": f"{A11OY}/api/a11oy/v1/verify/receipt",
        "workflow": ("RECEIPT", "SIGNATURE", "DIGEST", "CHAIN", "VERDICT"),
        "lens": "receipt",
        "labels": ("Verifier contract", "Integrity checks", "Evidence verdict"),
    },
"""
OLD_SENTRA_HTML = """    "sentra": '''<div class="domain"><section class="panel attack" aria-label="Illustrative assurance admission graph"><span class="illus">Illustrative — schematic, not live data</span><span class="path x1"></span><span class="path x2"></span><span class="path x3"></span><div class="node n1">EVIDENCE</div><div class="node n2">GATE<br>ADMISSION</div><div class="node n3">YAWAR<br>VERIFY</div><div class="node n4">REVIEW</div></section><aside class="panel queue"><span class="illus">Illustrative — schematic, not live data</span><div class="mono">ASSURANCE EVIDENCE QUEUE</div><div class="incident"><span class="sev">GATE</span><span>Admission remains deny-by-default and advisory only; evidence is required before approval.</span></div><div class="incident"><span class="sev">YAWAR</span><span>A receipt-chain verification requires an actual receipt and verification result.</span></div><div class="incident"><span class="sev">SCOPE</span><span>Sentra is the sole Assurance Command and absorbs Aegis. Immune engine migration remains UNVERIFIED until its contracts and runtime parity are proven.</span></div></aside></div>''',
"""
NEW_SENTRA_HTML = """    "sentra": '''<div class="domain"><section class="panel verification" aria-label="Illustrative receipt verification graph"><span class="illus">Illustrative — schematic, not live data</span><span class="path x1"></span><span class="path x2"></span><span class="path x3"></span><div class="node n1">RECEIPT</div><div class="node n2">SIGNATURE</div><div class="node n3">DIGEST</div><div class="node n4">CHAIN</div></section><aside class="panel queue"><span class="illus">Illustrative — schematic, not live data</span><div class="mono">VERIFICATION EVIDENCE QUEUE</div><div class="incident"><span class="sev">CONTRACT</span><span>The live upstream describes the public verifier and its supported checks; it does not claim a receipt verdict.</span></div><div class="incident"><span class="sev">VERDICT</span><span>PASS requires an actual caller-supplied receipt and successful signature, payload-digest, and hash-chain checks.</span></div><div class="incident"><span class="sev">SCOPE</span><span>This read-only surface performs no admission or approval. Immune engine migration remains UNVERIFIED until its contracts and runtime parity are proven.</span></div></aside></div>''',
"""
OLD_SENTRA_CSS_SELECTOR = ".attack{min-height:410px"
NEW_SENTRA_CSS_SELECTOR = ".verification{min-height:410px"

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
SENTRA_TEST = """

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
"""
OLD_CARD = '        "Admission, receipt verification, and evidence assurance",\n'
NEW_CARD = '        "Public receipt verification and assurance evidence",\n'


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def main() -> int:
    implementation = IMPLEMENTATION_PATH.read_text(encoding="utf-8")
    if (
        'f"{A11OY}/api/a11oy/v1/verify/receipt"' in implementation
        or "Public receipt verification and assurance evidence" in implementation
    ):
        raise SystemExit("Sentra verifier implementation already exists")
    implementation = replace_once(
        implementation,
        OLD_SENTRA_ENTRY,
        NEW_SENTRA_ENTRY,
        "Sentra registry entry",
    )
    implementation = replace_once(
        implementation,
        OLD_SENTRA_CSS_SELECTOR,
        NEW_SENTRA_CSS_SELECTOR,
        "Sentra semantic CSS selector",
    )
    implementation = replace_once(
        implementation,
        OLD_SENTRA_HTML,
        NEW_SENTRA_HTML,
        "Sentra receipt-verifier panel",
    )
    IMPLEMENTATION_PATH.write_text(implementation, encoding="utf-8")

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
