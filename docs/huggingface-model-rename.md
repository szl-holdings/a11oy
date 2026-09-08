<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# Regenerate public evidence after a model rename

The Hugging Face ecosystem manifest and stage matrix record observations.
Changing a repository name in those files does not rename the provider
repository. Keep their recorded IDs and observation times until the provider
change has been verified.

The planned OAC identifier migration is from
`SZLHOLDINGS/oac-clinical-transport-health-v1` to
`SZLHOLDINGS/oac-system-health-v1`. This is a planned identity change, not a
claim that the destination is already published. Its training and staging
source belongs to [szl-forge](https://github.com/szl-holdings/szl-forge/tree/main/clinical-gateway).
Model scope remains synthetic operational telemetry and advisory-only.

Before the provider move, prepare and validate the Forge source/staging rename,
including its generated source snapshot and receipts. Protect existing pinned
GitHub and Hub revisions. Follow the current source review and publication
authority; a generated inventory is not publication authority.

After the provider move, read back the destination's canonical ID and exact
40-hex revision. Supply that verified revision as `VERIFIED_HUB_REVISION` below:

```bash
python scripts/audit_huggingface_ecosystem.py \
  --model-rename SZLHOLDINGS/oac-clinical-transport-health-v1 \
    SZLHOLDINGS/oac-system-health-v1 VERIFIED_HUB_REVISION
python scripts/build_ecosystem_stage_matrix.py
python scripts/render_public_estate_alignment.py
python scripts/audit_huggingface_ecosystem.py --check \
  --model-rename SZLHOLDINGS/oac-clinical-transport-health-v1 \
    SZLHOLDINGS/oac-system-health-v1 VERIFIED_HUB_REVISION
python scripts/build_ecosystem_stage_matrix.py --check
python scripts/render_public_estate_alignment.py --check
git diff --check
```

The collector refuses to replace the inventory if the old canonical ID remains
listed, the new ID is absent, or the destination revision differs. It retains
the existing card, revision, and timestamp validation gates. Review the complete
generated diff and required CI before protected publication. The provider move,
source merge, inventory refresh, and publication are separate evidence steps.
