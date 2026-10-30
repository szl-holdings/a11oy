<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# Execution evidence and readiness

The provenance/readiness module `szl_execution_readiness.py` keeps passive coverage and execution evidence separate. All five POST rows remain `NOT_PROBED`. A distinct coverage record requires the independently approved exact plan, runtime observation signatures, immutable source/HF/boot bindings, and native receipt/readback predicates for every case. Export wrapper flags do not grant authority.

Production publisher and relock commands require the exact checked-out `tools/readiness-harness/tabs.json`; even an explicit matrix argument must contain identical bytes. The served artifact reader uses its own deployed matrix. Every passive row remains required according to that source contract, including schema, citations, labels, source identity and freshness.

## Sole publication workflow

`hf-sync.yml` retains its passive probe and browser checks in the credential-free `readiness-verdict` job. A separate `execution-readiness` job downloads that exact run/attempt’s unchanged passive artifact. Its GET-only collector reads an already completed current-boot export using independent context and existing operator/tenant credentials. Its fixed-origin reads bound bytes, time, encoding and content type, refuse redirects, preserve configured proxy/CA trust, and send credentials only to the exact export route. Source/HF/boot/fenced storage/snapshot/counter values must match before and after collection. Historical archive exports are rejected for current readiness.

The passive archive contains only `readiness-verdict.json`. The combined immutable readiness artifact contains exactly `readiness-verdict.json` and `execution-observations.json`. Public pin configuration is not taken from that archive. The compact publisher validates without changing a Space variable. Relock downloads the same run and attempt's raw artifact, independently verifies full passive coverage and native signatures, and finally re-reads the actual retained export. Cancellation, restart, missing storage, or a byte-different retained bundle prevents admission even when older signatures remain valid.

The served reader also verifies GitHub protected-main, run/attempt, successful passive/combined/relock jobs in dependency order and immutable artifact provenance. The passive observation clock belongs to the passive job; archive creation belongs to the combined producer job. Its startup binding accepts the actual application-owned observer, and every served snapshot rechecks that observer's current completed-run context. A caller-supplied plan, wrapper, nonce or key cannot install that context.

## Independent configuration required

The workflow references these configuration names without creating bindings:

- Existing secrets `A11OY_CODE_ADMIN_KEY` and `A11OY_CODE_TENANT`, scoped only to the collector and final relock verification steps.
- Public variables `A11OY_EXECUTION_AUTHORITY_PINS_JSON`, `A11OY_EXECUTION_HF_REVISION`, `A11OY_EXECUTION_BOOT_ID`, and `A11OY_EXECUTION_RUN_NONCE`.

The public pin JSON has schema `szl.execution-authority-pins/v1` and exactly `approval_public_pem`, `approval_key_id`, `runtime_public_pem`, and `runtime_key_id`. The approval and runtime identities must be independently provisioned and distinct. Expected revisions, boot and nonce must be chosen through the independent operator admission process, never copied from untrusted evidence to make it qualify.

The runtime may receive the independently admitted public document through its own deployment setting `A11OY_EXECUTION_AUTHORITY_PINS_JSON`, or through the file named by `A11OY_EXECUTION_AUTHORITY_FILE`, but never both. The inline setting is captured once during registration and uses the identical strict parser as the file. Repository variables are not automatically copied into the Space: CI and runtime configuration remain separate provisioning steps. Supplying an empty value does not resolve an ambiguous two-source configuration. Neither source accepts authority from requests or artifacts, generates a key, or grants approval for a run.

The runtime additionally requires the persistent signer, native storage owners, an immutable source/HF/boot identity verified through [authenticated publisher provenance](runtime-source-identity.md), current fenced StateStore and confirmed snapshots described in [execution-observer.md](execution-observer.md). This implementation does not generate those production authorities or make a live model call automatically.

A newly deployed boot invalidates old execution evidence. An independently approved completed bounded run must exist on the exact new boot before the workflow's GET-only collection stage. Missing configuration or completed evidence remains unavailable. Local fixture tests prove implementation behavior; they do not claim that the external prerequisites or live deployment are complete.

## Handoff after the final restart

The normal publisher still deploys and converges configuration before it verifies
execution. Its `execution-handoff` job freezes the three independently configured
execution variables and the public pins once. It checks the protected source and
two matching live source/HF/boot/storage readbacks. This readback grants no
execution authority and creates no challenge, signed plan, or observation.
Downstream collection and relock consume the frozen outputs; they do not reread
mutable repository variables.

If the final restart changed the boot, preserve that runtime while the designated
independent custodian approves the exact bounded plan and the authorized operator
completes it. Configure the three variables through that established admission
process. Do not select a nonce or expected identity from an export to make it pass.
An environment approval pause does not guarantee that a running job will refresh
repository variables, so continuing a paused run is not the supported handoff.

After the approved execution, manually dispatch the existing `hf-sync.yml` on
current protected main with `verify_current_deployment=true`. Leave
`open_deploy_window` and `publish_vertical_flagships` false and `vertical_plan_json`
empty. Contradictory inputs are refused. Verification mode skips preflight,
deployment, runtime configuration and vertical publication. It verifies the
already deployed runtime against the checked-out current source, produces fresh
passive evidence for its own run and attempt, collects the existing exact export,
and runs the existing relock and parity gates. It neither restarts the Space nor
writes a verdict into its environment.

Source drift, reboot, storage changes, missing credentials, invalid signatures,
incomplete cases, or expired observations still block completion. The existing
fifteen-minute evidence lifetime is unchanged; a verification run that misses
that window must obtain fresh contract-valid execution rather than reuse expired
evidence. No earlier run's passive artifact is accepted as a substitute. This
mode is a verification path within the sole canonical publisher, not a second
publisher or a replacement approval mechanism.
