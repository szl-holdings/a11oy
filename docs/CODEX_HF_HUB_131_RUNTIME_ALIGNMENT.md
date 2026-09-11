# A11oy Hub 1.31 runtime alignment

Canonical target: `huggingface/huggingface_hub@495b17c8529614759ae0f1ccf1ebe9a61c148b7c` (`v1.31.0`), annotated tag object `32ccc9ee57f3b3546165de105b4a0d8eba1b7446` (unsigned tag; do not claim signature verification).

The source contract is intentionally ahead of the current runtime: `requirements-audit.txt` is still 1.30.0 and the canonical Dockerfile is still 1.29.0. That state is HOLD, not an error to hide. Merged Forge evaluation `74a8a07ced6c6b8697b31b7d0e482c4241d55880` supplies exact-source Linux/Windows SDK evidence for 1.31.0 but does not prove A11oy consumption.

## Codex implementation step

On a fresh branch from the then-current protected main, update only the canonical A11oy runtime/audit dependency pins that are required to converge this path on `huggingface_hub==1.31.0`. Do not mass-bump purpose-pinned workflows. Run the existing dependency-audit parity checks, source-pin regressions, Docker build, security scans, no-HF-mirror guard, operational tests and publication/readback workflows. If any required check fails, keep HOLD and retain failure evidence.

Regression coverage must retain repository-aware resolved-revision authority and additionally exercise the 1.31 boundaries that matter to this runtime: unsafe remote filename rejection (including Windows traversal forms), concurrent snapshot cache ref behavior, dry-run no-payload-copy behavior, retry/resume handling, and Sandbox label validation without creating a billable Job. Valid upstream labels or model/provider eligibility never grant SZL job, route, publication or merge authority.

Do not claim GitHub -> Hugging Face -> a-11-oy.com convergence until exact publication/runtime readback exists. Do not update a11oy.net proof until that downstream evidence is immutable and source-bound.
