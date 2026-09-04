#!/usr/bin/env python3
"""Terminal payload for Grok. Public facts only. No private PEM."""

from __future__ import annotations

PAYLOAD = {
    "product_host": "https://a-11-oy.com",
    "proof_host": "https://a11oy.net",
    "never": "a11oy.com",
    "source": "https://github.com/szl-holdings/a11oy",
    "runtime_twin": "https://szlholdings-a11oy.hf.space",
    "lyte_bind": "https://github.com/szl-holdings/lyte-lattice",
    "bind": "BIND_AS_A11OY_PACKAGE",
    "doctrine": "v11 LOCKED",
    "kernel": "c7c0ba17",
    "lambda": "Conjecture 1",
    "signer": "ABSENT",
    "proven_trust": False,
    "joule": "UNAVAILABLE",
    "occupancy": "UNAVAILABLE",
    "halt_drone": "BLOCKED",
    "hub_running": "UNAVAILABLE",
}


def as_prompt() -> str:
    lines = [
        "Finish a11oy Command Center. Fail closed.",
        f"Product {PAYLOAD['product_host']}. Proof {PAYLOAD['proof_host']}. Never {PAYLOAD['never']}.",
        f"Source {PAYLOAD['source']}. Twin {PAYLOAD['runtime_twin']}.",
        f"LYTE {PAYLOAD['bind']} — not a flagship.",
        f"Doctrine {PAYLOAD['doctrine']} kernel {PAYLOAD['kernel']}. Λ {PAYLOAD['lambda']}.",
        f"Signer {PAYLOAD['signer']}. proven_trust {PAYLOAD['proven_trust']}.",
        f"Joule {PAYLOAD['joule']}. Occupancy {PAYLOAD['occupancy']}. halt_drone {PAYLOAD['halt_drone']}.",
        "Do not mint a replacement org identity. Do not invent Hub RUNNING.",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    print(as_prompt())
