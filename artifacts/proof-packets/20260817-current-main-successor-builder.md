# Current-main successor builder authority

Date: 2026-08-17

The one-shot workflow `.github/workflows/p0-promote-current-main.yml` is authorized to create `codex/p0-a11oy-successor-20260817` from the then-current protected `main`, apply the reviewed P0 work-branch delta with three-way integration for modified files, run focused compile and test gates, and push the resulting non-protected branch.

It is not authorized to write to protected `main`, merge a pull request, deploy, publish to Hugging Face, access provider credentials, train a model, weaken a check, or claim production parity.

The successor branch must still pass exact-head repository checks, independent review, protected merge authority, canonical deployment, and immutable runtime readback.
