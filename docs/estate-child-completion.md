# Explicit estate repair completion

Tracks A11oy #2154 and the existing Frontier #96 alignment wave.
This is supply-chain/controller wiring, not a new product route or publisher.

## Observed defect

Owner-dispatched parent 34791261715 observed its configured surface vector as
ALIGNED at 2026-09-14T00:27:36Z. Seven required projections passed, including the
previously mismatched Counsel, Finance and Terra. Its explicit public membership
predicate was aligned at 46 models, 35 datasets and 21 Spaces with no item deltas.
That did not qualify optional Sentra or David Leads.

The parent did not await canonical child 34792390665. The child's vertical job
later failed Lyte's immutable attestation. The parent snapshot is valid for its
own scope, but is not completed publication evidence. Moreover the vertical job
had job-level `continue-on-error: true`, allowing an aggregate successful run
with a failed requested publisher.

The downloaded parent archive SHA-256 is
`5352ba55dcdc300b87e37ee8940270fbefd970bf8f5a38fd51766d9cf494031c`.
The downloaded child archive SHA-256 is
`e85d74ed6b428dd19012e85e6ff621ce2f20c1eb88403f886b865bc828178607`.
The actual child receipt schema is `szl.hf-vertical-flagships/v4` with
`complete=false`, `combined_exit_code=0`, `generated_flagship_exit_code=0`,
`lyte_exit_code=1`. Its nested canonical Lyte v3 receipt is incomplete.
These records do not by themselves diagnose an application fault or justify a
resource allocation change. Do not replace the canonical Lyte source with A11oy.

## Changes

The existing HF workflow still skips vertical publication on pushes and on
product-only requests. When explicitly requested, the vertical job is blocking.
A terminal gate requires executed exact-main ownership, the admitted vertical
plan, successful publisher execution and a source/run-bound complete native v4
receipt, including successful canonical Lyte attestation. Skipped publication is
not recast as completed work. The existing publisher and its immutable attestor
are unchanged.

The existing estate controller dispatches the same canonical workflows through
the same approved planner. It journals each attempt before calling GitHub CLI,
requires a unique returned run URL, and never guesses the newest run or retries
an uncertain dispatch. Exact repository/workflow/source/attempt checks and
complete paginated job observations are mandatory. A green aggregate workflow
with a failed job is rejected. Explicit vertical requests additionally require
the successful terminal receipt gate; old runs lacking it are not retroactively
qualified. Both dispatched children must finish before repair re-observation.

Explicitly approved vertical requests remain actionable even if an initial
surface snapshot is ALIGNED. Their source/plan authority is not inferred from
that snapshot. Invalid or incomplete requested plans fail before any dispatch.
No-default-change, canonical concurrency, exact-source, signing, scope and
inventory protections remain intact.

Explicit repair uses a bounded 60-minute child wait followed by the existing
30-minute parity observation under a 110-minute outer job bound. Its initial
observation is immediate. Observation-only jobs retain the 55-minute outer and
20-minute initial bounds. Timeout is HOLD, not a reason to ignore a failing job.
The controller does not cancel, restart or automatically resend any child.

## Verification and bounds

`python tests/test_estate_child_completion.py` runs deterministic contracts.
They cover failed/skipped/missing requested jobs, wrong source/run/attempt,
ambiguous dispatch identity, pre-write source movement, uncertain response,
pagination, timeouts, native receipt failures and actual workflow wiring.
Fixture transport is not a live deployment replay or independent human review.
The new wiring regression fails on the exact original workflow blob and passes
with this source change. Existing tests and security checks remain required.

The journal is unsigned operational evidence. It does not replace canonical
immutable artifacts or independently authenticate model lineage. Source review
and hosted tests must precede normal admission. After admission, a fresh native
execution needs its own exact source-bound observations; PR tests cannot be
transferred to a main-branch deployment. Production inference, model quality,
licensed model/GPU execution and rollback qualification remain separate gates.
