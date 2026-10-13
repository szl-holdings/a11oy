#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Every live store opens from the state store's local root when v2 is on.

With A11OY_STATE_STORE unset nothing changes (env overrides keep working); with
A11OY_STATE_STORE=v2 the legacy /data values only name the bootstrap source.
"""

import json
from pathlib import Path

import pytest

import a11oy_state_store as ss
import gdw_runtime


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    monkeypatch.setattr(ss, "_ACTIVE", None)
    monkeypatch.setattr(gdw_runtime, "_STATE", json.loads(json.dumps(gdw_runtime._STATE)))
    gdw_runtime._STATE.update(startup_state="NOT_RUN", blocked=None, error=None)
    yield
    monkeypatch.setattr(ss, "_ACTIVE", None)


@pytest.fixture
def v2(monkeypatch, tmp_path):
    root = tmp_path / "state"
    monkeypatch.setenv(ss.ENABLE_ENV, ss.ENABLED_VALUE)
    monkeypatch.setenv("A11OY_STATE_ROOT", str(root))
    # The production Space variables still point at the bucket mount.
    monkeypatch.setenv("GDW_DB_PATH", "/data/a11oy/gdw/gdw.sqlite3")
    monkeypatch.setenv("A11OY_SERIES_A_DB", "/data/a11oy/series-a/control-plane-v2.sqlite3")
    monkeypatch.setenv("A11OY_SERIES_A_REQUIRE_MOUNT", "/data")
    monkeypatch.setenv("A11OY_REQUIRE_PERSISTENT_STORAGE", "1")
    monkeypatch.setenv("A11OY_SERIES_A_SQLITE_JOURNAL", "DELETE")
    monkeypatch.setenv("SZL_KHIPU_DIR", "/data/khipu")
    monkeypatch.setenv("UNAY_DATA_DIR", "/data")
    return root


def test_spec_paths_match_what_the_modules_derive(v2):
    expected = {
        "gdw": "gdw/gdw.sqlite3",
        "series_a": "series-a/control-plane-v2.sqlite3",
        "khipu": "khipu/khipu_a11oy.sqlite3",
        "khipu_council": "khipu/khipu_a11oy_council.sqlite3",
        "unay": "unay/unay_a11oy.sqlite",
        "khipu_lmdb": "unay/khipu_lmdb_a11oy",
        "khipu_repl": "unay/khipu_repl_a11oy",
    }
    assert {spec.label: spec.local for spec in ss.STORES} == expected
    for label, relative in expected.items():
        assert ss.local_path(label) == v2 / relative


def test_gdw_contract_and_workspace_use_the_local_root(v2, monkeypatch, tmp_path):
    monkeypatch.delenv("GDW_REQUIRED_MOUNT", raising=False)
    monkeypatch.setenv("GDW_PROOF_DIR", str(tmp_path / "proofs"))
    monkeypatch.setenv("GDW_RECEIPT_PROJECTION_DIR", str(tmp_path / "receipts"))
    contract = gdw_runtime.storage_contract()
    assert Path(contract["database_path"]) == (v2 / "gdw" / "gdw.sqlite3").resolve()
    assert contract["durability_authority"] == "a11oy-state-store-v2"
    from gdw_workspace import GDWWorkspace
    (v2 / "gdw").mkdir(parents=True)
    workspace = GDWWorkspace()
    assert workspace.path == (v2 / "gdw" / "gdw.sqlite3").resolve()


def test_gdw_database_is_not_bound_to_the_required_mount(v2, monkeypatch, tmp_path):
    mount = tmp_path / "mount"
    mount.mkdir()
    monkeypatch.setenv("GDW_REQUIRED_MOUNT", str(mount))
    monkeypatch.setenv("GDW_PROOF_DIR", str(mount / "proofs"))
    monkeypatch.setenv("GDW_RECEIPT_PROJECTION_DIR", str(mount / "receipts"))
    monkeypatch.setattr(gdw_runtime.os.path, "ismount", lambda _path: True)
    contract = gdw_runtime.storage_contract()
    assert Path(contract["database_path"]) == (v2 / "gdw" / "gdw.sqlite3").resolve()
    assert contract["mount_verified"] is True


def test_legacy_behaviour_is_unchanged_without_v2(monkeypatch, tmp_path):
    monkeypatch.delenv(ss.ENABLE_ENV, raising=False)
    monkeypatch.delenv("GDW_REQUIRED_MOUNT", raising=False)
    monkeypatch.setenv("GDW_DB_PATH", str(tmp_path / "legacy.sqlite3"))
    contract = gdw_runtime.storage_contract()
    assert Path(contract["database_path"]) == (tmp_path / "legacy.sqlite3").resolve()
    assert "durability_authority" not in contract


def test_series_a_store_resolves_the_local_root_despite_the_mount_contract(v2):
    from routers import series_a_control_plane as series_a
    store = series_a.Store()
    assert Path(store.path) == v2 / "series-a" / "control-plane-v2.sqlite3"
    assert (v2 / "series-a" / "control-plane-v2.sqlite3").is_file()


def test_unay_khipu_and_council_use_the_local_root(v2):
    import a11oy_ayllu
    import szl_be_hardening
    import szl_unay_routes
    assert Path(szl_unay_routes._pick_data_dir()) == v2 / "unay"
    khipu = szl_be_hardening.DurableKhipu("a11oy")
    assert Path(khipu._path) == v2 / "khipu" / "khipu_a11oy.sqlite3"
    path, source = a11oy_ayllu._council_store_path("a11oy")
    assert Path(path) == v2 / "khipu" / "khipu_a11oy_council.sqlite3"
    assert source == "A11OY_STATE_STORE_V2"


def test_preflight_reports_series_a_storage_from_the_state_store(v2, monkeypatch):
    import szl_boot_preflight as preflight
    env = dict(__import__("os").environ)
    blocked = preflight._subsystem_label(env, "series-a-storage")
    assert blocked["label"] == preflight.UNAVAILABLE, "not activated means not writable"
    monkeypatch.setattr(ss, "writable", lambda: True)
    assert preflight._subsystem_label(env, "series-a-storage")["label"] == preflight.LIVE


def test_main_degrades_when_activation_fails_and_still_serves(monkeypatch):
    served = []

    def failing_activate():
        raise ss.StorageBlocked("HF_TOKEN_MISSING")

    monkeypatch.setattr(ss, "activate", failing_activate)
    monkeypatch.setattr(gdw_runtime, "prepare_runtime", lambda: pytest.fail("must not prepare"))
    monkeypatch.setattr(gdw_runtime, "_serve", lambda: served.append(gdw_runtime.storage_block()))
    assert gdw_runtime.main() == 0
    assert len(served) == 1
    block = served[0]
    assert block["phase"] == "state_store" and block["error_code"] == "HF_TOKEN_MISSING"


def test_main_blocks_gdw_when_its_store_could_not_be_restored(monkeypatch):
    class Store:
        def blocked_labels(self):
            return ["gdw"]

    monkeypatch.setattr(ss, "activate", lambda: Store())
    monkeypatch.setattr(gdw_runtime, "prepare_runtime", lambda: pytest.fail("must not prepare"))
    served = []
    monkeypatch.setattr(gdw_runtime, "_serve", lambda: served.append(gdw_runtime.storage_block()))
    assert gdw_runtime.main() == 0
    assert served[0]["error_code"] == "STATE_STORE_GDW_UNRESTORABLE"


def test_main_registers_the_drain_for_quiesce_and_releases_on_exit(monkeypatch):
    calls = []

    class Store:
        def blocked_labels(self):
            return []

        def add_quiesce_hook(self, hook):
            calls.append(("hook", hook.__self__.__class__.__name__))

    monkeypatch.setattr(ss, "activate", lambda: Store())
    monkeypatch.setattr(ss, "shutdown", lambda: calls.append("shutdown"))
    monkeypatch.setattr(gdw_runtime.durable_storage, "enabled",
                        lambda *a, **k: pytest.fail("durable v1 must stay inert under v2"))

    def ready():
        with gdw_runtime._STATE_LOCK:
            gdw_runtime._STATE.update(startup_state="READY", blocked=None)
        return {}

    monkeypatch.setattr(gdw_runtime, "prepare_runtime", ready)
    monkeypatch.setattr(gdw_runtime, "_serve", lambda: calls.append("serve"))
    monkeypatch.setenv("GDW_OUTBOX_ENABLED", "0")
    assert gdw_runtime.main() == 0
    assert calls == [("hook", "OutboxSupervisor"), "serve", "shutdown"]


def test_runtime_health_names_the_state_store_and_retired_v1(monkeypatch):
    monkeypatch.delenv(ss.ENABLE_ENV, raising=False)
    health = gdw_runtime.runtime_health()
    assert health["durable_v1"] == "RETIRED"
    assert health["state_store"]["mode"] == ss.MODE_DISABLED
