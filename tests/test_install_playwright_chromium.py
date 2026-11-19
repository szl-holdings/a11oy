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
import shutil
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
        case "$*" in
          *'${{Version}}'*) grep "^$pkg " "{state}/versions" 2>/dev/null | tail -n 1 | cut -d' ' -f2 | tr -d '\\n' ;;
          *) grep -qx "$pkg" "{state}/installed" && printf installed || printf not-installed ;;
        esac
    """)
    # Archives are named <package>_<version>_all.deb; report those two fields.
    _exe(bin_dir / "dpkg-deb", """
        f="$(basename "${@: -1}" .deb)"
        pkg="${f%%_*}"; rest="${f#*_}"; printf '%s %s' "$pkg" "${rest%_*}"
    """)
    _exe(bin_dir / "apt-get", f"""
        echo "apt-get $*" >> "{state}/apt.log"
        [ "$1" = update ] && touch "{state}/updated"
        if [ "$1" = install ]; then
          pkgs=(); offline=0
          for arg in "$@"; do
            case "$arg" in --no-download) offline=1;; -*|install) ;; *) pkgs+=("$arg");; esac
          done
          # Before apt-get update the runner image's own package lists decide
          # the candidate version; afterwards the current archive does.
          if [ -f "{state}/updated" ]; then ver="${{WANT_VERSION:-1.0}}"; else ver="${{IMAGE_VERSION:-${{WANT_VERSION:-1.0}}}}"; fi
          installed_at() {{ echo "$1" >> "{state}/installed"; echo "$1 $ver" >> "{state}/versions"; }}
          if [ "$offline" = 1 ]; then
            [ -n "${{OFFLINE_NOOP:-}}" ] && exit 0
            for p in "${{pkgs[@]}}"; do
              if [ -n "${{OFFLINE_PARTIAL:-}}" ] && [ "$p" = "${{pkgs[0]}}" ]; then
                installed_at "$p"; continue
              fi
              [ -f "$SZL_PW_APT_ARCHIVES/${{p}}_${{ver}}_all.deb" ] || exit 100
            done
            for p in "${{pkgs[@]}}"; do installed_at "$p"; done
            exit 0
          fi
          n=$(grep -v -- '--no-download' "{state}/apt.log" | grep -c '^apt-get install')
          [ "$n" -gt "${{FAIL_INSTALLS:-0}}" ] || exit 100
          [ -n "${{INSTALL_IS_NOOP:-}}" ] && exit 0
          for p in "${{pkgs[@]}}"; do
            if [ -f "$SZL_PW_APT_ARCHIVES/${{p}}_${{ver}}_all.deb" ]; then
              echo "$p" >> "{state}/reused.log"
            else
              echo "$p" >> "{state}/downloads.log"
              echo "$p $ver" > "$SZL_PW_APT_ARCHIVES/${{p}}_${{ver}}_all.deb"
            fi
            installed_at "$p"
          done
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

    archives = state / "archives"

    def run(*, installed=(), cached=None, preexisting=(), **env):
        (state / "installed").write_text("".join(f"{p}\n" for p in installed))
        for log in ("pw.log", "apt.log", "sudo.log", "timeout.log", "versions", "updated",
                    "downloads.log", "reused.log"):
            (state / log).unlink(missing_ok=True)
        shutil.rmtree(archives, ignore_errors=True)
        archives.mkdir()
        for name in preexisting:
            (archives / name).write_text("left on the image\n")
        if cached is not None:
            shutil.rmtree(run.cache, ignore_errors=True)
            run.cache.mkdir()
            for name in cached:
                (run.cache / name).write_text(f"{name}\n")
            env.setdefault("SZL_PW_DEB_CACHE", run.cache)
        merged = {
            "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
            "HOME": str(tmp_path),
            "PLAYWRIGHT_BROWSERS_PATH": str(browsers),
            "SZL_PW_RETRY_PAUSE": "0",
            "SZL_PW_APT_CONF": str(state / "apt.conf"),
            "SZL_PW_APT_ARCHIVES": str(archives),
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
    run.archives = archives
    run.cache = tmp_path / "deb-cache"
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


def _debs(path):
    return sorted(p.name for p in path.glob("*.deb")) if path.exists() else []


def test_cached_archives_install_offline_without_the_network(rig):
    done, apt, _ = rig(installed=["libnss3"], cached=["fonts-wqy-zenhei_1.0_all.deb", "libgbm1_1.0_all.deb"])
    assert done.returncode == 0, done.stderr
    assert "Installed from 2 cached package archives; the Ubuntu archive was not used." in done.stdout
    assert apt.splitlines() == ["apt-get install -y --no-install-recommends --no-download fonts-wqy-zenhei libgbm1"]
    assert not (rig.state / "apt.conf").exists()
    assert ("sudo timeout --kill-after=15 300 env DEBIAN_FRONTEND=noninteractive apt-get install -y "
            "--no-install-recommends --no-download fonts-wqy-zenhei libgbm1") in rig.log("sudo.log").splitlines()


def test_stale_cache_falls_back_to_the_network_and_is_replaced(rig):
    done, apt, _ = rig(installed=["libnss3"], cached=["fonts-wqy-zenhei_0.9_all.deb", "libgbm1_0.9_all.deb"])
    assert done.returncode == 0, done.stderr
    assert "The runner's package lists do not match every cached archive; updating them and reusing the archives that still match." in done.stdout
    assert "apt-get update" in apt
    assert apt.splitlines()[-1] == "apt-get install -y --no-install-recommends fonts-wqy-zenhei libgbm1"
    assert _debs(rig.archives) == ["fonts-wqy-zenhei_1.0_all.deb", "libgbm1_1.0_all.deb"], "copied stale archives must be removed"
    assert _debs(rig.cache) == ["fonts-wqy-zenhei_1.0_all.deb", "libgbm1_1.0_all.deb"]
    assert "Kept 2 package archives matching the installed versions for the Actions cache." in done.stdout


def test_a_network_install_keeps_only_its_downloads_for_the_cache(rig):
    done, _, _ = rig(installed=["libnss3"], preexisting=["unrelated_2.0_all.deb"],
                     SZL_PW_DEB_CACHE=rig.cache)
    assert done.returncode == 0, done.stderr
    assert _debs(rig.cache) == ["fonts-wqy-zenhei_1.0_all.deb", "libgbm1_1.0_all.deb"]


def test_without_a_cache_directory_nothing_is_kept(rig):
    done, apt, _ = rig(installed=["libnss3"])
    assert done.returncode == 0, done.stderr
    assert "--no-download" not in apt
    assert not rig.cache.exists()


def test_a_partial_offline_install_never_reinstalls_what_it_installed(rig):
    done, apt, _ = rig(installed=[], cached=["fonts-wqy-zenhei_0.9_all.deb"], OFFLINE_PARTIAL=1)
    assert done.returncode == 0, done.stderr
    network = [l for l in apt.splitlines() if l.startswith("apt-get install") and "--no-download" not in l]
    assert network == ["apt-get install -y --no-install-recommends libgbm1 libnss3"]


def test_a_cache_that_cannot_be_written_only_warns(rig, tmp_path):
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("file in the way\n")
    done, _, _ = rig(installed=["libnss3"], SZL_PW_DEB_CACHE=blocker)
    assert done.returncode == 0, done.stderr
    assert "::warning::could not keep the package archives" in done.stderr
    assert "Chromium renders headlessly" in done.stdout


def test_a_tilde_cache_path_resolves_under_home(rig):
    done, _, _ = rig(installed=["libnss3"], SZL_PW_DEB_CACHE="~/deb-cache")
    assert done.returncode == 0, done.stderr
    assert _debs(rig.cache) == ["fonts-wqy-zenhei_1.0_all.deb", "libgbm1_1.0_all.deb"]


def test_an_offline_run_that_installs_nothing_is_not_reported_as_cached(rig):
    done, apt, _ = rig(installed=["libnss3"], cached=["fonts-wqy-zenhei_1.0_all.deb", "libgbm1_1.0_all.deb"],
                       OFFLINE_NOOP=1)
    assert done.returncode == 0, done.stderr
    assert "the Ubuntu archive was not used" not in done.stdout
    assert "The runner's package lists do not match every cached archive; updating them and reusing the archives that still match." in done.stdout
    assert "apt-get update" in apt


def test_a_failed_copy_into_the_cache_only_warns(rig):
    rig.cache.mkdir()
    (rig.cache / "libgbm1_1.0_all.deb").mkdir()  # a directory where an archive must go
    done, _, _ = rig(installed=["libnss3"], SZL_PW_DEB_CACHE=rig.cache)
    assert done.returncode == 0, done.stderr
    assert "::warning::could not keep the package archives" in done.stderr
    assert "Chromium renders headlessly" in done.stdout


def test_cached_archives_newer_than_the_image_lists_are_reused_after_update(rig):
    # The cache was filled after apt-get update (1.1); the image's lists still
    # name 1.0, so the offline attempt cannot match, but nothing is downloaded.
    done, apt, _ = rig(installed=["libnss3"], cached=["fonts-wqy-zenhei_1.1_all.deb", "libgbm1_1.1_all.deb"],
                       WANT_VERSION="1.1", IMAGE_VERSION="1.0")
    assert done.returncode == 0, done.stderr
    assert "apt-get update" in apt
    assert rig.log("downloads.log") == ""
    assert sorted(rig.log("reused.log").split()) == ["fonts-wqy-zenhei", "libgbm1"]
    assert _debs(rig.cache) == ["fonts-wqy-zenhei_1.1_all.deb", "libgbm1_1.1_all.deb"]
