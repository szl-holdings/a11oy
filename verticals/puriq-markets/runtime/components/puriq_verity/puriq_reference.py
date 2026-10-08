"""Offline reference-price research. No network, orders, or production claims.

The group labels are supplied assumptions, not measured source independence.
The receipt is a deterministic byte commitment, not a signature or truth proof.
"""
from collections import Counter
from decimal import Context, Decimal, InvalidOperation, ROUND_HALF_EVEN, localcontext
import hashlib
import json
import re


MAX_ROWS = 256
MAX_TEXT = 128
MAX_FIELDS = 16
MAX_DEPTH = 3
MAX_RECORD_BYTES = 8192
MAX_TIMESTAMP = Decimal("253402300799")
DECIMAL_CONTEXT = Context(prec=80, rounding=ROUND_HALF_EVEN)
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,63}\Z")
SYMBOL = re.compile(r"[A-Z0-9][A-Z0-9._/-]{0,31}\Z")
PRICE_TEXT = re.compile(r"[0-9]{1,20}(?:\.[0-9]{1,18})?\Z")
FIELDS = frozenset({"venue", "symbol", "quote", "price", "observed_at", "group"})


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False)


def _text(value):
    """Canonical decimal text, without depending on ambient decimal context."""
    result = format(value, "f")
    if "." in result:
        result = result.rstrip("0").rstrip(".")
    return "0" if result in ("", "-0") else result


def _capture(value, depth=0):
    """Bounded typed input snapshot, including rejected NaN and malformed rows.

    Invalid outer envelopes/types raise ValueError before any estimate is made.
    Types are tagged to avoid collisions between a real mapping and a float tag.
    """
    if depth > MAX_DEPTH:
        raise ValueError("INPUT_NESTING_LIMIT")
    if value is None:
        return ["null", None]
    if type(value) is bool:
        return ["bool", value]
    if type(value) is str:
        if len(value) > MAX_TEXT:
            raise ValueError("INPUT_TEXT_LIMIT")
        return ["str", value]
    if type(value) in (int, float, Decimal):
        if type(value) is int and value.bit_length() > 256:
            raise ValueError("INPUT_NUMBER_LIMIT")
        text = str(value)
        if len(text) > MAX_TEXT:
            raise ValueError("INPUT_NUMBER_LIMIT")
        return [type(value).__name__, text]
    if type(value) is dict:
        if len(value) > MAX_FIELDS:
            raise ValueError("INPUT_FIELD_LIMIT")
        if any(type(key) is not str or len(key) > MAX_TEXT for key in value):
            raise ValueError("INVALID_INPUT_KEY")
        return ["dict", [[key, _capture(value[key], depth + 1)]
                         for key in sorted(value)]]
    if type(value) in (list, tuple):
        if len(value) > MAX_FIELDS:
            raise ValueError("INPUT_FIELD_LIMIT")
        return [type(value).__name__, [_capture(item, depth + 1) for item in value]]
    raise ValueError("UNSUPPORTED_INPUT_TYPE")


def _seconds(value):
    if type(value) not in (int, float, str, Decimal):
        raise ValueError("INVALID_SECONDS")
    if type(value) is int and value.bit_length() > 64:
        raise ValueError("INVALID_SECONDS")
    text = str(value)
    if len(text) > 64:
        raise ValueError("INVALID_SECONDS")
    try:
        result = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError("INVALID_SECONDS") from exc
    if (not result.is_finite() or result < 0 or result > MAX_TIMESTAMP
            or len(result.as_tuple().digits) > 30
            or result.as_tuple().exponent < -18):
        raise ValueError("INVALID_SECONDS")
    return result


def _identifier(value):
    return value.lower() if type(value) is str and IDENTIFIER.fullmatch(value) else None


def _median(values):
    ordered = sorted(values)
    middle = len(ordered) // 2
    return (ordered[middle] if len(ordered) % 2
            else (ordered[middle - 1] + ordered[middle]) / Decimal(2))


