"""Focused security and honesty checks for the VSP OpenTelemetry boundary."""

from contextlib import contextmanager
import sys
from types import ModuleType, SimpleNamespace

import pytest

from vsp_otel import middleware as otel


class _DummyApp:
    title = "A11oy"

    def __init__(self):
        self.middlewares = []

    def middleware(self, kind):
        assert kind == "http"

        def decorate(fn):
            self.middlewares.append(fn)
            return fn

        return decorate


def test_traceparent_accepts_strict_v00_lowercase_only():
    valid = "00-0123456789abcdef0123456789abcdef-0123456789abcdef-01"
    assert otel.parse_traceparent(valid)["sampled"] is True
    assert otel.parse_traceparent(valid[:-2] + "00")["sampled"] is False
    assert otel.parse_traceparent(valid.replace("abcdef", "ABCDEF")) is None
    assert otel.parse_traceparent("01" + valid[2:]) is None
    assert otel.parse_traceparent("ff" + valid[2:]) is None
    assert otel.parse_traceparent(valid[:-2] + "03") is None
    assert otel.parse_traceparent(valid.replace("0123456789abcdef0123456789abcdef", "0" * 32)) is None


def test_endpoint_policy_is_private_fail_closed_and_secret_free():
    assert otel._endpoint_policy(None)["state"] == "NOT-CONFIGURED"
    local = otel._endpoint_policy("http://127.0.0.1:4317")
    assert local["allowed"] is True and local["reason"] == "LOOPBACK"
    assert local["fingerprint"] and len(local["fingerprint"]) == 16
    private = otel._endpoint_policy("http://10.10.0.4:4317")
    assert private["allowed"] is True and private["reason"] == "PRIVATE-IP"
    ipv6 = otel._endpoint_policy("http://[::1]:4317")
    assert ipv6["allowed"] is True and ipv6["endpoint"] == "http://[::1]:4317"
    assert otel._endpoint_policy("http://0.0.0.0:4317")["state"] == "POLICY-DENIED"
    assert otel._endpoint_policy("http://169.254.1.1:4317")["state"] == "POLICY-DENIED"
    assert otel._endpoint_policy("https://8.8.8.8:4317")["state"] == "POLICY-DENIED"
    assert otel._endpoint_policy("https://user:secret@localhost:4317")["state"] == "POLICY-DENIED"
    assert otel._endpoint_policy("https://localhost:4317/v1/traces")["state"] == "POLICY-DENIED"


def test_dns_endpoint_requires_exact_operator_allowlist():
    denied = otel._endpoint_policy("https://collector.internal:4317", allowed_hosts="")
    assert denied["allowed"] is False
    allowed = otel._endpoint_policy(
        "https://collector.internal:4317", allowed_hosts="collector.internal"
    )
    assert allowed["allowed"] is True
    assert allowed["reason"] == "OPERATOR-ALLOWLISTED-DNS"
    assert "collector.internal" not in allowed["fingerprint"]


def test_status_separates_propagation_from_export_and_redacts_endpoint():
    app = _DummyApp()
    otel.install(app, service_name="test", endpoint=None)
    got = otel.status(app)
    assert got["propagation"] == "READY"
    assert got["export"] == "IN-PROCESS-ONLY"
    assert got["endpoint"]["state"] == "NOT-CONFIGURED"
    assert got["receipt_minted"] is False
    assert "http" not in str(got)
    assert len(app.middlewares) == 1
    otel.install(app, service_name="test", endpoint=None)
    assert len(app.middlewares) == 1

def test_fastapi_environment_exporter_setup_requires_opt_in(monkeypatch):
    from fastapi import FastAPI
    from fastapi.telemetry import _runtime
    from fastapi.testclient import TestClient

    monkeypatch.delenv("FASTAPI_OTEL_AUTO_CONFIGURE", raising=False)
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "https://collector.invalid:4318")

    def refuse_export_endpoint(*args, **kwargs):
        raise AssertionError("default FastAPI startup must not configure exporters")

    monkeypatch.setattr(_runtime, "_export_endpoint", refuse_export_endpoint)
    with TestClient(FastAPI()) as client:
        assert client.get("/openapi.json").status_code == 200


