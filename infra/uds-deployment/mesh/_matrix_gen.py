# Copyright 2026 SZL Holdings
# SPDX-License-Identifier: Apache-2.0
#
# Authorization-matrix generator for the v0.4.0 mesh interconnect design.
# This script is a DESIGN ARTIFACT, not a runtime component. It deterministically
# derives the 6x6 module-to-module authorization matrix from the founder's
# hierarchy rules (PhD Systems verdict, 2026-05-30) and prints:
#   1. a Markdown table (caller = row, callee = column)
#   2. a flat list of the 36 ordered pair states for the design doc
#
# It does NOT touch a cluster and performs no network I/O.

MODULES = ["rosie", "a11oy", "amaru", "sentra", "vessels", "receipts"]

# Canonical namespace + service-account + DNS for each module.
NS = {
    "rosie":    "szl-rosie",
    "a11oy":    "szl-a11oy",
    "amaru":    "szl-amaru",
    "sentra":   "szl-sentra",
    "vessels":  "szl-vessels",
    "receipts": "szl-receipts",
}
SA = {  # Kubernetes ServiceAccount used as the SPIFFE identity in AuthorizationPolicy
    "rosie":    "rosie",
    "a11oy":    "a11oy",
    "amaru":    "amaru",
    "sentra":   "sentra",
    "vessels":  "vessels",
    "receipts": "szl-receipts-server",
}

# Rule engine. Returns ("ALLOW"|"DENY", rationale).
# caller -> callee.
def decision(caller, callee):
    if caller == callee:
        return ("ALLOW", "self-traffic (intra-namespace) is implicitly allowed")

    # Every module may POST receipts to the receipts-server (YAWAR fan-out).
    if callee == "receipts":
        return ("ALLOW", "receipt fan-out: every module emits to the chain authority")
    # receipts-server never initiates calls back into modules.
    if caller == "receipts":
        return ("DENY", "receipts-server is a sink; it never calls modules")

    # sentra is the immune system: it may inspect/reach any module.
    if caller == "sentra":
        return ("ALLOW", "sentra is the immune system; may inspect all module traffic")

    # rosie (operator console) commands ONLY a11oy. Direct rosie->organ is denied.
    if caller == "rosie":
        if callee == "a11oy":
            return ("ALLOW", "rosie commands a11oy (operator -> policy substrate)")
        return ("DENY", "operator commands route through a11oy, never direct to organs")

    # a11oy is the orchestrator: it commands every organ + replies to rosie.
    if caller == "a11oy":
        if callee == "rosie":
            return ("ALLOW", "a11oy emits events to rosie for human display")
        if callee in ("amaru", "sentra", "vessels"):
            return ("ALLOW", "a11oy delegates to the organ (memory/immune/skeleton)")

    # amaru (memory) only replies upward to a11oy; never reaches sibling organs.
    if caller == "amaru":
        if callee == "a11oy":
            return ("ALLOW", "amaru responds to a11oy's memory queries")
        return ("DENY", "memory has no need to reach immune/skeleton/operator")

    # vessels (skeleton/deployment fabric) is downstream: it only talks to a11oy
    # (status up) and the receipts sink. No sibling-organ or operator calls.
    if caller == "vessels":
        if callee == "a11oy":
            return ("ALLOW", "vessels reports deployment status up to a11oy")
        return ("DENY", "deployment fabric is downstream; no sibling/operator calls")

    return ("DENY", "no rule grants this pair; default-deny")


def main():
    # 1) Markdown matrix
    header = "| caller \\ callee | " + " | ".join(MODULES) + " |"
    sep = "|" + "---|" * (len(MODULES) + 1)
    rows = [header, sep]
    pairs = []
    allow_n = deny_n = 0
    for c in MODULES:
        cells = []
        for d in MODULES:
            verdict, why = decision(c, d)
            mark = "ALLOW" if verdict == "ALLOW" else "DENY"
            cells.append(mark)
            pairs.append((c, d, verdict, why))
            if c != d:
                if verdict == "ALLOW":
                    allow_n += 1
                else:
                    deny_n += 1
        rows.append(f"| **{c}** | " + " | ".join(cells) + " |")
    print("\n".join(rows))
    print()
    print(f"# cross-pairs: {allow_n} ALLOW, {deny_n} DENY, 6 self-ALLOW = 36 total")
    print()
    for c, d, v, why in pairs:
        if c == d:
            continue
        print(f"{c:9s} -> {d:9s} : {v:5s}  # {why}")


if __name__ == "__main__":
    main()
