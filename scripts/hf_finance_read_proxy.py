# SPDX-License-Identifier: Apache-2.0
"""Thin public finance projection for the existing canonical flagship publisher.

No provider credentials, connector logic, formula or independent deployment.
Only canonical JSON read endpoints are proxied; source semantics remain intact.
"""

FINANCE_PROXY = r'''
# Public finance projection. Core normalization remains in szl-holdings/a11oy.
if CFG.get("slug") == "finance":
    import re as _finance_re
    from fastapi import Request as _FinanceRequest
    from urllib.parse import urlencode as _finance_urlencode
    _FINANCE_ORIGIN = "https://szlholdings-a11oy.hf.space"
    _FINANCE_PREFIX = "/api/a11oy/v1/finance/"

    def _finance_get(kind, query=None):
        if not _finance_re.fullmatch(r"providers|overview|observations/[a-z][a-z-]{0,79}", kind):
            return {"ok":False,"state":"UNAVAILABLE","error":"ROUTE_DENIED"}, 404
        if kind.startswith(("observations/alpaca-", "observations/fred-")):
            return {"ok":False,"state":"UNAVAILABLE","error":"USE_PRIVATE_CANONICAL_SOURCE_ENDPOINT"}, 403
        target = _FINANCE_ORIGIN + _FINANCE_PREFIX + kind
        pairs = list(query or [])
        allowed_parameters={"limit","offset","token_id","interval","fidelity","cursor","series_ticker","ticker","depth","product","granularity","end","count","cik","series_id"}
        if any(k not in allowed_parameters for k,v in pairs):
            return {"ok":False,"state":"UNAVAILABLE","error":"INVALID_PARAMETERS"},422
        if len(pairs)>8 or len({k for k,v in pairs}) != len(pairs) or any(len(k)>32 or len(v)>2048 for k,v in pairs):
            return {"ok":False,"state":"UNAVAILABLE","error":"INVALID_PARAMETERS"}, 422
        if pairs:
            target += "?" + _finance_urlencode(pairs)
        try:
            # No caller auth header/cookie forwarded. Never follow an upstream redirect.
            with httpx.Client(timeout=15,follow_redirects=False,trust_env=False) as client:
                with client.stream("GET",target,headers={"Accept":"application/json","User-Agent":"SZL-Finance-Projection/1.0"}) as response:
                    if response.status_code not in (200,403,404,422,503) or "json" not in response.headers.get("content-type",""):
                        return {"ok":False,"state":"UNAVAILABLE","error":"CANONICAL_SOURCE_UNAVAILABLE"},503
                    chunks=[]
                    size=0
                    for chunk in response.iter_bytes():
                        size+=len(chunk)
                        if size>4_000_000:
                            return {"ok":False,"state":"UNAVAILABLE","error":"CANONICAL_RESPONSE_TOO_LARGE"},503
                        chunks.append(chunk)
                    body=json.loads(b"".join(chunks))
                    if not isinstance(body,dict):
                        return {"ok":False,"state":"UNAVAILABLE","error":"CANONICAL_SCHEMA_INVALID"},503
                    if response.status_code==200:
                        expected="szl.finance.providers/v1" if kind=="providers" else "szl.finance.overview/v1" if kind=="overview" else "szl.finance.observation/v1"
                        if body.get("schema")!=expected or body.get("execution_enabled") is not False:
                            return {"ok":False,"state":"UNAVAILABLE","error":"CANONICAL_SCHEMA_INVALID"},503
                        if kind.startswith("observations/") and body.get("source")!=kind.split("/",1)[1]:
                            return {"ok":False,"state":"UNAVAILABLE","error":"CANONICAL_SOURCE_IDENTITY_MISMATCH"},503
                        expected_revision=CFG.get("source_revision","")
                        if not _finance_re.fullmatch(r"[0-9a-f]{40}",expected_revision) or body.get("source_revision")!=expected_revision:
                            return {"ok":False,"state":"UNAVAILABLE","error":"CANONICAL_REVISION_MISMATCH"},503
                    return body,response.status_code
        except Exception:
            return {"ok":False,"state":"UNAVAILABLE","error":"CANONICAL_SOURCE_UNAVAILABLE"},503

    @app.get("/api/finance/providers")
    def finance_provider_projection():
        body,code=_finance_get("providers")
        return JSONResponse(body,status_code=code,headers={"Cache-Control":"private, no-store"})

    @app.get("/api/finance/overview")
    def finance_overview_projection():
        body,code=_finance_get("overview")
        return JSONResponse(body,status_code=code,headers={"Cache-Control":"private, no-store"})

    @app.get("/api/finance/observations/{source}")
    def finance_observation_projection(source:str,request:_FinanceRequest):
        body,code=_finance_get("observations/"+source,request.query_params.multi_items())
        return JSONResponse(body,status_code=code,headers={"Cache-Control":"private, no-store"})

    # Existing /api/live resolves this function at call time. An HTTP 200 alone
    # must never turn a partially unavailable finance overview into LIVE.
    def probe():
        body,code=_finance_get("overview")
        ok=code==200 and body.get("ok") is True
        return {"status":"SNAPSHOT" if ok else "UNAVAILABLE", "http_status":code,
                "source":_FINANCE_ORIGIN+_FINANCE_PREFIX+"overview", "data":body,
                "execution_enabled":False}
'''


def augment(app_source: str) -> str:
    if "# Public finance projection." in app_source:
        raise ValueError("finance projection already installed")
    compile(app_source + FINANCE_PROXY, "finance-flagship-app.py", "exec")
    return app_source + FINANCE_PROXY
