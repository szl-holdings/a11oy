"""Offline delivery accounting; fixtures never authorize a provider write."""

import json
import threading
from unittest.mock import Mock
from urllib.error import HTTPError

import pytest

from szl_khipu_replicate import Replicator


PEERS = ["https://szlholdings-a11oy.hf.space", "https://peer.example"]
BATCH = [{"seq": 0, "digest": "fixture-0"}, {"seq": 1, "digest": "fixture-1"}]
ACK = {"accepted": 2, "rejected": 0}


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.delenv("KHIPU_REPLICATION", raising=False)
    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: pytest.fail("network forbidden"))


def replicator(peers=PEERS, source=None):
    instance = Replicator("fixture", peers=peers, source_fn=source or Mock(return_value=BATCH))
    instance.enable()
    return instance


def test_disabled_is_default_and_does_not_read_or_send():
    source = Mock(side_effect=AssertionError("source must not run"))
    instance = Replicator("fixture", peers=PEERS, source_fn=source)
    instance._post = Mock(side_effect=AssertionError("delivery must not run"))
    assert instance.push_once() == {"pushed": 0, "enabled": False, "reason": "replication disabled"}
    assert instance.status()["cursor"] == 0
    source.assert_not_called()
    instance._post.assert_not_called()


def test_no_peers_preserves_cursor_without_reading_the_batch():
    source = Mock(side_effect=AssertionError("source must not run"))
    instance = replicator(peers=[], source=source)
    assert instance.push_once()["pushed"] == 0
    assert instance.status()["cursor"] == 0
    source.assert_not_called()


def test_http_401_preserves_batch_for_later_acknowledged_retry(monkeypatch):
    cursors, requests = [], []
    def source(cursor):
        cursors.append(cursor)
        return BATCH if cursor == 0 else []

    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self): return json.dumps(ACK).encode()

    def send(request, **kwargs):
        requests.append(request)
        assert request.get_header("Authorization") is None
        assert json.loads(request.data) == {"receipts": BATCH}
        if len(requests) == 1:
            raise HTTPError(request.full_url, 401, "secret-provider-message", {}, None)
        return Response()

    monkeypatch.setattr("urllib.request.urlopen", send)
    instance = replicator(peers=PEERS[:1], source=source)
    first = instance.push_once()
    assert first["pushed"] == 0
    assert first["results"] == {"peer_1": {"error": "AUTHENTICATION_REQUIRED"}}
    assert first["enabled"] is True and first["paused_reason"] is None
    assert instance.status()["cursor"] == 0
    assert instance.status()["last_push"]["count"] == 0
    assert instance.push_once()["pushed"] == 2
    assert instance.status()["cursor"] == 2
    assert instance.push_once()["pushed"] == 0
    assert cursors == [0, 0, 2] and len(requests) == 2


def test_partial_peer_delivery_pauses_without_skipping_or_replaying_batch():
    instance = replicator()
    instance._post = Mock(side_effect=[ACK, {"accepted": 1, "rejected": 1}])
    result = instance.push_once()
    assert result["pushed"] == 0 and result["enabled"] is False
    assert result["paused_reason"] == "RECONCILIATION_REQUIRED"
    assert instance.status()["cursor"] == 0
    assert instance.push_once() == {"pushed": 0, "enabled": False, "reason": "RECONCILIATION_REQUIRED"}
    assert [call.args[0] for call in instance._post.call_args_list] == PEERS
    assert [call.args[0] for call in instance.source_fn.call_args_list] == [0]


@pytest.mark.parametrize("ack", [
    None, [], {}, {"accepted": 2}, {"accepted": 2, "rejected": False},
    {"accepted": True, "rejected": 0}, {"accepted": "2", "rejected": 0},
    {"accepted": 2.0, "rejected": 0}, {"accepted": 2, "rejected": 0.0},
    {"accepted": -1, "rejected": 0}, {"accepted": 0, "rejected": 2},
    {"accepted": 1, "rejected": 0}, {"accepted": 3, "rejected": 0},
    {"accepted": 2, "rejected": -1}, {"accepted": 2, "rejected": 1},
])
def test_incomplete_or_malformed_acknowledgements_never_advance(ack):
    instance = replicator(peers=PEERS[:1])
    instance._post = Mock(return_value=ack)
    result = instance.push_once()
    assert result["pushed"] == 0 and instance.status()["cursor"] == 0
    assert result["enabled"] is False and result["paused_reason"] == "RECONCILIATION_REQUIRED"
    assert result["results"] == {"peer_1": {"error": "ACKNOWLEDGEMENT_INVALID"}}
    instance.push_once()
    instance._post.assert_called_once()


