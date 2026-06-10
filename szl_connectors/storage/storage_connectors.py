# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · Doctrine v11 · Perplexity Computer Agent.
"""Object-storage connectors — Amazon S3, Google Cloud Storage, Azure Blob.

REAL clients against documented endpoints. NO creds → READY + exact secret name;
NEVER fabricates a record. Reads are bucket/object listings (metadata-scoped).

S3 read uses AWS Signature v4 (auth_kind="aws_sigv4"); because SigV4 signing is
non-trivial without the long-term secret present, the READY path names the exact
secrets and the live path signs the request once the secret is supplied.

API refs (publicly documented shapes):
  S3 ListObjectsV2    https://docs.aws.amazon.com/AmazonS3/latest/API/API_ListObjectsV2.html
  GCS objects.list    https://cloud.google.com/storage/docs/json_api/v1/objects/list
  Azure Blob List     https://learn.microsoft.com/rest/api/storageservices/list-blobs
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import hmac
import os
import urllib.parse as _up

from ..base import State, Records, http_json, http_text
from ..ready import ReadyConnector
from ..registry import register


def _sigv4_headers(method, host, region, service, path, query, access_key, secret_key, session_token=None):
    """Minimal AWS SigV4 signer for a GET with empty payload."""
    now = _dt.datetime.now(_dt.timezone.utc)
    amzdate = now.strftime("%Y%m%dT%H%M%SZ")
    datestamp = now.strftime("%Y%m%d")
    payload_hash = hashlib.sha256(b"").hexdigest()
    canon_headers = f"host:{host}\nx-amz-content-sha256:{payload_hash}\nx-amz-date:{amzdate}\n"
    signed_headers = "host;x-amz-content-sha256;x-amz-date"
    canon_req = f"{method}\n{path}\n{query}\n{canon_headers}\n{signed_headers}\n{payload_hash}"
    scope = f"{datestamp}/{region}/{service}/aws4_request"
    string_to_sign = ("AWS4-HMAC-SHA256\n" + amzdate + "\n" + scope + "\n" +
                      hashlib.sha256(canon_req.encode()).hexdigest())

    def _hmac(key, msg):
        return hmac.new(key, msg.encode(), hashlib.sha256).digest()
    kdate = _hmac(("AWS4" + secret_key).encode(), datestamp)
    kregion = _hmac(kdate, region)
    kservice = _hmac(kregion, service)
    ksigning = _hmac(kservice, "aws4_request")
    signature = hmac.new(ksigning, string_to_sign.encode(), hashlib.sha256).hexdigest()
    auth = (f"AWS4-HMAC-SHA256 Credential={access_key}/{scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}")
    h = {"Authorization": auth, "x-amz-date": amzdate, "x-amz-content-sha256": payload_hash}
    if session_token:
        h["x-amz-security-token"] = session_token
    return h


# ── Amazon S3 (aws_sigv4; free 5GB tier) ──────────────────────────────────────
@register
class S3Connector(ReadyConnector):
    id = "s3"
    label = "Amazon S3"
    category = "storage"
    auth_kind = "aws_sigv4"
    free_tier = True  # 5 GB free tier
    env_vars = ["SZL_AWS_ACCESS_KEY_ID", "SZL_AWS_SECRET_ACCESS_KEY",
                "SZL_AWS_REGION", "SZL_S3_BUCKET"]
    _primary_secret = "SZL_AWS_SECRET_ACCESS_KEY"
    provider_base = "https://{bucket}.s3.{region}.amazonaws.com"
    docs_url = "https://docs.aws.amazon.com/AmazonS3/latest/API/API_ListObjectsV2.html"
    schema_preview = ["Key", "Size", "LastModified", "StorageClass"]

    def read(self, query=None):
        ak = os.environ.get("SZL_AWS_ACCESS_KEY_ID")
        sk = os.environ.get("SZL_AWS_SECRET_ACCESS_KEY")
        region = os.environ.get("SZL_AWS_REGION", "us-east-1")
        bucket = os.environ.get("SZL_S3_BUCKET", "")
        if not (ak and sk and bucket):
            return self._ready_records(
                "provide credentials to activate — set SZL_AWS_ACCESS_KEY_ID, "
                "SZL_AWS_SECRET_ACCESS_KEY, SZL_AWS_REGION, SZL_S3_BUCKET. "
                "Signs ListObjectsV2 with AWS SigV4.")
        host = f"{bucket}.s3.{region}.amazonaws.com"
        qs = "list-type=2&max-keys=10"
        headers = _sigv4_headers("GET", host, region, "s3", "/", qs, ak, sk,
                                 os.environ.get("SZL_AWS_SESSION_TOKEN"))
        url = f"https://{host}/?{qs}"
        st, body = http_text(url, headers=headers)
        if st == 200 and isinstance(body, str):
            import re
            keys = re.findall(r"<Key>(.*?)</Key>", body)
            sizes = re.findall(r"<Size>(.*?)</Size>", body)
            out = [{"Key": k, "Size": (sizes[i] if i < len(sizes) else None)}
                   for i, k in enumerate(keys[:10])]
            return Records(connector_id=self.id, category=self.category, state=State.CONNECTED,
                           records=out, source=f"S3 ListObjectsV2 {bucket}", live=True,
                           note=f"live · {len(keys)} objects", schema_preview=self.schema_preview)
        return Records(connector_id=self.id, category=self.category, state=State.ERROR,
                       records=[], source=self.provider_base, live=False,
                       note=f"credentials present but S3 HTTP {st}", schema_preview=self.schema_preview)


# ── Google Cloud Storage (oauth2 access token; free 5GB tier) ─────────────────
@register
class GcsConnector(ReadyConnector):
    id = "gcs"
    label = "Google Cloud Storage"
    category = "storage"
    auth_kind = "oauth2"
    free_tier = True
    env_vars = ["SZL_GCS_BUCKET", "SZL_GCS_ACCESS_TOKEN"]
    _primary_secret = "SZL_GCS_ACCESS_TOKEN"
    provider_base = "https://storage.googleapis.com/storage/v1"
    docs_url = "https://cloud.google.com/storage/docs/json_api/v1/objects/list"
    schema_preview = ["name", "size", "contentType", "updated"]
    _record_path = "items"

    def _auth_header(self):
        tok = os.environ.get("SZL_GCS_ACCESS_TOKEN")
        return {"Authorization": f"Bearer {tok}"} if tok else {}

    def read(self, query=None):
        if self._primary_missing():
            return self._ready_records(
                "provide credentials to activate — set SZL_GCS_BUCKET, "
                "SZL_GCS_ACCESS_TOKEN. Lists objects via storage.objects.list.")
        bucket = os.environ.get("SZL_GCS_BUCKET", "")
        url = f"{self.provider_base}/b/{bucket}/o?maxResults=10"
        st, raw = http_json(url, headers={"Accept": "application/json", **self._auth_header()})
        if st == 200 and isinstance(raw, dict):
            rows = raw.get("items", []) or []
            out = [{k: r.get(k) for k in self.schema_preview if k in r} for r in rows[:10]]
            return Records(connector_id=self.id, category=self.category, state=State.CONNECTED,
                           records=out, source=f"GCS objects.list {bucket}", live=True,
                           note=f"live · {len(rows)} objects", schema_preview=self.schema_preview)
        return Records(connector_id=self.id, category=self.category, state=State.ERROR,
                       records=[], source=self.provider_base, live=False,
                       note=f"credentials present but GCS HTTP {st}", schema_preview=self.schema_preview)


# ── Azure Blob Storage (SAS token; free tier) ─────────────────────────────────
@register
class AzureBlobConnector(ReadyConnector):
    id = "azure_blob"
    label = "Azure Blob Storage"
    category = "storage"
    auth_kind = "api_key"  # SAS token
    free_tier = True
    env_vars = ["SZL_AZURE_BLOB_ACCOUNT", "SZL_AZURE_BLOB_CONTAINER", "SZL_AZURE_BLOB_SAS"]
    _primary_secret = "SZL_AZURE_BLOB_SAS"
    provider_base = "https://{account}.blob.core.windows.net"
    docs_url = "https://learn.microsoft.com/rest/api/storageservices/list-blobs"
    schema_preview = ["Name", "Properties.Content-Length", "Properties.Last-Modified"]

    def read(self, query=None):
        acct = os.environ.get("SZL_AZURE_BLOB_ACCOUNT", "")
        cont = os.environ.get("SZL_AZURE_BLOB_CONTAINER", "")
        sas = os.environ.get("SZL_AZURE_BLOB_SAS", "")
        if not (acct and cont and sas):
            return self._ready_records(
                "provide credentials to activate — set SZL_AZURE_BLOB_ACCOUNT, "
                "SZL_AZURE_BLOB_CONTAINER, SZL_AZURE_BLOB_SAS. Lists blobs (restype=container&comp=list).")
        sep = "&" if sas.startswith("?") else "?"
        sas2 = sas.lstrip("?")
        url = f"https://{acct}.blob.core.windows.net/{cont}?restype=container&comp=list&maxresults=10&{sas2}"
        st, body = http_text(url)
        if st == 200 and isinstance(body, str):
            import re
            names = re.findall(r"<Name>(.*?)</Name>", body)
            out = [{"Name": n} for n in names[:10]]
            return Records(connector_id=self.id, category=self.category, state=State.CONNECTED,
                           records=out, source=f"Azure Blob list {cont}", live=True,
                           note=f"live · {len(names)} blobs", schema_preview=self.schema_preview)
        return Records(connector_id=self.id, category=self.category, state=State.ERROR,
                       records=[], source=self.provider_base, live=False,
                       note=f"credentials present but Azure Blob HTTP {st}", schema_preview=self.schema_preview)


__all__ = ["S3Connector", "GcsConnector", "AzureBlobConnector"]
