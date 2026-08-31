/**
 * Incident → Optimizer → Governance → Action/Proof pipeline.
 *
 * Wires Sentra's threat events end-to-end through the Guard Dog Brain:
 *   1. A Sentra Incident is enqueued as an optimizer problem (template
 *      selected by the incident's mitre stage / severity).
 *   2. The Ising solver runs with the active A11oy-derived constitution.
 *   3. Governance gate: solve.guardrailsPassed AND no critical violations.
 *      A blocked solve emits a `governance_block` proof and stops there.
 *   4. On approval, three side effects fire in the same async chain:
 *        a. emitProof(action_executed) to the A11oy fabric ledger
 *           (best-effort; if the orchestration API is unavailable the
 *           failure is recorded but does not block the pipeline).
 *        b. appendProofEntry to ROSIE's local proof ledger.
 *        c. appendResearchLogEntry to the local research log so the
 *           "Last evolved heuristic" tile updates in real time.
 *
 * The function returns a structured `PipelineRunResult` so the UI can
 * render a step-by-step audit trail.
 */
import { emitProof } from '@workspace/a11oy-orchestration/client';
import { solve, type AssignmentSolution } from './isingOptimizer';
import { PROBLEM_TEMPLATES } from '../data/optimizerTemplates';
import type { ProblemTemplate } from '../data/optimizerTemplates';
import type { RosieGuardrailClause } from '../data/a11oyConstitution';
import { appendProofEntry, type ProofEntry } from '../data/proofLedger';
import { appendResearchLogEntry, type ResearchLogEntry } from '../data/researchLog';

/**
 * Structural minimum the pipeline needs from an incident. Both
 * `sentra-twin.Incident` (seed catalog) and `sentra-api.Incident` (live
 * stream) are assignable to this shape — the pipeline does not read
 * `status`, which is the only field that differs between the two
 * sources, so unifying on this minimal shape avoids a strict-mode type
 * mismatch at the call site.
 */
export interface PipelineIncident {
  id: string;
  title: string;
  severity: 'critical' | 'high' | 'medium' | 'low';
  mitreStage: string;
  detectedAt: string;
  description: string;
  affectedAssets: string[];
}

export type PipelineStepStatus = 'pending' | 'running' | 'ok' | 'blocked' | 'error';

export interface PipelineStep {
  id: 'enqueue' | 'optimize' | 'governance' | 'a11oy-emit' | 'local-proof' | 'research';
  label: string;
  status: PipelineStepStatus;
  detail?: string;
}

export interface PipelineRunResult {
  incident: PipelineIncident;
  template: ProblemTemplate;
  solution: AssignmentSolution | null;
  steps: PipelineStep[];
  approved: boolean;
  proofEntry?: ProofEntry;
  researchEntry?: ResearchLogEntry;
  a11oyProofId?: string;
}

/**
 * Picks a problem template for an incident. Templates are matched by
 * Sentra-relevant domain heuristics; falls back to the first template
 * if no domain-specific match exists.
 */
function pickTemplateForIncident(incident: PipelineIncident): ProblemTemplate {
  const stage = incident.mitreStage.toLowerCase();
  if (stage.includes('exec') || stage.includes('lateral')) {
    return (
      PROBLEM_TEMPLATES.find((t) => t.id === 'sensor-tasking') ?? PROBLEM_TEMPLATES[0]
    );
  }
  if (stage.includes('access') || stage.includes('initial')) {
    return PROBLEM_TEMPLATES.find((t) => t.id === 'legal-staffing') ?? PROBLEM_TEMPLATES[0];
  }
  return PROBLEM_TEMPLATES[0];
}

export interface RunPipelineOptions {
  incident: PipelineIncident;
  constitution: RosieGuardrailClause[];
  constitutionVersion: string;
  constitutionSource: 'live' | 'fallback' | 'seed';
  /** Called after each step transitions so the UI can re-render. */
  onStep?: (steps: PipelineStep[]) => void;
}

