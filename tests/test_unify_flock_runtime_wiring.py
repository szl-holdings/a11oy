# SPDX-License-Identifier: Apache-2.0
from pathlib import Path


def test_unify_flock_is_wired_in_the_early_registration_lane() -> None:
    serve = Path("serve.py").read_text(encoding="utf-8")
    block = "import szl_unify_flock as _szl_unify_flock"
    call = '_szl_unify_flock.register(app, ns="a11oy")'
    later_registration = "# -- KHIPU product organ"
    assert block in serve
    assert call in serve
    assert later_registration in serve
    assert serve.index(block) < serve.index(later_registration)


def test_stale_khipu_chat_exemption_is_pruned() -> None:
    allowlist = Path(".github/register-invocation-allowlist.txt").read_text(encoding="utf-8")
    assert "a11oy_khipu_chat" not in allowlist
