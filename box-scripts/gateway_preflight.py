#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Read-only local gateway contract checks; never authorize public activation."""

import argparse
import http.client
import ipaddress
import json
import math
import os
from pathlib import Path
import re
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

import yaml

MAX_BYTES = 65536
SCHEMA = "szl.gateway-preflight/v1"


class InvalidInput(ValueError):
    """Messages are fixed codes, never upstream text or configuration values."""


class UniqueLoader(yaml.SafeLoader):
    pass


def _mapping(loader, node):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=True)
        if not isinstance(key, str) or key in result:
            raise InvalidInput("CONFIG_DUPLICATE_OR_NONSTRING_KEY")
        result[key] = loader.construct_object(value_node, deep=True)
    return result


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


def _unique_json(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InvalidInput("JSON_DUPLICATE_KEY")
        result[key] = value
    return result


def parse_json(data):
    if len(data) > MAX_BYTES:
        raise InvalidInput("INPUT_TOO_LARGE")
    return json.loads(data, object_pairs_hook=_unique_json,
                      parse_constant=lambda _: (_ for _ in ()).throw(InvalidInput("JSON_NONFINITE")))


def read_config(path):
    with Path(path).open("rb") as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise InvalidInput("CONFIG_TOO_LARGE")
    # Reject aliases/anchors and merge keys instead of expanding an input graph.
    for token in yaml.scan(raw):
        if isinstance(token, (yaml.tokens.AliasToken, yaml.tokens.AnchorToken)):
            raise InvalidInput("CONFIG_ALIAS_UNSUPPORTED")
    doc = yaml.load(raw, Loader=UniqueLoader)
    if not isinstance(doc, dict):
        raise InvalidInput("CONFIG_NOT_OBJECT")
    return doc


def base_url(value, *, loopback=False):
    if (not isinstance(value, str) or "?" in value or "#" in value
            or any(ord(c) < 33 or ord(c) > 126 for c in value)):
        raise InvalidInput("URL_INVALID")
    url = urllib.parse.urlsplit(value)
    if (url.username is not None or url.password is not None or url.query or url.fragment
            or url.path not in ("", "/") or not url.hostname):
        raise InvalidInput("URL_INVALID")
    if loopback:
        if url.scheme != "http" or url.hostname not in ("127.0.0.1", "::1"):
            raise InvalidInput("LITERAL_LOOPBACK_REQUIRED")
        if not ipaddress.ip_address(url.hostname).is_loopback or url.port is None:
            raise InvalidInput("LITERAL_LOOPBACK_REQUIRED")
    elif url.scheme != "https":
        raise InvalidInput("HTTPS_REQUIRED")
    if url.port is not None and not 1 <= url.port <= 65535:
        raise InvalidInput("URL_INVALID")
    return value.rstrip("/")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def get_json(url, *, timeout=3.0, bearer=None):
    """Bounded GET; no proxies, cookies, redirects, retries or response logging."""
    if bearer is not None:
        parsed = urllib.parse.urlsplit(url)
        base_url(urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, "", "", "")), loopback=True)
        if not isinstance(bearer, str) or not re.fullmatch(r"[!-~]{16,512}", bearer):
            return {"status": None, "error": "KEY_INVALID", "data": None}
    headers = {"Accept": "application/json", "User-Agent": "szl-gateway-preflight/1"}
    if bearer is not None:
        headers["Authorization"] = "Bearer " + bearer
    request = urllib.request.Request(url, headers=headers, method="GET")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    try:
        with opener.open(request, timeout=timeout) as response:
            status = response.status
            if response.headers.get_content_type() != "application/json":
                return {"status": status, "error": "NOT_JSON", "data": None}
            deadline = time.monotonic() + timeout
            chunks = []
            size = 0
            while size <= MAX_BYTES:
                if time.monotonic() >= deadline:
                    return {"status": status, "error": "READ_DEADLINE", "data": None}
                chunk = response.read1(min(4096, MAX_BYTES + 1 - size))
                if not chunk:
                    break
                chunks.append(chunk)
                size += len(chunk)
            if response.length not in (None, 0):
                return {"status": status, "error": "INCOMPLETE_BODY", "data": None}
            data = parse_json(b"".join(chunks))
            return {"status": status, "error": None, "data": data}
    except urllib.error.HTTPError as error:
        status = error.code
        error.close()
        return {"status": status, "error": "HTTP_STATUS", "data": None}
    except (OSError, ValueError, RecursionError, urllib.error.URLError, http.client.HTTPException):
        return {"status": None, "error": "PROBE_FAILED", "data": None}


