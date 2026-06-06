export type VariableType = 'assignment' | 'schedule' | 'route' | 'binary';

export interface Variable {
  id: string;
  label: string;
  type: VariableType;
  domain: string[];
}

/**
 * Semantic kind for constraint evaluation.
 * The solver evaluates each constraint by its kind + params — never by index.
 */
export type ConstraintKind =
  | 'unique-assignment'    // no two variables may take the same value
  | 'domain-exclusion'     // named variables must not take named values
  | 'adjacency-conflict'   // varA and varB must not share the same value
  | 'capacity-limit'       // each value may be used by ≤ maxCapacity variables
  | 'workload-balance'     // Gini of value distribution ≤ giniThreshold
  | 'preference'           // named variable should take one of preferredValues (soft)
  | 'coverage-frequency'   // targetValue must appear in ≥ minCount assignments
  | 'multi-modal-coverage'; // named variables should collectively cover same target (soft)

export interface ConstraintParams {
  /** For 'domain-exclusion': which vars are constrained */
  varIds?: string[];
  /** For 'domain-exclusion': values those vars must not take */
  excludedValues?: string[];
  /** For 'adjacency-conflict': first variable id */
  varA?: string;
  /** For 'adjacency-conflict': second variable id */
  varB?: string;
  /** For 'capacity-limit': max times a single value may be assigned */
  maxCapacity?: number;
  /** For 'workload-balance': Gini threshold above which penalty applies */
  giniThreshold?: number;
  /** For 'preference': which variable should express preference */
  varId?: string;
  /** For 'preference': values the variable should be assigned to */
  preferredValues?: string[];
  /** For 'coverage-frequency': the value that must appear frequently */
  targetValue?: string;
  /** For 'coverage-frequency': minimum number of assignments to targetValue */
  minCount?: number;
  /** For 'multi-modal-coverage': target values that should have multi-type coverage */
  targetValues?: string[];
}

export interface Constraint {
  id: string;
  label: string;
  type: 'hard' | 'soft';
  /** Semantic kind — used by the solver for evaluation, not index position */
  kind: ConstraintKind;
  params?: ConstraintParams;
  description: string;
}

/**
 * Semantic kind for objective evaluation.
 * Each objective evaluates a specific quality dimension of the assignment.
 */
export type ObjectiveKind =
  | 'minimize-hard-violations'  // reward maximizing hard constraint satisfaction
  | 'maximize-coverage'         // reward assigning variables to diverse domain values
  | 'maximize-balance'          // reward even distribution of assignments (low Gini)
  | 'minimize-conflicts'        // reward fewer same-value collisions
  | 'maximize-preferences';     // reward satisfying preference constraints

export interface ObjectiveWeight {
  id: string;
  label: string;
  weight: number;
  direction: 'maximize' | 'minimize';
  /** Semantic kind — used by the solver for evaluation */
  kind: ObjectiveKind;
}

export interface ProblemTemplate {
  id: string;
  label: string;
  domain: string;
  description: string;
  icon: string;
  accentColor: string;
  variables: Variable[];
  constraints: Constraint[];
  objectives: ObjectiveWeight[];
}

