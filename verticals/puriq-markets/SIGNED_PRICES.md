<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# Signed prices in the existing Finance runtime

The canonical A11oy runtime imports the offline verifier and modeled estimator
byte-for-byte from [PURIQ 2ea8ea4](https://github.com/szl-holdings/puriq-live/commit/2ea8ea4bb9de2ca432f40c0c55ea5a5ed02786bf).
`runtime/components/puriq_verity/source.json` binds the files, source revision and
license. A11oy owns the fixed, bounded public HTTP reads. The Finance Space is a
read projection of these canonical results, with exact source-revision and
component checks. The existing publisher remains the only release path.

| Surface | Route |
|---|---|
| Finance workspace | `/signed-prices#fin-signed` |
| Public observation | `/api/finance/signed-prices/BTC` (also ETH, SOL) |
| Public synthetic comparison | `/api/finance/signed-prices/model` |
| Canonical observation | `/api/a11oy/v1/finance/signed-prices/BTC` |
| Canonical synthetic comparison | `/api/a11oy/v1/finance/signed-prices/model` |

An observation is REVIEW only when both provider signatures verify, every
signed v2 field matches the outer record, the print is fresh within 30 seconds,
and the declared grade and source count meet the local policy. Invalid,
partial, stale or ineligible records are ABSTAIN with no display price. Source
failures return a bounded UNAVAILABLE response. The page invalidates prices on
selection changes, visibility changes, request failures and local expiry; it
requires manual refresh. Downloads contain unsigned local digests and the
provider assertion, not trading authority.

Provider keys are bootstrapped from the fixed HTTPS keyring; no independent
out-of-band key pin is claimed. Signature validity does not establish price
accuracy, source independence, or authorization. No account, order, custody,
private provider token, ledger write or model training is added.

The reference comparison is MODELED with SYNTHETIC inputs. It illustrates how a
median of declared-group medians differs from an equal-venue median under
correlated inputs. It is not empirical evidence of forecasting skill or a
novelty claim. [Research and prior art](https://github.com/szl-holdings/puriq-live/blob/2ea8ea4bb9de2ca432f40c0c55ea5a5ed02786bf/docs/SIGNED_PRICE_RESEARCH_2026-10-07.md).

Release sequence: qualify and merge the exact A11oy revision, let `hf-sync.yml`
publish the canonical runtime, then dispatch `hf-publish-vertical-flagships.yml`
on current main with `scope=finance`. The publisher checks live BTC verification,
the synthetic reference result, existing Finance functions and the complete
projection artifact manifest. A healthy landing page alone does not satisfy it.