export async function runIncidentPipeline(
  opts: RunPipelineOptions,
): Promise<PipelineRunResult> {
  const { incident, constitution, constitutionVersion, constitutionSource, onStep } = opts;

  const steps: PipelineStep[] = [
    { id: 'enqueue', label: 'Enqueue incident as optimizer problem', status: 'pending' },
    { id: 'optimize', label: 'Run Ising solver (A11oy-governed)', status: 'pending' },
    { id: 'governance', label: 'Constitutional governance gate', status: 'pending' },
    { id: 'a11oy-emit', label: 'Emit proof to A11oy fabric', status: 'pending' },
    { id: 'local-proof', label: 'Append signed proof to local ledger', status: 'pending' },
    { id: 'research', label: 'Append evolved heuristic to research log', status: 'pending' },
  ];
  const tick = (mutate: (s: PipelineStep[]) => void) => {
    mutate(steps);
    onStep?.([...steps]);
  };

  // 1. Enqueue
  const template = pickTemplateForIncident(incident);
  tick((s) => {
    s[0].status = 'ok';
    s[0].detail = `Selected template: ${template.label} (${template.domain})`;
  });

  // 2. Optimize
  tick((s) => { s[1].status = 'running'; });
  let solution: AssignmentSolution;
  try {
    solution = solve(template, constitution, constitutionVersion, constitutionSource);
  } catch (err) {
    tick((s) => {
      s[1].status = 'error';
      s[1].detail = `Solver crashed: ${String(err)}`;
    });
    return {
      incident, template, solution: null, steps, approved: false,
    };
  }
  tick((s) => {
    s[1].status = 'ok';
    s[1].detail = `Objective ${solution.objectiveScore.toFixed(3)} · ${solution.solveTimeMs}ms · ${solution.constraintResults.length} constraints`;
  });

  // 3. Governance gate — solve already ran the constitutional checks.
  tick((s) => { s[2].status = 'running'; });
  const approved = solution.guardrailsPassed && solution.guardrailViolations.length === 0;
  tick((s) => {
    s[2].status = approved ? 'ok' : 'blocked';
    s[2].detail = approved
      ? `All ${constitution.length} clauses satisfied`
      : `Blocked by: ${solution.guardrailViolations.join('; ') || 'guardrail check'}`;
  });

  if (!approved) {
    // Emit a governance_block proof so the operator can audit the rejection.
    let blockedProofId: string | undefined;
    try {
      const blocked = await emitProof({
        product: 'sentra',
        kind: 'governance_block',
        summary: `Incident ${incident.id} optimization blocked: ${solution.guardrailViolations.join('; ')}`,
        deepLink: `/sentra/brain/proofs`,
        payload: {
          incidentId: incident.id,
          templateId: template.id,
          guardrailViolations: solution.guardrailViolations,
          constitutionVersion,
        },
      });
      blockedProofId = blocked.id;
    } catch {
      // best-effort; pipeline result still records the block
    }
    return { incident, template, solution, steps, approved: false, a11oyProofId: blockedProofId };
  }

  // 4. A11oy fabric — explicit two-phase governance:
  //    a. emit action_approved (the routed approval decision recorded by
  //       the fabric on Sentra's behalf). If the fabric refuses (non-2xx),
  //       the action is treated as governance-blocked and the pipeline
  //       does not proceed to side effects.
  //    b. emit action_executed once the approval is acknowledged.
  // If the fabric is wholly unreachable (network error), we record the
  // step as degraded and proceed — local proof + research log still run
  // so single-product operation is not blocked by orchestration outages.
  // FAIL-CLOSED: any failure of the action_approved emit (non-2xx,
  // network error, missing credentials, transport error) aborts the
  // pipeline. Without an authoritative A11oy approval we MUST NOT
  // proceed to local proof or research side effects.
  tick((s) => { s[3].status = 'running'; });
  let a11oyProofId: string | undefined;
  let approval: Awaited<ReturnType<typeof emitProof>>;
  try {
    approval = await emitProof({
      product: 'sentra',
      kind: 'action_approved',
      summary: `A11oy approval: incident ${incident.id} (${incident.severity}) cleared for ${template.label}`,
      deepLink: `/sentra/brain/proofs`,
      payload: {
        incidentId: incident.id,
        templateId: template.id,
        constitutionVersion,
        guardrailsChecked: constitution.length,
      },
    });
  } catch (err) {
    const msg = String(err);
    // Distinguish substantive governance refusal from transport failure
    // for the operator's audit trail, but BOTH halt the pipeline.
    const isExplicitBlock = /\b(409|422|451)\b/.test(msg);
    tick((s) => {
      s[3].status = isExplicitBlock ? 'blocked' : 'error';
      s[3].detail = isExplicitBlock
        ? `A11oy governance refused: ${msg}`
        : `A11oy approval unavailable — pipeline halted (fail-closed): ${msg}`;
    });
    return { incident, template, solution, steps, approved: false };
  }

  try {
    const executed = await emitProof({
      product: 'sentra',
      kind: 'action_executed',
      summary: `Incident ${incident.id} (${incident.severity}) optimized via Guard Dog Brain — ${template.label}`,
      deepLink: `/sentra/brain/proofs`,
      payload: {
        incidentId: incident.id,
        templateId: template.id,
        objectiveScore: solution.objectiveScore,
        constitutionVersion,
        approvedByProofId: approval.id,
      },
    });
    a11oyProofId = executed.id;
    tick((s) => {
      s[3].status = 'ok';
      s[3].detail = `A11oy approved ${approval.id} → executed ${executed.id}`;
    });
  } catch (err) {
    // Approval was authoritative; only the execution-record emit failed.
    // Mark the step as degraded but continue: the action IS approved
    // and side effects MAY proceed.
    tick((s) => {
      s[3].status = 'error';
      s[3].detail = `A11oy approved ${approval.id} but action_executed emit failed: ${String(err)}`;
    });
  }

  // 5. Local proof ledger
  tick((s) => { s[4].status = 'running'; });
  const proofEntry = await appendProofEntry({
    inputs: { incidentId: incident.id, template: template.id, assignments: solution.assignments },
    problemId: template.id,
    problemLabel: `${template.label} ← incident ${incident.id}`,
    constitutionVersion: solution.constitutionVersion,
    constitutionSource: solution.constitutionSource,
    outcome: solution.improvementRatio > 0.5 ? 'optimal' : 'sub-optimal',
    objectiveScore: solution.objectiveScore,
    guardrailsChecked: constitution.length,
    guardrailsViolated: solution.guardrailViolations.length,
    solveTimeMs: solution.solveTimeMs,
    notes: `Triggered by Sentra incident: ${incident.title}`,
  });
  tick((s) => {
    s[4].status = 'ok';
    s[4].detail = `Local proof ${proofEntry.id}`;
  });

  // 6. Research log — record what the brain learned from this run.
  tick((s) => { s[5].status = 'running'; });
  const researchEntry = appendResearchLogEntry({
    title: `Heuristic evolved: ${template.domain} response to ${incident.mitreStage}`,
    source: 'incident-pipeline',
    incidentId: incident.id,
    problemId: template.id,
    distillation:
      `Incident "${incident.title}" mapped to ${template.label}. Solver converged at objective ` +
      `${solution.objectiveScore.toFixed(3)} after ${solution.solveTimeMs}ms with all ` +
      `${constitution.length} constitutional clauses satisfied. Assignment pattern recorded ` +
      `for future ${incident.mitreStage} responses.`,
    proofId: proofEntry.id,
  });
  tick((s) => {
    s[5].status = 'ok';
    s[5].detail = `Research entry ${researchEntry.id}`;
  });

  return {
    incident,
    template,
    solution,
    steps,
    approved: true,
    proofEntry,
    researchEntry,
    a11oyProofId,
  };
}