@pytest.fixture
def sdk_boundary(monkeypatch):
    state=SimpleNamespace(providers=[], processors=[], exporters=[], global_provider=None, set_calls=[], fail_get=False, fail_stage=None)
    class Provider:
        def __init__(self, resource=None):
            self.resource=resource;self.processors=[];self.spans=[];self.shutdown_calls=0
            state.providers.append(self)
        def add_span_processor(self, processor):
            if state.fail_stage == 'attach': raise RuntimeError('synthetic attach failure')
            self.processors.append(processor)
        def get_tracer(self, *_args, **_kwargs):
            if state.fail_get or state.fail_stage == 'tracer': raise RuntimeError('synthetic get_tracer failure')
            owner=self
            class Tracer:
                provider=owner
                @contextmanager
                def start_as_current_span(self, name, **kwargs):
                    attrs={}
                    span=SimpleNamespace(set_attribute=lambda k,v:attrs.__setitem__(k,v))
                    try: yield span
                    finally: owner.spans.append({'name':name,'attrs':attrs})
            return Tracer()
        def shutdown(self):
            self.shutdown_calls+=1
            for processor in self.processors: processor.shutdown()
    class Processor:
        def __init__(self, exporter):
            if state.fail_stage == 'processor': raise RuntimeError('synthetic processor failure')
            self.exporter=exporter;self.shutdown_calls=0;state.processors.append(self)
        def shutdown(self):
            self.shutdown_calls+=1;self.exporter.shutdown()
    class Exporter:
        def __init__(self, **kwargs):
            if state.fail_stage == 'exporter': raise RuntimeError('synthetic exporter failure')
            self.options=kwargs;self.shutdown_calls=0;state.exporters.append(self)
        def shutdown(self): self.shutdown_calls+=1
    def module(name, package=False):
        m=ModuleType(name)
        if package:m.__path__=[]
        monkeypatch.setitem(sys.modules,name,m)
        return m
    root=module('opentelemetry',True);trace=module('opentelemetry.trace')
    root.trace=trace;root.propagate=SimpleNamespace(extract=lambda carrier:carrier)
    trace.SpanKind=SimpleNamespace(SERVER='server')
    def set_provider(provider):
        state.set_calls.append(provider)
        if state.global_provider is None:state.global_provider=provider
    def get_tracer(*args,**kwargs):
        return state.global_provider.get_tracer(*args,**kwargs)
    trace.set_tracer_provider=set_provider;trace.get_tracer=get_tracer
    module('opentelemetry.sdk',True)
    module('opentelemetry.sdk.resources').Resource=SimpleNamespace(create=lambda attrs:attrs)
    module('opentelemetry.sdk.trace',True).TracerProvider=Provider
    module('opentelemetry.sdk.trace.export').BatchSpanProcessor=Processor
    for name in ('opentelemetry.exporter','opentelemetry.exporter.otlp',
                 'opentelemetry.exporter.otlp.proto','opentelemetry.exporter.otlp.proto.grpc'):
        module(name,True)
    module('opentelemetry.exporter.otlp.proto.grpc.trace_exporter').OTLPSpanExporter=Exporter
    state.Provider=Provider
    return state

def test_configured_destination_does_not_use_existing_global_provider(sdk_boundary):
    prior=sdk_boundary.Provider({'service.name':'unrelated'})
    sdk_boundary.global_provider=prior
    t=otel._Tracer('configured','http://127.0.0.1:14317')
    own=sdk_boundary.providers[-1]
    with t.server_span('binding-test',None,{'test':'local'}):pass
    assert len(own.spans)==1, 'configured endpoint got no span'
    assert prior.spans==[], 'span reached a different global provider'
    assert own.processors[0].exporter.options['endpoint']=='http://127.0.0.1:14317'
    assert sdk_boundary.global_provider is prior

def test_two_service_installations_keep_separate_destinations(sdk_boundary):
    first=otel._Tracer('first','http://127.0.0.1:14317')
    second=otel._Tracer('second','http://127.0.0.1:24317')
    with first.server_span('first-only',None,{}):pass
    with second.server_span('second-only',None,{}):pass
    assert [[s['name'] for s in p.spans] for p in sdk_boundary.providers]==[['first-only'],['second-only']]
    assert not sdk_boundary.set_calls, 'library changed process-wide telemetry authority'

@pytest.mark.parametrize('endpoint',[None,'https://8.8.8.8:4317'])
def test_unconfigured_or_denied_destination_never_constructs_sdk(sdk_boundary,endpoint):
    t=otel._Tracer('disabled',endpoint)
    assert t._tracer is None
    assert sdk_boundary.providers==[]
    assert not sdk_boundary.set_calls

def test_failed_local_provider_setup_is_closed_and_released(sdk_boundary):
    sdk_boundary.fail_get=True
    t=otel._Tracer('failed','http://127.0.0.1:14317')
    assert t._tracer is None
    assert not t.exporter.startswith('otlp-grpc:configured:')
    assert sdk_boundary.providers[0].shutdown_calls==1
    assert sdk_boundary.global_provider is None

@pytest.mark.parametrize('stage',['exporter','processor','attach','tracer'])
def test_partial_setup_releases_only_owned_resources(sdk_boundary,stage):
    prior=sdk_boundary.Provider({'service.name':'unrelated'})
    sdk_boundary.global_provider=prior
    sdk_boundary.fail_stage=stage
    result=otel._Tracer('failed','http://127.0.0.1:14317')
    assert result._tracer is None and result._provider is None
    assert result.exporter.startswith('in-process-only')
    assert sdk_boundary.providers[-1].shutdown_calls==1
    assert all(p.shutdown_calls==1 for p in sdk_boundary.processors)
    assert all(e.shutdown_calls==1 for e in sdk_boundary.exporters)
    assert prior.shutdown_calls==0
    assert sdk_boundary.global_provider is prior
    assert not sdk_boundary.set_calls

def test_cleanup_failure_still_degrades_without_export_claim(sdk_boundary,monkeypatch):
    sdk_boundary.fail_get=True
    def failed_cleanup(self): raise RuntimeError('synthetic shutdown failure')
    monkeypatch.setattr(sdk_boundary.Provider,'shutdown',failed_cleanup)
    result=otel._Tracer('failed','http://127.0.0.1:14317')
    assert result._tracer is None and result._provider is None
    assert result.exporter=='in-process-only (RuntimeError)'
    assert not sdk_boundary.set_calls
