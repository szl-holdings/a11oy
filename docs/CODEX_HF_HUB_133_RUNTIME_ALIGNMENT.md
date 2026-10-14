<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# A11oy Hub 1.33 runtime successor

The image and audit include target exact `huggingface_hub==1.33.0` and `hf-xet==1.7.0`. The successor control-client installs pin the same native transport used by the offline qualification; a wider transitive range is not qualified. Official upstream release commit is `9eeace5e467939b8f6af6ff280a134bc7c22802f`; annotated tag object `a93d85c0e6e0f35c29c33e60cb1e1ca9d60a1692` is **unsigned**. PyPI's universal wheel SHA-256 is `04e434b06e100eddbce9a6e817d72693a7884b10a79bd67ab48080d5c07eb899`. These identify source/package evidence, not a signed release or deployment.

The one-line #2588 proposal left the admitted managed-storage SDK, admission parser and source contract at 1.31. The successor aligns those runtime checks to **exactly 1.33**. It does not admit arbitrary versions. `scripts/hf_hub_133_source_contract.py` reports only EVALUATION with every production, publication, promotion and Sandbox authority flag false. Historical `hf_hub_131_source_contract.py`, its grouped-bump HOLD fixture, and archived Forge measurements remain unchanged and historical.

## Scoped API qualification

Independent offline qualification used isolated real SDK 1.31 and SDK 1.33 installations, HTTPX 0.28.1 and hf-xet 1.7.0, with sockets denied and no credentials, provider calls or model downloads. Existing 1.31 contracts passed 721 distinct tests plus 33 subtests after supplying their documented no-bytecode and immutable COPY-parser prerequisites (5 skips). Native 1.33 transport checks passed 16 cases, including the two failed-batch cases added here; these results do not qualify all transitive versions or a live runtime.

The checked native API behaviors preserve one add-only 152-file batch, exact bucket path/method, no repeat after an ambiguous mutation, immutable source/state pause readbacks, and cancellation propagation. SDK 1.33 moves the private `_BucketAddFile` test fixture to `huggingface_hub._buckets`; production does not import it. SDK 1.32 made the provider's `hardware:null` response valid, so the successor explicitly tests that acknowledgment **and** retains a genuinely malformed hardware negative case. SDK 1.33 failed-operation replies (`200` partial or `422` all-failed) remain unacknowledged after one POST, never a retry.

## Separate clients and admission

The image storage client, current read-only diagnostic workflow, `hf-sync` control client and restart-drill control client use exact 1.33. Managed admission reads launch `gdw_durable_storage` workers with the control process's own `sys.executable`, so retaining a 1.31 control interpreter would violate the worker's 1.33 guard. Both guards and the strict workflow contracts now agree. The genuinely separate canonical publisher's locked dependencies and the vertical-only 1.31 client remain unchanged. Source, identity, immutable manifest, CAS, paused-source and recovery prerequisites remain required; no control/publisher authority is enlarged.

An old 1.31 managed-storage admission is rejected by the new parser. A new record must come from the existing separately admitted acquisition path, bind the exact accepted source/image/installed source closure, and satisfy every existing identity, CAS, private-data, quiescence and recovery constraint. This change creates no such record and does not switch legacy storage to managed storage. It does not replay diagnostic or recovery workflows.

Before declaring the new image operational, require exact-head hosted tests and image build, normal protected source acceptance, canonical publisher success, installed SDK/source/runtime readback, and application readiness. Source equality alone does not establish GitHub/Hugging Face/domain convergence. No proof pointer changes are made here.

Primary release notes: <https://github.com/huggingface/huggingface_hub/releases/tag/v1.33.0> and <https://github.com/huggingface/huggingface_hub/releases/tag/v1.32.0>.
