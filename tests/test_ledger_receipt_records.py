#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""The ONE chain reports receipt records, not signed receipts, and read paths never mint.

GET /api/a11oy/v1/pcai/run used to append a MODELED probe to szl.lake.receipt/v1 on every
call and store only a `signed` boolean. The org overview then published the whole chain depth
as `thesis_stats.signed_receipts`.
"""

import base64
import json
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import szl_dsse
import szl_lake_store
import szl_org_lambda
import szl_proof_carrying_infer

ROOT = Path(__file__).resolve().parents[1]
# 70 opaque bytes, the size of a DER ECDSA-P256 signature. Never verified by these tests.
_SIG_B64 = base64.b64encode(bytes(range(70))).decode("ascii")


def _signing_disabled(*_args, **_kwargs):
    raise RuntimeError("signing disabled in this test")


def test_pcai_get_never_appends_to_lambda_ledger(monkeypatch):
    emitted = []
    monkeypatch.setattr(
        szl_org_lambda,
        "emit",
        lambda *args, **kwargs: emitted.append((args, kwargs)),
    )
    # The handler still runs the DSSE signer (a separate follow-up). Keep this test from signing
    # on a machine that happens to hold a cosign key: _sign_statement then takes its UNSIGNED-LOCAL
    # fallback.
    monkeypatch.setattr(szl_dsse, "sign_payload", _signing_disabled)

    response = szl_proof_carrying_infer._h_pcai_run(
        SimpleNamespace(query_params={"seed": "42", "model": "szl-modeled-lm"})
    )
    body = json.loads(response.body)

    assert emitted == []
    assert body["label"] == "MODELED"
    assert body["dsse"]["signed"] is False
    assert body["receipt_minted"] is False


def _probe(ts):
    return {
        "organ": "a11oy", "action": "pcai/run", "verb": "a11oy|pcai/run", "ts": ts,
        "payload": {"label": "MODELED", "seed": 42, "model": "szl-modeled-lm", "signed": True},
    }


def _with_sig(ts, sig):
    return {
        "organ": "a11oy-pinn", "action": "pinn/solve", "ts": ts, "signed": True,
        "dsse": {"payloadType": "application/vnd.in-toto+json", "payload": "e30=",
                 "signatures": [{"keyid": "szlholdings-cosign", "sig": sig}],
                 "signed": True},
    }


def _unsigned(ts):
    return {
        "organ": "a11oy-pinn", "action": "pinn/solve", "ts": ts, "signed": False,
        "dsse": {"payloadType": "application/vnd.in-toto+json", "payload": "e30=",
                 "signatures": [], "signed": False},
    }


def test_overview_counts_records_signature_bytes_and_probes_separately(monkeypatch, tmp_path):
    ledger = szl_lake_store.ReceiptLedger(str(tmp_path))
    for rec in (
        _probe("2026-09-25T00:00:01Z"),
        _probe("2026-09-25T00:00:02Z"),
        _with_sig("2026-09-25T00:00:03Z", _SIG_B64),
        _unsigned("2026-09-25T00:00:04Z"),
        _with_sig("2026-09-25T00:00:05Z", "DSSE_PLACEHOLDER"),
    ):
        assert ledger.append(rec)["accepted"] is True

    monkeypatch.setattr(szl_org_lambda, "_LAKE_OK", True)
    monkeypatch.setattr(szl_org_lambda._lake, "get_default_ledger", lambda: ledger)

    overview = szl_org_lambda.org_overview()
    ts = overview["thesis_stats"]

    assert "signed_receipts" not in ts
    assert "dsse_signed_records" not in ts
    assert ts["receipt_records"] == 5
    assert ts["dsse_sig_bytes_records"] == 1
    assert ts["modeled_probe_records"] == 2
    assert overview["chain"]["depth"] == 5
    assert "signed_receipts" not in overview["honest_notes"]
    assert "not verified" in overview["honest_notes"]["dsse_sig_bytes_records"]


def test_landing_reads_record_count_not_signed_count():
    landing = (ROOT / "a11oy_landing.html").read_text(encoding="utf-8")

    assert "One ledger. Every decision." not in landing
    # Overview/lake totals cannot replace the ledger's own returned window.
    assert "ts.receipt_records" not in landing
    assert "ts.signed_receipts" not in landing
    assert "__lakeReceiptTotal" not in landing
    assert 'id="chain-split"' in landing
    node = shutil.which("node")
    assert node, "Node is required to exercise the shipped landing receipt renderer"
    result = subprocess.run(
        [node, "-e", r'''
const assert=require('node:assert/strict'), fs=require('node:fs'), vm=require('node:vm');
const source=fs.readFileSync(0,'utf8');
const start=source.indexOf('  function ledgerReading(d){');
const end=source.indexOf('  // ---- (A)',start);
assert(start>=0 && end>start, 'The shipped ledger renderer must be present');
const nodes=new Map();
const node=id=>{if(!nodes.has(id))nodes.set(id,{textContent:'',innerHTML:''});return nodes.get(id);};
const context=vm.createContext({$:node, grayChip:s=>s, downChip:s=>s});
vm.runInContext(source.slice(start,end),context);
const empty={count:0,receipts:[],state:'live',data_kind:'live',operational:true,signature_state:'UNSIGNED'};
function counts(expected){for(const id of ['hs-receipts','chain-receipts','chain-depth'])assert.equal(node(id).textContent,expected);}
const reading=context.setHeroReceiptsFromLedger(empty);
assert.equal(reading.state,'OPERATIONAL'); counts('0');
assert.match(node('chain-split').textContent,/UNSIGNED/);
assert.match(node('hs-receipts-label').textContent,/Operational receipt records.*returned window/);
context.setHeroReceiptsFromLedger({...empty,count:1,receipts:[{digest:'a'.repeat(64),signed:true}],state:'sample',data_kind:'sample',operational:false,signature_state:'SIGNED'});
counts('1');
assert.match(node('hs-receipts-label').textContent,/SAMPLE.*not operational receipts/);
assert.equal(node('chain-split').textContent,'Signature reported · not verified here');
for(const invalid of [null,{...empty,count:1},{...empty,operational:false}]){
  assert.equal(context.setHeroReceiptsFromLedger(invalid),null); counts('UNAVAILABLE');
  assert.equal(node('chain-head').textContent,'UNAVAILABLE');
  assert.equal(node('chain-split').textContent,'Signer state unavailable');
}
'''],
        input=landing, text=True, capture_output=True, timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr
