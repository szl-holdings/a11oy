from __future__ import annotations

import json
import math
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Mapping

from ..canonical import canonical_json_bytes
from ..errors import AuthorizationError, ValidationError

_POLICY_SEGMENT = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        raise urllib.error.HTTPError(req.full_url, code, "redirect refused", headers, fp)


class OPAClient:
    """Narrow fail-closed OPA data API client.

    Redirects are refused, response size is bounded, and policy output must
    contain an explicit boolean ``allow``. OPA remains an external policy input;
    the Council Kernel is still the final authority.
    """

    def __init__(
        self,
        base_url: str,
        policy_path: str,
        *,
        timeout: float = 3.0,
        max_response_bytes: int = 256 * 1024,
    ) -> None:
        parsed = urllib.parse.urlsplit(base_url)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValidationError("OPA base_url must be a canonical HTTP(S) origin/path")
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(float(timeout)) or not 0.1 <= float(timeout) <= 30:
            raise ValidationError("OPA timeout must be finite and between 0.1 and 30 seconds")
        if isinstance(max_response_bytes, bool) or not isinstance(max_response_bytes, int) or not 1024 <= max_response_bytes <= 8 * 1024 * 1024:
            raise ValidationError("OPA max_response_bytes must be 1 KiB..8 MiB")
        segments = [item for item in policy_path.strip("/").split("/") if item]
        if not segments or any(not _POLICY_SEGMENT.fullmatch(item) for item in segments):
            raise ValidationError("OPA policy_path contains invalid segments")
        base = urllib.parse.urlunsplit(
            (parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", "")
        )
        self.url = base + "/v1/data/" + "/".join(segments)
        self.timeout = float(timeout)
        self.max_response_bytes = max_response_bytes
        self._opener = urllib.request.build_opener(_NoRedirect())

    def evaluate(self, input_value: Mapping[str, Any]) -> Mapping[str, Any]:
        request = urllib.request.Request(
            self.url,
            data=canonical_json_bytes({"input": dict(input_value)}),
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "szl-council-kernel/0.5.0rc1",
            },
        )
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                if getattr(response, "status", 200) != 200:
                    raise AuthorizationError("OPA policy endpoint returned a non-200 response")
                content_type = response.headers.get_content_type()
                if content_type not in {"application/json", "application/problem+json"}:
                    raise AuthorizationError("OPA policy endpoint returned a non-JSON response")
                raw = response.read(self.max_response_bytes + 1)
                if len(raw) > self.max_response_bytes:
                    raise AuthorizationError("OPA policy response exceeds configured limit")
                payload = json.loads(raw.decode("utf-8"))
        except AuthorizationError:
            raise
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AuthorizationError("OPA policy decision unavailable or invalid") from exc
        result = payload.get("result") if isinstance(payload, Mapping) else None
        if not isinstance(result, Mapping) or not isinstance(result.get("allow"), bool):
            raise AuthorizationError("OPA policy result lacks an explicit allow boolean")
        if set(result) - {"allow", "reason_codes", "obligations"}:
            raise AuthorizationError("OPA policy result contains unsupported authority fields")
        return dict(result)
