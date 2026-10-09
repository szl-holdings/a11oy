"""Float64 Liu Hui recurrence against an 80-digit rationalized reference.

The bound is agreement with that reference. It is not a proof that the
real sequence converges to pi, and it does not authorize a gate decision
beyond the configured residual.
"""

from __future__ import annotations

import sys
import types
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import starlette.requests  # noqa: F401
except ImportError:
    starlette = types.ModuleType("starlette")
    requests = types.ModuleType("starlette.requests")
    requests.Request = object  # type: ignore[attr-defined]
    starlette.requests = requests  # type: ignore[attr-defined]
    sys.modules.setdefault("starlette", starlette)
    sys.modules.setdefault("starlette.requests", requests)

from a11oy_v4_formulas import GateError, eval_liu_hui_pi

REFERENCES = {
    0: Decimal("3"),
    4: Decimal("3.1410319508905096381113529264596601070364"),
    12: Decimal("3.1415926450336908966721415089192384127226"),
    24: Decimal("3.1415926535897927284792022222880574573760"),
    27: Decimal("3.1415926535897932304941521151390111674024"),
    50: Decimal("3.1415926535897932384626433832793896451255"),
}
BOUND = Decimal("1e-15")


def _fail(message: str) -> None:
    raise AssertionError(message)


def check_all() -> None:
    for k, ref in REFERENCES.items():
        got = eval_liu_hui_pi({"k": k}, {"threshold": 1})
        estimate = Decimal(got["piEstimate"])
        if got["piEstimate"] == 0.0:
            _fail(f"collapsed at k={k}")
        if abs(estimate - ref) >= BOUND:
            _fail(f"reference miss at k={k}: {estimate} vs {ref}")
        if "does not identify it with pi" not in got["rationale"]:
            _fail("rationale dropped the limit-scope limit")
        if got["leanTheorem"] != "sideSquared_bounds":
            _fail("lean theorem anchor changed")
        if got["advisory"] is not True:
            _fail("advisory flag must stay true")

    early = eval_liu_hui_pi({"k": 12}, {"threshold": 1e-12})
    if early["allow"] is not False or early["absError"] <= 1e-12:
        _fail("k=12 must still miss a 1e-12 residual")

    late = eval_liu_hui_pi({"k": 27}, {"threshold": 1e-12})
    if late["allow"] is not True or late["absError"] >= 1e-12 or late["piEstimate"] == 0.0:
        _fail("k=27 rationalized estimate must meet 1e-12")

    for bad in (True, "27", 27.0, None, -1, 51):
        try:
            eval_liu_hui_pi({"k": bad}, {"threshold": 1e-4})
        except GateError:
            continue
        _fail(f"accepted malformed k={bad!r}")


def test_liu_hui_pi_matches_rationalized_reference() -> None:
    check_all()


if __name__ == "__main__":
    check_all()
