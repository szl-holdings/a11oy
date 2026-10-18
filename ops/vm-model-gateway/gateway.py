#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Bounded, loopback-only adapter for one declared VM model (local proposal surface)."""

import hashlib
import hmac
import http.client
import json
import os
import pathlib
import re
import socket
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

REPO = pathlib.Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
import szl_dsse  # noqa: E402 - canonical A11oy P-256 DSSE implementation

ALIAS = "prism-ml/Ternary-Bonsai-2-27B-PQ2_0"
RAW_MODEL = "./models/bonsai2-gguf/27B/Ternary-Bonsai-2-27B-PQ2_0.gguf"
MODEL_SHA256 = "3907dc1658db1f78a9826bf8d5bcb8dc65db0d466388937af57f2294fae62ec1"
UPSTREAM_HOST = "127.0.0.1"
UPSTREAM_PORT = 19483
PAYLOAD_TYPE = "application/vnd.szl.vm-model-gateway+json"
MAX_REQUEST = 65536
MAX_RESPONSE = 2097152
ALLOWED_REQUEST = {"model", "messages", "response_format", "stream", "max_tokens", "temperature", "seed"}
ALLOWED_MESSAGE = {"role", "content"}


def now():
    return datetime.now(timezone.utc).isoformat()


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def unique_pairs(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("duplicate_json_key")
        out[key] = value
    return out


def strict_json(raw):
    def bad_constant(_value):
        raise ValueError("nonfinite_json_number")
    return json.loads(raw, object_pairs_hook=unique_pairs, parse_constant=bad_constant)


def valid_request(obj):
    if not isinstance(obj, dict) or set(obj) - ALLOWED_REQUEST:
        raise ValueError("request_fields")
    if obj.get("model") != ALIAS or type(obj.get("model")) is not str:
        raise ValueError("model_alias")
    if obj.get("stream") is not False:
        raise ValueError("stream")
    messages = obj.get("messages")
    if not isinstance(messages, list) or not 1 <= len(messages) <= 16:
        raise ValueError("messages")
    for message in messages:
        if not isinstance(message, dict) or set(message) != ALLOWED_MESSAGE:
            raise ValueError("message_fields")
        if message["role"] not in ("system", "user", "assistant"):
            raise ValueError("message_role")
        if not isinstance(message["content"], str) or not message["content"] or len(message["content"]) > 16000:
            raise ValueError("message_content")
    if type(obj.get("max_tokens")) is not int or not 1 <= obj["max_tokens"] <= 1024:
        raise ValueError("max_tokens")
    temperature = obj.get("temperature")
    if type(temperature) not in (int, float) or not 0 <= temperature <= 2:
        raise ValueError("temperature")
    if "seed" in obj and (type(obj["seed"]) is not int or not -(2**31) <= obj["seed"] < 2**31):
        raise ValueError("seed")
    if "response_format" in obj and obj["response_format"] != {"type": "json_object"}:
        raise ValueError("response_format")
    return {**obj, "model": RAW_MODEL}


def valid_response(obj, max_tokens):
    if not isinstance(obj, dict) or "error" in obj or "tool_calls" in obj or obj.get("model") != RAW_MODEL:
        raise ValueError("upstream_model_mismatch")
    choices = obj.get("choices")
    if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict):
        raise ValueError("upstream_choices")
    choice = choices[0]
    message = choice.get("message")
    if choice.get("finish_reason") not in ("stop", "content_filter"):
        raise ValueError("upstream_finish_reason")
    if not isinstance(message, dict) or message.get("role") != "assistant":
        raise ValueError("upstream_role")
    if "tool_calls" in message or "function_call" in message or not isinstance(message.get("content"), str) or not message["content"]:
        raise ValueError("upstream_message")
    usage = obj.get("usage")
    if not isinstance(usage, dict) or any(type(usage.get(k)) is not int or usage[k] < 0 for k in ("prompt_tokens", "completion_tokens", "total_tokens")):
        raise ValueError("upstream_usage")
    if usage["prompt_tokens"] + usage["completion_tokens"] != usage["total_tokens"]:
        raise ValueError("upstream_usage_sum")
    if usage["completion_tokens"] > max_tokens:
        raise ValueError("upstream_completion_limit")
    return {
        "id": obj.get("id") if isinstance(obj.get("id"), str) else "",
        "object": "chat.completion",
        "created": obj.get("created") if type(obj.get("created")) is int else int(time.time()),
        "model": ALIAS,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": message["content"]}, "finish_reason": choice["finish_reason"]}],
        "usage": {k: usage[k] for k in ("prompt_tokens", "completion_tokens", "total_tokens")},
        "provenance": {"evidence_class": "DECLARED", "model_sha256": MODEL_SHA256, "upstream_model": RAW_MODEL, "gateway_acceptance": "LOCAL_ONLY"},
    }