def estimate_reference(rows, *, symbol, now, max_age_seconds=10, min_groups=3):
    """Return an offline modeled estimate and complete replayable receipt.

    `rows` must be a bounded list/tuple of flat observation dictionaries.
    USD quote and decimal-text price are mandatory. Future/stale/malformed rows
    are rejected; all occurrences of duplicate venues are rejected. A missing
    group assigns that venue its own group; supplied groups are case-insensitive.
    A rejected row cannot contribute to either estimate. Invalid parameters or
    oversized/unrepresentable input envelopes raise ValueError, never a price.

    Input row order does not affect the result or receipt. The receipt embeds
    the original typed inputs, accepted normalization, rejection reasons, recipe,
    clock and outputs. The SHA-256 can be recomputed over the `receipt` using
    json.dumps(..., sort_keys=True, separators=(',', ':'), ensure_ascii=True,
    allow_nan=False). This is project-specific encoding, not RFC 8785.
    """
    if type(rows) not in (list, tuple) or len(rows) > MAX_ROWS:
        raise ValueError("INPUT_ROW_LIMIT_OR_TYPE")
    if type(symbol) is not str or not SYMBOL.fullmatch(symbol):
        raise ValueError("INVALID_SYMBOL")
    if type(min_groups) is not int or not 3 <= min_groups <= MAX_ROWS:
        raise ValueError("MIN_GROUPS_MUST_BE_3_TO_256")
    with localcontext(DECIMAL_CONTEXT):
        clock = _seconds(now)
        max_age = _seconds(max_age_seconds)
        if not Decimal(0) < max_age <= Decimal(86400):
            raise ValueError("INVALID_MAX_AGE")
        snapshots = []
        for row in rows:
            snapshot = _capture(row)
            if len(_json(snapshot).encode("ascii")) > MAX_RECORD_BYTES:
                raise ValueError("INPUT_RECORD_SIZE_LIMIT")
            snapshots.append(snapshot)
        venues = Counter(_identifier(row.get("venue")) for row in rows
                         if type(row) is dict and _identifier(row.get("venue")))
        accepted, rejected = [], []
        for row, snapshot in zip(rows, snapshots):
            reasons = []
            if type(row) is not dict:
                rejected.append({"input": snapshot, "reasons": ["ROW_NOT_OBJECT"]})
                continue
            if set(row) - FIELDS:
                reasons.append("UNKNOWN_FIELDS")
            venue = _identifier(row.get("venue"))
            if venue is None:
                reasons.append("INVALID_VENUE")
            elif venues[venue] > 1:
                reasons.append("DUPLICATE_VENUE")
            if row.get("symbol") != symbol:
                reasons.append("SYMBOL_MISMATCH")
            if "quote" not in row:
                reasons.append("MISSING_QUOTE")
            elif row["quote"] != "USD":
                reasons.append("QUOTE_NOT_USD")
            price_value = row.get("price")
            price = None
            if type(price_value) is str and PRICE_TEXT.fullmatch(price_value):
                price = Decimal(price_value)
            if price is None or not price.is_finite() or price <= 0:
                reasons.append("INVALID_PRICE")
            try:
                observed = _seconds(row.get("observed_at"))
            except ValueError:
                observed = None
                reasons.append("INVALID_OBSERVED_AT")
            if observed is not None:
                if observed > clock:
                    reasons.append("FUTURE_OBSERVATION")
                elif clock - observed > max_age:
                    reasons.append("STALE_OBSERVATION")
            if "group" in row:
                group_name = _identifier(row["group"])
                group = "declared:" + group_name if group_name else None
                if group is None:
                    reasons.append("INVALID_GROUP")
            else:
                group = "venue:" + venue if venue else None
            if reasons:
                rejected.append({"input": snapshot, "reasons": sorted(reasons)})
                continue
            accepted.append({"venue": venue, "symbol": symbol, "quote": "USD",
                             "price": _text(price), "observed_at": _text(observed),
                             "age_seconds": _text(clock - observed), "group": group})
        accepted.sort(key=_json)
        rejected.sort(key=_json)
        groups = {}
        for row in accepted:
            groups.setdefault(row["group"], []).append(Decimal(row["price"]))
        group_medians = [{"group": group, "venue_count": len(prices),
                          "median_price_usd": _text(_median(prices))}
                         for group, prices in sorted(groups.items())]
        baseline = _median([Decimal(row["price"]) for row in accepted]) if accepted else None
        group_prices = [Decimal(row["median_price_usd"]) for row in group_medians]
        group_center = _median(group_prices) if group_prices else None
        sufficient = len(groups) >= min_groups
        dispersion = (_median([abs(price - group_center) for price in group_prices])
                      / group_center * Decimal(10000)) if sufficient else None
        outputs = {
            "truth_label": "MODELED", "state": "MODELED" if sufficient else "ABSTAIN",
            "reason": None if sufficient else "INSUFFICIENT_GROUPS",
            "symbol": symbol, "quote": "USD", "trading_enabled": False,
            "reference_price_usd": _text(group_center) if sufficient else None,
            "venue_median_usd": _text(baseline) if baseline is not None else None,
            "group_mad_bps": _text(dispersion) if dispersion is not None else None,
            "effective_groups": len(groups), "accepted_venues": len(accepted),
            "rejected_observations": len(rejected), "group_medians": group_medians,
            "group_independence_verified": False,
            "digest_is_signature": False, "digest_proves_market_truth": False,
        }
        recipe = {
            "id": "puriq-reference-research-v1", "truth_label": "MODELED",
            "algorithm": "median of within-declared-group equal-venue medians",
            "baseline": "equal-venue median of accepted observations",
            "even_median": "arithmetic midpoint", "quote": "USD",
            "age_rule": "0 <= now - observed_at <= max_age_seconds",
            "max_age_seconds": _text(max_age), "min_groups": min_groups,
            "duplicate_policy": "reject all rows sharing case-normalized venue",
            "missing_group_policy": "distinct venue-prefixed group",
            "identifier_normalization": "ASCII identifiers, lowercase venue and group",
            "price_format": "positive plain decimal text: <=20 integer and <=18 fractional digits",
            "dispersion": "10000 * median(abs(group_median - reference)) / reference",
            "dispersion_interpretation": "descriptive MAD, not confidence interval or error bound",
            "decimal_precision": 80, "decimal_rounding": "ROUND_HALF_EVEN",
            "receipt_encoding": "typed-input JSON; sorted keys; ASCII; compact; no NaN numbers; v1",
            "bounds": {"rows": MAX_ROWS, "text": MAX_TEXT, "fields": MAX_FIELDS,
                       "nesting": MAX_DEPTH, "record_bytes": MAX_RECORD_BYTES,
                       "maximum_age_seconds": 86400,
                       "timestamp_max": _text(MAX_TIMESTAMP), "timestamp_digits": 30,
                       "timestamp_fractional_digits": 18},
        }
        receipt = {"recipe": recipe, "clock_unix_seconds": _text(clock),
                   "symbol": symbol, "input_rows": sorted(snapshots, key=_json),
                   "accepted": accepted, "rejected": rejected, "outputs": outputs}
        return {**outputs, "receipt": receipt,
                "receipt_sha256": hashlib.sha256(_json(receipt).encode("ascii")).hexdigest()}


def synthetic_demo():
    """Return two deterministic synthetic comparisons, never market evidence."""
    def observation(venue, price, group=None):
        row = {"venue": venue, "symbol": "BTC-USD", "quote": "USD",
               "price": price, "observed_at": 1000}
        if group is not None:
            row["group"] = group
        return row
    cases = {
        "single_outlier": [observation("a", "99"), observation("b", "100"),
                           observation("c", "101"), observation("d", "1000")],
        "correlated_venue_cluster": [observation("a", "99"), observation("b", "100"),
                                     observation("c", "101")]
        + [observation("cluster-" + str(i), "1000", "shared-source") for i in range(7)],
    }
    return {"truth_label": "MODELED", "data_kind": "SYNTHETIC",
            "claim": "illustration only; no statistical performance or novelty claim",
            "cases": {name: estimate_reference(rows, symbol="BTC-USD", now=1000)
                      for name, rows in cases.items()}}


if __name__ == "__main__":
    print(json.dumps(synthetic_demo(), sort_keys=True, indent=2, allow_nan=False))
