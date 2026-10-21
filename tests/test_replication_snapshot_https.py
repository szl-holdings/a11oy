# SPDX-License-Identifier: Apache-2.0
"""Real TLS/process loss with consumer handlers and SIMULATED storage providers."""
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import queue
import secrets
import shutil
import ssl
import subprocess
import sys
import threading

from fastapi import FastAPI
from fastapi.testclient import TestClient

import a11oy_state_store as ss
from khipu_lmdb import KhipuLMDB, delivery
import szl_khipu_delivery_routes as routes
import szl_operator_auth as auth
from tests.state_store_support import FakeClock, FakeHeadBackend, replica

TOKEN_ENV = "SZL_TEST_SNAPSHOT_HTTPS_PEER"
MAP_SIZE = 8 * 1024 * 1024


class DiskFixtureHead(FakeHeadBackend):
    """Test-only CAS history surviving test-process exit; not a Hub backend."""
    def __init__(self, path):
        super().__init__()
        self.path = path
        if path.exists():
            self.commits = [(revision, None if raw is None else bytes.fromhex(raw))
                            for revision, raw in json.loads(path.read_bytes())]

    def _append(self, body):
        revision = super()._append(body)
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps([(rev, None if raw is None else raw.hex())
                                    for rev, raw in self.commits]), encoding="utf-8")
        os.replace(temp, self.path)
        return revision


def build_node(root, attempt, peer, direction):
    root.mkdir(parents=True, exist_ok=True)
    clock = FakeClock(1_790_000_000.0 + attempt * 1000)
    backend = DiskFixtureHead(root / "fixture-head.json")
    objects = ss.LocalDirObjectStore(root / "fixture-objects")
    owner = replica(root, f"fresh-container-{attempt}", objects, backend, clock)
    owner.boot()
    owner.heartbeat_once()
    ss._ACTIVE = owner
    os.environ[ss.ENABLE_ENV] = ss.ENABLED_VALUE
    os.environ[routes.CONFIG_ENV] = json.dumps([dict(direction=direction, **vars(peer))])
    source = KhipuLMDB(str(owner.local_path("khipu_lmdb")), organ="khipu", ns="a11oy", map_size=MAP_SIZE)
    mirror = KhipuLMDB(str(owner.local_path("khipu_repl")), organ="khipu-repl", ns="a11oy", map_size=MAP_SIZE)
    app = FastAPI()
    routes.register(app, ns="a11oy", source=source, mirror=mirror)
    auth.install_gate(app)
    ss.register(app)
    return TestClient(app), owner, source, mirror, backend


def configured(endpoint):
    return delivery.Peer("fixture", endpoint, "khipu", "a11oy", TOKEN_ENV)


def serve(root, attempt, port, lose_ack):
    """HTTPS framing only; the actual consumer owns auth, stream limit and ACK."""
    root = Path(root)
    client = None
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass
        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 4 * 1024 * 1024:
                self.send_error(413)
                return
            body = self.rfile.read(length)
            response = client.post(self.path, content=body,
                                   headers={"Authorization": self.headers.get("Authorization", "")})
            if response.status_code == 200:
                with (root / "requests.jsonl").open("a", encoding="utf-8") as output:
                    output.write(json.dumps({"sha256": hashlib.sha256(body).hexdigest(),
                                              "tls": self.connection.version()}) + "\n")
                if lose_ack:
                    # The consumer has confirmed its accepted immutable snapshot.
                    # Kill the process before any HTTP ACK reaches the sender.
                    os._exit(91)
            self.send_response(response.status_code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(response.content)))
            self.end_headers()
            self.wfile.write(response.content)
    server = HTTPServer(("127.0.0.1", port), Handler)
    peer = configured(f"https://localhost:{server.server_port}/api/a11oy/v2/khipu/replicate/batch/fixture")
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(root / "cert.pem", root / "key.pem")
    server.socket = context.wrap_socket(server.socket, server_side=True)
    client, owner, source, mirror, _ = build_node(root / "receiver", attempt, peer, "inbound")
    try:
        with client:
            print(json.dumps({"endpoint": peer.endpoint, "mirror_entries": mirror.stats()["entries"]}), flush=True)
            server.serve_forever(poll_interval=0.05)
    finally:
        server.server_close()
        owner._close_watchers()
        source.close()
        mirror.close()


class Receiver:
    def __init__(self, root, attempt, port=0, lose_ack=False):
        self.process = subprocess.Popen([sys.executable, "-B", __file__, "--server", str(root),
            str(attempt), str(port), "1" if lose_ack else "0"], stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True,
            env=dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1])))
        ready = queue.Queue(maxsize=1)
        threading.Thread(target=lambda: ready.put(self.process.stdout.readline()), daemon=True).start()
        try:
            line = ready.get(timeout=20)
            if not line:
                raise AssertionError(self.process.stderr.read(4000) if self.process.poll() is not None
                                     else "receiver closed readiness pipe before startup")
            self.state = json.loads(line)
        except BaseException:
            self.close()
            raise
    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=5)
        self.process.stdout.close()
        self.process.stderr.close()


