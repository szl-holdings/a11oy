# SPDX-License-Identifier: Apache-2.0
"""The existing publisher must qualify one exact Finance target before writing."""
from copy import deepcopy
import importlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import pytest

analytics = importlib.import_module("verticals.puriq-markets.runtime.analytics")
transport = importlib.import_module("verticals.puriq-markets.runtime.transport")
REVISION = "1" * 40


@pytest.fixture
def publisher(monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location("scope_fixture", Path(__file__).resolve().parents[1] / "scripts/hf_publish_vertical_flagships_v4.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setenv("GITHUB_SHA", REVISION)
    monkeypatch.setattr(module, "_github_json", lambda *a, **k: {"sha":REVISION})
    client = transport.FinanceClient(environ={"SZL_SOURCE_REVISION":REVISION})
    state = {"body":analytics.compute(client, "signals", "AAPL", "fixture"), "writes":[]}
    class Response:
        status = 200
        headers = {"Content-Type":"application/json"}
        def __enter__(self): return self
        def __exit__(self,*a): pass
        def geturl(self): return state["url"]
        def read(self,limit): return json.dumps(state["body"]).encode()[:limit]
    class Opener:
        def open(self,request,timeout):
            assert timeout == 15
            state["url"] = request.full_url
            return Response()
    monkeypatch.setattr(module.urllib.request, "build_opener", lambda *a: Opener())
    monkeypatch.chdir(tmp_path)
    return module, state


def test_preflight_qualifies_exact_fixture_and_preserves_live_limit(publisher):
    module, state = publisher
    result = module.finance_preflight()
    assert result["fixture_preflight"] is True and result["live_provider_verified"] is False
    assert result["source_revision"] == REVISION and result["component"] == analytics.COMPONENT


@pytest.mark.parametrize("change", ["source", "component", "flags", "truth", "payload", "signature", "authority", "symbol", "origin", "operation"])
def test_preflight_rejects_tampered_or_misbound_backend(publisher, change):
    module, state = publisher
    body = state["body"]
    if change == "source": body["source_revision"] = "2" * 40
    elif change == "component": body["component"] = {**body["component"],"revision":"2"*40}
    elif change == "flags": body["execution_enabled"] = True
    elif change == "truth": body["truth_label"] = "MEASURED"
    elif change == "payload": body["result"]["verdict"] = "TAMPERED"
    elif change == "signature": body["receipt"]["signed"] = True
    elif change == "authority": body["receipt"]["authority"] = "TRADING"
    elif change == "symbol": body["result"]["symbol"] = "WRONG"
    elif change == "origin": body["inputs"]["asset"]["origin"] = "coinbase"
    else: body["operation"] = "quote"
    with pytest.raises(RuntimeError): module.finance_preflight()


def test_preflight_refuses_moved_main_before_backend_request(publisher, monkeypatch):
    module, state = publisher
    monkeypatch.setattr(module,"_github_json",lambda *a, **k:{"sha":"2"*40})
    with pytest.raises(RuntimeError,match="current main"): module.finance_preflight()
    assert "url" not in state


def test_failed_preflight_causes_zero_publication_calls(publisher, monkeypatch):
    module, state = publisher
    state["body"]["source_revision"] = "2" * 40
    monkeypatch.setattr(module,"run_publisher",lambda *a,**k:pytest.fail("write attempted before preflight"))
    assert module.publish_finance_only(SimpleNamespace(guard_report=lambda:{})) == 1
    assert json.loads(module.FLAGSHIP_RECEIPT.read_text())["complete"] is False


def test_finance_scope_has_exactly_one_existing_writer_target(publisher, monkeypatch):
    module, state = publisher
    def run(name,path,**kwargs):
        state["writes"].append((name,path,kwargs))
        module.FLAGSHIP_RECEIPT.write_text(json.dumps({"complete":True,"rows":[{"id":"SZLHOLDINGS/finance"}]}))
        return 0,None,("finance",)
    monkeypatch.setattr(module,"run_publisher",run)
    assert module.publish_finance_only(SimpleNamespace(guard_report=lambda:{"existing_only":True})) == 0
    assert state["writes"] == [("szl_flagship_v4",module.FLAGSHIP_IMPL,{"finance_only":True})]
    receipt = json.loads(module.FLAGSHIP_RECEIPT.read_text())
    assert receipt["sibling_publications"] == 0 and receipt["delete_operations"] == 0


def test_finance_filter_cannot_leak_sibling_targets(publisher,monkeypatch):
    module, _ = publisher
    renderer = SimpleNamespace(FLAGSHIPS=tuple({"slug":slug} for slug in (*module.PUBLIC_FLAGSHIP_SLUGS,*module.FOLDED_INTO_KILLINCHU)))
    def run():
        assert renderer.FLAGSHIPS == ({"slug":"finance"},)
        return 0
    renderer.main = run
    monkeypatch.setattr(module,"load_module",lambda *a:renderer)
    assert module.run_publisher("szl_flagship_v4",module.FLAGSHIP_IMPL,finance_only=True) == (0,None,("finance",))
