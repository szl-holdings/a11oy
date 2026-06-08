<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 -->

# Release-receipt monitor — end-to-end negative proof

This document proves, on **real release data** (not monkeypatched), that the
release-asset receipt monitor catches a tampered receipt end-to-end:

- verifier: [`scripts/verify_release_receipts.py`](../../scripts/verify_release_receipts.py) (issue #241)
- workflow: [`.github/workflows/release-receipt-verify.yml`](../../.github/workflows/release-receipt-verify.yml)
- tamper helper: [`scripts/tamper_release_receipt.py`](../../scripts/tamper_release_receipt.py)

The repo's unit tests (`tests/test_verify_release_receipts.py`) deliberately
**monkeypatch** the Sigstore round-trip so they can run offline. That leaves one
thing only a live run can demonstrate: that the *real* Sigstore/Rekor
`verify_dsse()` rejects a cryptographically-tampered receipt. This proof closes
that gap with a real `workflow_dispatch` run.

## Why a default dispatch proves nothing

At the time of writing, no published release carried `*.dsse.json` assets (the
latest release exposed only `*.intoto.jsonl`). With nothing to verify the
monitor takes its honest **soft-pass** path (exit 0). To prove the negative you
must dispatch against a release that actually carries genuine `*.dsse.json`
receipt assets.

Creating a tagged pre-release is enough: the repo's `slsa.yml` / `release.yml`
producers fire on the new tag and attach genuine, Sigstore-signed
`*.dsse.json` receipts automatically. You can also attach a genuine receipt
pulled from the `governance-receipts` branch under `attestations/governance/`.

## Re-runnable procedure

All steps use the GitHub REST API with an org-scoped token (`$SZL_GITHUB_TOKEN`).
`REPO=szl-holdings/a11oy`, `WF=release-receipt-verify.yml`.

1. **Create a throwaway pre-release** with a unique tag, e.g.
   `release-verify-proof-<date>` (`prerelease: true`). Creating the tag triggers
   the producing workflows, which attach genuine `*.dsse.json` assets.

2. **(optional) Attach a known-genuine receipt** as an extra asset:

   ```sh
   curl -X POST -H "Authorization: Bearer $SZL_GITHUB_TOKEN" \
     -H "Content-Type: application/json" --data-binary @real_receipt.dsse.json \
     "https://uploads.github.com/repos/$REPO/releases/$RELID/assets?name=governance-proof.dsse.json"
   ```

3. **Positive run** — dispatch and expect PASS:

   ```sh
   curl -X POST -H "Authorization: Bearer $SZL_GITHUB_TOKEN" \
     "https://api.github.com/repos/$REPO/actions/workflows/$WF/dispatches" \
     -d '{"ref":"main","inputs":{"tag":"<TAG>"}}'
   ```

   Run conclusion `success`; the `release-receipt-verify-summary` artifact shows
   `failed: 0` and every asset `PASS`.

4. **Make a tampered copy** of a genuine asset and upload it:

   ```sh
   python3 scripts/tamper_release_receipt.py real_receipt.dsse.json \
     tampered.dsse.json --strategy payload-byteflip
   curl -X POST -H "Authorization: Bearer $SZL_GITHUB_TOKEN" \
     -H "Content-Type: application/json" --data-binary @tampered.dsse.json \
     "https://uploads.github.com/repos/$REPO/releases/$RELID/assets?name=governance-proof-TAMPERED.dsse.json"
   ```

5. **Negative run** — dispatch again and expect FAILURE. Run conclusion
   `failure` (non-zero exit), the summary marks the tampered asset
   `FAIL` with reason `DSSE: invalid signature`, and the rolling incident issue
   (label `release-receipt-verify`) is opened.

6. **Recovery run** — delete the tampered asset, dispatch once more. Run
   conclusion `success`; the incident issue auto-closes.

7. **Cleanup** — delete the throwaway release and its tag ref.

## Recorded evidence (2026-06-08)

Throwaway pre-release tag `release-verify-proof-2026-06-08` (deleted after the
proof). Genuine `*.dsse.json` assets were auto-produced by `slsa.yml`/
`release.yml` on tag creation, plus one attached genuine governance receipt.

| step | run | conclusion | summary |
| --- | --- | --- | --- |
| positive | [27165177324](https://github.com/szl-holdings/a11oy/actions/runs/27165177324) | success | checked 2 · passed 2 · failed 0 |
| negative | [27165257438](https://github.com/szl-holdings/a11oy/actions/runs/27165257438) | **failure** | checked 5 · passed 4 · **failed 1** |
| recovery | [27165315483](https://github.com/szl-holdings/a11oy/actions/runs/27165315483) | success | checked 4 · passed 4 · failed 0 |

Negative-run per-asset result for the tampered copy:

```
FAIL governance-proof-TAMPERED.dsse.json :: DSSE: invalid signature
```

Rolling incident [#292](https://github.com/szl-holdings/a11oy/issues/292) was
opened by the negative run and auto-closed by the recovery run.

**Conclusion.** A genuine published release receipt verifies (PASS); a
byte-flipped copy is rejected by the real Sigstore round-trip and fails the run
loudly (non-zero exit + incident), and removing it restores green. The monitor
is honest on real data, end-to-end.
