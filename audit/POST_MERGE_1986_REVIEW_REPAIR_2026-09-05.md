# Runtime-boundary post-merge review repair — clean successor

- `workcell_id`: `A11OY-1986-POSTMERGE-REVIEW-REPAIR-20260905-CLEAN`
- `source_base`: `083f9ff47b512a9ceb90a0a7da17c8f94e47f632`
- `shared_source_peer`: `szl-holdings/killinchu#421`
- `peer_merge_commit`: `f2a376f5ea2d55497674a20cd0ab9c199d32d4f5`
- `state`: `IMPLEMENTED_PENDING_EXACT_HEAD_CI`

## Permanent repairs

1. Nested `agent.nexus` request and program metadata must agree with the current request. Conflicting outer or nested duplicates fail closed before `SEALED`.
2. Every mutation of the shared run lineage is serialized through one lock-protected append primitive, preventing concurrent lineage forks.
3. The protected Ouroboros UI sends operator bearer authority only for the active request, never writes it to browser storage, and clears it after completion.
4. Receipt verification reports the key that actually verified through `verified_by_keyid`, including retained rotation keys.
5. IMMUNE Field compatibility fallback identifies the actual Channel A source and preserves the failed Channel B probe as bounded evidence.

## Zero-bandaid boundary

The abandoned repair branch used three self-modifying one-shot workflows and an explicitly ephemeral `sitecustomize.py` import shim. None of those files are present in this successor. The permanent regression suite fails if any exact transient path returns.

The shared runtime blobs and payload manifest are byte-identical to the already-merged Killinchu peer. No drift exclusion, provider mutation, secret-value readback, branch-protection weakening, force push, or direct-main write is introduced.

## Acceptance

- focused adversarial tests cover all five repairs;
- the shared payload manifest hashes the permanent source bytes exactly;
- repository-wide exact-head tests, container, security, doctrine, source-drift, and mobile gates pass;
- independent review finds no remaining high-severity defect;
- merge uses an unchanged head SHA and the protected pull-request path.