class NoRedirectHTTP(http.client.HTTPConnection):
    """HTTPConnection does not follow redirects; this name makes the boundary explicit."""


class Gateway:
    def __init__(self, key, receipts_dir, upstream_port=UPSTREAM_PORT, signer=szl_dsse):
        if not isinstance(key, str) or len(key) < 32 or any(ch.isspace() for ch in key):
            raise ValueError("gateway_key_invalid")
        if signer is szl_dsse and not os.environ.get("SZL_COSIGN_PRIVATE_PEM"):
            raise ValueError("persistent_p256_signer_unavailable")
        if not signer.signing_available():
            raise ValueError("persistent_p256_signer_unavailable")
        self.key = key
        self.signer = signer
        self.upstream_port = upstream_port
        self.instance_id = uuid.uuid4().hex
        self.lock = threading.Lock()
        supplied_dir = pathlib.Path(receipts_dir)
        if supplied_dir.is_symlink():
            raise ValueError("receipts_directory_symlink")
        self.receipts_dir = supplied_dir.resolve(strict=True)
        if not self.receipts_dir.is_dir() or self.receipts_dir == REPO or REPO in self.receipts_dir.parents:
            raise ValueError("receipts_directory_invalid")
        self.chain_file = self.receipts_dir / "chain-head.json"
        self.previous = self._verify_existing_chain()

    def _verify_existing_chain(self):
        files = list(self.receipts_dir.glob("*.dsse.json"))
        if len(files) > 100000:
            raise ValueError("receipt_chain_too_large")
        if not files:
            if self.chain_file.exists():
                raise ValueError("chain_head_without_receipts")
            return None
        if not self.chain_file.is_file() or self.chain_file.is_symlink():
            raise ValueError("receipt_chain_head_missing")
        state = strict_json(self.chain_file.read_bytes())
        if state.get("schema") != "szl.vm-model-gateway-chain/v1" or not re.fullmatch(r"[0-9a-f]{64}", state.get("sha256", "")):
            raise ValueError("receipt_chain_head_invalid")
        by_hash = {}
        for path in files:
            if path.is_symlink():
                raise ValueError("receipt_symlink")
            raw = path.read_bytes()
            if len(raw) > 65536:
                raise ValueError("receipt_too_large")
            envelope = strict_json(raw)
            verdict = self.signer.verify_envelope(envelope)
            payload = verdict.get("payload_decoded")
            if not verdict.get("verified") or envelope.get("payloadType") != PAYLOAD_TYPE or not isinstance(payload, dict):
                raise ValueError("receipt_signature_invalid")
            if payload.get("schema") != "szl.vm-model-gateway-receipt/v1" or payload.get("phase") not in ("intent", "outcome"):
                raise ValueError("receipt_payload_invalid")
            if path.name != payload.get("request_id", "") + "-" + payload["phase"] + ".dsse.json":
                raise ValueError("receipt_filename_invalid")
            item_hash = digest(raw)
            if item_hash in by_hash:
                raise ValueError("duplicate_receipt_hash")
            by_hash[item_hash] = payload
        cursor = state["sha256"]
        visited = set()
        while cursor is not None:
            if cursor in visited or cursor not in by_hash:
                raise ValueError("receipt_chain_broken")
            visited.add(cursor)
            cursor = by_hash[cursor].get("previous_sha256")
        if len(visited) != len(files):
            raise ValueError("receipt_chain_orphan_or_fork")
        if by_hash[state["sha256"]].get("phase") != "outcome":
            raise ValueError("receipt_chain_incomplete_effect")
        return state["sha256"]

    def authorized(self, header):
        if not isinstance(header, str) or not header.startswith("Bearer ") or header.count(" ") != 1:
            return False
        return hmac.compare_digest(header[7:].encode("utf-8"), self.key.encode("utf-8"))

    def upstream_get(self, path):
        deadline = time.monotonic() + 5
        conn = NoRedirectHTTP(UPSTREAM_HOST, self.upstream_port, timeout=5)
        timer = None
        try:
            conn.connect()
            timer = self._watchdog(conn, deadline)
            conn.request("GET", path, headers={"Accept": "application/json", "Connection": "close"})
            self._remaining_timeout(conn, deadline)
            response = conn.getresponse()
            body = self._read_bounded(conn, response, deadline)
            if response.status != 200 or len(body) > MAX_RESPONSE:
                raise ValueError("upstream_get_status_or_size")
            return strict_json(body)
        finally:
            if timer is not None:
                timer.cancel()
            conn.close()

    @staticmethod
    def _watchdog(conn, deadline):
        sock = conn.sock
        if sock is None:
            raise ValueError("upstream_socket_unavailable")
        def abort():
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        timer = threading.Timer(max(0.001, deadline - time.monotonic()), abort)
        timer.daemon = True
        timer.start()
        return timer

    @staticmethod
    def _remaining_timeout(conn, deadline, response=None):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("upstream_total_deadline")
        sock = conn.sock
        if sock is None and response is not None and response.fp is not None:
            sock = getattr(getattr(response.fp, "raw", None), "_sock", None)
        if sock is None:
            raise ValueError("upstream_socket_unavailable")
        sock.settimeout(remaining)

    @classmethod
    def _read_bounded(cls, conn, response, deadline):
        content_lengths = response.headers.get_all("Content-Length", [])
        if len(content_lengths) > 1 or (content_lengths and response.headers.get_all("Transfer-Encoding", [])):
            raise ValueError("upstream_response_framing")
        declared_length = None
        if content_lengths:
            if not re.fullmatch(r"[0-9]+", content_lengths[0]):
                raise ValueError("upstream_response_length")
            declared_length = int(content_lengths[0])
            if declared_length > MAX_RESPONSE:
                raise ValueError("upstream_body_too_large")
        chunks = []
        size = 0
        while True:
            if response.isclosed():
                break
            cls._remaining_timeout(conn, deadline, response)
            chunk = response.read(min(65536, MAX_RESPONSE + 1 - size))
            if time.monotonic() > deadline:
                raise TimeoutError("upstream_total_deadline")
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
            if size > MAX_RESPONSE:
                raise ValueError("upstream_body_too_large")
        if declared_length is not None and size != declared_length:
            raise ValueError("upstream_response_truncated")
        return b"".join(chunks)

    def append_receipt(self, event):
        payload = {"schema": "szl.vm-model-gateway-receipt/v1", "at_utc": now(), "previous_sha256": self.previous, **event}
        envelope = self.signer.sign_payload(payload, PAYLOAD_TYPE)
        # The canonical signer supplies historical /cosign.pub wording; this
        # isolated audit key is locally verified and has no public trust pin.
        envelope.pop("verify_key_url", None)
        envelope["honesty"] = "REAL local P-256 DSSE signature; independent verifier UNKNOWN"
        envelope["key_trust"] = "REPO_DECLARED"
        verification = self.signer.verify_envelope(envelope)
        if not envelope.get("signed") or not verification.get("verified") or verification.get("payload_decoded") != payload:
            raise ValueError("receipt_signature_failed")
        raw = canonical(envelope)
        event_hash = digest(raw)
        destination = self.receipts_dir / (payload["request_id"] + "-" + payload["phase"] + ".dsse.json")
        with destination.open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        state = canonical({"schema": "szl.vm-model-gateway-chain/v1", "sha256": event_hash})
        tmp = self.receipts_dir / ("chain-head-" + uuid.uuid4().hex + ".tmp")
        with tmp.open("xb") as stream:
            stream.write(state)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, self.chain_file)
        self.previous = event_hash
        return event_hash

    def generate(self, request, request_raw):
        if not self.lock.acquire(blocking=False):
            return 503, {"error": "gateway_busy"}
        try:
            slots = self.upstream_get("/slots")
            if not isinstance(slots, list) or not slots or any(not isinstance(slot, dict) or slot.get("is_processing") is not False for slot in slots):
                return 503, {"error": "upstream_busy_or_unknown"}
            upstream_request = valid_request(request)
            body = canonical(upstream_request)
            request_id = uuid.uuid4().hex
            try:
                self.append_receipt({"request_id": request_id, "phase": "intent", "request_sha256": digest(request_raw), "upstream_request_sha256": digest(body), "model": ALIAS, "model_sha256": MODEL_SHA256, "effect": "ONE_INFERENCE_PROPOSAL"})
            except Exception:
                self.signer = _UnavailableSigner()
                return 503, {"error": "receipt_intent_unavailable"}
            outcome = {"request_id": request_id, "phase": "outcome", "upstream_response_sha256": None, "status": "UNKNOWN_AFTER_DISPATCH"}
            status, public = 503, {"error": "upstream_unavailable"}
            try:
                deadline = time.monotonic() + 30
                conn = NoRedirectHTTP(UPSTREAM_HOST, self.upstream_port, timeout=30)
                timer = None
                try:
                    conn.connect()
                    timer = self._watchdog(conn, deadline)
                    conn.request("POST", "/v1/chat/completions", body=body, headers={"Content-Type": "application/json", "Accept": "application/json", "Connection": "close"})
                    self._remaining_timeout(conn, deadline)
                    response = conn.getresponse()
                    raw = self._read_bounded(conn, response, deadline)
                    outcome["upstream_status"] = response.status
                    outcome["upstream_response_sha256"] = digest(raw)
                    if response.status != 200:
                        raise ValueError("upstream_status_or_size")
                    public = valid_response(strict_json(raw), request["max_tokens"])
                    outcome["downstream_response_sha256"] = digest(canonical(public))
                    outcome["status"] = "VALIDATED_RESPONSE"
                    status = 200
                finally:
                    if timer is not None:
                        timer.cancel()
                    conn.close()
            except Exception as exc:
                outcome["error_code"] = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
                public = {"error": "upstream_result_unavailable"}
            try:
                self.append_receipt(outcome)
            except Exception:
                # An intent exists, but the outcome is not sealed. Stop future effects.
                self.signer = _UnavailableSigner()
                return 503, {"error": "receipt_outcome_unavailable"}
            return status, public
        except Exception:
            return 503, {"error": "upstream_preflight_unavailable"}
        finally:
            self.lock.release()


