#!/usr/bin/env python3
"""Tests for vendored_pin_check.py. Standard library only; synthetic fixtures only.

Black-box: every test runs the checker as a subprocess and asserts its exit code AND the failure code it
reports, so a disabled guard is detected even when another guard would still make the run exit 1.
Test names start with test_<GUARD>__ so the mutation harness can map each guard to its scenario.

Run: python3 -I -B tests/test_vendored_pin_check.py
Env: VENDORED_PIN_CHECK = path of the checker under test (default: ../scripts/vendored_pin_check.py)
     PIN_TEST_TMP       = folder for scratch fixtures (default: current directory)
     PIN_TEST_OBS       = optional JSON file; each test appends {test, rc, codes} (used by the mutation harness)
"""
import hashlib, io, itertools, json, os, shutil, subprocess, sys, tarfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
CHECKER = os.environ.get("VENDORED_PIN_CHECK") or next(
    (p for p in (os.path.join(HERE, "..", "scripts", "vendored_pin_check.py"), os.path.join(HERE, "vendored_pin_check.py")) if os.path.isfile(p)),
    os.path.join(HERE, "..", "scripts", "vendored_pin_check.py"))
TMP = os.environ.get("PIN_TEST_TMP") or os.getcwd()
OBS = os.environ.get("PIN_TEST_OBS")
COMMIT = "0123456789abcdef0123456789abcdef01234567"
OTHER = "fedcba9876543210fedcba9876543210fedcba98"
REPO = "example-org/example-proofs"
PREFIX = "vendor/proofs/"
UPSTREAM = {
    "Main.lean": b"import Lib\n\ntheorem main_ok : True := trivial\n",
    "Lib/A.lean": b"theorem a : True := trivial\n",
    "Lib/B.lean": b"theorem b : 1 = 1 := rfl\n",
    "README.md": b"# upstream proofs\n",
    "assets/big.bin": b"\x00\x01\x02 synthetic binary asset",
}
TREE = {
    "Main.lean": b"import Lib\nimport Local\n\ntheorem main_ok : True := trivial\n",
    "Lib/A.lean": b"theorem a : True := trivial\n",
    "Lib/B.lean": b"theorem b : 1 = 1 := rfl\n",
    "README.md": b"# upstream proofs\n",
    "Local.lean": b"theorem local_ok : True := trivial\n",
}
_n = itertools.count()


def H(b):
    return hashlib.sha256(b).hexdigest()


def build_pin(tree=TREE, upstream=UPSTREAM):
    files = {k: H(v) for k, v in sorted(tree.items())}
    deltas, om = {}, {}
    for k in sorted(tree):
        if k not in upstream:
            deltas[k] = {"kind": "added", "sha256": files[k], "reason": "local file"}
        elif upstream[k] != tree[k]:
            deltas[k] = {"kind": "modified", "sha256": files[k], "upstream_sha256": H(upstream[k]), "reason": "local edit"}
    for k in sorted(set(upstream) - set(tree)):
        om[k] = {"upstream_sha256": H(upstream[k]), "reason": "not needed downstream"}
    return {"schema": "szl.upstream_pin/v1", "upstream": {"repo": REPO, "commit": COMMIT}, "vendored_prefix": PREFIX,
            "files": files, "local_deltas": deltas, "omitted_upstream": om}


def can_symlink():
    d = os.path.join(TMP, f"_vpc_symprobe_{os.getpid()}")
    os.makedirs(d, exist_ok=True)
    try:
        os.symlink("x", os.path.join(d, "l"))
        return True
    except (OSError, NotImplementedError, AttributeError):
        return False
    finally:
        shutil.rmtree(d, ignore_errors=True)


SYMLINKS = can_symlink()


