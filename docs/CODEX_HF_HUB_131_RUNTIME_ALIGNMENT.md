# Historical A11oy Hub 1.31 runtime alignment

This document preserves the 1.31 evaluation history. It does not qualify the
current Hub 1.33 / Xet 1.7 runtime. The historical evaluator deliberately returns
HOLD for that successor. Its retired v1 storage SDK constant and all v1 code are
unchanged; the active ADR-0001 state store uses interface-based compatibility
tests described in [the 1.33 upgrade](CODEX_HF_HUB_133_STATE_STORE.md).
The branch changes and remaining gates below describe the historical 1.31 work.

Canonical target: `huggingface/huggingface_hub@495b17c8529614759ae0f1ccf1ebe9a61c148b7c` (`v1.31.0`), annotated tag object `32ccc9ee57f3b3546165de105b4a0d8eba1b7446` (unsigned tag; do not claim signature verification).

That source change converged the canonical Dockerfile and `requirements-audit.txt` to `huggingface_hub==1.31.0`. It was EVALUATION of the admitted client, not production admission, Hub publication, Sandbox Job creation, or GitHub → Hugging Face → a-11-oy.com → a11oy.net closure.

The previous 1.29.0 runtime / 1.30.0 audit mismatch is retained as a synthetic negative fixture in `tests/test_hf_hub_131_source_contract.py`. Merged Forge evaluation `74a8a07ced6c6b8697b31b7d0e482c4241d55880` supplies exact-source Linux/Windows SDK evidence for 1.31.0 but still does not prove the published A11oy image consumed this pin until independent image/runtime readback exists.

## Audit-closure blocker that is not a Hub successor

Exact-head `Dependency Audit` compares every `requirements-audit.txt` equality pin that also appears in the Dockerfile. That check failed on this branch because of a pre-existing `openai` mismatch (`audit 3.8.0` vs `Dockerfile 2.43.0`), independent of Hub 1.31.

This branch repairs the audit file to `openai==2.43.0` so it matches the canonical runtime pin. That is **not** an openai upgrade, not an openai 3.x admission, and not a production default change. The former `3.8.0` audit pin is retained as a synthetic HOLD fixture. A real openai 3.8 successor needs its own issue, exact source, and evaluation.

Do not `pip install -r requirements-audit.txt`.

## Single source of runtime pins (2026-09-29)

The runtime pins now live only in `requirements-runtime.txt`. The Dockerfile installs that file and `requirements-audit.txt` includes it with `-r`, so `evaluate_repository` reads the runtime pin from the file the image installs (and refuses a Dockerfile that does not install it). This restores `huggingface_hub==1.31.0`, `openai==2.43.0`, `uvicorn==0.52.4` and `numpy==2.5.2`: #2315 had moved the Dockerfile to Hub 1.32.0, uvicorn 0.53.0 and numpy 2.5.3 without review, and #2307 had moved only the audit file to openai 3.8.0. Neither is an admitted successor.

## Remaining gates (not granted by this source change)

- exact-head repository checks on this PR
- built-image `importlib.metadata.version('huggingface-hub')` readback
- protected publisher receipt
- HF artifact and runtime source binding
- public-domain product readback
- proof pointer update only after those subjects exist

Do not claim GitHub -> Hugging Face -> a-11-oy.com convergence from a dependency change. Do not update a11oy.net proof until that downstream evidence is immutable and source-bound. Issue `a11oy#2087` stays open until the runtime actually consumes 1.31.0.
