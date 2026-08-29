#!/usr/bin/env python3
"""Remove the obsolete whole-Dockerfile hash freeze from the admission regression."""
from pathlib import Path
import subprocess

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

# `git diff --name-only` omits an untracked file. Intent-to-add makes the new
# regression visible to the exact-path and diff-check gates without creating a
# local commit or changing its bytes.
subprocess.run(
    ["git", "add", "-N", "tests/test_verify_hf_n25_copy_admission.py"],
    check=True,
)
print("updated admission regression and exposed the new N25 test to diff validation")
