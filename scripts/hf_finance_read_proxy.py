# SPDX-License-Identifier: Apache-2.0
"""Thin public finance projection for the existing canonical flagship publisher.

No provider credentials, connector logic, formula or independent deployment.
Only canonical JSON read endpoints are proxied; source semantics remain intact.
"""

import json
from pathlib import Path

COMPONENT = json.loads((Path(__file__).resolve().parents[1] /
    "verticals/puriq-markets/runtime/components/finance_v2/source.json").read_text(encoding="utf-8"))

FINANCE_PROXY = r'''
# Public finance projection. Core normalization remains in szl-holdings/a11oy.
if CFG.get("slug") == "finance":
    import hashlib as _finance_hashlib
    import math as _finance_math
    import re as _finance_re
    import time as _finance_time
    from urllib.parse import urlencode as _finance_urlencode, urlsplit as _finance_urlsplit
    _FINANCE_ORIGIN = "https://szlholdings-a11oy.hf.space"
    _FINANCE_PREFIX = "/api/a11oy/v1/finance/"
    _FINANCE_COMPONENT = __COMPONENT_BINDING__
    _FINANCE_OVERVIEW_SOURCES = frozenset((
        "polymarket-markets", "kalshi-markets", "coinbase-ticker", "treasury-rates"))

    def _finance_unavailable(code, status=503):
        return {"ok":False,"state":"UNAVAILABLE","error":code,"execution_enabled":False},status

    def _finance_upstream_rejected(response, mime):
        body,status=_finance_unavailable("CANONICAL_SOURCE_UNAVAILABLE")
        location=response.headers.get("location","")
        host=None
        if isinstance(location,str) and len(location)<=2048:
            try:
                candidate=_finance_urlsplit(location).hostname
                if candidate and len(candidate)<=253 and _finance_re.fullmatch(r"[a-z0-9.-]+",candidate):
                    host=candidate
            except ValueError:
                pass
        media="JSON" if mime=="application/json" or mime.startswith("application/") and mime.endswith("+json") else "HTML" if mime=="text/html" else "TEXT" if mime.startswith("text/") else "OTHER" if mime else "MISSING"
        code=response.status_code
        body["upstream_response"]={"http_status":code if type(code) is int and 100<=code<=599 else None,
            "media_type":media,"redirect_host":host}
        return body,status

    def _finance_json(raw):
        def pairs(items):
            out={}
            for key,value in items:
                if key in out:
                    raise ValueError("duplicate key")
                out[key]=value
            return out
        def finite(value):
            number=float(value)
            if (not _finance_math.isfinite(number)
                    or number == 0 and any(char in "123456789" for char in value.lower().split("e", 1)[0])):
                raise ValueError("nonfinite or underflowed number")
            return number
        def invalid(value):
            raise ValueError("nonfinite literal")
        return json.loads(raw,object_pairs_hook=pairs,parse_float=finite,parse_constant=invalid)

    def _finance_identity(body,expected,source=None):
        if not isinstance(body,dict) or body.get("schema")!=expected or body.get("execution_enabled") is not False:
            return "CANONICAL_SCHEMA_INVALID"
        revision=CFG.get("source_revision","")
        if not _finance_re.fullmatch(r"[0-9a-f]{40}",revision) or body.get("source_revision")!=revision:
            return "CANONICAL_REVISION_MISMATCH"
        if source is not None and body.get("source")!=source:
            return "CANONICAL_SOURCE_IDENTITY_MISMATCH"
        return None

    class _FinanceBoundaryError(ValueError):
        pass

    def _finance_digest(value):
        return _finance_hashlib.sha256(json.dumps(value, sort_keys=True,
            separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()).hexdigest()

    def _finance_check_identity(body, schema):
        error = _finance_identity(body, schema)
        if error:
            raise _FinanceBoundaryError(error)
        if CFG.get("source_revision") == "0" * 40:
            raise _FinanceBoundaryError("CANONICAL_REVISION_MISMATCH")

    def _finance_check_observation(body, source, status):
        _finance_check_identity(body, "szl.finance.observation/v1")
        if body.get("source") != source:
            raise _FinanceBoundaryError("CANONICAL_SOURCE_IDENTITY_MISMATCH")
        state = body.get("state")
        if not ((status == 200 and body.get("ok") is True and state in ("SNAPSHOT", "CACHED"))
                or (status == 503 and body.get("ok") is False and state in ("STALE", "UNAVAILABLE"))):
            raise _FinanceBoundaryError("CANONICAL_STATUS_MISMATCH")
        if state == "UNAVAILABLE":
            if (body.get("data") is not None or body.get("provenance") is not None
                    or body.get("retrieved_at") is not None or body.get("truth_label") != "UNAVAILABLE"):
                raise _FinanceBoundaryError("CANONICAL_SCHEMA_INVALID")
        else:
            proof = body.get("provenance")
            if (not isinstance(proof, dict) or not isinstance(body.get("data"), dict)
                    or proof.get("source") != source
                    or proof.get("runtime_reported_source_revision") != body["source_revision"]
                    or proof.get("retrieved_at") != body.get("retrieved_at")
                    or not isinstance(proof.get("retrieved_at"), str)
                    or proof.get("signed") is not False or body.get("truth_label") != "REPORTED"):
                raise _FinanceBoundaryError("CANONICAL_PROVENANCE_MISMATCH")
            if any(not isinstance(proof.get(k), str) or not _finance_re.fullmatch(r"[0-9a-f]{64}", proof[k])
                   for k in ("source_bytes_sha256", "normalized_data_sha256", "observation_id")):
                raise _FinanceBoundaryError("CANONICAL_PROVENANCE_MISMATCH")
            unsigned = {k:v for k,v in proof.items() if k != "observation_id"}
            if (proof["normalized_data_sha256"] != _finance_digest(body["data"])
                    or proof["observation_id"] != _finance_digest(unsigned)):
                raise _FinanceBoundaryError("CANONICAL_PROVENANCE_MISMATCH")
        if state in ("STALE", "UNAVAILABLE"):
            error = body.get("error")
            if not isinstance(error, str) or not _finance_re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", error):
                raise _FinanceBoundaryError("CANONICAL_SCHEMA_INVALID")

    def _finance_validate(body, kind, status):
        if kind.startswith("observations/"):
            _finance_check_observation(body, kind.split("/", 1)[1], status)
            return
        if status != 200:
            raise _FinanceBoundaryError("CANONICAL_SOURCE_UNAVAILABLE")
        schema = "szl.finance.providers/v1" if kind == "providers" else "szl.finance.overview/v1"
        _finance_check_identity(body, schema)
        if kind == "providers":
            if (body.get("read_only") is not True or body.get("canonical_repository") != "szl-holdings/a11oy"
                    or not isinstance(body.get("sources"), list) or len(body["sources"]) > 64):
                raise _FinanceBoundaryError("CANONICAL_SCHEMA_INVALID")
            seen = set()
            for item in body["sources"]:
                source = item.get("id") if isinstance(item, dict) else None
                if (not isinstance(source, str) or not _finance_re.fullmatch(r"[a-z][a-z-]{0,79}", source)
                        or source in seen):
                    raise _FinanceBoundaryError("CANONICAL_SCHEMA_INVALID")
                seen.add(source)
            return
        data = body.get("data")
        if (not isinstance(data, dict) or set(data) != _FINANCE_OVERVIEW_SOURCES
                or type(body.get("sources_requested")) is not int or body["sources_requested"] != len(data)
                or type(body.get("sources_available")) is not int
                or body.get("event_equivalence") != "NOT_ESTABLISHED"):
            raise _FinanceBoundaryError("CANONICAL_SCHEMA_INVALID")
        for source, child in data.items():
            _finance_check_observation(child, source, 200 if isinstance(child,dict) and child.get("ok") is True else 503)
        count = sum(child["ok"] is True for child in data.values())
        success = count == len(data)
        if (body["sources_available"] != count or body.get("ok") is not success
                or body.get("state") != ("SNAPSHOTS_AVAILABLE" if success else "DEGRADED")):
            raise _FinanceBoundaryError("CANONICAL_STATUS_MISMATCH")

    def _finance_check_analytics(body, kind, query, method):
        _finance_check_identity(body, "szl.finance.analytics/v2")
        if (body.get("component") != _FINANCE_COMPONENT or body.get("ok") is not True
                or body.get("state") != "COMPUTED" or body.get("truth_label") != "MODELED"
                or any(body.get(key) is not True for key in ("advisory_only", "paper_only", "not_financial_advice"))):
            raise _FinanceBoundaryError("CANONICAL_COMPONENT_MISMATCH")
        operation=kind.removeprefix("analytics/v2/").split("/",1)[0]
        expected = ("receipt-verification" if method == "POST" else "receipt-verification-contract") if kind.endswith("receipts/verify") else operation
        if body.get("operation") != expected:
            raise _FinanceBoundaryError("CANONICAL_SCHEMA_INVALID")
        if operation in ("signals", "quote"):
            origin = dict(query).get("origin", "coinbase")
            proof = body.get("inputs", {}).get("asset", {})
            if (body.get("result", {}).get("symbol") != kind.rsplit("/", 1)[1]
                    or body["result"].get("data_origin") != origin
                    or proof.get("origin") != origin
                    or proof.get("truth_label") != ("SYNTHETIC" if origin == "fixture" else "REPORTED")):
                raise _FinanceBoundaryError("CANONICAL_SCHEMA_INVALID")
        receipt=body.get("receipt")
        if not isinstance(receipt,dict):
            raise _FinanceBoundaryError("CANONICAL_RECEIPT_INVALID")
        receipt=dict(receipt)
        claimed=receipt.pop("receipt_sha256",None)
        content={key:value for key,value in body.items() if key!="receipt"}
        if (claimed!=_finance_digest(receipt) or receipt.get("payload_sha256")!=_finance_digest(content)
                or receipt.get("signing")!="UNSIGNED_HONEST" or receipt.get("signed") is not False
                or receipt.get("persistence")!="CALLER_HELD" or receipt.get("authority")!="NONE"
                or receipt.get("source_revision")!=body["source_revision"]
                or receipt.get("component_revision")!=_FINANCE_COMPONENT["revision"]
                or receipt.get("component_sha256")!=_FINANCE_COMPONENT["engine_sha256"]):
            raise _FinanceBoundaryError("CANONICAL_RECEIPT_INVALID")
        for proof in (body.get("inputs",{}).get("asset"),body.get("inputs",{}).get("benchmark")):
            if proof is not None and proof.get("origin")=="coinbase":
                _finance_check_observation(proof.get("observation"), "coinbase-candles", 200)

    def _finance_check_research(body, submitted):
        _finance_check_identity(body, "szl.finance.research/v1")
        result = body.get("result")
        if (body.get("ok") is not True or body.get("state") != "COMPUTED"
                or body.get("truth_label") != "MODELED" or body.get("operation") != "research-audit"
                or any(body.get(k) is not True for k in ("advisory_only", "paper_only", "not_financial_advice"))
                or not isinstance(result, dict) or result.get("schema") != "szl.finance.research-audit/v1"
                or result.get("truth_label") != "MODELED"
                or type(result.get("audit_accepted")) is not bool
                or body.get("inputs_sha256") != _finance_digest(submitted)
                or _finance_digest(body.get("inputs")) != _finance_digest(submitted)):
            raise _FinanceBoundaryError("CANONICAL_SCHEMA_INVALID")
        # A valid unsigned digest proves internal consistency, not these claims.
        # Enforce the presentation contract before forwarding a canonical result.
        def require(condition):
            if not condition:
                raise _FinanceBoundaryError("CANONICAL_SCHEMA_INVALID")
        def count(value, maximum=10000):
            return type(value) is int and 0 <= value <= maximum
        require(isinstance(submitted, dict) and isinstance(submitted.get("records"), list))
        require(result.get("as_of") == submitted.get("as_of")
            and result.get("status") == ("AUDITED" if result["audit_accepted"] else "BLOCKED"))
        inputs = result.get("inputs")
        require(isinstance(inputs, dict) and inputs.get("origin") == "caller_supplied"
            and inputs.get("truth_label") == "SAMPLE"
            and inputs.get("externally_verified") is False
            and inputs.get("release_dates_verified") is False
            and inputs.get("source_url") == submitted.get("source_url"))
        summary, coverage = result.get("summary"), result.get("coverage")
        require(isinstance(summary, dict) and isinstance(coverage, dict))
        summary_counts = ("total_records", "kept_records", "excluded_records", "unique_entity_periods",
            "duplicate_cells", "observed_records", "suppressed_records", "missing_records",
            "invalid_records", "null_records", "observed_zero_records", "kept_zero_records",
            "unknown_release_records", "after_cutoff_records")
        require(all(count(summary.get(key), 5000) for key in summary_counts))
        total, kept = summary["total_records"], summary["kept_records"]
        require(total == len(submitted["records"]) and kept + summary["excluded_records"] == total
            and summary["kept_zero_records"] <= min(kept, summary["observed_zero_records"]))
        coverage_counts = ("expected_cells", "recorded_cells", "observed_cells", "missing_cells",
            "absent_cells", "eligible_cells")
        require(all(count(coverage.get(key)) for key in coverage_counts))
        require(coverage["eligible_cells"] <= coverage["observed_cells"] <= coverage["recorded_cells"] <= coverage["expected_cells"]
            and coverage["observed_cells"] + coverage["missing_cells"] == coverage["expected_cells"]
            and coverage["recorded_cells"] + coverage["absent_cells"] == coverage["expected_cells"]
            and coverage["eligible_cells"] == kept
            and isinstance(coverage.get("cells"), list) and len(coverage["cells"]) <= 1000
            and type(coverage.get("cells_truncated")) is bool
            and coverage.get("grid_origin") in ("caller_supplied", "partly_or_fully_inferred"))
        for cell in coverage["cells"]:
            require(isinstance(cell, dict) and isinstance(cell.get("entity"), str)
                and type(cell.get("period")) is int and 1 <= cell["period"] <= 9999
                and type(cell.get("eligible")) is bool
                and cell.get("state") in ("observed", "suppressed", "missing", "invalid", "observed_null", "duplicate", "absent"))
        attrition, robustness = result.get("attrition"), result.get("robustness")
        require(isinstance(attrition, dict) and isinstance(robustness, dict))
        for key in ("entities", "groups"):
            require(isinstance(attrition.get(key), list) and len(attrition[key]) <= 6000)
            for row in attrition[key]:
                require(isinstance(row, dict) and all(count(row.get(k), 5000)
                    for k in ("total_records", "kept_records", "excluded_records")))
                require(row["kept_records"] + row["excluded_records"] == row["total_records"])
        require(robustness.get("truth_label") == "REPORTED" and robustness.get("computed") is False
            and robustness.get("externally_verified") is False
            and isinstance(robustness.get("specifications"), list)
            and robustness["specifications"] == submitted.get("specifications", [])
            and len(robustness["specifications"]) <= 100
            and type(robustness.get("sign_change")) is bool
            and robustness.get("small_cluster_threshold") == 30
            and robustness.get("small_cluster_threshold_kind") == "HEURISTIC_NOT_VALIDITY_TEST"
            and isinstance(robustness.get("flags"), list) and len(robustness["flags"]) <= 101)
        require(isinstance(result.get("issues"), list) and len(result["issues"]) <= 64
            and isinstance(result.get("record_audit"), list) and len(result["record_audit"]) == total)
        require(all(isinstance(flag, dict) and isinstance(flag.get("code"), str)
            for flag in [*result["issues"], *robustness["flags"]]))
        receipt = body.get("receipt")
        if not isinstance(receipt, dict):
            raise _FinanceBoundaryError("CANONICAL_RECEIPT_INVALID")
        unsigned = {k:v for k,v in receipt.items() if k != "receipt_sha256"}
        content = {k:v for k,v in body.items() if k != "receipt"}
        if (receipt.get("schema") != "szl.finance.research-receipt/v1"
                or receipt.get("receipt_sha256") != _finance_digest(unsigned)
                or receipt.get("payload_sha256") != _finance_digest(content)
                or receipt.get("source_revision") != body["source_revision"]
                or receipt.get("signing") != "UNSIGNED_HONEST" or receipt.get("signed") is not False
                or receipt.get("persistence") != "CALLER_HELD" or receipt.get("authority") != "NONE"):
            raise _FinanceBoundaryError("CANONICAL_RECEIPT_INVALID")

    def _finance_get(kind, query=None, method="GET", content=None):
        if not _finance_re.fullmatch(r"providers|overview|research/audit|observations/[a-z][a-z-]{0,79}|analytics/v2/(?:(?:signals|quote)/[A-Z0-9][A-Z0-9.-]{0,23}|portfolio|receipts(?:/verify)?)", kind):
            return _finance_unavailable("ROUTE_DENIED",404)
        analytics=kind.startswith("analytics/v2/")
        research=kind=="research/audit"
        if method not in ("GET","POST") or method=="POST" and kind not in ("analytics/v2/portfolio","analytics/v2/receipts/verify","research/audit") or research and method!="POST":
            return _finance_unavailable("ROUTE_DENIED",404)
        if kind.startswith(("observations/alpaca-", "observations/fred-")):
            return _finance_unavailable("USE_PRIVATE_CANONICAL_SOURCE_ENDPOINT",403)
        target = _FINANCE_ORIGIN + _FINANCE_PREFIX + kind
        pairs = list(query or [])
        allowed_parameters={"limit","offset","token_id","interval","fidelity","cursor","series_ticker","ticker","depth","product","granularity","end","count","cik","series_id"}
        if research:
            allowed_parameters=set()
        elif analytics:
            allowed_parameters={"origin","benchmark"} if method=="GET" else set()
        if any(k not in allowed_parameters for k,v in pairs):
            return _finance_unavailable("INVALID_PARAMETERS",422)
        if len(pairs)>8 or len({k for k,v in pairs}) != len(pairs) or any(len(k)>32 or len(v)>2048 for k,v in pairs):
            return _finance_unavailable("INVALID_PARAMETERS",422)
        if pairs:
            target += "?" + _finance_urlencode(pairs)
        try:
            deadline=_finance_time.monotonic()+12
            # No caller auth/cookies, environment proxy, redirect or decompression.
            with httpx.Client(timeout=5,follow_redirects=False,trust_env=False) as client:
                options={"content":content} if content is not None else {}
                with client.stream(method,target,headers={"Accept":"application/json","Accept-Encoding":"identity","Content-Type":"application/json","User-Agent":"SZL-Finance-Projection/1.1"},**options) as response:
                    mime=response.headers.get("content-type","").split(";",1)[0].strip().lower()
                    if response.status_code not in (200,403,404,422,503) or not (mime=="application/json" or mime.startswith("application/") and mime.endswith("+json")):
                        return _finance_upstream_rejected(response,mime)
                    if response.headers.get("content-encoding","identity").lower() not in ("","identity"):
                        return _finance_unavailable("CANONICAL_ENCODING_DENIED")
                    declared=response.headers.get("content-length")
                    if declared is not None and (not declared.isdigit() or int(declared)>4_000_000):
                        return _finance_unavailable("CANONICAL_RESPONSE_TOO_LARGE")
                    chunks=[]
                    size=0
                    for chunk in response.iter_bytes():
                        if _finance_time.monotonic()>deadline:
                            return _finance_unavailable("CANONICAL_RESPONSE_DEADLINE")
                        size+=len(chunk)
                        if size>4_000_000:
                            return _finance_unavailable("CANONICAL_RESPONSE_TOO_LARGE")
                        chunks.append(chunk)
                    if _finance_time.monotonic()>deadline:
                        return _finance_unavailable("CANONICAL_RESPONSE_DEADLINE")
                    try:
                        body=_finance_json(b"".join(chunks))
                    except (ValueError,UnicodeError,RecursionError):
                        return _finance_unavailable("CANONICAL_SCHEMA_INVALID")
                    if not isinstance(body,dict):
                        return _finance_unavailable("CANONICAL_SCHEMA_INVALID")
                    # Request errors carry no source evidence. Never relay arbitrary
                    # bodies, data, credentials, HTML, or upstream exception strings.
                    if response.status_code in (403,404,422):
                        allowed_errors={"UNKNOWN_SOURCE","INVALID_PARAMETERS","DUPLICATE_QUERY_PARAMETER","PRIVATE_SOURCE_ACCESS_REQUIRED"}
                        error=body.get("error")
                        return _finance_unavailable(error if error in allowed_errors else "CANONICAL_REQUEST_DENIED",response.status_code)
                    if research:
                        if response.status_code!=200:
                            return _finance_unavailable("CANONICAL_RESEARCH_BLOCKED",response.status_code)
                        try:
                            _finance_check_research(body,_finance_json(content))
                        except (_FinanceBoundaryError,TypeError,AttributeError,ValueError) as exc:
                            return _finance_unavailable(str(exc) if isinstance(exc,_FinanceBoundaryError) else "CANONICAL_SCHEMA_INVALID")
                        return body,200
                    if analytics:
                        if response.status_code!=200:
                            return _finance_unavailable("CANONICAL_ANALYTICS_BLOCKED",response.status_code)
                        try:
                            _finance_check_analytics(body,kind,pairs,method)
                        except (_FinanceBoundaryError,TypeError,AttributeError) as exc:
                            return _finance_unavailable(str(exc) if isinstance(exc,_FinanceBoundaryError) else "CANONICAL_SCHEMA_INVALID")
                        return body,200
                    expected="szl.finance.providers/v1" if kind=="providers" else "szl.finance.overview/v1" if kind=="overview" else "szl.finance.observation/v1"
                    source=kind.split("/",1)[1] if kind.startswith("observations/") else None
                    error=_finance_identity(body,expected,source)
                    if error:
                        return _finance_unavailable(error)
                    # Failure status is not an escape hatch for stale or misbound data.
                    if response.status_code==503 and (source is None or body.get("ok") is not False or body.get("state") not in ("STALE","UNAVAILABLE")):
                        return _finance_unavailable("CANONICAL_SCHEMA_INVALID")
                    if kind=="overview" and "data" in body:
                        if not isinstance(body["data"],dict) or len(body["data"])>8:
                            return _finance_unavailable("CANONICAL_SCHEMA_INVALID")
                        for child_source,child in body["data"].items():
                            if child_source not in {"polymarket-markets","kalshi-markets","coinbase-ticker","treasury-rates"}:
                                return _finance_unavailable("CANONICAL_SOURCE_IDENTITY_MISMATCH")
                            error=_finance_identity(child,"szl.finance.observation/v1",child_source)
                            if error:
                                return _finance_unavailable(error)
                    # Nested payload/digest/coverage checks apply equally to success and stale data.
                    # This proves internal consistency, not source authenticity or predictive skill.
                    try:
                        _finance_validate(body, kind, response.status_code)
                    except _FinanceBoundaryError as exc:
                        return _finance_unavailable(str(exc))
                    return body,response.status_code
        except _FinanceTimeoutException:
            return _finance_unavailable("CANONICAL_SOURCE_TIMEOUT")
        except _FinanceTransportError:
            return _finance_unavailable("CANONICAL_SOURCE_TRANSPORT_UNAVAILABLE")
        except Exception:
            return _finance_unavailable("CANONICAL_INTERNAL_ERROR")

    from fastapi import Request as _FinanceRequest
    from httpx import TimeoutException as _FinanceTimeoutException, TransportError as _FinanceTransportError

    @app.get("/research", response_class=HTMLResponse)
    def finance_research_workspace():
        return HTMLResponse(INDEX, headers={"Cache-Control":"private, no-store", "X-Content-Type-Options":"nosniff"})

    @app.get("/api/finance/v2/signals/{symbol}")
    def finance_signal_projection(symbol:str,request:_FinanceRequest):
        body,code=_finance_get("analytics/v2/signals/"+symbol,request.query_params.multi_items())
        return JSONResponse(body,status_code=code,headers={"Cache-Control":"private, no-store","X-Content-Type-Options":"nosniff"})

    @app.get("/api/finance/v2/quote/{symbol}")
    def finance_quote_projection(symbol:str,request:_FinanceRequest):
        body,code=_finance_get("analytics/v2/quote/"+symbol,request.query_params.multi_items())
        return JSONResponse(body,status_code=code,headers={"Cache-Control":"private, no-store","X-Content-Type-Options":"nosniff"})

    @app.get("/api/finance/v2/receipts")
    def finance_receipt_projection():
        body,code=_finance_get("analytics/v2/receipts")
        return JSONResponse(body,status_code=code,headers={"Cache-Control":"private, no-store","X-Content-Type-Options":"nosniff"})

    @app.get("/api/finance/v2/receipts/verify")
    def finance_verification_contract_projection():
        body,code=_finance_get("analytics/v2/receipts/verify")
        return JSONResponse(body,status_code=code,headers={"Cache-Control":"private, no-store","X-Content-Type-Options":"nosniff"})

    async def _finance_post(request,kind):
        raw=bytearray()
        async for chunk in request.stream():
            raw.extend(chunk)
            if len(raw)>160_000:
                body,code=_finance_unavailable("INVALID_PARAMETERS",422)
                return JSONResponse(body,status_code=code)
        try:
            _finance_json(bytes(raw))
        except (ValueError,UnicodeError,RecursionError):
            body,code=_finance_unavailable("INVALID_PARAMETERS",422)
            return JSONResponse(body,status_code=code)
        # Run bounded synchronous upstream I/O outside the ASGI event loop.
        from starlette.concurrency import run_in_threadpool
        body,code=await run_in_threadpool(_finance_get,kind,request.query_params.multi_items(),"POST",bytes(raw))
        return JSONResponse(body,status_code=code,headers={"Cache-Control":"private, no-store","X-Content-Type-Options":"nosniff"})

    @app.post("/api/finance/v2/portfolio")
    async def finance_portfolio_projection(request:_FinanceRequest):
        return await _finance_post(request,"analytics/v2/portfolio")

    @app.post("/api/finance/v2/receipts/verify")
    async def finance_verify_projection(request:_FinanceRequest):
        return await _finance_post(request,"analytics/v2/receipts/verify")

    @app.post("/api/finance/research/audit")
    async def finance_research_audit_projection(request:_FinanceRequest):
        return await _finance_post(request,"research/audit")

    @app.get("/api/finance/providers")
    def finance_provider_projection():
        body,code=_finance_get("providers")
        return JSONResponse(body,status_code=code,headers={"Cache-Control":"private, no-store","X-Content-Type-Options":"nosniff"})

    @app.get("/version")
    def finance_version():
        revision=CFG.get("source_revision")
        return JSONResponse({"schema":"szl.finance.version/v1",
            "version":revision,"source_repository":CFG.get("source_repository"),
            "source_revision":revision,"hf_repository":CFG.get("hf_repository"),
            "model_revision":None,"execution_enabled":False},
            headers={"Cache-Control":"no-store","X-Content-Type-Options":"nosniff"})

    @app.get("/api/finance/overview")
    def finance_overview_projection():
        body,code=_finance_get("overview")
        return JSONResponse(body,status_code=code,headers={"Cache-Control":"private, no-store","X-Content-Type-Options":"nosniff"})

    @app.get("/api/finance/observations/{source}")
    def finance_observation_projection(source:str,request:_FinanceRequest):
        body,code=_finance_get("observations/"+source,request.query_params.multi_items())
        return JSONResponse(body,status_code=code,headers={"Cache-Control":"private, no-store","X-Content-Type-Options":"nosniff"})

    # The existing landing-page reader must use the same source validation as
    # the explicit finance routes. HTTP 200 alone is never a LIVE-data claim.
    def probe():
        started = _finance_time.monotonic()
        body, status = _finance_get("overview")
        accepted = status == 200 and body.get("ok") is True
        return JSONResponse({"status": "SNAPSHOT" if accepted else "UNAVAILABLE",
            "http_status": status, "latency_ms": round((_finance_time.monotonic()-started)*1000, 1),
            "source": _FINANCE_ORIGIN + _FINANCE_PREFIX + "overview", "data": body,
            "execution_enabled": False, "live_provider_verified": False},
            status_code=200 if accepted else 503,
            headers={"Cache-Control":"private, no-store", "X-Content-Type-Options":"nosniff"})

'''


def augment(app_source: str) -> str:
    if "# Public finance projection." in app_source:
        raise ValueError("finance projection already installed")
    projection=FINANCE_PROXY.replace("__COMPONENT_BINDING__", repr(COMPONENT))
    compile(app_source + projection, "finance-flagship-app.py", "exec")
    return app_source + projection


def validation_namespace(revision: str) -> dict:
    """Run the emitted app's exact validators without ASGI, network or credentials."""
    source = FINANCE_PROXY.replace("__COMPONENT_BINDING__", repr(COMPONENT))
    validators = source.split("    def _finance_get(", 1)[0]
    namespace = {"CFG": {"slug": "finance", "source_revision": revision}, "json": json}
    exec(compile(validators, "finance-emitted-validators.py", "exec"), namespace)
    return namespace
