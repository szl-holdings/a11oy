/**
 * @szl-holdings/a11oy-knowledge — Vertical Policy Router
 * Author: Lutar, Stephen P. · ORCID 0009-0001-0110-4173 · Apache-2.0
 * Source: publications_harvest/publications_harvest/verticals/
 */
import type { VerticalPolicy } from './schema.js';

export const VERTICAL_POLICIES: VerticalPolicy[] = [
  {
    id: 'defense',
    name: 'Defense / DoD',
    regulations: ['NIST SP 800-53', 'CMMC 2.0', 'FedRAMP High', 'DISA STIGs', 'ATO framework'],
    required_attestors: ['authorizing_official', 'system_owner', 'security_control_assessor'],
    lambda_floors: {
      moralGrounding: 0.99, measurabilityHonesty: 0.99, actionReversibility: 0.95,
      scopeContainment: 0.99, informationIntegrity: 0.99, consentBoundary: 0.95,
      temporalConsistency: 0.95, stakeholderAlignment: 0.95, evidenceAdequacy: 0.99,
    },
    primitives_applicable: ['A1','A4','A5','A6','A8','A9','A12','A13','T5','T9','T10','TH1'],
    policy_yaml_path: 'policies/defense.policy.yaml',
    acv_range_usd: { low: 500000, mid: 2000000, high: 5000000 },
    sales_cycle_months: 18,
  },
  {
    id: 'financial_services',
    name: 'Financial Services / Banking',
    regulations: ['SR 11-7', 'OCC 2011-12', 'Basel III model risk', 'MiFID II RTS 6', 'FINRA Rule 3110'],
    required_attestors: ['model_risk_officer', 'chief_risk_officer', 'internal_audit'],
    lambda_floors: {
      moralGrounding: 0.97, measurabilityHonesty: 0.99, actionReversibility: 0.95,
      scopeContainment: 0.97, informationIntegrity: 0.99, consentBoundary: 0.95,
      temporalConsistency: 0.99, stakeholderAlignment: 0.95, evidenceAdequacy: 0.99,
      economicGrounding: 1.0,
    },
    primitives_applicable: ['A1','A5','A6','A8','A9','A14','T5','T9','T10','TH1','TH2'],
    policy_yaml_path: 'policies/financial_services.policy.yaml',
    acv_range_usd: { low: 200000, mid: 800000, high: 2000000 },
    sales_cycle_months: 12,
  },
  {
    id: 'healthcare',
    name: 'Healthcare / Clinical AI',
    regulations: ['HIPAA 45 CFR §164', 'FDA 21 CFR Part 11', 'FDA SaMD guidance', 'ONC HTI-1 rule'],
    required_attestors: ['licensed_clinician', 'clinical_informatics_officer', 'compliance_officer'],
    lambda_floors: {
      moralGrounding: 0.99, measurabilityHonesty: 0.99, actionReversibility: 0.90,
      scopeContainment: 0.99, informationIntegrity: 0.99, consentBoundary: 0.99,
      causalSeparability: 0.99, constructiveTransparency: 0.99,
    },
    primitives_applicable: ['A1','A4','A5','A8','A9','A11','A12','T5','T7','T10','TH1'],
    policy_yaml_path: 'policies/healthcare.policy.yaml',
    acv_range_usd: { low: 150000, mid: 600000, high: 2000000 },
    sales_cycle_months: 14,
  },
  {
    id: 'insurance',
    name: 'Insurance',
    regulations: ['NAIC Model Law 881', 'NY DFS Circular Letter 1 (2019)', 'NY DFS Circular Letter 7 (2022)', 'NAIC AI principles'],
    required_attestors: ['chief_actuary', 'compliance_officer', 'ai_ethics_board'],
    lambda_floors: {
      moralGrounding: 0.97, measurabilityHonesty: 0.99, informationIntegrity: 0.99,
      constructiveTransparency: 0.99, economicGrounding: 0.97,
    },
    primitives_applicable: ['A1','A5','A8','A9','A12','A14','T6','T9','T10'],
    policy_yaml_path: 'policies/insurance.policy.yaml',
    acv_range_usd: { low: 200000, mid: 750000, high: 2000000 },
    sales_cycle_months: 10,
  },
  {
    id: 'legal',
    name: 'Legal / e-Discovery',
    regulations: ['FRCP 26', 'FRCP 34', 'FRE 902(13)', 'FRE 902(14)', 'ABA Model Rule 1.1'],
    required_attestors: ['supervising_attorney', 'records_custodian'],
    lambda_floors: {
      moralGrounding: 0.97, measurabilityHonesty: 0.99, informationIntegrity: 0.99,
      actionReversibility: 0.95, consentBoundary: 0.97, constructiveTransparency: 0.99,
    },
    primitives_applicable: ['A5','A6','A8','A12','T5','T8','T10','TH2'],
    policy_yaml_path: 'policies/legal.policy.yaml',
    acv_range_usd: { low: 75000, mid: 300000, high: 1000000 },
    sales_cycle_months: 8,
  },
  {
    id: 'public_sector',
    name: 'Public Sector / Civic AI',
    regulations: ['EU AI Act Annex III', 'NYC Local Law 144', 'NIST AI RMF', 'OMB M-24-10'],
    required_attestors: ['agency_ai_officer', 'civil_rights_officer', 'procurement_officer'],
    lambda_floors: {
      moralGrounding: 0.99, measurabilityHonesty: 0.99, stakeholderAlignment: 0.99,
      constructiveTransparency: 1.0, consentBoundary: 0.99, adversarialRobustness: 0.95,
    },
    primitives_applicable: ['A1','A5','A8','A12','A13','T6','T10','TH1','TH3'],
    policy_yaml_path: 'policies/public_sector.policy.yaml',
    acv_range_usd: { low: 300000, mid: 1200000, high: 5000000 },
    sales_cycle_months: 24,
  },
  {
    id: 'pharma',
    name: 'Pharma / Life Sciences R&D',
    regulations: ['FDA 21 CFR Part 11', 'GxP guidelines', 'EMA Annex 11', 'ICH E6(R3) GCP'],
    required_attestors: ['qualified_person', 'computational_scientist', 'gxp_compliance_officer'],
    lambda_floors: {
      moralGrounding: 0.97, measurabilityHonesty: 1.0, informationIntegrity: 1.0,
      temporalConsistency: 0.99, constructiveTransparency: 1.0,
    },
    primitives_applicable: ['A5','A6','A8','A10','A12','T5','TH2'],
    policy_yaml_path: 'policies/pharma.policy.yaml',
    acv_range_usd: { low: 500000, mid: 2000000, high: 10000000 },
    sales_cycle_months: 18,
  },
  {
    id: 'critical_infrastructure',
    name: 'Critical Infrastructure / Utilities',
    regulations: ['NERC CIP-013', 'IEC 62443-3-3', 'TSA Security Directives (pipelines/rail)', 'NIST CSF 2.0'],
    required_attestors: ['system_security_officer', 'control_systems_engineer', 'incident_commander'],
    lambda_floors: {
      moralGrounding: 0.99, actionReversibility: 0.99, scopeContainment: 1.0,
      informationIntegrity: 0.99, adversarialRobustness: 0.99, temporalConsistency: 0.99,
    },
    primitives_applicable: ['A4','A5','A6','A10','A13','T5','T9','T10','TH1'],
    policy_yaml_path: 'policies/critical_infrastructure.policy.yaml',
    acv_range_usd: { low: 1000000, mid: 5000000, high: 20000000 },
    sales_cycle_months: 24,
  },
  {
    id: 'capital_markets',
    name: 'Capital Markets / Quant / Hedge Funds',
    regulations: ['SEC Rule 17a-4', 'MiFID II RTS 6', 'FINRA Rule 4370', 'Reg SCI'],
    required_attestors: ['chief_compliance_officer', 'quant_review_committee', 'external_auditor'],
    lambda_floors: {
      moralGrounding: 0.97, measurabilityHonesty: 1.0, temporalConsistency: 1.0,
      economicGrounding: 1.0, constructiveTransparency: 0.99, informationIntegrity: 0.99,
    },
    primitives_applicable: ['A5','A6','A10','A12','A14','T5','T9','TH2'],
    policy_yaml_path: 'policies/capital_markets.policy.yaml',
    acv_range_usd: { low: 500000, mid: 2000000, high: 10000000 },
    sales_cycle_months: 12,
  },
  {
    id: 'academic',
    name: 'Academic / Research Integrity',
    regulations: ['NIH NOT-OD-23-149', 'NSF PAPPG CH2', 'ORI research integrity standards', 'Elsevier COPE guidelines'],
    required_attestors: ['principal_investigator', 'research_integrity_officer'],
    lambda_floors: {
      measurabilityHonesty: 1.0, constructiveTransparency: 1.0, informationIntegrity: 0.99,
      temporalConsistency: 0.99,
    },
    primitives_applicable: ['A5','A8','A12','T5','T10','TH2'],
    policy_yaml_path: 'policies/academic.policy.yaml',
    acv_range_usd: { low: 10000, mid: 50000, high: 200000 },
    sales_cycle_months: 6,
  },
];

export const getPolicyForVertical = (vertical_id: string): VerticalPolicy | undefined =>
  VERTICAL_POLICIES.find(v => v.id === vertical_id);

export const getTopVerticalsByDensity = (n = 3): VerticalPolicy[] =>
  [...VERTICAL_POLICIES]
    .sort((a, b) => b.primitives_applicable.length - a.primitives_applicable.length)
    .slice(0, n);
