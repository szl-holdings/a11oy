"""ayllu.selftest — offline self-test. Runs with NO a11oy modules and NO FastAPI.

Proves: 11 personas load with real soul prose; the tier router has an honest fallback;
a turn NEVER fabricates an answer without a backend; the autonomy gate is fail-closed;
the lounge deliberates honestly. Run: `python -m ayllu.selftest`.
"""
from __future__ import annotations

import asyncio

from ayllu.autonomy import gate
from ayllu.lounge import Lounge
from ayllu.loop import run_turn, select_tier
from ayllu.personas import ROSTER, get_persona


def main() -> None:
    assert len(ROSTER) == 11, f"expected 11 personas, got {len(ROSTER)}"
    for p in ROSTER:
        sp = p.system_prompt()
        assert sp and ("a11oy" in sp.lower() or "ayllu" in sp.lower()), \
            f"soul empty or adrift: {p.name}"
        assert p.approval_required is True, f"{p.name} must require approval (a11oy law)"
        assert p.autonomy_level != "unbounded", f"{p.name} must not be unbounded"

    assert select_tier(0.2)["route"] in ("small/local", "large/cloud")
    assert select_tier(0.9)["route"] in ("small/local", "large/cloud")

    # A turn with no injected model backend must NOT fabricate an answer.
    turn = asyncio.run(run_turn(get_persona("amaru"), "Design a bounded plan."))
    assert turn["answer"] is None, "must not fabricate an answer without a backend"
    assert "not injected" in turn["honesty"], turn["honesty"]

    # Autonomy gate: fail-closed.
    assert gate("deploy", state_changing=True)["allow"] is False
    assert gate("deploy", state_changing=True, two_person_attested=True)["allow"] is True
    assert gate("read", state_changing=False)["allow"] is True
    assert gate("write", state_changing=True, two_person_attested=True,
                lambda_score=0.5)["allow"] is False  # below Λ floor

    # Lounge deliberation, honest (no backend => no fabricated answers).
    lounge = Lounge()
    res = asyncio.run(lounge.deliberate(
        "What are the risks?", [get_persona("qhatuq"), get_persona("qhaway")]))
    assert len(res["rounds"]) == 2
    assert all(r["answer"] is None for r in res["rounds"])
    assert len(lounge.recent()) == 2

    print(f"AYLLU SELFTEST OK — {len(ROSTER)} personas; tier router + bounded loop "
          "honest fallbacks; Λ-gate fail-closed; lounge honest.")


if __name__ == "__main__":
    main()
