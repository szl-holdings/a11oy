from __future__ import annotations

import copy
import importlib.util
import json
import sys
from datetime import timedelta
from pathlib import Path

import pytest
from tests.test_combined_consumers import combined, world

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("publish_readiness_verdict", ROOT / ".github/scripts/publish_readiness_verdict.py")
assert SPEC and SPEC.loader
publisher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(publisher)


@pytest.fixture
def canonical(combined):
    """Full source matrix plus actual local signed/native execution evidence."""
    value = combined
    gate = publisher.execution_validator()
    matrix = gate.canonical_matrix()
    rows = []
    for path, spec in matrix["endpoints"].items():
        mutation = path in gate.acceptance.CONTRACTS.values()
        rows.append({"path": path, "method": spec.get("method", "GET"), "required": True,
            "skipped": mutation, "runtimeState": "NOT_PROBED" if mutation else "OBSERVED",
            "samples": 0 if mutation else 1, "status": None if mutation else 200,
            "lie": False, "unreachable": False, "throttled": False, "degraded": False,
            **{field: None if mutation else True for field in ("schemaOk", "citationOk", "labelPolicyOk", "freshOk")}})
    value["matrix"] = matrix
    value["passive"]["results"] = rows
    value["passive"]["summary"].update(endpoints=len(rows), ok=len(rows)-5)
    return value


def compact(c, payload=None):
    return publisher.compact_verdict(payload if payload is not None else c["passive"],
        expected_origin="https://szlholdings-a11oy.hf.space", expected_source_sha="a"*40,
        now=c["now"], matrix=c["matrix"], execution_bundle=c["bundle"], execution_context=c["context"])


def test_compact_verdict_is_source_origin_and_freshness_bound(canonical):
    result = compact(canonical)
    assert result["schema"] == publisher.VERDICT_SCHEMA and result["sourceRevision"] == "a"*40
    assert result["base"] == "https://szlholdings-a11oy.hf.space"
    assert result["summary"]["endpoints"] == len(canonical["matrix"]["endpoints"])
    assert result["summary"]["blockingDegraded"] == 0
    assert result["summary"]["requiredNotProbed"] == result["summary"]["skippedStateChanging"] == 5
    assert result["executionCoverage"]["requiredExecutionCovered"] == 5
    assert "results" not in result


@pytest.mark.parametrize("field,value", [("schema","unknown"),("sourceRevision","b"*40),("base","https://unrelated.example")])
def test_compact_verdict_rejects_identity_drift(canonical,field,value):
    canonical["passive"][field] = value
    with pytest.raises(publisher.VerdictError,match="identity|origin|source revision"): compact(canonical)


def test_compact_verdict_rejects_future_stale_and_incomplete_results(canonical):
    for checked in (canonical["now"]+timedelta(seconds=1), canonical["now"]-timedelta(seconds=publisher.MAX_INGEST_AGE_SECONDS+1)):
        payload=copy.deepcopy(canonical["passive"]);payload["checkedAt"]=checked.isoformat().replace("+00:00","Z")
        with pytest.raises(publisher.VerdictError,match="future-dated|old"):compact(canonical,payload)
    canonical["passive"]["summary"]["endpoints"] += 1
    with pytest.raises(publisher.VerdictError,match="inconsistent"):compact(canonical)


def test_compact_verdict_rejects_doctrine_lies(canonical):
    summary=canonical["passive"]["summary"];summary["ok"]-=1;summary["lies"]=1
    canonical["passive"]["results"][0]["lie"]=True
    with pytest.raises(publisher.VerdictError):compact(canonical)


@pytest.mark.parametrize("value",[True,-1,1.5,"1",None])
def test_compact_verdict_rejects_invalid_degraded_counts(canonical,value):
    canonical["passive"]["summary"]["degraded"]=value
    with pytest.raises(publisher.VerdictError,match="counts"):compact(canonical)


def test_unavailable_required_source_cannot_be_published_as_ready(canonical):
    summary=canonical["passive"]["summary"];summary["ok"]-=1;summary["degraded"]=1
    canonical["passive"]["results"][0]["degraded"]=True
    for blocking in (1,0):
        summary["blockingDegraded"]=blocking
        # Relabeling degradation nonblocking cannot admit a failed required passive row.
        with pytest.raises(publisher.VerdictError):compact(canonical)


@pytest.mark.parametrize("value",[True,-1,2,1.5,"1",None])
def test_compact_verdict_rejects_invalid_blocking_degraded_count(canonical,value):
    canonical["passive"]["summary"]["blockingDegraded"]=value
    with pytest.raises(publisher.VerdictError):compact(canonical)


