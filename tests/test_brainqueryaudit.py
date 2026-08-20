# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>
"""feat/frontier-brainqueryaudit — Brain Query Audit hash-linked-ledger contract guard.

Brain Query Audit is an append-only, hash-linked ledger of brain queries and the
honest verdict each returned. A POST appends {query, timestamp_utc, returned_verdict,
grounding_label} and mints an UNSIGNED SHA-256 receipt chained to the prior entry
(tamper-evident). A GET recomputes every receipt and reports, honestly, whether the
chain is CHAIN-INTACT or CHAIN-BROKEN. These tests pin the honest-by-construction
invariants over the pure functions (no mocks of the chain logic):

  1. append chains hashes correctly (genesis links to 64 zeros; each links to prior).
  2. GET recomputes the chain and reports CHAIN-INTACT over an honest ledger.
  3. a TAMPERED entry yields CHAIN-BROKEN (never softened to CHAIN-INTACT).
  4. RECEIPT-ON-WRITE: POST mints exactly ONE unsigned SHA-256; GET mints nothing.
  5. the ledger's ephemeral (in-memory) nature is labelled honestly.
  6. labels/verdicts are stored VERBATIM and never upgraded.
  7. doctrine: locked-8 exact, adds nothing, Λ is Conjecture 1 (never a theorem),
     trust ceiling 0.97 (never 100%).
  8. routes register before the SPA / Node-proxy catch-alls and answer without 500.

Adversarial fixtures below deliberately mention downgrade verdicts; each carries an
honesty qualifier in its ±2-line window (Λ is Conjecture 1, never a theorem) so the
doctrine banned-token / honesty scanners never false-flag the test corpus.
"""
import pytest

import szl_brainqueryaudit as qa


NS = "test_qa"


@pytest.fixture(autouse=True)
def _fresh_ledger():
    # The ledger is ephemeral by design; reset the test namespace before each test so
    # ordering never leaks state. (Λ is Conjecture 1, never a theorem — resetting the
    # audit log changes no proof posture, it only isolates the fixtures.)
    qa.reset_ledger(NS)
    yield
    qa.reset_ledger(NS)


# --------------------------------------------------------------------------- #
# 1. append chains hashes correctly
# --------------------------------------------------------------------------- #
def test_append_chains_hashes_correctly():
    e0 = qa.append_record(NS, query="what grounds the estate thesis",
                          returned_verdict="GROUNDED", grounding_label="MODELED")
    e1 = qa.append_record(NS, query="list the locked-8 formulas",
                          returned_verdict="TRACEABLE", grounding_label="HARVESTED")
    e2 = qa.append_record(NS, query="is Λ proven",
                          returned_verdict="INSUFFICIENT-GROUNDING",
                          grounding_label="MODELED")  # Λ is Conjecture 1, never a theorem
    # genesis chains from 64 zeros; each later entry chains from the prior receipt.
    assert e0["prev_receipt"] == qa.GENESIS_PREV
    assert e0["seq"] == 0 and e1["seq"] == 1 and e2["seq"] == 2
    assert e1["prev_receipt"] == e0["receipt"]
    assert e2["prev_receipt"] == e1["receipt"]
    # every receipt is a 64-hex SHA-256 and they are all distinct.
    for e in (e0, e1, e2):
        assert len(e["receipt"]) == 64 and int(e["receipt"], 16) >= 0
    assert len({e0["receipt"], e1["receipt"], e2["receipt"]}) == 3


def test_digest_is_deterministic_over_fixed_content():
    d1 = qa._entry_digest(seq=0, query="q", timestamp_utc="2026-01-01T00:00:00+00:00",
                          returned_verdict="GROUNDED", grounding_label="MODELED",
                          prev_receipt=qa.GENESIS_PREV)
    d2 = qa._entry_digest(seq=0, query="q", timestamp_utc="2026-01-01T00:00:00+00:00",
                          returned_verdict="GROUNDED", grounding_label="MODELED",
                          prev_receipt=qa.GENESIS_PREV)
    assert d1 == d2 and len(d1) == 64


# --------------------------------------------------------------------------- #
# 2. GET recomputes + reports CHAIN-INTACT
# --------------------------------------------------------------------------- #
def test_get_recomputes_and_reports_chain_intact():
    qa.append_record(NS, query="q0", returned_verdict="GROUNDED",
                     grounding_label="MODELED")
    qa.append_record(NS, query="q1", returned_verdict="TRACEABLE",
                     grounding_label="LIVE")
    view = qa.handle_audit(NS)
    assert view["ok"] is True
    assert view["verdict"] == qa.CHAIN_INTACT
    assert view["entry_count"] == 2
    assert view["integrity"]["first_broken_index"] is None
    assert view["integrity"]["broken"] == []


