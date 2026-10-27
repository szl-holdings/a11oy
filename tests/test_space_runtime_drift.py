"""Tests for .github/scripts/check_space_runtime_drift.py (stdlib unittest, no network)."""
import contextlib
import datetime as dt
import importlib.util
import io
import pathlib
import unittest
import urllib.error

_P = pathlib.Path(__file__).resolve().parents[1] / ".github" / "scripts" / "check_space_runtime_drift.py"
_spec = importlib.util.spec_from_file_location("drift", _P)
drift = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(drift)

NOW = dt.datetime(2026, 10, 22, 12, 0, tzinfo=dt.timezone.utc)
DEP = "1b05d180bf41ee56163e72f0846be5ad6485bf10"
MAIN = "bedffee35bc1aaaaaaaaaaaaaaaaaaaaaaaaaaaa"


def cmp_(ahead, first_date, status="ahead"):
    return {"status": status, "ahead_by": ahead,
            "commits": [{"commit": {"committer": {"date": first_date}}}] * max(ahead, 0)}


def fake(dep=DEP, main=MAIN, compare=None, honest_raises=None):
    def f(url, token=None, timeout=20):
        if url.endswith("/api/a11oy/v1/honest"):
            if honest_raises:
                raise honest_raises
            return {"git_sha": dep}
        if "/commits/" in url:
            return {"sha": main}
        if "/compare/" in url:
            return compare if compare is not None else cmp_(9, "2026-10-20T12:00:00Z")
        raise AssertionError(url)
    return f


def run(**kw):
    with contextlib.redirect_stdout(io.StringIO()):
        return drift.main(["--origin", "https://x.hf.space", "--repository", "o/r"], fetch=fake(**kw), now=NOW)


class Evaluate(unittest.TestCase):
    def test_in_sync(self):
        self.assertEqual(drift.evaluate(MAIN, MAIN, {}, NOW, 24)["verdict"], "IN_SYNC")

    def test_short_sha_prefix_in_sync(self):
        self.assertEqual(drift.evaluate(MAIN[:12], MAIN, {}, NOW, 24)["verdict"], "IN_SYNC")

    def test_within_grace(self):
        r = drift.evaluate(DEP, MAIN, cmp_(2, "2026-10-22T06:00:00Z"), NOW, 24)
        self.assertEqual((r["verdict"], r["exit"], r["lag_hours"]), ("WITHIN_GRACE", 0, 6.0))

    def test_drift_beyond_grace(self):
        r = drift.evaluate(DEP, MAIN, cmp_(9, "2026-10-20T12:00:00Z"), NOW, 24)
        self.assertEqual((r["verdict"], r["exit"], r["behind_by"], r["lag_hours"]), ("DRIFT", 1, 9, 48.0))

    def test_grace_boundary_is_inclusive(self):
        self.assertEqual(drift.evaluate(DEP, MAIN, cmp_(1, "2026-10-21T12:00:00Z"), NOW, 24)["verdict"], "WITHIN_GRACE")

    def test_deployment_not_on_main_is_drift(self):
        r = drift.evaluate(DEP, MAIN, {"status": "behind", "ahead_by": 0, "commits": []}, NOW, 24)
        self.assertEqual(r["verdict"], "DRIFT")

    def test_diverged_counts_lag(self):
        r = drift.evaluate(DEP, MAIN, cmp_(3, "2026-10-19T12:00:00Z", status="diverged"), NOW, 24)
        self.assertEqual(r["verdict"], "DRIFT")


class Main(unittest.TestCase):
    def test_exit_codes(self):
        self.assertEqual(run(), 1)
        self.assertEqual(run(dep=MAIN), 0)
        self.assertEqual(run(compare=cmp_(1, "2026-10-22T11:00:00Z")), 0)

    def test_runtime_unreachable_fails_closed(self):
        self.assertEqual(run(honest_raises=urllib.error.URLError("down")), 2)

    def test_malformed_runtime_sha_fails_closed(self):
        self.assertEqual(run(dep="unknown"), 2)
        self.assertEqual(run(dep=None), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
