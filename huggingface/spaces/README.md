# Packet 8 Hugging Face Space source archive

Thin Docker adapters generated from `verticals/`. They do not own product logic.
The source files remain in Git. The automatic Packet 8 publisher has been
retired so a future source change cannot recreate Spaces pending consolidation.

| Space | Vertical | Visibility | Status |
| --- | --- | --- | --- |
| `SZLHOLDINGS/terra-assurance` | terra | private, paused at 2026-10-02 readback | Deletion pending |
| `SZLHOLDINGS/aegis-assurance` | aegis | Not checked here | Source archived |
| `SZLHOLDINGS/puriq-markets` | puriq-markets | private, paused at 2026-10-02 readback | Deletion pending |
| `SZLHOLDINGS/counsel-assurance` | counsel | private, paused at 2026-10-02 readback | Deletion pending |

At protected A11oy revision `379daa8555efac108d5e2dcacd07fa299343e899`,
the ten files in each of the three private Space trees (excluding the
Hub-managed `.gitattributes`) matched their source Git blobs here at exact Hub
revisions `5aa7cd88a00b0a957fbb955760c4d1e064760eab`,
`18112a2d2d804a959bf794acc6993b1ec9565209`, and
`5d6d27cb9e6dac966b96b4a28371be7a214c4e44` respectively. This is source
preservation evidence, not a deletion or replacement-runtime verdict.
Finalization remains governed by
[immune#124](https://github.com/szl-holdings/immune/issues/124). The older
protected lifecycle policy in `szl-holdings/.github` still lists
`terra-assurance` as a keep target; reconcile that policy before deletion.
