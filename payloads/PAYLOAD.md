# lambda_gate payload

BIND of [a11oy](https://github.com/szl-holdings/a11oy). Not a second flagship.

| Pin | Value |
|---|---|
| Product origin | https://a-11-oy.com |
| Proof origin | https://a11oy.net |
| Runtime twin | Hugging Face Space `SZLHOLDINGS/a11oy` |
| Doctrine | v11 LOCKED |
| Kernel | `c7c0ba17` |
| Λ uniqueness | Conjecture 1 — not a theorem |
| Trust ceiling | 0.97 |
| Energy | UNAVAILABLE unless a live NVML/RAPL meter exists |
| Signer | UNSIGNED-honest unless persistent key verifies |
| Invariant | receipts.in ≡ receipts.out |

`a11oy.net` is static proof. Do not host this payload there.
Do not pin a sixth Hub Space for this file.

## Run

```bash
printf '%s' '{"intent":"pin retrieval state for the Mooncake KV fabric","kernel":null}' | python3 payloads/lambda_gate.py
# expect ok=true decision=ADMIT honesty=MEASURED kernel=retrieval

printf '%s' '{"intent":"claim FedRAMP and proven theorem","kernel":null}' | python3 payloads/lambda_gate.py
# expect decision=BLOCKED
```

Missing interpreter, invalid JSON, or crash → honesty=UNAVAILABLE and no admit.
An LLM must not decide ADMIT/BLOCKED. This file is the gate.
