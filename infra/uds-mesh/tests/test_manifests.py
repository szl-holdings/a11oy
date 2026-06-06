"""WU-2 manifest validation (offline): YAML well-formedness + invariant checks.

HONESTY: this does NOT contact a live Istio/k8s cluster. It asserts the manifests
parse and carry the security invariants we claim (STRICT mTLS, ISTIO_MUTUAL,
OTLP gRPC receiver, forwarding exporter). Full schema validation against the
Istio CRDs is done with kubeconform offline — see manifests/README.md for the
exact `kubeconform`/`kubectl --dry-run=client` commands.
"""
from __future__ import annotations

from pathlib import Path

import yaml

MANIFESTS = Path(__file__).resolve().parents[1] / "manifests"


def load_all(rel: str):
    docs = list(yaml.safe_load_all((MANIFESTS / rel).read_text()))
    return [d for d in docs if d]


def test_peer_authentication_all_strict():
    docs = load_all("istio/peer-authentication.yaml")
    assert len(docs) == 5, "one PeerAuthentication per organ"
    organs = set()
    for d in docs:
        assert d["kind"] == "PeerAuthentication"
        assert d["spec"]["mtls"]["mode"] == "STRICT", f"{d['metadata']['name']} not STRICT"
        organs.add(d["metadata"]["labels"]["szl.mesh/organ"])
    assert organs == {"a11oy", "sentra", "amaru", "killinchu", "rosie"}


def test_destination_rule_istio_mutual():
    docs = load_all("istio/destination-rule.yaml")
    assert docs, "destination rules present"
    for d in docs:
        assert d["kind"] == "DestinationRule"
        assert d["spec"]["trafficPolicy"]["tls"]["mode"] == "ISTIO_MUTUAL"


def test_collector_has_otlp_grpc_receiver_and_exporter_pipeline():
    docs = load_all("otel/collector.yaml")
    cms = [d for d in docs if d["kind"] == "ConfigMap"]
    assert cms, "collector ConfigMap present"
    cfg = yaml.safe_load(cms[0]["data"]["collector.yaml"])
    # gRPC receiver
    assert "grpc" in cfg["receivers"]["otlp"]["protocols"]
    assert cfg["receivers"]["otlp"]["protocols"]["grpc"]["endpoint"].endswith(":4317")
    # exporter pipeline forwards to vsp-otel
    assert any(k.startswith("otlphttp") for k in cfg["exporters"])
    pipe = cfg["service"]["pipelines"]["traces"]
    assert "otlp" in pipe["receivers"]
    assert any(e.startswith("otlphttp") for e in pipe["exporters"])


def test_collector_deployment_and_service_present():
    docs = load_all("otel/collector.yaml")
    kinds = {d["kind"] for d in docs}
    assert {"ConfigMap", "Deployment", "Service"} <= kinds


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-v"]))
