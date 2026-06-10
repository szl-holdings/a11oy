# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · Doctrine v11 · Perplexity Computer Agent.
"""szl_connectors.ready — a reusable REAL client base for credential-READY connectors.

These connectors are GENUINELY ready, NOT stubs: each declares the provider's
documented REST endpoint, the documented record shape (schema_preview), the auth
header builder, and a real `read()` that performs the documented HTTP call. With
NO credentials it returns state=READY + "set <ENV_VAR> to activate" + the exact
secret name(s) — and NEVER fabricates records. The moment the customer's
credentials land in the Space secret, `health()`/`read()` flip to CONNECTED and
render the customer's live data.

DOCTRINE: env-only creds; never a fabricated record; honest READY/CONNECTED/ERROR.
"""
from __future__ import annotations

import os
from typing import Any, Callable

from .base import Connector, Records, State, WriteResult, http_json, cred_fingerprint
from .governance import gate_write


class ReadyConnector(Connector):
    """A connector whose read() hits a documented REST endpoint with a header-auth.

    Subclasses set: id, label, category, auth_kind, env_vars, provider_base,
    docs_url, schema_preview, _read_path (the endpoint path appended to
    provider_base, may contain {sub} from a base_sub() override), _record_path
    (dotted path into the JSON to the list of records), and _auth_header().
    """
    _read_path: str = ""
    _record_path: str = ""           # e.g. "value" or "results" or "data.contacts"
    _record_fields: list[str] = []   # which fields to project (defaults to schema_preview)
    _query_param: dict[str, Any] = {}
    writable = False
    _primary_secret: str = ""        # the single secret to name in the READY chip

    # ── auth header (override per provider) ───────────────────────────────
    def _token(self) -> str | None:
        for k in self.env_vars:
            v = os.environ.get(k)
            if v:
                return v
        return None

    def _auth_header(self) -> dict[str, str]:
        tok = self._token()
        return {"Authorization": f"Bearer {tok}"} if tok else {}

    def _base_url(self) -> str:
        """Substitute {sub} placeholders from env (instance/host/tenant)."""
        url = self.provider_base
        # common substitutions from env
        for env_name in self.env_vars:
            val = os.environ.get(env_name)
            if val and "{" in url:
                tag = env_name.split("_")[-1].lower()  # e.g. ...INSTANCE -> instance
                url = url.replace("{" + tag + "}", val)
        return url

    def _primary_missing(self) -> bool:
        sec = self._primary_secret or (self.env_vars[0] if self.env_vars else "")
        return not os.environ.get(sec)

    def _missing_env(self):
        return [k for k in self.env_vars if not os.environ.get(k)]

    def _probe(self):
        if self._primary_missing():
            return None, "no creds"
        url = self._base_url().rstrip("/") + "/" + self._read_path.lstrip("/")
        st, _ = http_json(url, headers={"Accept": "application/json", **self._auth_header()})
        return (st in (200, 201)), f"{self.label} HTTP {st}"

    def _dig(self, raw: Any) -> list[dict]:
        cur = raw
        if self._record_path:
            for part in self._record_path.split("."):
                if isinstance(cur, dict):
                    cur = cur.get(part, [])
                else:
                    cur = []
        if isinstance(cur, dict):
            cur = cur.get("results") or cur.get("data") or cur.get("value") or list(cur.values())
        return cur if isinstance(cur, list) else []

    def read(self, query: dict | None = None) -> Records:
        if self._primary_missing():
            sec = self._primary_secret or (self.env_vars[0] if self.env_vars else "?")
            return self._ready_records(
                f"provide credentials to activate — set {', '.join(self._missing_env())} "
                f"(primary secret: {sec}). Hits {self.provider_base}/{self._read_path}.")
        limit = max(1, min(int((query or {}).get("limit", 12)), 50))
        url = self._base_url().rstrip("/") + "/" + self._read_path.lstrip("/")
        import urllib.parse as up
        params = dict(self._query_param)
        if params:
            url += ("&" if "?" in url else "?") + up.urlencode(params)
        st, raw = http_json(url, headers={"Accept": "application/json", **self._auth_header()})
        if st in (200, 201):
            rows = self._dig(raw)
            fields = self._record_fields or self.schema_preview
            proj = []
            for r in rows[:limit]:
                if isinstance(r, dict):
                    p = {f: r.get(f) for f in fields if f in r}
                    proj.append(p or {k: v for k, v in list(r.items())[:6] if not isinstance(v, (dict, list))})
            return Records(connector_id=self.id, category=self.category, state=State.CONNECTED,
                           records=proj, source=f"{self.label} {url}", live=True,
                           note=f"live · {len(rows)} records", schema_preview=fields)
        return Records(connector_id=self.id, category=self.category, state=State.ERROR,
                       records=[], source=self.provider_base, live=False,
                       note=f"credentials present but {self.label} returned HTTP {st}",
                       schema_preview=self.schema_preview)


class WritableReadyConnector(ReadyConnector):
    """A ReadyConnector that also exposes a Λ-gated + receipted write()."""
    writable = True
    mcp_tool = "szl_connector_read/write"
    _write_path: str = ""

    def write(self, action: dict | None = None) -> WriteResult:
        action = action or {}
        connected = not self._primary_missing()
        gate_action = {"method": action.get("method", "create"),
                       "object": action.get("object", self._write_path or "record"),
                       "values_keys": sorted((action.get("values") or {}).keys())}
        tok = self._token()
        creds_fp = {"token": cred_fingerprint(tok)} if tok else {}
        allowed, lam, receipt, quorum, detail = gate_write(
            connector_id=self.id, connected=connected, action=gate_action,
            cred_fingerprints=creds_fp, quorum_present=action.get("quorum_present"))
        if not allowed:
            return WriteResult(connector_id=self.id, ok=False,
                               state=State.READY if not connected else State.CONNECTED,
                               receipt_hash=receipt["receipt_hash"], lambda_value=lam,
                               quorum=quorum, detail=detail, dsse=receipt["dsse"])
        import json as _json
        url = self._base_url().rstrip("/") + "/" + (self._write_path or self._read_path).lstrip("/")
        st, raw = http_json(url, method="POST",
                            headers={"Content-Type": "application/json", **self._auth_header()},
                            data=_json.dumps(action.get("values", {})).encode())
        ok = st in (200, 201)
        return WriteResult(connector_id=self.id, ok=ok,
                           state=State.CONNECTED if ok else State.ERROR,
                           receipt_hash=receipt["receipt_hash"], lambda_value=lam, quorum=quorum,
                           detail=f"{self.label} write HTTP {st}", dsse=receipt["dsse"])


__all__ = ["ReadyConnector", "WritableReadyConnector"]
