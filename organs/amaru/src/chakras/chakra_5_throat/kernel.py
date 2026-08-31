"""Chakra 5 — CH'ULLA-RUWAY kernel. ≤10 lines of functional logic."""
import hashlib
import json


def continuum_hash(state, proposal, critic):
    blob = json.dumps({"s": state, "p": proposal, "c": critic}, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()

def ruway(state, proposal, gate_pass, yawar_bus):
    if not gate_pass:
        return state, yawar_bus
    receipt = continuum_hash(state, proposal, gate_pass)
    new_state = {**state, **proposal, "__receipt": receipt}
    return new_state, yawar_bus + [receipt]