def evaluate(config, *, model, backend_model, backend_digest, ollama_url,
             public_gateway, key_env, environ, catalog=None, consumer=None,
             anonymous=None, invalid=None, authenticated=None):
    """Pure comparison. Input observations confer no deployment authority."""
    checks = {}
    model_list = config.get("model_list")
    entries = ([x for x in model_list if isinstance(x, dict) and x.get("model_name") == model]
               if isinstance(model_list, list) else [])
    params = entries[0].get("litellm_params") if len(entries) == 1 else None
    params = params if isinstance(params, dict) else {}
    checks["unique_gateway_alias"] = len(entries) == 1
    checks["backend_identity"] = params.get("model") in (
        "ollama/" + backend_model, "ollama_chat/" + backend_model)
    checks["backend_origin"] = params.get("api_base", "").rstrip("/") == ollama_url if isinstance(params.get("api_base"), str) else False
    settings = config.get("general_settings")
    settings = settings if isinstance(settings, dict) else {}
    reference = "os.environ/" + key_env
    checks["auth_environment_reference"] = settings.get("master_key") == reference
    key = environ.get(key_env, "")
    checks["auth_key_available"] = isinstance(key, str) and re.fullmatch(r"[!-~]{16,512}", key) is not None
    # Database overlays, env injection and dynamic routing cannot be proven from this file.
    checks["static_config_only"] = (set(config) <= {"model_list", "general_settings"}
        and set(settings) == {"master_key"}
        and isinstance(model_list, list) and len(model_list) == 1
        and len(entries) == 1 and set(entries[0]) == {"model_name", "litellm_params"}
        and set(params) == {"model", "api_base"}
        and not environ.get("DATABASE_URL") and not environ.get("STORE_MODEL_IN_DB")
    )
    checks["digest_pin_present"] = isinstance(backend_digest, str) and re.fullmatch(r"[0-9a-f]{64}", backend_digest) is not None

    def payload(probe):
        return probe.get("data") if isinstance(probe, dict) and probe.get("status") == 200 and isinstance(probe.get("data"), dict) else {}

    models = payload(catalog).get("models", [])
    selected = [x for x in models if isinstance(x, dict) and x.get("name") == backend_model] if isinstance(models, list) else []
    checks["installed_model_digest"] = (checks["digest_pin_present"] and len(selected) == 1
                                         and selected[0].get("digest") == backend_digest)
    observed = payload(consumer)
    checks["consumer_model"] = (observed.get("configured_model") == model
                                 and observed.get("requested_model") == model)
    checks["consumer_endpoint"] = (observed.get("base_url") == public_gateway
                                    and observed.get("url") == public_gateway)
    checks["consumer_api"] = observed.get("api_style") == "openai /v1"
    checks["anonymous_catalog_rejected"] = isinstance(anonymous, dict) and anonymous.get("status") in (401, 403)
    checks["invalid_key_catalog_rejected"] = isinstance(invalid, dict) and invalid.get("status") in (401, 403)
    served = payload(authenticated).get("data", [])
    checks["authenticated_catalog_model"] = (isinstance(served, list)
        and sum(isinstance(x, dict) and x.get("id") == model for x in served) == 1)
    probes = {"ollama_catalog": catalog, "consumer_health": consumer,
              "anonymous_catalog": anonymous, "invalid_key_catalog": invalid,
              "authenticated_catalog": authenticated}
    result = {
        "schema": SCHEMA, "observed_at": datetime.now(timezone.utc).isoformat(),
        "status": "LOCAL_PREFLIGHT_PASS" if all(checks.values()) else "BLOCKED",
        "evidence_class": "UNSIGNED_READ_ONLY_OBSERVATION",
        "checks": checks, "failures": [k for k, passed in checks.items() if not passed],
        "probes": {k: {"status": v.get("status"), "error": v.get("error")} if v else {"status": None, "error": "NOT_TESTED"} for k, v in probes.items()},
        "production_ready": False, "activation_authorized": False,
        "not_verified": ["public_access_policy", "tunnel_identity_and_connectors",
            "origin_listener_binding", "all_route_authentication", "inference",
            "restart_persistence", "model_qualification", "running_config_binding"],
    }
    # Only fixed fields and booleans leave this function; no config/response echo.
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--model", required=True, help="Exact consumer/gateway alias; no fallback")
    parser.add_argument("--backend-model", required=True, help="Exact Ollama tag; no automatic aliasing")
    parser.add_argument("--backend-digest", help="Separately retained expected digest, not learned from the candidate")
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    parser.add_argument("--gateway-origin", default="http://127.0.0.1:4000")
    parser.add_argument("--public-gateway", default="https://gateway.a-11-oy.com")
    parser.add_argument("--consumer-base", default="https://a-11-oy.com")
    parser.add_argument("--key-env", default="LITELLM_MASTER_KEY")
    parser.add_argument("--timeout", type=float, default=3.0)
    parser.add_argument("--probe", action="store_true", help="Perform at most five bounded GETs; never generate or start services")
    args = parser.parse_args(argv)
    try:
        if not math.isfinite(args.timeout) or not 0.1 <= args.timeout <= 10:
            raise InvalidInput("TIMEOUT_INVALID")
        if not re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", args.key_env):
            raise InvalidInput("ENV_NAME_INVALID")
        for name in (args.model, args.backend_model):
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:/-]{0,199}", name):
                raise InvalidInput("MODEL_ID_INVALID")
        if args.backend_digest is not None and not re.fullmatch(r"[0-9a-f]{64}", args.backend_digest):
            raise InvalidInput("DIGEST_INVALID")
        ollama = base_url(args.ollama_url, loopback=True)
        origin = base_url(args.gateway_origin, loopback=True)
        public = base_url(args.public_gateway)
        consumer_base = base_url(args.consumer_base)
        config = read_config(args.config)
        inputs = dict(model=args.model, backend_model=args.backend_model,
            backend_digest=args.backend_digest, ollama_url=ollama,
            public_gateway=public, key_env=args.key_env, environ=os.environ)
        if args.probe:
            inputs["catalog"] = get_json(ollama + "/api/tags", timeout=args.timeout)
            inputs["consumer"] = get_json(consumer_base + "/api/a11oy/v1/llm/sovereign/health", timeout=args.timeout)
            inputs["anonymous"] = get_json(origin + "/v1/models", timeout=args.timeout)
            inputs["invalid"] = get_json(origin + "/v1/models", timeout=args.timeout, bearer="sk-invalid-" + secrets.token_hex(24))
            preliminary = evaluate(config, **inputs)
            # Inline keys are deliberately unsupported. Only use the exact env reference.
            if preliminary["checks"]["auth_environment_reference"] and preliminary["checks"]["auth_key_available"]:
                inputs["authenticated"] = get_json(origin + "/v1/models", timeout=args.timeout, bearer=os.environ[args.key_env])
        result = evaluate(config, **inputs)
    except (OSError, ValueError, TypeError, RecursionError, yaml.YAMLError):
        result = {"schema": SCHEMA, "status": "BLOCKED", "error": "INPUT_INVALID",
                  "production_ready": False, "activation_authorized": False}
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    return 0 if result["status"] == "LOCAL_PREFLIGHT_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
