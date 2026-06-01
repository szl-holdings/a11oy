"""Default reference handlers for OrganAgents.

A genome's [boot] handler points at "module:callable". For organs whose real runtime code
lives elsewhere (amaru/, rosie/, sentra/ repos), the genome can point at one of these
generic reference handlers so the agent has a working, gated step() out of the box.

Each handler receives the bound OrganAgent and returns a dict summary of what it did. They
only ever write receipt KINDS the genome authorizes (the OrganAgent.write() gate enforces
this), so a handler cannot exceed its declared role.
"""

from __future__ import annotations

import time


def echo(agent, message: str = "alive") -> dict:
    """Write a single heartbeat receipt of the organ's first authorized write-kind."""
    kind = agent.genome.writes[0]
    cid = agent.write(kind, {"message": message, "ts": time.time()})
    return {"organ": agent.genome.name, "wrote_kind": kind, "cid": cid}


def reconcile(agent) -> dict:
    """No-op reconcile: report current authorization surface. Writes nothing."""
    return {
        "organ": agent.genome.name,
        "reads": agent.genome.reads,
        "writes": agent.genome.writes,
        "reconciled": True,
    }