def test_actual_consumer_https_replays_after_receiver_and_sender_restore(tmp_path, monkeypatch):
    executable = shutil.which("openssl")
    if executable is None and sys.platform == "win32":
        executable = str(Path(r"C:\Program Files\Git\usr\bin\openssl.exe"))
    assert executable, "OpenSSL is required for the real HTTPS qualification"
    config = tmp_path / "openssl.cnf"
    config.write_text("[req]\nprompt=no\ndistinguished_name=dn\nx509_extensions=ext\n"
                      "[dn]\nCN=localhost\n[ext]\nsubjectAltName=DNS:localhost\n"
                      "basicConstraints=critical,CA:TRUE\n", encoding="ascii")
    subprocess.run([executable, "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
        "-keyout", str(tmp_path / "key.pem"), "-out", str(tmp_path / "cert.pem"), "-config", str(config)],
        check=True, capture_output=True, timeout=30)
    monkeypatch.setenv(TOKEN_ENV, secrets.token_urlsafe(32))
    operator = secrets.token_urlsafe(32)
    monkeypatch.setenv("A11OY_CODE_ADMIN_KEY", operator)
    monkeypatch.setenv("SSL_CERT_FILE", str(tmp_path / "cert.pem"))
    monkeypatch.setattr(ss, "_ACTIVE", None)
    # Restore test-local environment mutations after the two isolated nodes.
    monkeypatch.setenv(ss.ENABLE_ENV, ss.ENABLED_VALUE)
    monkeypatch.setenv(routes.CONFIG_ENV, "[]")
    first = Receiver(tmp_path, 1, lose_ack=True)
    peer = configured(first.state["endpoint"])
    port = int(peer.endpoint.split(":")[2].split("/")[0])
    client, owner, source, mirror, backend = build_node(tmp_path / "sender", 1, peer, "outbound")
    try:
        source.append("fixture", {"value": "synthetic receipt only"})
        with client:
            response = client.post("/api/a11oy/v2/khipu/replicate/dispatch/fixture",
                headers={"Authorization": "Bearer " + operator})
        assert response.status_code == 503
        assert first.process.wait(timeout=5) == 91
        pending = source.prepare_replication_batch(peer.peer_id, peer.binding_sha256)
        assert pending is not None
        batch_id = pending["batch_id"]
        assert backend.head()["snapshots"]["khipu_lmdb"]["kind"] == "lmdb"
    finally:
        first.close()
        owner._close_watchers()
        source.close()
        mirror.close()
    # Both sides use fresh local directories and restore only fixture provider
    # snapshots. No old LMDB directory, in-memory cursor or ACK is reused.
    second = Receiver(tmp_path, 2, port=port)
    client, owner, source, mirror, backend = build_node(tmp_path / "sender", 2, peer, "outbound")
    try:
        assert second.state["mirror_entries"] == 1
        recovered = source.prepare_replication_batch(peer.peer_id, peer.binding_sha256)
        assert recovered["body"] == pending["body"] and recovered["batch_id"] == batch_id
        with client:
            response = client.post("/api/a11oy/v2/khipu/replicate/dispatch/fixture",
                headers={"Authorization": "Bearer " + operator})
        assert response.status_code == 200, response.text
        assert response.json()["batch_id"] == batch_id
        assert source.replication_outbound_state(peer.peer_id, peer.binding_sha256)["pending"] is None
        restored = replica(tmp_path / "sender", "independent-readback", owner.objects,
                           backend, FakeClock(1_790_003_000.0))
        restored._restore_from_head(backend.head())
        assert routes._ack_contains(restored.local_path("khipu_lmdb"), source, peer, pending)
        restored._close_watchers()
        requests = [json.loads(line) for line in (tmp_path / "requests.jsonl").read_text().splitlines()]
        assert [request["sha256"] for request in requests] == [batch_id, batch_id]
        assert all(request["tls"] in ("TLSv1.2", "TLSv1.3") for request in requests)
        receiver_backend = DiskFixtureHead(tmp_path / "receiver" / "fixture-head.json")
        recovered_receiver = replica(tmp_path / "receiver", "independent-readback",
            ss.LocalDirObjectStore(tmp_path / "receiver" / "fixture-objects"), receiver_backend,
            FakeClock(1_790_003_000.0))
        recovered_receiver._restore_from_head(receiver_backend.head())
        assert routes._received_contains(recovered_receiver.local_path("khipu_repl"), mirror, peer, pending["body"])
        recovered_receiver._close_watchers()
    finally:
        second.close()
        owner._close_watchers()
        source.close()
        mirror.close()


if __name__ == "__main__" and len(sys.argv) == 6 and sys.argv[1] == "--server":
    serve(sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), sys.argv[5] == "1")