export const PROBLEM_TEMPLATES: ProblemTemplate[] = [
  {
    id: 'vessel-berth',
    label: 'Vessel Berth Assignment',
    domain: 'Maritime',
    description:
      'Assign vessels to berths across a 72-hour port window, minimizing demurrage costs while respecting draft limits, crane availability, and hazmat segregation.',
    icon: '⚓',
    accentColor: '#06b6d4',
    variables: [
      { id: 'v1', label: 'MAERSK AURORA',  type: 'assignment', domain: ['Berth-1', 'Berth-2', 'Berth-3', 'Berth-4'] },
      { id: 'v2', label: 'PACIFIC STAR',   type: 'assignment', domain: ['Berth-1', 'Berth-2', 'Berth-5'] },
      { id: 'v3', label: 'NEPTUNE GLORY',  type: 'assignment', domain: ['Berth-2', 'Berth-3', 'Berth-4'] },
      { id: 'v4', label: 'OCEAN EMPRESS',  type: 'assignment', domain: ['Berth-1', 'Berth-4', 'Berth-5'] },
      { id: 'v5', label: 'CAPE VICTORIA',  type: 'assignment', domain: ['Berth-3', 'Berth-4', 'Berth-5'] },
      { id: 'v6', label: 'ATLAS MERIDIAN', type: 'assignment', domain: ['Berth-1', 'Berth-2', 'Berth-5'] },
    ],
    constraints: [
      {
        id: 'c1', label: 'One vessel per berth', type: 'hard',
        kind: 'unique-assignment',
        description: 'No two vessels may share a berth at the same time window.',
      },
      {
        id: 'c2', label: 'Draft limit — Berth-1', type: 'hard',
        kind: 'domain-exclusion',
        params: { varIds: ['v3'], excludedValues: ['Berth-1'] },
        description: 'NEPTUNE GLORY (draft 14.2m) cannot use Berth-1 (max draft 13m).',
      },
      {
        id: 'c3', label: 'Hazmat segregation', type: 'hard',
        kind: 'adjacency-conflict',
        params: { varA: 'v2', varB: 'v3' },
        description: 'PACIFIC STAR (hazmat class B) must be separated from NEPTUNE GLORY.',
      },
      {
        id: 'c4', label: 'Crane priority', type: 'soft',
        kind: 'preference',
        params: { varId: 'v1', preferredValues: ['Berth-1'] },
        description: 'MAERSK AURORA (highest-value cargo) should prefer Berth-1 (twin-crane).',
      },
      {
        id: 'c5', label: 'Minimize idle time', type: 'soft',
        kind: 'workload-balance',
        params: { giniThreshold: 0.35 },
        description: 'All berths should be utilized — reward even distribution across berths.',
      },
    ],
    objectives: [
      { id: 'o1', label: 'Minimize demurrage cost',       weight: 0.45, direction: 'minimize', kind: 'minimize-conflicts' },
      { id: 'o2', label: 'Maximize berth utilization',    weight: 0.30, direction: 'maximize', kind: 'maximize-coverage' },
      { id: 'o3', label: 'Minimize cargo-handling risk',  weight: 0.15, direction: 'minimize', kind: 'minimize-hard-violations' },
      { id: 'o4', label: 'Maximize schedule reliability', weight: 0.10, direction: 'maximize', kind: 'maximize-preferences' },
    ],
  },
  {
    id: 'legal-staffing',
    label: 'Legal Matter Staffing',
    domain: 'Legal',
    description:
      'Assign attorneys and paralegals to 8 active matters over a two-week sprint, respecting conflict-of-interest rules, billing-rate caps, and seniority requirements.',
    icon: '⚖',
    accentColor: '#c9b787',
    variables: [
      { id: 'v1', label: 'Matter: Reyes v. Consolidated',   type: 'assignment', domain: ['Partner-A', 'Associate-1', 'Associate-2', 'Paralegal-1'] },
      { id: 'v2', label: 'Matter: IPO Filing — TechCo',     type: 'assignment', domain: ['Partner-B', 'Associate-3', 'Associate-4'] },
      { id: 'v3', label: 'Matter: Merger Review — HealthCo',type: 'assignment', domain: ['Partner-A', 'Partner-C', 'Associate-1'] },
      { id: 'v4', label: 'Matter: Patent Dispute — DrugCo', type: 'assignment', domain: ['Partner-B', 'Associate-2', 'Paralegal-2'] },
      { id: 'v5', label: 'Matter: SEC Investigation',       type: 'assignment', domain: ['Partner-C', 'Associate-3', 'Associate-4'] },
      { id: 'v6', label: 'Matter: Employment Class Action', type: 'assignment', domain: ['Partner-A', 'Associate-1', 'Paralegal-1', 'Paralegal-2'] },
    ],
    constraints: [
      {
        id: 'c1', label: 'Conflict of interest — Partner-A', type: 'hard',
        kind: 'adjacency-conflict',
        params: { varA: 'v1', varB: 'v3' },
        description: 'Partner-A cannot lead both Reyes v. Consolidated and HealthCo merger (former client overlap).',
      },
      {
        id: 'c2', label: 'Billing rate cap — IPO Filing', type: 'hard',
        kind: 'domain-exclusion',
        params: { varIds: ['v2'], excludedValues: ['Partner-B'] },
        description: 'IPO Filing has a blended rate cap of $450/hr — Partner-B ($650/hr) alone exceeds the cap.',
      },
      {
        id: 'c3', label: 'Seniority requirement — SEC', type: 'hard',
        kind: 'domain-exclusion',
        params: { varIds: ['v5'], excludedValues: ['Associate-3', 'Associate-4'] },
        description: 'SEC Investigation requires a Partner-level lead (regulatory matter).',
      },
      {
        id: 'c4', label: 'Workload balance', type: 'soft',
        kind: 'workload-balance',
        params: { giniThreshold: 0.40 },
        description: 'No attorney should carry a disproportionate share of matters.',
      },
      {
        id: 'c5', label: 'Client continuity', type: 'soft',
        kind: 'preference',
        params: { varId: 'v1', preferredValues: ['Associate-1'] },
        description: 'Associate-1 has prior history on Reyes v. Consolidated — prefer continuity.',
      },
    ],
    objectives: [
      { id: 'o1', label: 'Maximize matter coverage quality', weight: 0.40, direction: 'maximize', kind: 'minimize-hard-violations' },
      { id: 'o2', label: 'Minimize billing rate variance',   weight: 0.25, direction: 'minimize', kind: 'minimize-conflicts' },
      { id: 'o3', label: 'Maximize workload equity',         weight: 0.20, direction: 'maximize', kind: 'maximize-balance' },
      { id: 'o4', label: 'Maximize client continuity',       weight: 0.15, direction: 'maximize', kind: 'maximize-preferences' },
    ],
  },
  {
    id: 'defense-sensor',
    label: 'Defense Sensor Tasking',
    domain: 'Defense & Security',
    description:
      'Task 6 ISR assets (satellites, UAVs, ground sensors) to priority grid areas, balancing collection coverage, revisit rates, and threat-tiered priority.',
    icon: '⬡',
    accentColor: '#a78bfa',
    variables: [
      { id: 'v1', label: 'SAT-1 (SAR)',     type: 'assignment', domain: ['Grid-A1', 'Grid-B2', 'Grid-C3', 'Grid-D4'] },
      { id: 'v2', label: 'SAT-2 (EO)',      type: 'assignment', domain: ['Grid-A1', 'Grid-B2', 'Grid-E5', 'Grid-F6'] },
      { id: 'v3', label: 'UAV-ALPHA',       type: 'assignment', domain: ['Grid-C3', 'Grid-D4', 'Grid-G7'] },
      { id: 'v4', label: 'UAV-BRAVO',       type: 'assignment', domain: ['Grid-E5', 'Grid-F6', 'Grid-H8'] },
      { id: 'v5', label: 'GND-SENSOR-01',   type: 'assignment', domain: ['Grid-A1', 'Grid-B2'] },
      { id: 'v6', label: 'GND-SENSOR-02',   type: 'assignment', domain: ['Grid-G7', 'Grid-H8', 'Grid-I9'] },
    ],
    constraints: [
      {
        id: 'c1', label: 'Weather window — SAT-2 EO', type: 'hard',
        kind: 'domain-exclusion',
        params: { varIds: ['v2'], excludedValues: ['Grid-D4', 'Grid-F6'] },
        description: 'SAT-2 (EO) cannot task Grid-D4 or Grid-F6 — cloud cover 90%+ in next 24h.',
      },
      {
        id: 'c2', label: 'RF deconfliction — UAVs', type: 'hard',
        kind: 'adjacency-conflict',
        params: { varA: 'v3', varB: 'v4' },
        description: 'UAV-ALPHA and UAV-BRAVO cannot operate in the same grid (RF deconfliction).',
      },
      {
        id: 'c3', label: 'Tier-1 revisit — Grid-A1', type: 'hard',
        kind: 'coverage-frequency',
        params: { targetValue: 'Grid-A1', minCount: 2 },
        description: 'Grid-A1 (Tier-1 threat) must have at least two sensor passes for adequate revisit rate.',
      },
      {
        id: 'c4', label: 'Fuel/power budget — UAV-ALPHA', type: 'soft',
        kind: 'preference',
        params: { varId: 'v3', preferredValues: ['Grid-C3', 'Grid-D4'] },
        description: 'UAV-ALPHA should prefer extended loiter over single target rather than multi-grid hops.',
      },
      {
        id: 'c5', label: 'Multi-modal coverage', type: 'soft',
        kind: 'multi-modal-coverage',
        params: { varIds: ['v1', 'v2'], targetValues: ['Grid-A1', 'Grid-B2'] },
        description: 'Prefer SAR + EO sensor fusion on Tier-1 grids for higher confidence.',
      },
    ],
    objectives: [
      { id: 'o1', label: 'Maximize Tier-1 coverage',   weight: 0.45, direction: 'maximize', kind: 'maximize-coverage' },
      { id: 'o2', label: 'Minimize detection latency',  weight: 0.30, direction: 'minimize', kind: 'minimize-hard-violations' },
      { id: 'o3', label: 'Maximize sensor diversity',   weight: 0.15, direction: 'maximize', kind: 'maximize-balance' },
      { id: 'o4', label: 'Minimize asset exposure',     weight: 0.10, direction: 'minimize', kind: 'minimize-conflicts' },
    ],
  },
];

export const CUSTOM_TEMPLATE: ProblemTemplate = {
  id: 'custom',
  label: 'Custom Problem',
  domain: 'Custom',
  description: 'Define your own allocation or assignment problem.',
  icon: '◉',
  accentColor: '#06b6d4',
  variables: [],
  constraints: [],
  objectives: [
    { id: 'o1', label: 'Primary objective',   weight: 0.6, direction: 'maximize', kind: 'maximize-coverage' },
    { id: 'o2', label: 'Secondary objective', weight: 0.4, direction: 'minimize', kind: 'minimize-conflicts' },
  ],
};
