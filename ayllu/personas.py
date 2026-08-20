"""ayllu.personas — the a11oy-native roster, learned from the AlloyScape tribe.

Each persona is an a11oy archetype (see INGEST.md for the tribe→a11oy mapping). The
soul prose lives in ayllu/souls/<name>.soul.md and is loaded at runtime, mirroring the
tribe's souls/<name>.system.md convention — but authored fresh in a11oy's voice, tied
to a11oy's own domains, and carrying a11oy's bounded-autonomy law.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

_SOULS_DIR = Path(__file__).resolve().parent / "souls"


@dataclass(frozen=True)
class Persona:
    name: str
    quechua: str
    archetype: str
    domain: str
    soul_file: str
    default_difficulty: float = 0.5
    # a11oy law: every persona requires attestation for state-changing actions.
    approval_required: bool = True
    # "propose" (advise + stage) or "act-nonstate" (may run read-only tools);
    # NEVER unbounded — the tribe's "always execute" level is intentionally absent.
    autonomy_level: str = "propose"

    def soul_path(self) -> Path:
        return _SOULS_DIR / self.soul_file

    def system_prompt(self) -> str:
        p = self.soul_path()
        if p.exists():
            prompt = p.read_text(encoding="utf-8")
        else:
            prompt = f"[soul file missing for {self.name}: {p} — honest empty persona]"
        shared = _SOULS_DIR / "_shared_knowledge.md"
        if shared.exists():
            # Knowledge INSTILLED (curated, cited text appended to the system
            # prompt) — never "training"; no weights are changed anywhere.
            prompt += "\n\n" + shared.read_text(encoding="utf-8")
        return prompt

    def metadata(self) -> dict:
        return {
            "name": self.name,
            "quechua": self.quechua,
            "archetype": self.archetype,
            "domain": self.domain,
            "autonomy_level": self.autonomy_level,
            "approval_required": self.approval_required,
            "default_difficulty": self.default_difficulty,
            "soul_present": self.soul_path().exists(),
            "knowledge_instilled": (_SOULS_DIR / "_shared_knowledge.md").exists(),
        }


ROSTER: list[Persona] = [
    Persona("Amaru", "serpent / vision", "architect",
            "whole-system architecture, org-Λ", "amaru.soul.md", 0.7),
    Persona("Ruwaq", "maker", "builder",
            "code engine, factory", "ruwaq.soul.md", 0.5),
    Persona("Yupaq", "one who counts", "mathematician",
            "formulas, Lean proofs, Λ rigor", "yupaq.soul.md", 0.8),
    Persona("Qhaway", "one who sees", "simulator",
            "simulation, PINN, resilience, seismic", "qhaway.soul.md", 0.7),
    Persona("Maskaq", "seeker", "researcher",
            "evidence-research, org-RAG, citation", "maskaq.soul.md", 0.6),
    Persona("Hampiq", "healer", "reliability",
            "organ-health, observability, remediation", "hampiq.soul.md", 0.5),
    Persona("Yanapaq", "helper", "ops",
            "readiness, incident/ops support", "yanapaq.soul.md", 0.4),
    Persona("Chaka", "bridge", "integrator",
            "MCP, compliance-crosswalk, integration", "chaka.soul.md", 0.5),
    Persona("Kamachiq", "organizer", "orchestrator",
            "orchestration, planning, routing", "kamachiq.soul.md", 0.6),
    Persona("Qhatuq", "trader", "markets",
            "markets, risk-first, revenue model", "qhatuq.soul.md", 0.6),
    Persona("Willakuq", "chronicler", "memory",
            "khipu chain, provenance, org memory", "willakuq.soul.md", 0.5),
]

_BY_NAME = {p.name.lower(): p for p in ROSTER}


def get_persona(name: str) -> Optional[Persona]:
    return _BY_NAME.get((name or "").strip().lower())


def load_soul(name: str) -> Optional[str]:
    p = get_persona(name)
    return p.system_prompt() if p else None