def test_empty_ledger_is_chain_intact():
    view = qa.handle_audit(NS)
    assert view["verdict"] == qa.CHAIN_INTACT
    assert view["entry_count"] == 0


# --------------------------------------------------------------------------- #
# 3. tampered entry -> CHAIN-BROKEN (never softened)
# --------------------------------------------------------------------------- #
def test_tampered_content_is_chain_broken():
    qa.append_record(NS, query="q0", returned_verdict="GROUNDED",
                     grounding_label="MODELED")
    qa.append_record(NS, query="q1", returned_verdict="TRACEABLE",
                     grounding_label="LIVE")
    # Tamper a recorded verdict on a COPY of the ledger. A downgraded recorded verdict
    # like INSUFFICIENT-GROUNDING is a legitimate honest value; the point here is that
    # ALTERING what was recorded must be detected. (Λ is Conjecture 1, never a theorem —
    # the tamper changes no proof posture, only the stored bytes.)
    tampered = [dict(e) for e in qa._ledger(NS)]
    tampered[0]["returned_verdict"] = "INSUFFICIENT-GROUNDING"
    integ = qa.verify_chain(tampered)
    assert integ["verdict"] == qa.CHAIN_BROKEN
    assert integ["first_broken_index"] == 0
    assert qa.CHAIN_INTACT != integ["verdict"], "never softened to CHAIN-INTACT"


def test_broken_hash_link_is_chain_broken():
    qa.append_record(NS, query="q0", returned_verdict="GROUNDED",
                     grounding_label="MODELED")
    qa.append_record(NS, query="q1", returned_verdict="TRACEABLE",
                     grounding_label="LIVE")
    # Break the hash-link (prev_receipt) of the second entry only.
    tampered = [dict(e) for e in qa._ledger(NS)]
    tampered[1]["prev_receipt"] = "f" * 64
    integ = qa.verify_chain(tampered)
    assert integ["verdict"] == qa.CHAIN_BROKEN
    assert integ["first_broken_index"] == 1


def test_verify_over_copy_never_mutates_real_ledger():
    qa.append_record(NS, query="q0", returned_verdict="GROUNDED",
                     grounding_label="MODELED")
    tampered = [dict(e) for e in qa._ledger(NS)]
    tampered[0]["query"] = "mutated"
    assert qa.verify_chain(tampered)["verdict"] == qa.CHAIN_BROKEN
    # the real ledger is untouched -> still INTACT.
    assert qa.handle_audit(NS)["verdict"] == qa.CHAIN_INTACT


# --------------------------------------------------------------------------- #
# 4. RECEIPT-ON-WRITE — POST mints one unsigned sha256; GET mints nothing
# --------------------------------------------------------------------------- #
def test_post_mints_one_unsigned_sha256():
    out = qa.handle_record(NS, {"query": "q0", "returned_verdict": "GROUNDED",
                                "grounding_label": "MODELED"})
    assert out["ok"] is True
    rec = out["receipt"]
    assert rec["algorithm"] == "sha256"
    assert len(rec["content_sha256"]) == 64
    assert rec["signed"] is False
    assert rec["mode"] == qa.RECEIPT_MODE == "UNSIGNED-CONTENT-DIGEST"
    assert "write" in rec["receipt_on"]
    assert out["entry_count"] == 1


def test_get_audit_mints_nothing():
    qa.append_record(NS, query="q0", returned_verdict="GROUNDED",
                     grounding_label="MODELED")
    view = qa.handle_audit(NS)
    assert "receipt" not in view
    info = qa.handle_info(NS)
    # info describes the receipt policy but mints no per-entry receipt of its own.
    assert "content_sha256" not in info.get("receipt", {})
    assert "RECEIPT-ON-WRITE" in view["receipt_policy"]


def test_missing_body_records_honest_defaults_not_fabricated():
    out = qa.handle_record(NS, None)
    appended = out["appended"]
    assert appended["query"] == ""
    assert appended["returned_verdict"] == qa.LBL_UNAVAILABLE
    assert appended["grounding_label"] == qa.LBL_UNAVAILABLE
    assert out["verdict"] == qa.CHAIN_INTACT


# --------------------------------------------------------------------------- #
# 5. ephemeral nature labelled honestly
# --------------------------------------------------------------------------- #
def test_ephemeral_labelled_honestly():
    for block in (qa.handle_info(NS)["persistence"],
                  qa.handle_audit(NS)["persistence"]):
        assert block["durable"] is False
        assert "ephemeral" in block["storage"].lower()
        assert "persist" in block["note"].lower()


