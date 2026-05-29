/**
 * Staged pipeline runner — re-expression of the CRISPResso2 multi-stage
 * shape (read-quality-filter → alignment → edit-classification →
 * allele-frequency → statistical-test). Each stage emits one hashed
 * artefact; the terminal stage may emit a tabulated statistic.
 *
 * The runner is intentionally generic — anything that fits a "staged
 * ingest with per-stage evidence" shape (genomic, AIS tracks, log
 * windows, incident timelines) consumes it.
 */

import type { TabulatedStatistic } from './tabulated-statistic.js';
import { validateTabulatedStatistic } from './tabulated-statistic.js';

export interface StageContext<TStageName extends string> {
  readonly parentPipelineId: string;
  readonly stageOrdinal: number;
  readonly stageName: TStageName;
}

export interface StageDefinition<TStageName extends string, TInput, TOutput> {
  readonly name: TStageName;
  /** Params hashed into the per-stage receipt. */
  readonly params: Readonly<Record<string, unknown>>;
  run(input: TInput, ctx: StageContext<TStageName>): Promise<TOutput> | TOutput;
}

export interface StageArtefact<TStageName extends string> {
  readonly stageName: TStageName;
  readonly stageOrdinal: number;
  readonly parentPipelineId: string;
  readonly inputsHash: string;
  readonly paramsHash: string;
  readonly outputsHash: string;
  readonly tooling: Readonly<Record<string, string>>;
  readonly receiptClass: 'pipeline.stage.v1';
}

export interface PipelineResult<TStageName extends string, TFinal> {
  readonly pipelineId: string;
  readonly stages: readonly StageArtefact<TStageName>[];
  readonly final: TFinal;
  /** Optional terminal tabulated statistic; validated at write boundary. */
  readonly tabulatedStatistic?: TabulatedStatistic;
}

export interface StagedPipelineOptions {
  readonly pipelineId: string;
  readonly tooling: Readonly<Record<string, string>>;
  /** Hash function — accepts a stable JSON-serialisable value, returns a hex digest. */
  hash(value: unknown): string;
}

export class StagedPipeline {
  constructor(private readonly options: StagedPipelineOptions) {}

  async run<TStageName extends string, TInput, TFinal>(
    input: TInput,
    stages: readonly StageDefinition<TStageName, unknown, unknown>[],
    finaliser?: (last: unknown) => TabulatedStatistic | undefined,
  ): Promise<PipelineResult<TStageName, TFinal>> {
    if (stages.length === 0) {
      throw new Error('staged-pipeline: at least one stage is required');
    }
    const artefacts: StageArtefact<TStageName>[] = [];
    let current: unknown = input;
    for (let i = 0; i < stages.length; i++) {
      const stage = stages[i]!;
      const ctx: StageContext<TStageName> = {
        parentPipelineId: this.options.pipelineId,
        stageOrdinal: i,
        stageName: stage.name,
      };
      const inputsHash = this.options.hash(current);
      const paramsHash = this.options.hash(stage.params);
      const next = await stage.run(current, ctx);
      const outputsHash = this.options.hash(next);
      artefacts.push({
        stageName: stage.name,
        stageOrdinal: i,
        parentPipelineId: this.options.pipelineId,
        inputsHash,
        paramsHash,
        outputsHash,
        tooling: this.options.tooling,
        receiptClass: 'pipeline.stage.v1',
      });
      current = next;
    }
    const tabulatedStatistic = finaliser?.(current);
    if (tabulatedStatistic) validateTabulatedStatistic(tabulatedStatistic);
    const result: PipelineResult<TStageName, TFinal> = tabulatedStatistic
      ? {
          pipelineId: this.options.pipelineId,
          stages: artefacts,
          final: current as TFinal,
          tabulatedStatistic,
        }
      : {
          pipelineId: this.options.pipelineId,
          stages: artefacts,
          final: current as TFinal,
        };
    return result;
  }
}
