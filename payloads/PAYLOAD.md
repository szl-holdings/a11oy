# lambda_gate payload

BIND of [a11oy](https://github.com/szl-holdings/a11oy). Not a second flagship.

| Pin | Value |
|---|---|
| Product origin | https://a-11-oy.com |
| Proof origin | https://a11oy.net |
| Runtime twin | Hugging Face Space `SZLHOLDINGS/a11oy` |
| Doctrine | v11 LOCKED |
| Kernel | `c7c0ba17` |
| Lambda uniqueness | Conjecture 1 - not a theorem |
| Trust ceiling | 0.97 |
| Energy | UNAVAILABLE unless a live NVML/RAPL meter exists |
| Signer | UNSIGNED-honest unless persistent key verifies |
| Invariant | receipts.in == receipts.out |

`a11oy.net` is static proof. Do not host this payload there.
Do not pin a sixth Hub Space for this file.

## Run

```bash
printf '%s' '{"intent":"pin retrieval state for the Mooncake KV fabric","kernel":null}' | python3 payloads/lambda_gate.py
# expect ok=true decision=ADMIT honesty=SOFTWARE kernel=retrieval

printf '%s' '{"intent":"claim FedRAMP and proven theorem","kernel":null}' | python3 payloads/lambda_gate.py
# expect decision=BLOCKED honesty=SOFTWARE
```

Missing interpreter, invalid JSON, or crash -> honesty=UNAVAILABLE and no admit.
An LLM must not decide ADMIT/BLOCKED. This file is the gate.
`score_axes()` is a hardcoded analog. Do not label it MEASURED.
Pass `x` (13 floats, Yuyay-13 order) to compute Λ from the System One vector instead of the 5-axis silhouette. That path is still SOFTWARE unless TypeSafe Jev actually ran.
Use `payloads/yuyay_jev.py` for Yuyay-13 measurement.
Use `payloads/typesafe_bind.py` for the TypeSafe contract receipt (missing key = UNAVAILABLE).
Use `payloads/evaluate_surface.py` for the Command / COP envelope.

## YUYAY-JEV (replacement measurement organ)

`lambda_gate.py` `score_axes()` is a hardcoded SOFTWARE analog (0.84-0.95). The Yuyay-13 bind lives next to it:

- `payloads/yuyay_jev.py` - TypeSafe Jev measurement. Missing key -> UNAVAILABLE.
- `payloads/khipu_organs.py` - sentra, amaru, a11oy, killinchu. n=4 t=3.
- `payloads/yuyay_khipu_gate.py` - compose. Khipu decides ADMIT/BLOCKED.
- `payloads/hf_align.py` - GitHub canonical <-> Hugging Face `SZLHOLDINGS`.
- See `payloads/YUYAY_JEV.md`.

Jev is not organ 5 and never ALLOW-alone.
