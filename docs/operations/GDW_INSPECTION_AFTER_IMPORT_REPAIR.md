<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->
# GDW inspection after preservation entrypoint repair

The #2566 checkpoint selected only the existing metadata-only inspector.
Its result was not a retry, restore, bootstrap, deployment or storage admission.

## Observed predecessor

- Corrected source: `fed6a0449192e2156728676d52960991aea137de` (#2564).
- Exact merged tree: `7dac234abc0406fada8d142e04b97e7ee290c842`.
- The preceding supervised run `37261603104`, attempt 1, on `cb571495...`
  passed source/reconciliation but held at manual classification. Its acquisition,
  resume, publication and runtime-proof jobs were skipped.
- Native prerequisite artifact `11325096172`: 6,328-byte ZIP, SHA-256
  `cc18c8bb9c04543d3c0dc34f7868d13ede27abf1ab553381afa7e7f91b40b043`.
  Both copy and fallback destination readbacks were empty; report fields alone
  do not prove that either provider method was reached or that all effects are absent.
- The import repair addresses a reproduced pre-provider module-resolution defect.
  It does not qualify old private artifacts or erase uncertain history.

## Inspection-checkpoint effect boundary

At #2566, the workflow and three shape-test files were identical to the
previously admitted inspection-only `bedc2f55...` source. Reconciliation and
manual preservation retain literal false holds. The acquisition-named job runs
only `--inspect-held-acquisition`; pair configuration is independently disabled.
The inspector always exits HELD. All downstream writers remain unreachable,
including when a synthetic successful inspector result is supplied to the graph tests.

Only three reviewed job hashes change in the COPY guard. All helper/reference
pins remain from the corrected source, including the import repair and latest
reconciliation evidence. No runtime Python, provider selector, credential,
permission, endpoint, SDK, dataset, bucket or DNS setting is modified.

The existing fixed inspector reads private dataset metadata only. It does not
inspect database contents, remove objects, repair SQLite or grant any recovery
permission. Its resulting native source/run/artifact must be inspected and bound
into a separately reviewed direct recovery successor. Do not replay a historical
write-enabled run or promote expected absence to proof of no orphan data.

## Verification and rollback

The local change packet verifies exact inspection-file equality, a three-scalar
COPY-guard delta and unchanged helper hashes. Selected offline graph tests must
show that no downstream writer can become eligible. Hosted native checks remain
mandatory; this document does not predeclare their outcome.

Before admission, close the proposal. After admission, use a reviewed source
revert; no force push or provider deletion is a rollback mechanism.

## Verified inspection and separately gated successor

The inspection merged as `a60125af336ea97ac29678a79110c30ec0122e99`.
Canonical push run `37262929675`, attempt 1, admitted source in job `111613728997`.
Inspection job `111613776558` returned HELD; all eleven other jobs skipped, and
paired configuration remained disabled. Artifact `11324359120` is the exact
565-byte ZIP `863191708947e38f6d3338e0f99cefff25f19fde55919132dd991e099d7c4513`.
Its sole 640-byte JSON hashes to
`d5f84ce152b3c46d5295792d1db44b0031568079719aa375a04be9750e38dee8`.
It observes ABSENT private HEAD at revision `dd34d6b0b20d918cc862888030569d03d99a9b37`;
provider writes, retry, restore and deployment are all false. This does not
prove absent orphan objects, erase historical uncertainty or admit a replay.

The companion source change restores the already reviewed supervised graph
from `fed6a044...`, retaining the repaired preservation helper and its tests.
Only the fixed reconciliation source/run/job/artifact identities and byte
bounds are re-bound to the actual inspection above; the private revision is
unchanged. A signed direct successor, unique first push, current protected
source, the exact native producer and artifact, two private absence reads,
qualified preservation and every later acquisition/runtime gate remain required.
Any source movement or uncertain provider result must hold without blind retry.
No code preparation grants provider success. Actual native receipts and live
readback must establish whether any later recovery occurred.