@pytest.mark.parametrize("value",[True,-1,2,1.5,"1",None])
def test_compact_verdict_rejects_invalid_required_not_probed_count(canonical,value):
    summary=canonical["passive"]["summary"];summary.update(ok=summary["endpoints"]-1,skippedStateChanging=1,requiredNotProbed=value)
    with pytest.raises(publisher.VerdictError,match="required-not-probed count"):compact(canonical)


def test_compact_verdict_blocks_required_or_unclassified_skips(canonical):
    payload=copy.deepcopy(canonical["passive"])
    del payload["summary"]["requiredNotProbed"]
    with pytest.raises(publisher.VerdictError):compact(canonical,payload)
    for required in (1,0):
        payload["summary"].update(requiredNotProbed=required,skippedStateChanging=1,ok=payload["summary"]["endpoints"]-1)
        with pytest.raises(publisher.VerdictError):compact(canonical,payload)


@pytest.mark.parametrize("failure",["unreachable","throttled"])
def test_compact_verdict_rejects_all_failed_release_evidence(canonical,failure):
    summary=canonical["passive"]["summary"];summary.update(ok=0,**{failure:summary["endpoints"]-5})
    for row in canonical["passive"]["results"]:
        if row["method"] in ("GET","HEAD"):row[failure]=True
    with pytest.raises(publisher.VerdictError):compact(canonical)


def cli_arguments(c,tmp_path):
    context=c["context"]
    values={"verdict":c["passive"],"bundle":c["bundle"],"pins":{
        "schema":"szl.execution-authority-pins/v1","approval_public_pem":context.authority_public_key.decode(),
        "approval_key_id":context.authority_key_id,"runtime_public_pem":context.runtime_public_key.decode(),"runtime_key_id":context.runtime_key_id}}
    for name,value in values.items():(tmp_path/(name+".json")).write_text(json.dumps(value),encoding="utf-8")
    return ["--validate-only","--input",str(tmp_path/"verdict.json"),"--expected-origin","https://szlholdings-a11oy.hf.space",
        "--expected-source-sha",context.source_revision,"--execution-bundle",str(tmp_path/"bundle.json"),
        "--authority-pins",str(tmp_path/"pins.json"),"--expected-runtime-sha",context.runtime_revision,
        "--expected-boot-id",context.runtime_boot_id,"--expected-run-nonce",context.run_nonce]


def test_validate_only_gates_the_verdict_without_any_space_write(canonical,tmp_path,monkeypatch,capsys):
    arguments=cli_arguments(canonical,tmp_path)
    monkeypatch.delenv("HF_TOKEN",raising=False);monkeypatch.setitem(sys.modules,"huggingface_hub",None)
    assert publisher.main(arguments)==0
    printed=json.loads(capsys.readouterr().out)
    assert printed["validated"] is True and printed["space_variable_written"] is False
    assert printed["verdict"]["executionCoverage"]["requiredExecutionCovered"]==5
    canonical["passive"]["summary"]["ok"]-=1;canonical["passive"]["summary"]["lies"]=1
    (tmp_path/"verdict.json").write_text(json.dumps(canonical["passive"]),encoding="utf-8")
    with pytest.raises(publisher.VerdictError):publisher.main(arguments)


def test_publishing_still_requires_an_explicit_target(tmp_path):
    with pytest.raises(SystemExit):publisher.main(["--input",str(tmp_path/"missing.json"),"--expected-origin","https://szlholdings-a11oy.hf.space","--expected-source-sha","a"*40])


def test_validate_only_hands_the_compact_verdict_to_relock(canonical,tmp_path,monkeypatch,capsys):
    output=tmp_path/"github-output";arguments=cli_arguments(canonical,tmp_path)+["--github-output",str(output)]
    monkeypatch.setitem(sys.modules,"huggingface_hub",None)
    assert publisher.main(arguments)==0;capsys.readouterr()
    lines=output.read_text().splitlines()
    assert len(lines)==1 and lines[0].startswith("verdict=")
    assert json.loads(lines[0][len("verdict="):])==compact(canonical)
    output.unlink();canonical["passive"]["summary"]["ok"]-=1;canonical["passive"]["summary"]["unreachable"]=1
    (tmp_path/"verdict.json").write_text(json.dumps(canonical["passive"]),encoding="utf-8")
    with pytest.raises(publisher.VerdictError):publisher.main(arguments)
    assert not output.exists()
    with pytest.raises(SystemExit):publisher.main([arg for arg in arguments if arg!="--validate-only"]+["--repo-id","SZLHOLDINGS/a11oy"])
