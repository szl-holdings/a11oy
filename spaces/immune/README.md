---
title: IMMUNE Investor Demo
emoji: 🔒
colorFrom: indigo
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
license: apache-2.0
short_description: Append-only SHA-256 receipt chain + HUKLLA tripwires demo
---

# IMMUNE — Verifiable AI You Can't Fake

**Stage:** LIVE · MEASURED — append-only SHA-256 receipt chain + HUKLLA tripwires; receipts and hashes run for real.

Investor demo for IMMUNE: the governed AI safety layer. A self-contained deployment that shows:

- **Append-only SHA-256 receipt chain** — every action sealed into a tamper-evident hash-linked ledger
- **GATE admission gate** — governed access control, no fabricated green lights
- **HUKLLA tripwires** — honest refusal of unverifiable queries; no hallucinated answers
- **Live threat feeds** — Sigstore Rekor, MITRE ATLAS, OWASP LLM Top 10 with honest `LIVE / REFERENCE / UNAVAILABLE` labels per source

Nothing here is faked. Every externally-sourced datum carries an honest provenance label.

## API

| Endpoint | What |
|---|---|
| `GET /api/immune/state` | Ledger count + lastHash |
| `GET /api/immune/ledger/verify` | Chain integrity check — `ok: true` on clean chain |
| `GET /api/immune/ledger` | Full append-only receipt ledger |

## Related

- [a11oy Space](https://huggingface.co/spaces/SZLHOLDINGS/a11oy) — governed command platform
- [killinchu Space](https://huggingface.co/spaces/SZLHOLDINGS/killinchu) — edge organ
- [hatun-mcp](https://huggingface.co/spaces/SZLHOLDINGS/hatun-mcp) — governed MCP server
- [a11oy-verifiable-corpus](https://huggingface.co/datasets/SZLHOLDINGS/a11oy-verifiable-corpus) — live receipt ledger

---

*SZL Holdings · Doctrine v11 LOCKED · SLSA L1 honest · Apache-2.0*  
*Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>*

---

## Source & provenance

This is a self-contained SZL demo Space — its full source (Dockerfile, `index.html`,
app/vendor assets) lives **in this Space's own repository** and rebuilds directly here;
it is not generated from a hidden source. It is part of the SZL ecosystem:

> **Governed AI you can prove** — every decision comes with a signed, verifiable
> receipt, built on public data, running on your own hardware.

Flagship: **a11oy — Command Center** ([SZLHOLDINGS/a11oy](https://huggingface.co/spaces/SZLHOLDINGS/a11oy)).
Naming glossary & org: [github.com/szl-holdings](https://github.com/szl-holdings).
Public-data only · honest by design · nothing fabricated.
