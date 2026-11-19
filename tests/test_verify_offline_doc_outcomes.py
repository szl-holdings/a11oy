"""Docs test for docs/verify-offline.md "Try every outcome".

Every command in that section must run and exit with the documented code, and
every documented output line must be what the verifier actually prints.
Offline: the `curl` line is skipped and a manifest that does not list the demo
key is written in its place (the demo key is deliberately absent from the real
org manifest too, so the documented outcome is the same).
"""
import json, os, re, shlex, shutil, subprocess, sys
from pathlib import Path
import pytest

HERE = Path(__file__).parent
ROOT = HERE.parent
DOC = Path(os.environ.get("DOC") or ROOT / "docs" / "verify-offline.md").resolve()
VERIFIER = Path(os.environ.get("VERIFIER") or ROOT / "examples" / "verify_chain_offline.py").resolve()
SAMPLE = ROOT / "examples" / "offline-verify-sample"


def section(text):
    m = re.search(r"## Try every outcome.*?\n(.*?)\n## ", text, re.S)
    assert m, "doc has no 'Try every outcome' section"
    return m.group(1)


def blocks(sec):
    return re.findall(r"```(\w*)\n(.*?)```", sec, re.S)


@pytest.fixture()
def repo(tmp_path):
    ex = tmp_path / "examples" / "offline-verify-sample"; ex.mkdir(parents=True)
    shutil.copy(VERIFIER, tmp_path / "examples" / "verify_chain_offline.py")
    for f in ("bundle.json", "pubkey.pem"):
        shutil.copy(SAMPLE / f, ex / f)
    (tmp_path / "MANIFEST.json").write_text(json.dumps(
        {"schema": "szl.khipu.cosign-keys/v1", "organs": {}}))
    return tmp_path


def test_doc_promises_are_labelled_as_targets():
    text = DOC.read_text()
    assert "Under 5 minutes." not in text, "unqualified timing claim"
    assert "not yet timed" in text


def test_every_outcome_command_exits_as_documented(repo):
    sec = section(DOC.read_text())
    bash = [b for lang, b in blocks(sec) if lang == "bash"]
    assert bash, "no bash block"
    expectations, outputs = 0, []
    for line in bash[0].splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("curl "):
            continue
        m = re.search(r"#\s*expect exit (\d+)\s*$", line)
        cmd = line[: m.start()].strip() if m else line
        argv = shlex.split(cmd)
        if argv[0] == "python":
            argv[0] = sys.executable
        p = subprocess.run(argv, cwd=repo, capture_output=True, text=True)
        if m:
            expectations += 1
            assert p.returncode == int(m.group(1)), (cmd, p.returncode, p.stdout, p.stderr)
            outputs.append(p.stdout + p.stderr)
        else:
            assert p.returncode == 0, (cmd, p.stderr)
    assert expectations == 3
    documented = [b for lang, b in blocks(sec) if lang == ""][0].strip().splitlines()
    for want in documented:
        assert any(want in o for o in outputs), f"documented output not produced: {want!r}"


def test_outcome_table_lists_every_exit_code():
    sec = section(DOC.read_text())
    for code in ("| 0 |", "| 1 |", "| 2 |", "| 3 |", "| 4 |", "| 5 |"):
        assert code in sec


def test_limits_section_present():
    text = " ".join(DOC.read_text().split())
    assert "## What this verification does not prove" in text
    for phrase in ("written by the", "not independent verification", "unknown"):
        assert phrase in text
