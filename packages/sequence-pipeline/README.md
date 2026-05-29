# @szl-holdings/sequence-pipeline

Multi-stage ingest pipeline with per-stage hashed artefacts and
CI-bearing tabulated statistics. Re-expressed from CRISPResso2's
**pipeline-as-evidence-ledger** shape: every stage emits a
`(inputsHash, paramsHash, outputsHash)` triple so any downstream claim
walks back to the exact data that produced it.

## Doctrine rules enforced

- **No claim without an interval.** `pipeline.tabulated-statistic.v1`
  rows with missing CI bounds are rejected at the write boundary.
- **Absence is a row.** When the schema declares the domain has a
  meaningful "no event" label, the table must include at least one
  `isNegativeSpace: true` row.

## Worked example — edit-call

```ts
import { StagedPipeline, wilsonInterval } from '@szl-holdings/sequence-pipeline';
import { createHash } from 'node:crypto';

const hash = (v: unknown) => createHash('sha256').update(JSON.stringify(v)).digest('hex');
const pipeline = new StagedPipeline({ pipelineId: 'run-001', tooling: { tool: 'edit-call@1.2' }, hash });

const result = await pipeline.run(
  rawReads,
  [
    { name: 'filter',   params: { minQ: 30 },    run: filterReads },
    { name: 'align',    params: { ref: 'GRCh38' }, run: alignReads },
    { name: 'classify', params: { caller: 'edit-v1' }, run: callEdits },
  ],
  (final) => buildTabulatedStatistic(final, wilsonInterval),
);

// `result.stages[]` → write each as a `pipeline.stage.v1` receipt.
// `result.tabulatedStatistic` → write as `pipeline.tabulated-statistic.v1`.
```

## Source provenance

Pipeline shape re-expressed (not copied) from
`github.com/standardgalactic/CRISPResso2` (AGPL — upstream).

## Consumers

| Artifact | Use                                                       |
|----------|-----------------------------------------------------------|
| Amaru    | Sync-envelope ingest as a staged pipeline                 |
| Sentra   | Incident timeline as a staged pipeline (det → triage → ...) |
| api-server | Pipeline receipt-write endpoints (downstream task)      |

See [`docs/research/perception-bio-synthesis-2026.md`](../../docs/research/perception-bio-synthesis-2026.md) §2.
