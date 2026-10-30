# SPDX-License-Identifier: Apache-2.0
"""Keep release event data out of the privileged UDS signing shell."""

from pathlib import Path
import re
import unittest


WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/uds-sign-release.yml"


class UdsSignReleaseTagInputTests(unittest.TestCase):
    def setUp(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        step = workflow.split("      - name: Resolve tag name\n", 1)[1]
        self.step = step.split("\n      - name:", 1)[0]
        self.script = self.step.split("        run: |\n", 1)[1]

    def test_event_tag_is_shell_data(self):
        self.assertIn("DISPATCH_TAG_NAME: ${{ inputs.tag_name }}", self.step)
        self.assertIn("RELEASE_TAG_NAME: ${{ github.event.release.tag_name }}", self.step)
        self.assertNotIn("${{", self.script)

    def test_only_safe_tag_reaches_outputs(self):
        validation = re.search(r'if \[\[ ! "\$TAG" =~ (\^.+?\$) \]\]; then', self.script)
        self.assertIsNotNone(validation)
        self.assertLess(validation.start(), self.script.index('echo "tag=${TAG}" >> "$GITHUB_OUTPUT"'))
        pattern = validation.group(1)
        for tag in ("uds-v0.3.1", "uds-v12.0.4-rc.1"):
            self.assertIsNotNone(re.fullmatch(pattern, tag), tag)
        for tag in ("v0.3.1", "uds-v0.3", "uds-v../x", "uds-v0.3.1$(id)",
                    'uds-v0.3.1"; echo injected; #', "uds-v0.3.1\nother=1"):
            self.assertIsNone(re.fullmatch(pattern, tag), tag)


if __name__ == "__main__":
    unittest.main(verbosity=2)