class _UnavailableSigner:
    def signing_available(self):
        return False
    def sign_payload(self, *_args):
        raise ValueError("signer_latched_off")


class Handler(BaseHTTPRequestHandler):
    gateway = None
    protocol_version = "HTTP/1.1"

    def setup(self):
        super().setup()
        self.connection.settimeout(5)
        self._header_timer = threading.Timer(5, self._abort_socket)
        self._header_timer.daemon = True
        self._header_timer.start()

    def _abort_socket(self):
        try:
            self.connection.shutdown(2)
        except OSError:
            pass

    def parse_request(self):
        try:
            return super().parse_request()
        finally:
            self._header_timer.cancel()

    def handle_expect_100(self):
        self.send_error(417, "Expect header unsupported")
        return False

    def log_message(self, _format, *_args):
        pass  # Never log URL, authorization, or prompts.

    def send_json(self, status, obj):
        data = canonical(obj)
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(data)
        self.close_connection = True

    def auth_ok(self):
        values = self.headers.get_all("Authorization", [])
        return len(values) == 1 and self.gateway.authorized(values[0])

    def do_GET(self):
        if self.headers.get_all("Transfer-Encoding", []) or len(self.headers.as_bytes()) > 16384:
            return self.send_json(400, {"error": "http_framing"})
        if self.path == "/health":
            return self.send_json(200, {"status": "local_gateway", "evidence_class": "DECLARED", "instance_id": self.gateway.instance_id})
        if self.path != "/v1/models":
            return self.send_json(404, {"error": "not_found"})
        if not self.auth_ok():
            return self.send_json(401, {"error": "unauthorized"})
        try:
            models = self.gateway.upstream_get("/v1/models")
            data = models.get("data") if isinstance(models, dict) else None
            if not isinstance(data, list) or len(data) != 1 or data[0].get("id") != RAW_MODEL:
                raise ValueError("upstream_model_mismatch")
        except Exception:
            return self.send_json(503, {"error": "upstream_model_unavailable"})
        return self.send_json(200, {"object": "list", "data": [{"id": ALIAS, "object": "model", "provenance": {"evidence_class": "DECLARED", "model_sha256": MODEL_SHA256}}]})

    def do_POST(self):
        if self.path != "/v1/chat/completions":
            return self.send_json(404, {"error": "not_found"})
        if not self.auth_ok():
            return self.send_json(401, {"error": "unauthorized"})
        if len(self.headers.as_bytes()) > 16384:
            return self.send_json(400, {"error": "http_framing"})
        if len(self.headers.get_all("Content-Length", [])) != 1 or self.headers.get_all("Transfer-Encoding", []):
            return self.send_json(400, {"error": "http_framing"})
        if self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
            return self.send_json(415, {"error": "content_type"})
        try:
            length_raw = self.headers.get("Content-Length", "")
            if not re.fullmatch(r"[0-9]{1,5}", length_raw):
                raise ValueError("content_length")
            length = int(length_raw)
            if not 0 < length <= MAX_REQUEST:
                raise ValueError("content_length")
            self.connection.settimeout(5)
            body_timer = threading.Timer(5, self._abort_socket)
            body_timer.daemon = True
            body_timer.start()
            try:
                raw = self.rfile.read(length)
            finally:
                body_timer.cancel()
            if len(raw) != length:
                raise ValueError("short_body")
            request = strict_json(raw)
            valid_request(request)
        except Exception:
            return self.send_json(400, {"error": "invalid_request"})
        status, result = self.gateway.generate(request, raw)
        return self.send_json(status, result)


class BoundedServer(ThreadingHTTPServer):
    request_queue_size = 8
    daemon_threads = True

    def __init__(self, address, handler):
        self._workers = threading.BoundedSemaphore(8)
        super().__init__(address, handler)

    def get_request(self):
        sock, address = super().get_request()
        sock.settimeout(5)
        return sock, address

    def process_request(self, request, client_address):
        if not self._workers.acquire(blocking=False):
            request.close()
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self._workers.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._workers.release()


def main():
    key = os.environ.get("SZL_LITELLM_KEY", "")
    receipt_path = os.environ.get("SZL_VM_GATEWAY_RECEIPTS_DIR", "")
    if not os.environ.get("SZL_COSIGN_PRIVATE_PEM") or not receipt_path:
        raise SystemExit("persistent signer and receipts directory required")
    gateway = Gateway(key, receipt_path)
    Handler.gateway = gateway
    with BoundedServer(("127.0.0.1", 4000), Handler) as server:
        server.serve_forever(poll_interval=0.2)


if __name__ == "__main__":
    main()
