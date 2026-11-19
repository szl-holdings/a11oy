#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Contract for .github/scripts/install_playwright_chromium.sh (offline).

Every external tool the script calls (the Playwright CLI, dpkg-query, apt-get,
sudo, ldd and the Chromium headless shell) is replaced by a fake on PATH, so
each branch is exercised without network, root or a real browser: apt is
skipped when nothing is missing, retried within bounds when it fails, and
the script fails closed whenever Chromium cannot be shown to work.
"""

import os
import re
import stat
import subprocess
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".github/scripts/install_playwright_chromium.sh"
PACKAGES = ["libnss3", "libgbm1", "fonts-wqy-zenhei"]


def _exe(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/usr/bin/env bash\n" + textwrap.dedent(body))
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


@pytest.fixture
def rig(tmp_path):
    bin_dir, state = tmp_path / "bin", tmp_path / "state"
    state.mkdir()
    (state / "installed").write_text("")
    _exe(bin_dir / "pw", f"""
        echo "$*" >> "{state}/pw.log"
        if [ "$1" = install ] && [ "$2" = chromium ]; then
          n=$(grep -c '^install chromium$' "{state}/pw.log")
          [ "$n" -gt "${{FAIL_DOWNLOADS:-0}}" ] || exit 1
          exit 0
        fi
        if [ "$1" = install-deps ] && [ "$2" = --dry-run ]; then
          [ -n "${{EMPTY_PLAN:-}}" ] && {{ echo "nothing to do"; exit 0; }}
          [ -n "${{PLAN_FAILS:-}}" ] && {{ echo "ERROR: host not supported"; exit 1; }}
          [ -n "${{PLAN_LISTS_AND_FAILS:-}}" ] && {{ echo 'sh -c "apt-get update&& apt-get install -y --no-install-recommends {' '.join(PACKAGES)}"'; exit 1; }}
          [ -n "${{SELF_CHECKED:-}}" ] && {{ echo "All system dependencies are installed."; exit 0; }}
          echo 'sh -c "apt-get update&& apt-get install -y --no-install-recommends {' '.join(PACKAGES)}"'
          exit 0
        fi
        if [ "$1" = install-deps ] && [ "$2" = chromium ]; then
          n=$(grep -c '^install-deps chromium$' "{state}/pw.log")
          [ "$n" -gt "${{FAIL_PW_DEPS:-0}}" ] || exit 1
          exit 0
        fi
        exit 64
    """)
    _exe(bin_dir / "dpkg-query", f"""
        pkg="${{@: -1}}"
        grep -qx "$pkg" "{state}/installed" && printf installed || printf not-installed
    """)
    _exe(bin_dir / "apt-get", f"""
        echo "apt-get $*" >> "{state}/apt.log"
        if [ "$1" = install ]; then
          n=$(grep -c '^apt-get install' "{state}/apt.log")
          [ "$n" -gt "${{FAIL_INSTALLS:-0}}" ] || exit 100
          [ -n "${{INSTALL_IS_NOOP:-}}" ] && exit 0
          for arg in "$@"; do case "$arg" in -*|install) ;; *) echo "$arg" >> "{state}/installed";; esac; done
        fi
        exit 0
    """)
    _exe(bin_dir / "sudo", f'echo "sudo $*" >> "{state}/sudo.log"\nexec "$@"\n')
    # Pretend to be the unprivileged runner user so the sudo path is exercised.
    _exe(bin_dir / "id", '[ "$1" = -u ] && { echo "${FAKE_UID:-1001}"; exit 0; }\nexec /usr/bin/id "$@"\n')
    _exe(bin_dir / "timeout", f'echo "timeout $*" >> "{state}/timeout.log"\nexec /usr/bin/timeout "$@"\n')
    _exe(bin_dir / "ldd", """
        echo "  libc.so.6 => /lib/libc.so.6"
        [ -n "${MISSING_LIB:-}" ] && echo "  libnss3.so => not found"
        exit 0
    """)
    browsers = tmp_path / "browsers"
    shell = browsers / "chromium_headless_shell-1200/chrome-linux/headless_shell"
    _exe(shell, """
        [ -n "${NO_RENDER:-}" ] && exit 1
        echo '<html><body><p>szl-chromium-ok</p></body></html>'
    """)

    def run(*, installed=(), **env):
        (state / "installed").write_text("".join(f"{p}\n" for p in installed))
        for log in ("pw.log", "apt.log", "sudo.log", "timeout.log"):
            (state / log).unlink(missing_ok=True)
        merged = {
            "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
            "HOME": str(tmp_path),
            "PLAYWRIGHT_BROWSERS_PATH": str(browsers),
            "SZL_PW_RETRY_PAUSE": "0",
            "SZL_PW_APT_CONF": str(state / "apt.conf"),
            **{k: str(v) for k, v in env.items()},
        }
        done = subprocess.run(["bash", str(SCRIPT), str(bin_dir / "pw")], env=merged,
                              capture_output=True, text=True, timeout=120, cwd=tmp_path)
        apt = (state / "apt.log").read_text() if (state / "apt.log").exists() else ""
        pw = (state / "pw.log").read_text() if (state / "pw.log").exists() else ""
        return done, apt, pw

    run.shell = shell
    run.state = state
    run.log = lambda name: (state / name).read_text() if (state / name).exists() else ""
    return run


def test_everything_installed_never_touches_apt(rig):
    done, apt, _ = rig(installed=PACKAGES)
    assert done.returncode == 0, done.stderr
    assert "apt was not used" in done.stdout
    assert "Chromium renders headlessly" in done.stdout
    assert apt == ""
    assert not (rig.state / "apt.conf").exists()


def test_installs_only_the_missing_packages_with_hardened_apt(rig):
    done, apt, _ = rig(installed=["libnss3"])
    assert done.returncode == 0, done.stderr
    install = [line for line in apt.splitlines() if line.startswith("apt-get install")]
    assert install == ["apt-get install -y --no-install-recommends fonts-wqy-zenhei libgbm1"]
    conf = (rig.state / "apt.conf").read_text()
    assert 'Acquire::Retries "5";' in conf and 'Acquire::https::Timeout "30";' in conf


def test_transient_apt_failure_is_retried_within_bounds(rig):
    done, apt, _ = rig(installed=["libnss3", "libgbm1"], FAIL_INSTALLS=2)
    assert done.returncode == 0, done.stderr
    assert apt.count("apt-get install") == 3
    assert done.stderr.count("::warning::apt-get install failed") == 2


def test_persistent_apt_failure_fails_closed(rig):
    done, apt, _ = rig(installed=[], FAIL_INSTALLS=99)
    assert done.returncode != 0
    assert apt.count("apt-get install") == 3
    assert "::error::apt-get install failed after 3 attempts" in done.stderr


def test_an_install_that_leaves_packages_missing_fails_closed(rig):
    done, _, _ = rig(installed=[], INSTALL_IS_NOOP=1)
    assert done.returncode != 0
    assert "OS packages still missing after install" in done.stderr


def test_browser_download_is_retried_then_fails_closed(rig):
    done, _, pw = rig(installed=PACKAGES, FAIL_DOWNLOADS=2)
    assert done.returncode == 0, done.stderr
    assert pw.count("install chromium\n") == 3
    done, _, pw = rig(installed=PACKAGES, FAIL_DOWNLOADS=3)
    assert done.returncode != 0
    assert pw.count("install chromium\n") == 3
    assert "::error::Chromium download failed after 3 attempts" in done.stderr


def test_newer_playwright_self_check_skips_apt(rig):
    done, apt, pw = rig(installed=[], SELF_CHECKED=1)
    assert done.returncode == 0, done.stderr
    assert "Playwright reports every OS dependency installed; apt was not used." in done.stdout
    assert apt == ""
    assert "install-deps chromium\n" not in pw


@pytest.mark.parametrize("env", [{"EMPTY_PLAN": 1}, {"PLAN_FAILS": 1}])
def test_unreadable_plan_falls_back_to_playwrights_installer(rig, env):
    done, apt, pw = rig(installed=PACKAGES, **env)
    assert done.returncode == 0, done.stderr
    assert "could not read Chromium's OS package plan" in done.stderr
    assert pw.count("install-deps chromium\n") == 1
    assert apt == ""
    assert 'Acquire::Retries "5";' in (rig.state / "apt.conf").read_text()


def test_listed_packages_are_used_even_if_the_dry_run_exits_non_zero(rig):
    done, apt, pw = rig(installed=["libnss3", "libgbm1"], PLAN_LISTS_AND_FAILS=1)
    assert done.returncode == 0, done.stderr
    assert "dry-run exited 1 but listed its packages" in done.stdout
    assert [l for l in apt.splitlines() if l.startswith("apt-get install")] == [
        "apt-get install -y --no-install-recommends fonts-wqy-zenhei"]
    assert "install-deps chromium\n" not in pw


def test_failed_plan_is_reported_never_swallowed(rig):
    done, _, _ = rig(installed=PACKAGES, PLAN_FAILS=1)
    assert "(exit 1): ERROR: host not supported" in done.stderr


def test_fallback_installer_failure_fails_closed(rig):
    done, _, pw = rig(installed=PACKAGES, PLAN_FAILS=1, FAIL_PW_DEPS=99)
    assert done.returncode != 0
    assert pw.count("install-deps chromium\n") == 3
    assert "::error::playwright install-deps failed after 3 attempts" in done.stderr


@pytest.mark.parametrize("env,message", [
    ({"MISSING_LIB": 1}, "missing shared libraries"),
    ({"NO_RENDER": 1}, "did not render a test page"),
])
def test_a_browser_that_cannot_run_fails_closed(rig, env, message):
    done, _, _ = rig(installed=PACKAGES, **env)
    assert done.returncode != 0
    assert message in done.stderr


def test_missing_headless_shell_fails_closed(rig):
    rig.shell.unlink()
    done, _, _ = rig(installed=PACKAGES)
    assert done.returncode != 0
    assert "no Chromium headless shell found" in done.stderr


def test_usage_without_a_cli_is_an_error():
    done = subprocess.run(["bash", str(SCRIPT)], capture_output=True, text=True)
    assert done.returncode == 2
    assert "usage:" in done.stderr


def test_apt_timeouts_run_under_sudo_so_they_can_kill_apt(rig):
    done, _, _ = rig(installed=["libnss3"])
    assert done.returncode == 0, done.stderr
    sudo = rig.log("sudo.log").splitlines()
    assert "sudo timeout --kill-after=15 240 apt-get update" in sudo
    assert ("sudo timeout --kill-after=15 300 env DEBIAN_FRONTEND=noninteractive "
            "apt-get install -y --no-install-recommends fonts-wqy-zenhei libgbm1") in sudo
    wrapped = [l for l in rig.log("timeout.log").splitlines() if re.match(r"timeout( -\S+)* \S+ sudo ", l)]
    assert wrapped == [], "a timeout outside sudo cannot stop a stalled apt-get"
