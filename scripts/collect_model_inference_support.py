#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Prepare or validate a reviewable provider-status source; public metadata GETs only."""

import argparse
import copy
import hashlib
import json
import socket
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import a11oy_model_support as support  # noqa: E402


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch_observation(model_id):
    url = support.mapping_url(model_id)
    try:
        request = urllib.request.Request(url, headers={
            "Accept": "application/json", "User-Agent": "a11oy-model-support/1.0",
        })
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=8) as response:
            if response.status != 200 or response.geturl() != url:
                raise support.SupportDataError("unexpected response")
            payload = support.decode_json(response.read(support.MAX_RESPONSE_BYTES + 1), support.MAX_RESPONSE_BYTES)
        return support.observation_from_mapping(model_id, payload, support.utc_now())
    except urllib.error.HTTPError as exc:
        exc.close()
        error = "HTTP_ERROR"
    except (TimeoutError, socket.timeout):
        error = "TIMEOUT"
    except urllib.error.URLError:
        error = "NETWORK_ERROR"
    except (OSError, support.SupportDataError, ValueError, TypeError, KeyError):
        error = "INVALID_RESPONSE"
    return support.unavailable_observation(model_id, support.utc_now(), error)


def _prior_request(row):
    return {
        "model_id": row["title"], "discussion_number": row["num"], "url": row["url"],
        "author": row["author"], "recorded_status": row["status"],
        "evidence_kind": "PRIOR_DISCUSSION", "model_revision": None,
        "requested_at": None, "readback_at": None, "body_sha256": None,
        "readback_body_sha256": None, "readback_normalization": None,
    }


def _submitted_request(row):
    support._require(row.get("verified_readback") is True, "submission has no verified readback")
    support._require(row.get("target_repository") == "huggingface/InferenceSupport", "wrong support repository")
    support._require(row.get("request_state") == "SUBMITTED_RESEARCH_COMPATIBILITY_REVIEW", "unsupported submission claim")
    return {
        "model_id": row["model_id"], "discussion_number": row["discussion_number"],
        "url": row["url"], "author": row["author"], "recorded_status": row["status"],
        "evidence_kind": "VERIFIED_SUBMISSION", "model_revision": row["model_revision"],
        "requested_at": row["requested_at"], "readback_at": row["readback_at"],
        "body_sha256": row["body_sha256"], "readback_body_sha256": row["readback_body_sha256"],
        "readback_normalization": row["readback_normalization"],
    }


def bootstrap(audit, submitted, prior, inventory_raw):
    """Import reviewed evidence, keeping prior unmatched identities without aliases."""
    support._require(audit.get("schema") == "szl.inference-provider-eligibility-audit/v1", "unsupported audit input")
    support._require(isinstance(submitted, list) and isinstance(prior, list), "invalid request input")
    models = []
    ids = [row["id"] for row in audit["rows"]]
    support._require(len(ids) == len(set(ids)), "duplicate audit model")
    submitted_ids = [row["model_id"] for row in submitted]
    support._require(len(submitted_ids) == len(set(submitted_ids)) and set(submitted_ids) <= set(ids), "duplicate or unknown submitted model")
    requests = [_submitted_request(row) for row in submitted] + [_prior_request(row) for row in prior]
    for row in audit["rows"]:
        model_id = row["id"]
        support._require(row["mapping_url"] == support.mapping_url(model_id), "audit mapping URL mismatch")
        support._require(row["mapping_revision"] == row["hub_revision"], "audit metadata/mapping revision mismatch")
        matched = sorted((request for request in requests if request["model_id"] == model_id),
                         key=lambda request: request["discussion_number"])
        models.append({
            "id": model_id, "repo_type": "model",
            "assessment": {
                "hub_revision": row["hub_revision"], "observed_at": row["observed_at"],
                "source_url": row["qualification_source"], "artifact_class": row["artifact_class"],
                "qualification_note": row["qualification_note"],
                "request_disposition": row["request_disposition"], "suggested_route": row["suggested_route"],
            },
            "inference": support.observation_from_mapping(model_id, {
                "id": model_id, "sha": row["mapping_revision"],
                "inferenceProviderMapping": row["provider_mapping"],
            }, row["observed_at"]),
            "support": {"state": support.request_state(matched), "requests": matched},
        })
    document = {
        "$comment": support.NOTICE, "schema": support.SCHEMA,
        "generated_at": support.utc_now(), "organization": "SZLHOLDINGS",
        "scope": "PUBLIC_MODEL_NAMESPACE_ONLY",
        "inventory_source": {"path": "docs/huggingface-ecosystem-manifest.json",
                             "model_ids_sha256": hashlib.sha256(support.canonical_bytes(sorted(ids))).hexdigest()},
        "max_observation_age_seconds": support.MAX_AGE_SECONDS,
        "authority": dict(support.AUTHORITY), "models": sorted(models, key=lambda row: row["id"]),
        "unmatched_prior_requests": sorted((request for request in requests if request["model_id"] not in ids),
                                           key=lambda request: request["discussion_number"]),
    }
    return support.validate_document(document, support.decode_json(inventory_raw))


def refresh(document, inventory_raw, fetcher=fetch_observation):
    """Keep source assessments/requests intact; failed reads replace availability with unknown."""
    inventory = support.decode_json(inventory_raw)
    support.validate_document(document, inventory)
    output = copy.deepcopy(document)
    ids = [row["id"] for row in output["models"]]
    with ThreadPoolExecutor(max_workers=4) as pool:
        observations = list(pool.map(fetcher, ids))
    for row, observation in zip(output["models"], observations):
        row["inference"] = observation
    output["generated_at"] = support.utc_now()
    return support.validate_document(output, inventory)


def render(document):
    return json.dumps(document, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="strict offline source and inventory validation")
    mode.add_argument("--refresh", action="store_true", help="bounded anonymous metadata reads, no inference")
    mode.add_argument("--bootstrap-audit", type=Path, help="initial reviewed eligibility audit")
    parser.add_argument("--submitted", type=Path, help="verified submitted request evidence for initial import")
    parser.add_argument("--prior", type=Path, help="prior discussion observations for initial import")
    parser.add_argument("--source", type=Path, default=support.STATUS_PATH)
    parser.add_argument("--output", type=Path, default=support.STATUS_PATH)
    parser.add_argument("--inventory", type=Path, default=support.INVENTORY_PATH)
    args = parser.parse_args(argv)
    try:
        with args.inventory.open("rb") as handle:
            inventory_raw = handle.read(support.MAX_BYTES + 1)
        if args.bootstrap_audit:
            if args.submitted is None or args.prior is None:
                parser.error("bootstrap requires --submitted and --prior")
            document = bootstrap(support.read_json(args.bootstrap_audit), support.read_json(args.submitted),
                                 support.read_json(args.prior), inventory_raw)
        else:
            document = support.validate_document(support.read_json(args.source), support.decode_json(inventory_raw))
            if args.refresh:
                document = refresh(document, inventory_raw)
        if args.check:
            support._require(args.source.read_text(encoding="utf-8") == render(document), "noncanonical source encoding")
        else:
            args.output.write_text(render(document), encoding="utf-8")
        print(json.dumps({"schema": support.SCHEMA, "models": len(document["models"]),
                          "mode": "CHECK" if args.check else "SOURCE_CANDIDATE",
                          "authority": support.AUTHORITY}))
        return 0
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        print(f"Model support source unavailable: {type(exc).__name__}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
