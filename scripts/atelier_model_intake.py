#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Read-only, bounded public Hub metadata intake; no weights or inference calls.

Taxonomy home: research/tools. Writes JSON to stdout only. Does not use cached
credentials, import model code, follow redirects, or mutate any remote resource.
"""

import datetime
import hashlib
import json
import re
import urllib.error
import urllib.parse
import urllib.request

LIMIT = 5
MAX_REQUESTS = 24
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
TIMEOUT_SECONDS = 20
REPOSITORY_ID = re.compile(r"^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$")
REVISION = re.compile(r"^[0-9a-f]{40}$")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, "redirect denied", headers, fp)


class PublicMetadataReader:
    def __init__(self):
        self.requests = 0
        self.opener = urllib.request.build_opener(NoRedirect())

    def get(self, path, params):
        if self.requests >= MAX_REQUESTS:
            raise ValueError("request budget exhausted")
        self.requests += 1
        url = "https://huggingface.co" + path + "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "SZL-Atelier-Model-Intake/1.0 (public read-only research)", "Accept": "application/json"},
            method="GET",
        )
        with self.opener.open(req, timeout=TIMEOUT_SECONDS) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise ValueError("response byte budget exceeded")
        return json.loads(raw), {
            "url": url,
            "observed_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "response_sha256": hashlib.sha256(raw).hexdigest(),
            "response_bytes": len(raw),
        }


def collect():
    reader = PublicMetadataReader()
    rankings = []
    selected = {}
    for cohort in ("text-generation", "text-generation-with-provider-mapping"):
        for metric in ("trendingScore", "downloads"):
            params = [("pipeline_tag", "text-generation"), ("sort", metric), ("direction", "-1"), ("limit", str(LIMIT)), ("full", "true")]
            if cohort.endswith("with-provider-mapping"):
                params.append(("inference_provider", "all"))
            rows, observation = reader.get("/api/models", params)
            if not isinstance(rows, list) or len(rows) > LIMIT:
                raise ValueError("invalid bounded listing")
            ranking = {"cohort": cohort, "metric": metric, **observation, "models": []}
            for position, row in enumerate(rows, 1):
                model_id = row.get("id")
                if not isinstance(model_id, str) or not REPOSITORY_ID.fullmatch(model_id):
                    raise ValueError("invalid public repository id")
                list_sha = row.get("sha")
                ranking["models"].append({"rank": position, "id": model_id, "metric_value": row.get(metric), "listed_revision": list_sha if isinstance(list_sha, str) and REVISION.fullmatch(list_sha) else None})
                selected.setdefault(model_id, {
                    "id": model_id,
                    "downloads": row.get("downloads"),
                    "likes": row.get("likes"),
                    "trending_score": row.get("trendingScore"),
                    "pipeline_tag": row.get("pipeline_tag"),
                    "library_name": row.get("library_name"),
                })
            rankings.append(ranking)
    for model_id, model in selected.items():
        try:
            details, observation = reader.get("/api/models/" + model_id, [("expand", "sha"), ("expand", "cardData"), ("expand", "inferenceProviderMapping")])
            sha = details.get("sha")
            valid_revision = isinstance(sha, str) and REVISION.fullmatch(sha)
            card = details.get("cardData") or {}
            model.update({
                "metadata_observation": observation,
                "revision": sha if valid_revision else None,
                "model_card_url": "https://huggingface.co/" + model_id + "/blob/" + sha + "/README.md" if valid_revision else None,
                "card_license_declared": card.get("license"),
                "card_license_name": card.get("license_name"),
                "model_license_text_reviewed": False,
                "base_model": card.get("base_model"),
                "inference_provider_mapping": details.get("inferenceProviderMapping"),
                "provider_evidence_class": "REPORTED_METADATA_NOT_INFERENCE",
                "official_code_repository": None,
                "code_license": None,
                "code_license_reviewed": False,
                "local_inference_witnessed": False,
                "quality_score": None,
                "first_token_latency_ms": None,
                "tokens_per_second": None,
                "joules": None,
                "price_per_million_tokens": None,
                "deployment_admitted": False,
            })
        except (ValueError, urllib.error.URLError, TimeoutError) as exc:
            model.update({"revision": None, "card_license_declared": None, "code_license": None, "inference_provider_mapping": None, "metadata_state": "UNAVAILABLE", "error_kind": type(exc).__name__})
    return {
        "schema": "szl.atelier.public-model-metadata.v1",
        "observed_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source": "Hugging Face public Hub API",
        "ranking_is_quality": False,
        "metadata_is_successful_inference": False,
        "external_mutation_performed": False,
        "billable_inference_performed": False,
        "model_weights_downloaded": False,
        "public_code_executed": False,
        "bounds": {"per_ranking_limit": LIMIT, "ranking_count": 4, "requests_made": reader.requests, "max_requests": MAX_REQUESTS, "max_response_bytes": MAX_RESPONSE_BYTES, "timeout_seconds": TIMEOUT_SECONDS},
        "rankings": rankings,
        "models": list(selected.values()),
    }


if __name__ == "__main__":
    print(json.dumps(collect(), ensure_ascii=False, indent=2, allow_nan=False))