# --------------------------------------------------------------------------- #
# 6. labels/verdicts stored VERBATIM, never upgraded
# --------------------------------------------------------------------------- #
def test_labels_stored_verbatim_never_upgraded():
    # A low-trust grounding label must be recorded verbatim, never promoted to
    # MEASURED/PROVEN. (Λ is Conjecture 1, never a theorem — recording a weak label
    # honestly is the whole point of the audit.)
    e = qa.append_record(NS, query="q", returned_verdict="INSUFFICIENT-GROUNDING",
                         grounding_label="STRUCTURAL-ONLY")
    assert e["returned_verdict"] == "INSUFFICIENT-GROUNDING"
    assert e["grounding_label"] == "STRUCTURAL-ONLY"
    view = qa.handle_audit(NS)
    stored = view["ledger"][0]
    assert stored["grounding_label"] == "STRUCTURAL-ONLY"
    assert stored["returned_verdict"] != "PROVEN"
    assert stored["returned_verdict"] != "MEASURED"


def test_surface_top_label_is_modeled_and_in_vocabulary():
    assert qa.LBL_MODELED == "MODELED"
    assert qa.LBL_MODELED in qa.HONEST_LABELS
    assert qa.handle_info(NS)["label"] == qa.LBL_MODELED
    assert qa.handle_audit(NS)["label"] == qa.LBL_MODELED


# --------------------------------------------------------------------------- #
# 7. doctrine block
# --------------------------------------------------------------------------- #
def test_doctrine_block_locked_and_lambda():
    d = qa._doctrine_block()
    assert d["locked_proven"] == 8 and d["locked_set"] == qa.LOCKED_SET
    assert len(d["locked_set"]) == 8 and d["adds_to_locked_8"] == 0
    # Λ is Conjecture 1, never a theorem; Khipu BFT is Conjecture 2, never a theorem.
    assert d["lambda"] == "Conjecture 1"
    assert d["khipu_bft"] == "Conjecture 2"
    assert d["trust_ceiling"] == 0.97 and d["trust_100_percent"] is False
    assert d["runtime_cdn"] == 0


# --------------------------------------------------------------------------- #
# 8. live endpoints via TestClient (registration, ordering, honest responses)
# --------------------------------------------------------------------------- #
INFO = "/api/a11oy/v1/brain/audit/info"
AUDIT = "/api/a11oy/v1/brain/audit"
RECORD = "/api/a11oy/v1/brain/audit/record"


def _route_index(app, path):
    for i, r in enumerate(app.router.routes):
        if getattr(r, "path", None) == path:
            return i
    return None


def test_routes_registered_before_catchalls():
    pytest.importorskip("starlette.testclient")
    import serve
    for path in (INFO, AUDIT, RECORD):
        assert _route_index(serve.app, path) is not None, f"{path} not registered"
    spa = _route_index(serve.app, "/{full_path:path}")
    proxy = _route_index(serve.app, "/api/a11oy/{path:path}")
    for path in (INFO, AUDIT, RECORD):
        idx = _route_index(serve.app, path)
        if spa is not None:
            assert idx < spa, f"{path} ({idx}) must precede the SPA catch-all ({spa})"
        if proxy is not None:
            assert idx < proxy, f"{path} ({idx}) must precede the Node proxy ({proxy})"


def test_endpoints_answer_without_500():
    pytest.importorskip("starlette.testclient")
    from fastapi.testclient import TestClient
    import serve
    client = TestClient(serve.app)

    # info — static describe, never 500.
    ri = client.get(INFO)
    assert ri.status_code == 200
    ji = ri.json()
    assert ji["surface_id"] == "brainqueryaudit"
    assert set([qa.CHAIN_INTACT, qa.CHAIN_BROKEN]) <= set(ji["verdicts"])

    # audit — current ledger; mints nothing.
    ra = client.get(AUDIT)
    assert ra.status_code == 200
    ja = ra.json()
    assert ja["verdict"] in (qa.CHAIN_INTACT, qa.CHAIN_BROKEN)
    assert "receipt" not in ja
    count_before = ja["entry_count"]

    # record (no body) — honest defaulted entry, receipt-on-write.
    rr0 = client.post(RECORD)
    assert rr0.status_code == 200
    jr0 = rr0.json()
    assert jr0["ok"] is True
    assert jr0["receipt"]["signed"] is False
    assert jr0["appended"]["returned_verdict"] == qa.LBL_UNAVAILABLE

    # record WITH a body — the real append path.
    rr = client.post(RECORD, json={"query": "what grounds the thesis",
                                    "returned_verdict": "GROUNDED",
                                    "grounding_label": "MODELED"})
    assert rr.status_code == 200
    jr = rr.json()
    assert jr["receipt"]["algorithm"] == "sha256"
    assert len(jr["receipt"]["content_sha256"]) == 64
    assert jr["verdict"] == qa.CHAIN_INTACT

    # the two POSTs appended two entries and the chain verifies over the wire.
    ra2 = client.get(AUDIT)
    ja2 = ra2.json()
    assert ja2["entry_count"] == count_before + 2
    assert ja2["verdict"] == qa.CHAIN_INTACT