class Fixture:
    def __init__(self, tree=None, pin=None, upstream=None, commit=COMMIT, links=()):
        self.root = os.path.join(TMP, f"_vpc_{os.getpid()}_{next(_n)}")
        shutil.rmtree(self.root, ignore_errors=True)
        os.makedirs(self.root)
        self.tree = dict(TREE if tree is None else tree)
        for rel, b in self.tree.items():
            self.write(rel, b)
        self.pin_path = os.path.join(self.root, "pin.json")
        p = build_pin() if pin is None else pin
        if p is not False:
            self.write_pin(p)
        self.archive = os.path.join(self.root, "upstream.tar.gz")
        self.make_archive(dict(UPSTREAM if upstream is None else upstream), commit, links)

    def write(self, rel, b):
        p = os.path.join(self.root, *PREFIX.rstrip("/").split("/"), *rel.split("/"))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as fh:
            fh.write(b)

    def write_pin(self, pin):
        with open(self.pin_path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(pin if isinstance(pin, str) else json.dumps(pin, indent=1))

    def make_archive(self, files, commit, links=()):
        with tarfile.open(self.archive, "w:gz", format=tarfile.PAX_FORMAT, pax_headers={"comment": commit}) as tf:
            for rel, b in sorted(files.items()):
                ti = tarfile.TarInfo(f"example-proofs-0123456/{rel}"); ti.size = len(b); ti.mtime = 0; ti.mode = 0o644
                tf.addfile(ti, io.BytesIO(b))
            for rel in links:
                ti = tarfile.TarInfo(f"example-proofs-0123456/{rel}"); ti.type = tarfile.SYMTYPE; ti.linkname = "Main.lean"
                tf.addfile(ti)

    def run(self, *extra, upstream=False, pin=True):
        rep = os.path.join(self.root, "report.json")
        args = [sys.executable, "-I", "-B", CHECKER, "--root", self.root, "--json", rep]
        if pin:
            args += ["--pin", self.pin_path]
        if upstream:
            args += ["--upstream-archive", self.archive]
        r = subprocess.run(args + list(extra), capture_output=True, text=True, timeout=120)
        try:
            with open(rep, encoding="utf-8") as fh:
                report = json.load(fh)
        except (OSError, ValueError):
            report = {"status": None, "failures": []}
        return r.returncode, {f["code"] for f in report.get("failures", [])}, r.stdout + r.stderr

    def close(self):
        shutil.rmtree(self.root, ignore_errors=True)


class PinCheckTests(unittest.TestCase):
    def go(self, fx, expect_rc, expect_code=None, **kw):
        try:
            rc, codes, out = fx.run(**kw)
        finally:
            fx.close()
        if OBS:
            with open(OBS, "a", encoding="utf-8") as fh:
                fh.write(json.dumps({"test": self.id().split(".")[-1], "rc": rc, "codes": sorted(codes)}) + "\n")
        self.assertEqual(rc, expect_rc, out[-800:])
        if expect_code:
            self.assertIn(expect_code, codes, out[-800:])
        else:
            self.assertEqual(codes, set(), out[-800:])

    def mutate_pin(self, fn):
        p = build_pin(); fn(p); return p

    # ---- clean baselines ----
    def test_CLEAN__local_passes(self):
        self.go(Fixture(), 0)

    def test_CLEAN__upstream_archive_passes(self):
        self.go(Fixture(), 0, upstream=True)

    # ---- pin file ----
    def test_PIN_MISSING__no_pin_file(self):
        self.go(Fixture(pin=False), 1, "PIN_MISSING")

    def test_PIN_JSON__not_json(self):
        self.go(Fixture(pin="{ not json"), 1, "PIN_JSON")

    def test_PIN_NOT_OBJECT__array(self):
        self.go(Fixture(pin="[]"), 1, "PIN_NOT_OBJECT")

    def test_PIN_DUPLICATE_KEYS__shadowed_file_hash(self):
        text = json.dumps(build_pin(), indent=1)
        real = '"Lib/A.lean": "' + H(TREE["Lib/A.lean"]) + '"'
        self.assertIn(real, text)
        text = text.replace(real, '"Lib/A.lean": "' + "0" * 64 + '",\n  ' + real, 1)
        self.go(Fixture(pin=text), 1, "PIN_DUPLICATE_KEYS")

    def test_PIN_UNKNOWN_KEYS__typo_key(self):
        self.go(Fixture(pin=self.mutate_pin(lambda p: p.update(local_delta={}))), 1, "PIN_UNKNOWN_KEYS")

    def test_PIN_SCHEMA__wrong_schema(self):
        self.go(Fixture(pin=self.mutate_pin(lambda p: p.update(schema="szl.upstream_pin/v0"))), 1, "PIN_SCHEMA")

    def test_PIN_REPO__no_owner(self):
        self.go(Fixture(pin=self.mutate_pin(lambda p: p["upstream"].update(repo="example-proofs"))), 1, "PIN_REPO")

    def test_PIN_COMMIT__short_sha(self):
        self.go(Fixture(pin=self.mutate_pin(lambda p: p["upstream"].update(commit=COMMIT[:8]))), 1, "PIN_COMMIT")

    def test_PIN_PREFIX__parent_traversal(self):
        self.go(Fixture(pin=self.mutate_pin(lambda p: p.update(vendored_prefix="../vendor/proofs/"))), 1, "PIN_PREFIX")

    def test_PIN_FILES__empty(self):
        self.go(Fixture(pin=self.mutate_pin(lambda p: p.update(files={}))), 1, "PIN_FILES")

    def test_PIN_FILE_ENTRY__traversal_path(self):
        self.go(Fixture(pin=self.mutate_pin(lambda p: p["files"].update({"../escape.lean": "0" * 64}))), 1, "PIN_FILE_ENTRY")

    def test_PIN_FILE_ENTRY__non_sha256_value(self):
        self.go(Fixture(pin=self.mutate_pin(lambda p: p["files"].update({"README.md": "abc"}))), 1, "PIN_FILE_ENTRY")

    def test_PIN_DELTAS__not_object(self):
        self.go(Fixture(pin=self.mutate_pin(lambda p: p.update(local_deltas=[]))), 1, "PIN_DELTAS")

    def test_PIN_DELTA_FIELDS__empty_reason(self):
        self.go(Fixture(pin=self.mutate_pin(lambda p: p["local_deltas"]["Local.lean"].update(reason=" "))), 1, "PIN_DELTA_FIELDS")

    def test_PIN_DELTA_PINNED__delta_not_pinned(self):
        self.go(Fixture(pin=self.mutate_pin(lambda p: p["local_deltas"].update({"Ghost.lean": {"kind": "added", "sha256": "1" * 64, "reason": "x"}}))), 1, "PIN_DELTA_PINNED")

    def test_PIN_DELTA_PINNED__hash_disagrees_with_files(self):
        self.go(Fixture(pin=self.mutate_pin(lambda p: p["local_deltas"]["Local.lean"].update(sha256="2" * 64))), 1, "PIN_DELTA_PINNED")

    def test_PIN_DELTA_UPSTREAM_HASH__modified_without_upstream_hash(self):
        self.go(Fixture(pin=self.mutate_pin(lambda p: p["local_deltas"]["Main.lean"].pop("upstream_sha256"))), 1, "PIN_DELTA_UPSTREAM_HASH")

    def test_PIN_DELTA_UPSTREAM_HASH__added_with_upstream_hash(self):
        self.go(Fixture(pin=self.mutate_pin(lambda p: p["local_deltas"]["Local.lean"].update(upstream_sha256="3" * 64))), 1, "PIN_DELTA_UPSTREAM_HASH")

    def test_PIN_OMISSIONS__not_object(self):
        self.go(Fixture(pin=self.mutate_pin(lambda p: p.update(omitted_upstream=None))), 1, "PIN_OMISSIONS")

    def test_PIN_OMISSION_FIELDS__empty_reason(self):
        self.go(Fixture(pin=self.mutate_pin(lambda p: p["omitted_upstream"]["assets/big.bin"].update(reason=""))), 1, "PIN_OMISSION_FIELDS")

    def test_PIN_OMISSION_OVERLAP__also_vendored(self):
        self.go(Fixture(pin=self.mutate_pin(lambda p: p["omitted_upstream"].update({"README.md": {"upstream_sha256": H(UPSTREAM["README.md"]), "reason": "x"}}))), 1, "PIN_OMISSION_OVERLAP")

    # ---- local tree ----
    def test_TREE_MISSING__prefix_absent(self):
        fx = Fixture(); shutil.rmtree(os.path.join(fx.root, "vendor"))
        self.go(fx, 1, "TREE_MISSING")

    def test_FILE_CHANGED__tampered_vendored_file(self):
        fx = Fixture(); fx.write("Lib/A.lean", b"theorem a : True := sorry\n")
        self.go(fx, 1, "FILE_CHANGED")

    def test_FILE_CHANGED__tampered_declared_delta(self):
        fx = Fixture(); fx.write("Main.lean", TREE["Main.lean"] + b"-- edited\n")
        self.go(fx, 1, "FILE_CHANGED")

    def test_FILE_EXTRA__undeclared_extra_file(self):
        fx = Fixture(); fx.write("Lib/C.lean", b"axiom c : False\n")
        self.go(fx, 1, "FILE_EXTRA")

    def test_FILE_MISSING__vendored_file_deleted(self):
        fx = Fixture(); os.remove(os.path.join(fx.root, "vendor", "proofs", "Lib", "B.lean"))
        self.go(fx, 1, "FILE_MISSING")

    @unittest.skipUnless(SYMLINKS, "symlink creation not permitted on this host")
    def test_SYMLINK_FILE__file_link(self):
        fx = Fixture(); os.symlink("A.lean", os.path.join(fx.root, "vendor", "proofs", "Lib", "L.lean"))
        self.go(fx, 1, "SYMLINK")

    @unittest.skipUnless(SYMLINKS, "symlink creation not permitted on this host")
    def test_SYMLINK_DIR__dir_link(self):
        fx = Fixture(); os.symlink("Lib", os.path.join(fx.root, "vendor", "proofs", "LibLink"), target_is_directory=True)
        self.go(fx, 1, "SYMLINK")

    # ---- upstream comparison (offline archive) ----
    def test_UPSTREAM_FETCH__archive_unreadable(self):
        fx = Fixture(); os.remove(fx.archive)
        self.go(fx, 1, "UPSTREAM_FETCH", upstream=True)

    def test_UPSTREAM_COMMIT__archive_names_other_commit(self):
        self.go(Fixture(commit=OTHER), 1, "UPSTREAM_COMMIT", upstream=True)

    def test_UPSTREAM_LINKS__archive_with_symlink(self):
        self.go(Fixture(links=("Lib/Link.lean",)), 1, "UPSTREAM_LINKS", upstream=True)

    def test_UPSTREAM_DIFFERS__tampered_and_repinned(self):
        tree = dict(TREE, **{"Lib/A.lean": b"theorem a : True := sorry\n"})
        pin = build_pin(tree, UPSTREAM)
        pin["local_deltas"].pop("Lib/A.lean")  # tamper hidden: hash re-pinned, no delta declared
        fx = Fixture(tree=tree, pin=pin)
        rc_local, codes_local, _ = fx.run()
        self.assertEqual((rc_local, codes_local), (0, set()), "local mode cannot see a re-pinned tamper; upstream mode must")
        self.go(fx, 1, "UPSTREAM_DIFFERS", upstream=True)

    def test_UPSTREAM_MISSING__vendored_file_not_upstream(self):
        tree = dict(TREE, **{"Lib/Extra.lean": b"theorem e : True := trivial\n"})
        pin = build_pin(tree, UPSTREAM); pin["local_deltas"].pop("Lib/Extra.lean")
        self.go(Fixture(tree=tree, pin=pin), 1, "UPSTREAM_MISSING", upstream=True)

    def test_DELTA_MODIFIED_ABSENT__modified_but_not_upstream(self):
        up = {k: v for k, v in UPSTREAM.items() if k != "Main.lean"}
        self.go(Fixture(upstream=up), 1, "DELTA_MODIFIED_ABSENT", upstream=True)

    def test_DELTA_EQUALS_UPSTREAM__stale_delta(self):
        up = dict(UPSTREAM, **{"Main.lean": TREE["Main.lean"]})
        self.go(Fixture(upstream=up), 1, "DELTA_EQUALS_UPSTREAM", upstream=True)

    def test_DELTA_UPSTREAM_HASH__recorded_hash_wrong(self):
        self.go(Fixture(pin=self.mutate_pin(lambda p: p["local_deltas"]["Main.lean"].update(upstream_sha256="4" * 64))), 1, "DELTA_UPSTREAM_HASH", upstream=True)

    def test_DELTA_ADDED_EXISTS__added_but_upstream_has_it(self):
        up = dict(UPSTREAM, **{"Local.lean": b"theorem upstream_local : True := trivial\n"})
        self.go(Fixture(upstream=up), 1, "DELTA_ADDED_EXISTS", upstream=True)

    def test_UNDECLARED_OMISSION__upstream_file_not_vendored(self):
        self.go(Fixture(pin=self.mutate_pin(lambda p: p["omitted_upstream"].clear())), 1, "UNDECLARED_OMISSION", upstream=True)

    def test_OMISSION_ABSENT__declared_omission_not_upstream(self):
        self.go(Fixture(pin=self.mutate_pin(lambda p: p["omitted_upstream"].update({"assets/ghost.bin": {"upstream_sha256": "5" * 64, "reason": "x"}}))), 1, "OMISSION_ABSENT", upstream=True)

    def test_OMISSION_HASH__recorded_hash_wrong(self):
        self.go(Fixture(pin=self.mutate_pin(lambda p: p["omitted_upstream"]["assets/big.bin"].update(upstream_sha256="6" * 64))), 1, "OMISSION_HASH", upstream=True)

    # ---- generator ----
    def gen(self, fx, reasons):
        rp = os.path.join(fx.root, "reasons.json"); out = os.path.join(fx.root, "gen_pin.json")
        with open(rp, "w", encoding="utf-8") as fh:
            json.dump(reasons, fh)
        rep = os.path.join(fx.root, "gen_report.json")
        r = subprocess.run([sys.executable, "-I", "-B", CHECKER, "--generate", "--repo", REPO, "--commit", COMMIT, "--prefix", PREFIX,
                            "--root", fx.root, "--upstream-archive", fx.archive, "--reasons", rp, "--out", out, "--json", rep],
                           capture_output=True, text=True, timeout=120)
        with open(rep, encoding="utf-8") as fh:
            codes = {f["code"] for f in json.load(fh)["failures"]}
        return r.returncode, codes, out

    REASONS = {"Main.lean": "local edit", "Local.lean": "local file", "assets/big.bin": "not needed downstream"}

    def test_GENERATE__roundtrip_matches_independent_pin_and_passes(self):
        fx = Fixture(pin=False)
        try:
            rc, codes, out = self.gen(fx, self.REASONS)
            self.assertEqual((rc, codes), (0, set()))
            with open(out, encoding="utf-8") as fh:
                got = json.load(fh)
            exp = build_pin()
            for k in ("files", "local_deltas", "omitted_upstream", "upstream", "vendored_prefix", "schema"):
                self.assertEqual(got[k], exp[k], k)
            shutil.copyfile(out, fx.pin_path)
            rc2, codes2, o2 = fx.run(upstream=True)
            self.assertEqual((rc2, codes2), (0, set()), o2)
        finally:
            fx.close()

    def test_GEN_REASON_REQUIRED__delta_without_reason(self):
        fx = Fixture(pin=False)
        try:
            r = dict(self.REASONS); r.pop("Local.lean")
            rc, codes, out = self.gen(fx, r)
            self.assertEqual(rc, 1); self.assertIn("GEN_REASON_REQUIRED", codes); self.assertFalse(os.path.exists(out))
        finally:
            fx.close()

    def test_GEN_STALE_REASON__reason_for_non_delta(self):
        fx = Fixture(pin=False)
        try:
            rc, codes, out = self.gen(fx, dict(self.REASONS, **{"Lib/A.lean": "not a delta"}))
            self.assertEqual(rc, 1); self.assertIn("GEN_STALE_REASON", codes); self.assertFalse(os.path.exists(out))
        finally:
            fx.close()

    def test_USAGE__unknown_argument_exits_1(self):
        r = subprocess.run([sys.executable, "-I", "-B", CHECKER, "--no-such-flag"], capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
