# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""gh must come from an immutable, hash-checked release asset, not a mutable apt index."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = ROOT / "Dockerfile"

GH_VERSION = "2.102.0"
GH_DEB = f"gh_{GH_VERSION}_linux_amd64.deb"
GH_DEB_SHA256 = "7e54a307f90afdc59796c325ec0c49fb09e6c18537727207a8ac7513584ea5b0"


def _text() -> str:
    return DOCKERFILE.read_text(encoding="utf-8")


def test_gh_is_not_installed_from_the_apt_index() -> None:
    text = _text()
    assert "cli.github.com/packages" not in text
    assert not re.search(r"\bgh=\d", text)


def test_gh_release_asset_is_hash_checked_before_install() -> None:
    text = _text()
    url = f"https://github.com/cli/cli/releases/download/v{GH_VERSION}/{GH_DEB}"
    check = f'echo "{GH_DEB_SHA256}  /tmp/{GH_DEB}"'
    install = f"apt-get install -y --no-install-recommends /tmp/{GH_DEB}"
    assert url in text and check in text and install in text
    assert text.index(url) < text.index(check) < text.index("sha256sum -c -") < text.index(install)
    assert f"grep -F 'gh version {GH_VERSION} '" in text
    assert 'test "$(dpkg --print-architecture)" = "amd64"' in text