def test_status_and_delivery_results_do_not_echo_peer_urls_or_provider_data():
    instance = replicator(peers=["https://user:secret@peer.example/private?token=secret"])
    instance._post = Mock(side_effect=[RuntimeError("secret https://signed.example/?sig=secret"),
                                      {**ACK, "private": "secret"}])
    assert instance.push_once()["pushed"] == 0
    assert "secret" not in json.dumps(instance.status())
    # Explicit local reset models the existing operator API, not a claim that
    # production readback or receiver deduplication has been qualified.
    instance.enable()
    result = instance.push_once()
    assert result["pushed"] == 2
    assert result["results"] == {"peer_1": ACK}
    assert "secret" not in json.dumps(instance.status())


@pytest.mark.parametrize("failure", [TimeoutError("secret"),
    HTTPError("https://private.example?token=secret", 503, "secret", {}, None)])
def test_unknown_delivery_stops_remaining_peers_and_later_automatic_attempts(failure):
    instance = replicator()
    instance._post = Mock(side_effect=failure)
    result = instance.push_once()
    assert result["enabled"] is False and result["pushed"] == 0
    assert result["results"]["peer_2"] == {"error": "NOT_ATTEMPTED_RECONCILIATION_REQUIRED"}
    assert instance.push_once()["reason"] == "RECONCILIATION_REQUIRED"
    assert instance.status()["cursor"] == 0
    instance._post.assert_called_once()
    instance.source_fn.assert_called_once_with(0)


@pytest.mark.parametrize("reverse", [False, True])
def test_acknowledged_peer_plus_authentication_refusal_requires_readback(reverse):
    responses = [ACK, HTTPError(PEERS[1], 401, "BLOCKED", {}, None)]
    instance = replicator()
    instance._post = Mock(side_effect=list(reversed(responses)) if reverse else responses)
    result = instance.push_once()
    assert result["pushed"] == 0 and result["enabled"] is False
    assert result["paused_reason"] == "RECONCILIATION_REQUIRED"
    assert instance.status()["cursor"] == 0
    assert instance.push_once()["pushed"] == 0
    assert instance._post.call_count == 2


def test_every_peer_must_acknowledge_before_any_cursor_advance():
    instance = replicator()
    instance._post = Mock(return_value=ACK)
    assert instance.push_once()["pushed"] == len(BATCH)
    assert instance.status()["cursor"] == len(BATCH)
    assert instance.status()["paused_reason"] is None
    assert [call.args[0] for call in instance._post.call_args_list] == PEERS


@pytest.mark.parametrize("source", [None, {}, ["invalid"], RuntimeError("secret")])
def test_unavailable_source_never_sends_or_advances(source):
    read = Mock(side_effect=source) if isinstance(source, Exception) else Mock(return_value=source)
    instance = replicator(source=read)
    instance._post = Mock(side_effect=AssertionError("delivery must not run"))
    assert instance.push_once()["pushed"] == 0
    assert instance.status()["cursor"] == 0
    instance._post.assert_not_called()


def test_concurrent_pushes_serialize_cursor_and_do_not_send_the_same_batch_twice():
    entered, release, second_started = threading.Event(), threading.Event(), threading.Event()
    cursors, results = [], []
    def source(cursor):
        cursors.append(cursor)
        return BATCH if cursor == 0 else []
    def send(*args):
        entered.set()
        assert release.wait(5)
        return ACK
    instance = replicator(peers=PEERS[:1], source=source)
    instance._post = Mock(side_effect=send)
    def push(second=False):
        if second:
            second_started.set()
        results.append(instance.push_once())
    first = threading.Thread(target=push)
    second = threading.Thread(target=push, args=(True,))
    try:
        first.start()
        assert entered.wait(5)
        second.start()
        assert second_started.wait(5)
    finally:
        release.set()
        first.join(5)
        if second.ident is not None:
            second.join(5)
    assert not first.is_alive() and not second.is_alive()
    assert sorted(result["pushed"] for result in results) == [0, 2]
    assert cursors == [0, 2] and instance.status()["cursor"] == 2
    instance._post.assert_called_once()
