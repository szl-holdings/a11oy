# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""The image build must not pipe downloaded scripts into a shell."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = ROOT / "Dockerfile"

# Same shape as the org file audit's remote-shell-pipe rule (szl-org-health
# census/file_audit.py), applied to logical lines so continuations count.
REMOTE_SHELL_PIPE = re.compile(r"(?i)(?:curl|wget)[^|]{0,240}\|\s*(?:ba)?sh\b")
NODESOURCE_FINGERPRINT = "6F71F525282841EEDAF851B42F59B5F99B1BE0B4"


def _logical_lines(text: str) -> list[str]:
    return text.replace("\\\n", " ").splitlines()


def test_dockerfile_has_no_remote_script_pipe() -> None:
    hits = [line.strip() for line in _logical_lines(DOCKERFILE.read_text(encoding="utf-8"))
            if not line.lstrip().startswith("#") and REMOTE_SHELL_PIPE.search(line)]
    assert hits == []


def test_node_comes_from_fingerprint_checked_signed_repository() -> None:
    text = DOCKERFILE.read_text(encoding="utf-8")
    assert "deb.nodesource.com/setup_" not in text
    assert f'= "{NODESOURCE_FINGERPRINT}"' in text
    assert "signed-by=/usr/share/keyrings/nodesource.gpg] https://deb.nodesource.com/node_22.x nodistro main" in text
    assert "Pin: origin deb.nodesource.com" in text
    assert "node --version | grep -E '^v22\\.'" in text


def test_guard_still_detects_the_removed_pattern() -> None:
    removed = "    curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \\\n    apt-get install -y nodejs\n"
    assert any(REMOTE_SHELL_PIPE.search(line) for line in _logical_lines(removed))
