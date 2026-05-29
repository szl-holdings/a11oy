/**
 * @szl-holdings/sequence-pipeline
 *
 * Multi-stage sequence-style ingest with per-stage hashed artefacts and
 * CI-bearing tabulated statistics. Re-expressed from CRISPResso2's
 * pipeline-as-evidence-ledger shape. See
 * docs/research/perception-bio-synthesis-2026.md §2.
 */

export { StagedPipeline } from './staged.js';
export type {
  StageDefinition,
  StageContext,
  StageArtefact,
  PipelineResult,
  StagedPipelineOptions,
} from './staged.js';

export { validateTabulatedStatistic } from './tabulated-statistic.js';
export type { TabulatedRow, TabulatedStatistic } from './tabulated-statistic.js';

export { wilsonInterval } from './wilson-ci.js';
export type { WilsonInterval, ConfidenceLevel } from './wilson-ci.js';

export const SEQUENCE_PIPELINE_VERSION = '0.1.0' as const;
export const PIPELINE_STAGE_RECEIPT_CLASS = 'pipeline.stage.v1' as const;
export const PIPELINE_TABULATED_STATISTIC_RECEIPT_CLASS = 'pipeline.tabulated-statistic.v1' as const;
