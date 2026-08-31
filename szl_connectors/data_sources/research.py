# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · Doctrine v11 · Perplexity Computer Agent.
"""a11oy research / model-atlas / ontology live connectors (keyless → CONNECTED now).

  arxiv     arXiv API (Atom XML)                     keyless
  hf_hub    Hugging Face Hub API (models/datasets)   public keyless; token → higher rate
  wikidata  Wikidata WDQS SPARQL                      keyless (60/min)
"""
from __future__ import annotations

import os
import time
import urllib.parse as up
import xml.etree.ElementTree as ET
from typing import Any

from ..base import Connector, Records, State, http_json, http_text, _now
from ..registry import register

_CACHE: dict[str, tuple[float, Any]] = {}


def _cached(k, ttl):
    h = _CACHE.get(k)
    return h[1] if h and (time.time() - h[0]) < ttl else None


def _put(k, v):
    _CACHE[k] = (time.time(), v)


@register
class ArxivConnector(Connector):
    id = "arxiv"
    label = "arXiv research papers"
    category = "research"
    auth_kind = "none"
    free_tier = True
    provider_base = "http://export.arxiv.org/api/query"
    docs_url = "https://info.arxiv.org/help/api/index.html"
    schema_preview = ["id", "title", "authors", "published", "url"]
    _NS = {"a": "http://www.w3.org/2005/Atom"}

    def _probe(self):
        st, _ = http_text(self.provider_base + "?search_query=all:test&max_results=1")
        return (st == 200), f"arXiv HTTP {st}"

    def read(self, query: dict | None = None) -> Records:
        q = (query or {}).get("q", "formal verification temporal logic")
        limit = max(1, min(int((query or {}).get("limit", 8)), 30))
        ck = f"arxiv:{q}:{limit}"
        c = _cached(ck, 900)
        if c:
            return c
        url = self.provider_base + "?" + up.urlencode({
            "search_query": f"all:{q}", "start": 0, "max_results": limit,
            "sortBy": "submittedDate", "sortOrder": "descending"})
        st, xml = http_text(url)
        if st == 200 and "<entry" in xml:
            root = ET.fromstring(xml)
            papers = []
            for e in root.findall("a:entry", self._NS):
                aid = (e.findtext("a:id", "", self._NS) or "").rsplit("/", 1)[-1]
                title = " ".join((e.findtext("a:title", "", self._NS) or "").split())
                authors = ", ".join((a.findtext("a:name", "", self._NS) or "")
                                    for a in e.findall("a:author", self._NS))
                pub = (e.findtext("a:published", "", self._NS) or "")[:10]
                papers.append({"id": aid, "title": title, "authors": authors,
                               "published": pub, "url": e.findtext("a:id", "", self._NS)})
            r = Records(connector_id=self.id, category=self.category, state=State.CONNECTED,
                        records=papers, source="arXiv API (Cornell, free)", live=True,
                        note=f"live · query={q}", schema_preview=self.schema_preview)
            _put(ck, r)
            return r
        return self._ready_records(f"arXiv unreachable (HTTP {st})")


@register
class HfHubConnector(Connector):
    id = "hf_hub"
    label = "Hugging Face Hub"
    category = "research"
    auth_kind = "token"
    free_tier = True  # public keyless tier
    env_vars = ["SZL_HF_TOKEN", "HF_TOKEN", "HUGGING_FACE_HUB_TOKEN"]
    provider_base = "https://huggingface.co/api"
    docs_url = "https://huggingface.co/docs/hub/api"
    schema_preview = ["id", "downloads", "likes", "pipeline_tag", "library_name"]

    def _missing_env(self):
        return []  # public tier keyless

    def _headers(self):
        tok = (os.environ.get("SZL_HF_TOKEN") or os.environ.get("HF_TOKEN")
               or os.environ.get("HUGGING_FACE_HUB_TOKEN"))
        return {"Authorization": f"Bearer {tok}"} if tok else {}

    def _probe(self):
        st, _ = http_json(self.provider_base + "/models?limit=1", headers=self._headers())
        return (st == 200), f"HF Hub HTTP {st}"

    def read(self, query: dict | None = None) -> Records:
        kind = (query or {}).get("kind", "models")  # models|datasets|spaces
        search = (query or {}).get("search", "")
        limit = max(1, min(int((query or {}).get("limit", 10)), 30))
        ck = f"hf:{kind}:{search}:{limit}"
        c = _cached(ck, 300)
        if c:
            return c
        params = {"limit": limit, "sort": "downloads", "direction": -1}
        if search:
            params["search"] = search
        st, raw = http_json(f"{self.provider_base}/{kind}?" + up.urlencode(params),
                            headers=self._headers())
        if st == 200 and isinstance(raw, list):
            items = [{"id": m.get("id") or m.get("modelId"), "downloads": m.get("downloads"),
                      "likes": m.get("likes"), "pipeline_tag": m.get("pipeline_tag"),
                      "library_name": m.get("library_name")} for m in raw[:limit]]
            r = Records(connector_id=self.id, category=self.category, state=State.CONNECTED,
                        records=items, source=f"HF Hub /{kind}", live=True,
                        note=f"live · {kind}", schema_preview=self.schema_preview)
            _put(ck, r)
            return r
        return self._ready_records(f"HF Hub HTTP {st}")


@register
class WikidataConnector(Connector):
    id = "wikidata"
    label = "Wikidata (WDQS SPARQL)"
    category = "ontology"
    auth_kind = "none"
    free_tier = True
    provider_base = "https://query.wikidata.org/sparql"
    docs_url = "https://www.mediawiki.org/wiki/Wikidata_Query_Service/User_Manual"
    schema_preview = ["item", "itemLabel"]

    def _probe(self):
        st, _ = http_json(self.provider_base + "?format=json&query=" + up.quote("SELECT ?x WHERE{?x wdt:P31 wd:Q5}LIMIT 1"))
        return (st == 200), f"WDQS HTTP {st}"

    def read(self, query: dict | None = None) -> Records:
        sparql = (query or {}).get("sparql") or (
            "SELECT ?item ?itemLabel WHERE { ?item wdt:P31 wd:Q4830453 . "
            "SERVICE wikibase:label { bd:serviceParam wikibase:language 'en'. } } LIMIT 10")
        ck = f"wd:{hash(sparql)}"
        c = _cached(ck, 600)
        if c:
            return c
        st, raw = http_json(self.provider_base + "?format=json&query=" + up.quote(sparql))
        if st == 200 and isinstance(raw, dict):
            cols = raw.get("head", {}).get("vars", [])
            rows = []
            for b in raw.get("results", {}).get("bindings", []):
                rows.append({c2: b.get(c2, {}).get("value") for c2 in cols})
            r = Records(connector_id=self.id, category=self.category, state=State.CONNECTED,
                        records=rows, source="Wikidata WDQS SPARQL", live=True,
                        note="live SPARQL", schema_preview=cols or self.schema_preview)
            _put(ck, r)
            return r
        return self._ready_records(f"WDQS unreachable (HTTP {st})")


__all__ = ["ArxivConnector", "HfHubConnector", "WikidataConnector"]
