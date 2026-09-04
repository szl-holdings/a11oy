from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    source = target.read_text(encoding="utf-8")
    count = source.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one exact anchor, found {count}: {old!r}")
    target.write_text(source.replace(old, new, 1), encoding="utf-8", newline="\n")


replace_once(
    "a11oy_vertical_feeds.py",
    '        return JSONResponse({"vertical": "realestate", "hpd_litigations": hpd,\n'
    '                             "dob_violations": dob, "rates": rates,\n'
    '                             "sources_cited": cited_leaders("realestate"), "doctrine": DOCTRINE})\n',
    '        return JSONResponse({"vertical": "realestate",\n'
    '                             "hpd_litigations": _readiness_public_source(hpd),\n'
    '                             "dob_violations": _readiness_public_source(dob),\n'
    '                             "rates": rates,\n'
    '                             "sources_cited": cited_leaders("realestate"), "doctrine": DOCTRINE})\n',
)

helper = '''

_READINESS_PUBLIC_FRESHNESS = frozenset({"live", "cached"})


def _readiness_public_source(entry: Any) -> Any:
    """Publish one DEV-A source wrapper under the readiness truth contract.

    No-value failures remain explicit ``UNAVAILABLE`` evidence and carry the
    instant at which the failure was observed. Last-good values may be served as
    ``cached`` only when their original observation timestamp is retained.
    """
    normalized = entry
    if _HAS_VF and hasattr(_vf, "_readiness_public_source"):
        try:
            normalized = _vf._readiness_public_source(entry)
        except Exception:
            normalized = entry
    if not isinstance(normalized, dict):
        return normalized
    freshness = normalized.get("freshness")
    if not isinstance(freshness, dict):
        return normalized

    out = dict(normalized)
    public = dict(freshness)
    status = str(public.get("status") or "").strip().lower()
    if out.get("value") is None:
        public["status"] = "UNAVAILABLE"
        if public.get("fetched_at") is None:
            public["fetched_at"] = datetime.now(timezone.utc).isoformat()
        if not str(public.get("error") or "").strip():
            public["error"] = "source returned no observed value"
    elif status not in _READINESS_PUBLIC_FRESHNESS:
        if public.get("fetched_at") is None:
            age_s = public.get("age_s")
            if (
                isinstance(age_s, (int, float))
                and not isinstance(age_s, bool)
                and math.isfinite(float(age_s))
            ):
                observed = time.time() - max(0.0, float(age_s))
                public["fetched_at"] = datetime.fromtimestamp(
                    observed, tz=timezone.utc
                ).isoformat()
        if public.get("fetched_at") is not None:
            public["status"] = "cached"
    out["freshness"] = public
    return out
'''

replace_once(
    "a11oy_deva_feeds.py",
    '''    return result


# ===========================================================================
# GOVERNED TURN — delegate to the proven machinery in a11oy_vertical_feeds.
# ===========================================================================
''',
    '''    return result
'''
    + helper
    + '''

# ===========================================================================
# GOVERNED TURN — delegate to the proven machinery in a11oy_vertical_feeds.
# ===========================================================================
''',
)
replace_once(
    "a11oy_deva_feeds.py",
    '        return JSONResponse({"tab": "pulse", "hpd": hpd, "dob": dob, "rates": rates, "doctrine": DOCTRINE})\n',
    '        return JSONResponse({"tab": "pulse",\n'
    '                             "hpd": _readiness_public_source(hpd),\n'
    '                             "dob": _readiness_public_source(dob),\n'
    '                             "rates": rates, "doctrine": DOCTRINE})\n',
)
replace_once(
    "a11oy_deva_feeds.py",
    '        return JSONResponse({"tab": "distress", "hpd": hpd, "doctrine": DOCTRINE})\n',
    '        return JSONResponse({"tab": "distress",\n'
    '                             "hpd": _readiness_public_source(hpd),\n'
    '                             "doctrine": DOCTRINE})\n',
)

Path("tests/test_realestate_readiness_truth_contract.py").write_text(
    '''# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import a11oy_deva_feeds as deva
import a11oy_vertical_feeds as vertical


def _assert_timestamp(value: object) -> None:
    assert value is not None
    if isinstance(value, (int, float)):
        assert float(value) > 0
        return
    assert isinstance(value, str) and value.strip()
    datetime.fromisoformat(value.replace("Z", "+00:00"))


def test_vertical_no_value_failure_is_canonical_unavailable() -> None:
    raw = {
        "value": None,
        "freshness": {
            "status": "unavailable",
            "fetched_at": 1788559200.0,
            "error": "TimeoutError: bounded upstream timeout",
        },
    }
    result = vertical._readiness_public_source(raw)
    assert result["value"] is None
    assert result["freshness"]["status"] == "UNAVAILABLE"
    assert result["freshness"]["fetched_at"] == 1788559200.0
    assert result["freshness"]["error"] == raw["freshness"]["error"]


def test_deva_cold_failure_adds_observation_clock_without_inventing_data() -> None:
    raw = {
        "value": None,
        "freshness": {
            "status": "unavailable",
            "error": "ReadTimeout: upstream did not answer",
        },
    }
    result = deva._readiness_public_source(raw)
    assert result["value"] is None
    assert result["freshness"]["status"] == "UNAVAILABLE"
    _assert_timestamp(result["freshness"]["fetched_at"])
    assert result["freshness"]["error"] == raw["freshness"]["error"]


def test_deva_last_good_failure_is_cached_with_original_clock() -> None:
    observed_at = "2026-09-04T21:00:00+00:00"
    raw = {
        "value": {"items": [{"id": "observed"}]},
        "freshness": {
            "status": "stale",
            "age_s": 42.0,
            "fetched_at": observed_at,
            "error": "ReadTimeout: refresh failed",
        },
    }
    result = deva._readiness_public_source(raw)
    assert result["value"] == raw["value"]
    assert result["freshness"]["status"] == "cached"
    assert result["freshness"]["fetched_at"] == observed_at
    assert result["freshness"]["error"] == raw["freshness"]["error"]


def test_all_three_realestate_readiness_routes_apply_the_public_wrapper() -> None:
    vertical_source = Path("a11oy_vertical_feeds.py").read_text(encoding="utf-8")
    deva_source = Path("a11oy_deva_feeds.py").read_text(encoding="utf-8")
    assert '"hpd_litigations": _readiness_public_source(hpd)' in vertical_source
    assert '"dob_violations": _readiness_public_source(dob)' in vertical_source
    assert deva_source.count('"hpd": _readiness_public_source(hpd)') == 2
    assert '"dob": _readiness_public_source(dob)' in deva_source
''',
    encoding="utf-8",
    newline="\n",
)
