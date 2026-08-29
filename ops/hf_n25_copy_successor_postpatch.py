#!/usr/bin/env python3
"""Remove the obsolete whole-Dockerfile hash freeze from the admission regression."""
from pathlib import Path

# This no-semantic-change marker intentionally triggers the already-present
# non-default-branch materializer workflow.
path = Path("tests/test_verify_hf_candidate_admission.py")
text = path.read_text(encoding="utf-8")
old = '''        self.assertEqual(
            report["head_blob"],
            "cb5eb49b1c3b38e9150d6085013b979a11e1e9fd",
        )
'''
new = '''        self.assertEqual(report["head_blob"], oid(live))
'''
if text.count(old) != 1:
    raise SystemExit(
        "tests/test_verify_hf_candidate_admission.py: obsolete blob assertion was not unique"
    )
path.write_text(text.replace(old, new, 1), encoding="utf-8")
print("updated admission regression to bind the current exact Dockerfile bytes")
