# A11oy Hub 1.31 runtime alignment

Canonical target: `huggingface/huggingface_hub@495b17c8529614759ae0f1ccf1ebe9a61c148b7c` (`v1.31.0`), annotated tag object `32ccc9ee57f3b3546165de105b4a0d8eba1b7446` (unsigned tag; do not claim signature verification).

Source pins on this branch converge the canonical Dockerfile and `requirements-audit.txt` to `huggingface_hub==1.31.0`. That is EVALUATION of the admitted client, not production admission, Hub publication, Sandbox Job creation, or GitHub → Hugging Face → a-11-oy.com → a11oy.net closure.

The previous 1.29.0 runtime / 1.30.0 audit mismatch is retained as a synthetic negative fixture in `tests/test_hf_hub_131_source_contract.py`. Merged Forge evaluation `74a8a07ced6c6b8697b31b7d0e482c4241d55880` supplies exact-source Linux/Windows SDK evidence for 1.31.0 but still does not prove the published A11oy image consumed this pin until independent image/runtime readback exists.

## Audit-closure blocker that is not a Hub successor

Exact-head `Dependency Audit` compares every `requirements-audit.txt` equality pin that also appears in the Dockerfile. That check failed on this branch because of a pre-existing `openai` mismatch (`audit 3.8.0` vs `Dockerfile 2.43.0`), independent of Hub 1.31.

This branch repairs the audit file to `openai==2.43.0` so it matches the canonical runtime pin. That is **not** an openai upgrade, not an openai 3.x admission, and not a production default change. The former `3.8.0` audit pin is retained as a synthetic HOLD fixture. A real openai 3.8 successor needs its own issue, exact source, and evaluation.

Do not `pip install -r requirements-audit.txt`.

## Remaining gates (not granted by this source change)

- exact-head repository checks on this PR
- built-image `importlib.metadata.version('huggingface-hub')` readback
- protected publisher receipt
- HF artifact and runtime source binding
- public-domain product readback
- proof pointer update only after those subjects exist

Do not claim GitHub -> Hugging Face -> a-11-oy.com convergence from a dependency change. Do not update a11oy.net proof until that downstream evidence is immutable and source-bound. Issue `a11oy#2087` stays open until the runtime actually consumes 1.31.0.
