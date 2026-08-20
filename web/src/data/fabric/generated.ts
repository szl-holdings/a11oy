import type { FabricSignal, FabricRisk, FabricDecision, FabricOutcome, FabricEvidence, VerticalId, SignalType, SignalStatus, RiskCategory, RiskStatus, DecisionType, DecisionStatus, EvidenceType, EvidenceStatus, PriorityLevel } from './types';

function mulberry32(seed: number) {
  return () => {
    seed |= 0; seed = seed + 0x6D2B79F5 | 0;
    let t = Math.imul(seed ^ seed >>> 15, 1 | seed);
    t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
    return ((t ^ t >>> 14) >>> 0) / 4294967296;
  };
}

function pick<T>(rng: () => number, arr: readonly T[]): T {
  return arr[Math.floor(rng() * arr.length)];
}

const VIDS: readonly VerticalId[] = ['terra', 'vessels', 'counsel', 'carlota', 'aegis', 'lyte', 'sentra', 'atlas'];
const TWIN_IDS: Record<VerticalId, string> = { terra: 'twin-terra', vessels: 'twin-vessels', counsel: 'twin-counsel', carlota: 'twin-carlota', aegis: 'twin-aegis', lyte: 'twin-lyte', sentra: 'twin-sentra', atlas: 'twin-atlas' };

const SIGNAL_TITLES: Record<VerticalId, readonly string[]> = {
  terra: ['Pipeline velocity declining in Southeast', 'Vendor SLA breach — HVAC contractor overdue', 'Occupancy below 92% threshold', 'Budget variance on renovation project', 'Inspection overdue — property TX-0412', 'Lease expiration approaching — 4 units', 'Document gap in acquisition package', 'Maintenance escalation — roof leak', 'Tenant complaint spike — noise issue', 'Cap rate compression signal', 'Property tax reassessment notice', 'Vendor insurance lapse detected', 'Environmental assessment pending', 'Parking lot resurfacing behind schedule', 'Fire suppression inspection overdue', 'Zoning variance hearing scheduled', 'Construction permit delay', 'Appraisal value divergence detected'],
  vessels: ['AIS gap detected — 4h dark window', 'Demurrage accruing at Rotterdam', 'Sanctions screening delayed', 'Weather disruption — typhoon track', 'Fuel cost spike — bunker prices up 8%', 'Port congestion at Singapore', 'Charter party clause conflict', 'Cargo temperature deviation', 'Crew certification expiring', 'Ballast water compliance gap', 'Hull inspection overdue', 'Route deviation detected — 12nm off course', 'Port state control deficiency', 'Bunker quality dispute', 'Insurance P&I renewal approaching', 'ETA variance exceeding 6h threshold', 'Cargo stowage plan conflict', 'Piracy risk zone transit planned'],
  counsel: ['Discovery deadline in 5 days', 'Missing medical records — claimant Jenkins', 'Filing status change — Motion granted', 'Expert witness availability conflict', 'Deposition scheduling gap', 'Statute of limitations approaching', 'Settlement demand received', 'Opposing counsel motion filed', 'Document production incomplete', 'Privilege review needed — 200 docs', 'Court scheduling conflict', 'Mediation window opening', 'Insurance coverage dispute', 'Witness statement inconsistency', 'New evidence received — surveillance', 'Appellate brief deadline approaching', 'Pro hac vice application needed'],
  carlota: ['Landscaping vendor behind schedule', 'HVAC maintenance window approaching', 'Guest arrival coordination gap', 'Pool service reliability concern', 'Staff NDA processing incomplete', 'Wine cellar temperature alert', 'Security system firmware update due', 'Seasonal transition prep needed', 'Art collection insurance renewal', 'Vehicle maintenance schedule conflict', 'Catering vendor confirmation pending', 'Smart home system update available', 'Garden irrigation system fault', 'Guest suite preparation needed', 'Holiday decoration timeline starting', 'Household inventory audit due'],
  aegis: ['Critical CVE detected — 12 assets exposed', 'Identity anomaly — lateral movement attempt', 'MFA bypass rate increased 3x', 'Vulnerability backlog at 14d MTTR', 'Access review overdue — 340 identities', 'Backup verification gap — 3 systems', 'Firewall rule change — unauthorized', 'Endpoint agent offline — 8 devices', 'Phishing campaign detected', 'Certificate expiration — production TLS', 'Privileged access spike detected', 'Security baseline drift — 12 controls', 'Data loss prevention alert', 'Third-party access review overdue', 'SIEM correlation rule gap', 'Cloud configuration drift detected', 'API key rotation overdue', 'Network segmentation violation'],
  lyte: ['Revenue KPI 4% below Q2 target', 'Initiative milestone slipped 2 weeks', 'Ownership gap — team lead transition', 'Decision delay — pricing approval 8d', 'Board reporting gap — Q1 narrative', 'Dependency blockage — API integration', 'Budget variance — marketing overspend', 'Stakeholder alignment gap detected', 'Strategic initiative stalled — 3 weeks', 'Customer churn signal — enterprise tier', 'Hiring pipeline behind target', 'Product roadmap conflict detected', 'Cross-department dependency unresolved', 'OKR progress behind schedule', 'Executive escalation — customer issue', 'Competitor launch detected', 'Partnership negotiation stalled'],
  sentra: ['Policy exception requested — Terra vendor', 'Rollback triggered — firewall rule reverted', 'Audit compilation deadline — SOC 2', 'Policy bypass attempt blocked', 'Approval queue depth — 8 items stale', 'Secret detected in log output', 'Cross-vertical policy conflict found', 'Rollback readiness test failed', 'Governance SLA approaching breach', 'Approval delegation chain broken', 'Policy version conflict detected', 'Emergency override used — audit required', 'Evidence chain gap — 2 controls', 'Approval latency exceeding 48h SLA', 'Policy enforcement exception logged', 'Audit finding remediation overdue', 'Access control policy update needed'],
  atlas: ['Fed rate decision repricing risk exposure', 'FX hedge drift — EUR/USD beyond band', 'Liquidity coverage ratio nearing floor', 'Counterparty credit downgrade flagged', 'Covenant breach risk — portfolio company', 'Cash sweep shortfall detected', 'Mark-to-market swing exceeds VaR limit', 'Invoice aging spike — DSO climbing', 'Treasury settlement break unresolved', 'Yield curve inversion signal', 'Portfolio concentration limit approached', 'Margin call risk — collateral shortfall', 'Audit adjustment pending — revenue recognition', 'Budget variance — opex overrun', 'Working capital gap widening', 'Dividend coverage ratio declining', 'Interest coverage weakening'],
};

const SIG_TYPES: readonly SignalType[] = ['risk', 'opportunity', 'deadline', 'anomaly', 'drift', 'compliance', 'cost', 'vendor', 'document', 'operational', 'security', 'legal_workflow', 'executive_decision'];
const SIG_STATUSES: readonly SignalStatus[] = ['new', 'triaged', 'routed', 'approved', 'resolved', 'deferred', 'blocked'];
const SEVERITIES: readonly PriorityLevel[] = ['critical', 'high', 'medium', 'low'];
const SOURCES: readonly string[] = ['System monitor', 'Operator report', 'Automated scan', 'Vendor notification', 'External feed', 'Scheduled check', 'Anomaly detector', 'Threshold alert'];

const rng = mulberry32(42);

function ts(i: number): string {
  const base = new Date('2026-04-01T00:00:00Z').getTime();
  const offset = Math.floor(i * 7200000 + rng() * 3600000);
  return new Date(base + offset).toISOString();
}

export const FABRIC_SIGNALS: readonly FabricSignal[] = VIDS.flatMap((vid, vi) => {
  const titles = SIGNAL_TITLES[vid];
  return titles.map((title, ti): FabricSignal => {
    const idx = vi * 18 + ti;
    return {
      id: `sig-${vid}-${String(ti + 1).padStart(3, '0')}`,
      verticalId: vid,
      twinId: TWIN_IDS[vid],
      title,
      description: `${title}. Detected by ${pick(rng, SOURCES)} and routed to ${vid} operations for review.`,
      signalType: pick(rng, SIG_TYPES),
      source: pick(rng, SOURCES),
      severity: pick(rng, SEVERITIES),
      confidence: Math.round((0.65 + rng() * 0.3) * 100) / 100,
      timestamp: ts(idx),
      relatedEntity: `${vid.toUpperCase()}-${String(Math.floor(rng() * 9000 + 1000))}`,
      recommendedAction: `Review and triage: ${title.toLowerCase()}`,
      sentraReviewRequired: rng() > 0.6,
      chainlightScenarioId: `chl-${vid}-${String(ti + 1).padStart(3, '0')}`,
      proofChainAnchorId: `pca-${vid}-${String(ti + 1).padStart(3, '0')}`,
      status: pick(rng, SIG_STATUSES),
    };
  });
});

const RISK_TITLES: Record<VerticalId, readonly string[]> = {
  terra: ['Deal slippage on Dallas industrial portfolio', 'Budget overrun risk — Miami renovation', 'Lease expiration cluster — Q3 2026', 'Vendor failure — electrical subcontractor', 'Compliance gap — fire code violation', 'Asset degradation — parking structure', 'Property tax appeal deadline risk', 'Environmental remediation exposure', 'Tenant default — anchor tenant', 'Occupancy rate decline trajectory', 'Insurance coverage gap — flood zone', 'Capital reserve depletion risk'],
  vessels: ['Sanctions exposure — Black Sea route', 'Weather disruption — Pacific typhoon track', 'Fuel cost spike propagation', 'Port congestion delay cascade', 'Charter party default risk', 'Crew visa expiration — 4 seafarers', 'Hull condition — class survey overdue', 'Cargo damage liability — reefer malfunction', 'P&I insurance coverage gap', 'Ballast water treatment system failure', 'Piracy risk — Gulf of Aden transit', 'Demurrage cost escalation'],
  counsel: ['Evidentiary gap — Rodriguez depositions', 'Deadline cluster — 4 filings in 72h', 'Expert witness conflict — Dr. Chen', 'Statute of limitations exposure', 'Adverse discovery ruling risk', 'Settlement authority gap', 'Privilege waiver risk — document review', 'Opposing expert report quality gap', 'Court scheduling conflict — parallel matters', 'Insurance coverage dispute escalation', 'Witness credibility challenge', 'Appeal deadline proximity'],
  carlota: ['Vendor reliability — pool service', 'Privacy exposure — staff onboarding', 'Seasonal transition delay', 'Security system vulnerability', 'Wine collection insurance lapse', 'Household staff retention risk', 'Property maintenance backlog', 'Guest experience quality gap', 'Smart home integration failure', 'Art storage climate control issue'],
  aegis: ['Critical vulnerability backlog — 14d MTTR', 'Access review overdue — 340 identities', 'Backup verification gap — 3 systems', 'Endpoint protection coverage gap', 'Certificate expiration cascade risk', 'Third-party vendor access exposure', 'Cloud misconfiguration propagation', 'API security posture degradation', 'SIEM detection coverage gap', 'Privileged access management drift', 'Data exfiltration vector — unmonitored', 'Security baseline erosion trend'],
  lyte: ['Execution drift — 3 strategic initiatives', 'Pricing model decision delay', 'Board reporting completeness gap', 'Revenue target miss trajectory', 'Talent pipeline quality decline', 'Product roadmap dependency conflict', 'Customer churn acceleration signal', 'Cross-department handoff failure', 'OKR coverage gap — 2 departments', 'Strategic initiative resource gap', 'Partnership deal stall risk'],
  sentra: ['Policy bypass attempt pattern', 'Audit evidence gap — 3 controls', 'Approval queue stale items', 'Cross-vertical policy contradiction', 'Rollback readiness degradation', 'Secret exposure — log scanning gap', 'Governance SLA breach trajectory', 'Policy version synchronization gap', 'Emergency override pattern concern'],
  atlas: ['Interest rate shock — duration mismatch', 'Liquidity crunch — coverage ratio breach', 'Counterparty default exposure — top 3 names', 'FX translation loss — unhedged exposure', 'Covenant breach — portfolio company leverage', 'Credit concentration — single sector 38%', 'Working capital shortfall trajectory', 'Fraud exposure — payment controls gap', 'Revenue recognition audit risk', 'Mark-to-market volatility breach', 'Refinancing risk — maturity wall 2027', 'Margin/collateral shortfall risk'],
};

const EV_TITLES: Record<VerticalId, readonly string[]> = {
  terra: ['Property appraisal report — TX-0412', 'Vendor SLA compliance log — Q1 2026', 'Inspection report — fire suppression system', 'Lease agreement — anchor tenant renewal', 'Budget approval — Miami renovation', 'Environmental assessment — Phase I report', 'Property tax assessment notice — Dallas', 'Maintenance work order — roof repair', 'Tenant complaint log — noise abatement', 'Insurance certificate — flood coverage', 'Capital improvement plan — parking lot', 'Vendor insurance verification — HVAC contractor', 'Zoning variance application', 'Construction permit — electrical upgrade', 'Property condition assessment — annual'],
  vessels: ['AIS track log — MV Horizon Star', 'Sanctions screening report — OFAC', 'Bunker delivery receipt — Rotterdam', 'Charter party agreement — TC-2026-041', 'Port state control report — Singapore', 'Hull condition survey — class certificate', 'Cargo manifest — bill of lading', 'Weather routing report — Pacific crossing', 'Fuel quality test certificate', 'Crew certification bundle — officers', 'P&I insurance policy — annual renewal', 'Demurrage calculation worksheet', 'Ballast water treatment log', 'Voyage P&L settlement — VY-2026-018', 'Piracy risk assessment — Gulf transit'],
  counsel: ['Discovery response — CM-2024-0891', 'Medical records — claimant Jenkins', 'Expert report — Dr. Chen biomechanics', 'Deposition transcript — witness Rodriguez', 'Filing receipt — Motion to Dismiss', 'Settlement demand letter — $1.2M', 'Privilege log — document review batch', 'Court order — scheduling conference', 'Insurance coverage opinion — excess layer', 'Mediation brief — joint session prep', 'Opposing counsel motion — summary judgment', 'Witness statement — accident reconstruction', 'Appellate brief draft — final version', 'Document production log — batch 3', 'Expert engagement letter — Dr. Park'],
  carlota: ['Vendor service agreement — landscaping', 'Staff NDA — new hire batch Q2', 'Security system audit report', 'Wine cellar inventory — annual', 'Smart home system configuration log', 'Guest preference registry — updated', 'Art collection appraisal — 2026', 'Household maintenance schedule — Q2', 'HVAC service record — primary residence', 'Vehicle maintenance log — fleet', 'Catering vendor contract — events', 'Holiday preparation checklist', 'Irrigation system maintenance record', 'Guest suite inspection report', 'Insurance policy — art collection'],
  aegis: ['Vulnerability scan report — Q2 2026', 'Access review completion certificate', 'Backup recovery drill results', 'Penetration test report — external', 'Certificate inventory — production TLS', 'SIEM rule update changelog', 'Firewall rule audit report', 'Endpoint agent deployment manifest', 'Phishing simulation results — April', 'Cloud security baseline assessment', 'DLP policy coverage report', 'Incident response drill after-action', 'Third-party vendor security assessment', 'Security awareness training completion', 'API security scan results'],
  lyte: ['Revenue KPI dashboard — Q2 tracking', 'Initiative status report — Platform v3', 'Board meeting minutes — March 2026', 'Decision log — pricing model review', 'OKR scorecard — Q1 final', 'Cross-department dependency matrix', 'Marketing ROI analysis — Q1 campaigns', 'Customer retention report — enterprise', 'Hiring pipeline status — engineering', 'Strategic plan — FY2027 draft', 'Stakeholder survey results — alignment', 'Budget variance report — marketing', 'Partnership term sheet — draft', 'Product roadmap — Q3 plan', 'Executive escalation log — Q1'],
  sentra: ['Policy exception log — Q1 2026', 'Rollback execution record — firewall', 'SOC 2 Type II evidence bundle', 'Approval queue audit report', 'Policy version control log', 'Secret scanning coverage report', 'Governance SLA compliance dashboard', 'Emergency override justification log', 'Cross-vertical policy alignment matrix', 'Approval delegation chain registry', 'Audit finding remediation tracker', 'Policy contradiction analysis report', 'Access control policy — v3.2', 'Blocked action register — Q1', 'Governance training completion log'],
  atlas: ['Treasury position report — daily cash', 'FX hedge ledger — Q2 2026', 'Liquidity coverage ratio worksheet', 'Counterparty credit memo — top exposures', 'Covenant compliance certificate — Q1', 'VaR model output — portfolio', 'Accounts receivable aging report', 'Bank reconciliation — settlement breaks', 'Board finance pack — March 2026', 'Audit adjustment log — revenue', 'Budget vs actual — opex detail', 'Debt schedule — maturity ladder', 'Investment mandate compliance report', 'Cash flow forecast — 13-week', 'Capital allocation memo — 2026'],
};

const RISK_CATS: readonly RiskCategory[] = ['operational', 'financial', 'legal_workflow', 'security', 'compliance', 'vendor', 'asset', 'deadline', 'reputation', 'data_quality', 'decision_delay', 'control_drift'];
const RISK_STATS: readonly RiskStatus[] = ['open', 'mitigating', 'accepted', 'closed'];
const OWNERS: readonly string[] = ['J. Martinez', 'S. Chen', 'A. Patel', 'M. Johnson', 'R. Williams', 'K. Nakamura', 'D. Thompson', 'L. Garcia', 'B. Anderson', 'T. Robinson'];
const MITIGATIONS: readonly string[] = ['Escalate to domain lead', 'Apply compensating control', 'Schedule remediation sprint', 'Request additional evidence', 'Trigger approval workflow', 'Deploy interim workaround', 'Engage vendor for resolution', 'Activate contingency plan'];

export const FABRIC_RISKS: readonly FabricRisk[] = VIDS.flatMap((vid) => {
  const titles = RISK_TITLES[vid];
  return titles.map((title, ti): FabricRisk => {
    const prob = Math.round((0.2 + rng() * 0.7) * 100) / 100;
    const impact = Math.round((0.3 + rng() * 0.6) * 100) / 100;
    const velocity = Math.round((0.5 + rng() * 0.5) * 100) / 100;
    return {
      id: `risk-${vid}-${String(ti + 1).padStart(3, '0')}`,
      verticalId: vid,
      twinId: TWIN_IDS[vid],
      title,
      description: `${title}. Requires mitigation and monitoring through the Command Fabric governance layer.`,
      riskCategory: pick(rng, RISK_CATS),
      riskScore: Math.round(prob * impact * velocity * 100),
      probability: prob,
      impact,
      velocity,
      owner: pick(rng, OWNERS),
      mitigation: pick(rng, MITIGATIONS),
      approvalRequired: rng() > 0.4,
      evidenceIds: [`ev-${vid}-${String((ti * 2) % EV_TITLES[vid].length + 1).padStart(3, '0')}`, `ev-${vid}-${String((ti * 2 + 1) % EV_TITLES[vid].length + 1).padStart(3, '0')}`],
      relatedSignals: [`sig-${vid}-${String(ti + 1).padStart(3, '0')}`],
      status: pick(rng, RISK_STATS),
      route: `/fabric/risks?id=risk-${vid}-${String(ti + 1).padStart(3, '0')}`,
    };
  });
});

const DEC_TITLES: Record<VerticalId, readonly string[]> = {
  terra: ['Advance Dallas industrial acquisition', 'Approve HVAC vendor replacement', 'Budget exception — Miami capex overage', 'Renew anchor tenant lease at revised terms', 'Engage environmental consultant', 'Approve property tax appeal filing', 'Schedule capital improvement — parking', 'Authorize emergency roof repair', 'Approve vendor insurance waiver'],
  vessels: ['Approve route deviation — weather avoidance', 'Escalate sanctions screening to compliance', 'Authorize bunker procurement — spot market', 'Approve demurrage claim filing', 'Schedule hull inspection — dry dock', 'Accept charter party amendment', 'Approve crew overtime — port operations', 'Authorize cargo re-stowage', 'Escalate piracy risk — re-route decision'],
  counsel: ['Prepare discovery response packet', 'Authorize settlement negotiation range', 'Retain backup expert witness', 'File motion for extension', 'Approve document production scope', 'Schedule mediation session', 'Authorize deposition transcript rush', 'Approve expert report engagement', 'File appellate brief — proceed decision'],
  carlota: ['Engage replacement pool vendor', 'Approve staff bonus — holiday season', 'Schedule wine cellar maintenance', 'Authorize security system upgrade', 'Approve guest suite renovation', 'Engage landscape redesign vendor', 'Schedule art collection appraisal', 'Authorize smart home platform migration'],
  aegis: ['Deploy critical CVE patch — production', 'Approve emergency access review', 'Schedule backup recovery drill', 'Authorize firewall rule rollback', 'Approve endpoint agent mass update', 'Engage third-party pentest vendor', 'Authorize certificate rotation — all prod', 'Approve SIEM rule update package', 'Escalate identity anomaly investigation'],
  lyte: ['Approve pricing model revision', 'Assign interim Data Engineering lead', 'Authorize marketing budget reallocation', 'Approve initiative pivot — Platform v3', 'Schedule board strategy session', 'Approve cross-department resource share', 'Authorize customer retention package', 'Escalate partnership negotiation', 'Approve OKR target revision'],
  sentra: ['Grant Terra vendor fast-track exception', 'Approve policy update — access controls', 'Authorize rollback readiness test', 'Approve audit evidence remediation plan', 'Grant emergency override retrospective', 'Approve cross-vertical policy alignment', 'Authorize secret scanning expansion', 'Approve governance SLA revision'],
  atlas: ['Approve FX hedge rebalance', 'Authorize liquidity buffer increase', 'Escalate counterparty exposure reduction', 'Approve covenant waiver negotiation', 'Reallocate capital — portfolio rebalance', 'Authorize short-term financing draw', 'Approve revenue recognition treatment', 'Escalate credit concentration remediation', 'Approve budget variance exception'],
};

const DEC_TYPES: readonly DecisionType[] = ['approve_vendor', 'escalate_risk', 'adjust_route', 'request_evidence', 'assign_owner', 'approve_patch', 'update_policy', 'schedule_service', 'advance_deal', 'prepare_attorney_packet', 'close_exception'];
const DEC_STATS: readonly DecisionStatus[] = ['draft', 'awaiting_review', 'approved', 'rejected', 'executed', 'deferred'];

export const FABRIC_DECISIONS: readonly FabricDecision[] = VIDS.flatMap((vid) => {
  const titles = DEC_TITLES[vid];
  return titles.map((title, ti): FabricDecision => {
    const opts = ['Approve as proposed', 'Approve with conditions', 'Defer for additional review', 'Reject — insufficient evidence'];
    return {
      id: `dec-${vid}-${String(ti + 1).padStart(3, '0')}`,
      verticalId: vid,
      twinId: TWIN_IDS[vid],
      title,
      decisionType: pick(rng, DEC_TYPES),
      summary: `${title}. Decision routed through Command Fabric for governance review and human approval.`,
      options: opts,
      recommendedOption: pick(rng, opts),
      chainlightConfidence: Math.round((0.7 + rng() * 0.25) * 100) / 100,
      sentraApprovalState: pick(rng, DEC_STATS),
      humanOwner: pick(rng, OWNERS),
      deadline: new Date(Date.now() + Math.floor(rng() * 14 * 86400000)).toISOString().slice(0, 10),
      evidenceIds: [`ev-${vid}-${String(ti % EV_TITLES[vid].length + 1).padStart(3, '0')}`],
      expectedOutcome: `Successful resolution of: ${title.toLowerCase()}`,
      downsideRisk: `Delay or failure in: ${title.toLowerCase()}`,
      status: pick(rng, DEC_STATS),
    };
  });
});

const OUTCOME_TEMPLATES: Record<VerticalId, readonly { predicted: string; actual: string; lesson: string }[]> = {
  terra: [
    { predicted: 'Deal closes within 45 days', actual: 'Deal closed in 52 days — vendor delay', lesson: 'Build 15% buffer into deal timelines for vendor dependencies' },
    { predicted: 'Occupancy stabilizes above 93%', actual: 'Occupancy reached 94.2%', lesson: 'Tenant retention incentives effective at current rate' },
    { predicted: 'Budget holds within 5% variance', actual: 'Budget exceeded by 7% — material cost spike', lesson: 'Lock material pricing at contract signing for renovations' },
    { predicted: 'Vendor remediation within SLA', actual: 'Vendor completed 1 day early', lesson: 'Escalation protocol effective for SLA enforcement' },
    { predicted: 'Lease renewal at market rate', actual: 'Renewal at 2% below market — tenant retention priority', lesson: 'Below-market renewals acceptable when vacancy cost exceeds discount' },
    { predicted: 'Inspection closes clean', actual: 'Inspection flagged minor electrical issue', lesson: 'Pre-inspection walkthroughs reduce surprise findings by 60%' },
    { predicted: 'Property tax appeal reduces assessment 8%', actual: 'Assessment reduced 6%', lesson: 'Comparable selection methodology needs refinement for suburban properties' },
    { predicted: 'Environmental assessment clears', actual: 'Phase I clean — no further action', lesson: 'Pre-screening with desktop review saves 40% on clean sites' },
    { predicted: 'Capital improvement on schedule', actual: 'Completed 3 weeks late — permit delay', lesson: 'Submit permit applications 30 days earlier for municipality X' },
    { predicted: 'Vendor replacement improves SLA', actual: 'New vendor meeting 98% SLA — improvement confirmed', lesson: 'Vendor scorecard system accurately predicts replacement outcomes' },
    { predicted: 'Tenant complaint resolution within 48h', actual: 'Resolved in 36h', lesson: 'Dedicated response team reduces complaint resolution time 25%' },
    { predicted: 'Cap rate holds within 10bps', actual: 'Cap rate compressed 15bps — market movement', lesson: 'Monthly market comps needed for volatile submarkets' },
  ],
  vessels: [
    { predicted: 'Voyage completes within ETA window', actual: 'Arrived 8h late — weather deviation', lesson: 'Weather-adjusted ETA models need 12h buffer for monsoon season' },
    { predicted: 'Sanctions screening clears', actual: 'Cleared after 3 additional checks', lesson: 'Pre-screening reduces clearance time by 40% for repeat counterparties' },
    { predicted: 'Fuel cost within 5% of estimate', actual: 'Fuel cost 3% under estimate', lesson: 'Slow steaming saves 6-8% fuel on Pacific routes in current market' },
    { predicted: 'No demurrage incurred', actual: 'Demurrage at $12,000 — port congestion', lesson: 'Singapore congestion patterns predictable with 5-day AIS density analysis' },
    { predicted: 'Charter renewed at improved rate', actual: 'Charter renewed — rate flat', lesson: 'Market leverage limited in current oversupply conditions' },
    { predicted: 'Route optimization saves 2 days', actual: 'Saved 1.5 days — current adjustment needed', lesson: 'Real-time ocean current data improves route optimization by 20%' },
    { predicted: 'AIS coverage maintained 100%', actual: 'AIS gap of 2h detected — equipment malfunction', lesson: 'AIS equipment redundancy reduces dark window risk significantly' },
    { predicted: 'Port state control passes clean', actual: 'One deficiency noted — fire equipment', lesson: 'Monthly fire equipment checks prevent PSC deficiencies' },
    { predicted: 'Cargo loaded within window', actual: 'Loading delayed 6h — crane availability', lesson: 'Pre-book cranes 72h in advance for high-traffic ports' },
    { predicted: 'Ballast water treatment compliant', actual: 'Compliant — treatment system functioned correctly', lesson: 'Quarterly calibration maintains treatment effectiveness' },
    { predicted: 'Insurance P&I renewal at same terms', actual: 'Renewal with 5% premium increase — claims history', lesson: 'Loss prevention investment reduces P&I premiums over 24-month horizon' },
    { predicted: 'Crew rotation on schedule', actual: 'Rotation delayed 2 days — visa processing', lesson: 'Begin visa processing 45 days before rotation date' },
  ],
  counsel: [
    { predicted: 'Discovery response filed on time', actual: 'Filed 1 day early', lesson: 'Assembly buffer of 3 days prevents deadline stress' },
    { predicted: 'Evidence completeness reaches 95%', actual: 'Reached 92% — 3 records outstanding', lesson: 'Medical records requests should begin at matter intake, not discovery' },
    { predicted: 'Expert deposition strengthens case', actual: 'Expert performance rated strong by attorney', lesson: 'Pre-deposition prep session improves expert performance significantly' },
    { predicted: 'Settlement within authority range', actual: 'Settlement below authority — favorable outcome', lesson: 'Evidence quality drives settlement outcomes more than negotiation tactics' },
    { predicted: 'Filing accepted by court', actual: 'Accepted — no deficiencies', lesson: 'Court-specific formatting checklists eliminate rejection risk' },
    { predicted: 'Mediation produces resolution', actual: 'Mediation reached partial agreement', lesson: 'Pre-mediation brief exchange improves resolution rate by 30%' },
    { predicted: 'Document production complete', actual: 'Completed with 2 privilege log additions', lesson: 'Privilege review automation reduces manual review time by 50%' },
    { predicted: 'Expert report quality meets threshold', actual: 'Report exceeded expectations — comprehensive analysis', lesson: 'Detailed expert engagement letter produces better work product' },
    { predicted: 'Motion granted in full', actual: 'Motion granted in part — partial relief', lesson: 'Narrower motions with targeted relief tend to succeed more fully' },
    { predicted: 'Matter cycle time within benchmark', actual: 'Cycle time 10% below benchmark', lesson: 'Early case assessment reduces overall matter duration consistently' },
    { predicted: 'Attorney review completed on schedule', actual: 'Review completed — 2 issues flagged', lesson: 'Structured review checklists catch 30% more issues than narrative review' },
    { predicted: 'Court date maintained', actual: 'Court date held as scheduled', lesson: 'Proactive judge communication reduces continuance risk' },
  ],
  carlota: [
    { predicted: 'Vendor service window maintained', actual: 'Window maintained — vendor arrived on time', lesson: 'Confirmed vendor 24h in advance reduces no-show rate to near zero' },
    { predicted: 'Preference honored for event', actual: 'All preferences met — guest satisfaction high', lesson: 'Preference registry with version dates prevents stale preference errors' },
    { predicted: 'Maintenance completed before season', actual: 'Completed 1 week before deadline', lesson: 'Seasonal maintenance calendar with 2-week buffer works well' },
    { predicted: 'Staff onboarding completed securely', actual: 'All NDAs processed — background checks clear', lesson: 'Parallel processing of NDA and background check saves 5 days' },
    { predicted: 'Smart home update deployed cleanly', actual: 'Update successful — one device required manual restart', lesson: 'Phased rollout to non-critical devices first reduces disruption risk' },
    { predicted: 'Guest experience rated excellent', actual: 'Experience rated excellent by principal', lesson: 'Pre-arrival walkthrough with checklist ensures quality consistently' },
    { predicted: 'Art collection appraisal on schedule', actual: 'Appraisal completed — 2 pieces need re-evaluation', lesson: 'Market-based appraisals should be refreshed annually for volatile categories' },
    { predicted: 'Security system upgrade completed', actual: 'Upgrade completed — firmware verified', lesson: 'Vendor-managed firmware updates more reliable than self-managed' },
    { predicted: 'Wine cellar temperature maintained', actual: 'Temperature held within 0.5F of target', lesson: 'Dual-sensor monitoring catches HVAC drift before threshold breach' },
    { predicted: 'Holiday prep completed on time', actual: 'Prep completed 2 days early', lesson: 'Starting holiday prep 6 weeks out instead of 4 reduces stress' },
  ],
  aegis: [
    { predicted: 'Critical CVE patched within 72h', actual: 'Patched in 48h — accelerated deployment', lesson: 'Pre-approved emergency patch workflow reduces MTTR by 40%' },
    { predicted: 'Access review completes within SLA', actual: 'Completed — 12 accounts deprovisioned', lesson: 'Automated access review reminders increase completion rate by 60%' },
    { predicted: 'Backup recovery drill succeeds', actual: 'Recovery successful — 2h RTO achieved', lesson: 'Quarterly drills maintain team readiness and verify backup integrity' },
    { predicted: 'Endpoint agent coverage reaches 100%', actual: 'Coverage at 99.2% — 3 legacy devices excluded', lesson: 'Legacy device exemption policy needed with compensating controls' },
    { predicted: 'Certificate rotation completed clean', actual: 'All certificates rotated — no service disruption', lesson: 'Automated certificate management eliminates manual rotation errors' },
    { predicted: 'Pentest report clean of critical findings', actual: 'One high finding identified — remediated in 5d', lesson: 'Continuous pentest engagement catches issues between annual assessments' },
    { predicted: 'SIEM rules tuned — false positive rate drops', actual: 'False positive rate reduced 35%', lesson: 'Quarterly SIEM tuning sprints maintain detection quality' },
    { predicted: 'Firewall rule cleanup reduces attack surface', actual: 'Removed 42 unused rules — 15% reduction', lesson: 'Monthly firewall hygiene reviews prevent rule bloat' },
    { predicted: 'Phishing simulation — click rate below 5%', actual: 'Click rate at 3.2%', lesson: 'Monthly micro-training more effective than quarterly deep sessions' },
    { predicted: 'Cloud configuration aligned to baseline', actual: 'Aligned — 2 exceptions documented', lesson: 'Infrastructure-as-code enforcement prevents configuration drift' },
    { predicted: 'DLP policy covers all sensitive data types', actual: 'Coverage at 94% — 2 new data types identified', lesson: 'Data classification refresh needed quarterly for evolving data landscape' },
    { predicted: 'Incident response drill completes successfully', actual: 'Drill completed — communication gap identified', lesson: 'Include business stakeholders in IR drills, not just security team' },
  ],
  lyte: [
    { predicted: 'Revenue KPI recovers to target', actual: 'Recovery to 98% of target — gap closing', lesson: 'Early intervention on KPI drift prevents full-quarter misses' },
    { predicted: 'Initiative milestone back on track', actual: 'Milestone achieved with 3-day delay', lesson: 'Dedicated resource allocation for blocked initiatives accelerates recovery' },
    { predicted: 'Ownership gap resolved within 2 weeks', actual: 'Interim owner assigned in 5 days', lesson: 'Pre-identified succession candidates reduce ownership gap duration' },
    { predicted: 'Decision velocity improves 20%', actual: 'Velocity improved 15%', lesson: 'Decision deadline enforcement alone improves velocity by 10-15%' },
    { predicted: 'Board report quality meets standard', actual: 'Board report rated excellent', lesson: 'Structured narrative template plus data dashboard improves board satisfaction' },
    { predicted: 'Cross-department dependency resolved', actual: 'Dependency resolved — API delivered', lesson: 'Weekly cross-department standup prevents dependency escalations' },
    { predicted: 'Marketing ROI within expected range', actual: 'ROI exceeded expectation by 12%', lesson: 'Data-driven campaign selection outperforms intuition-based allocation' },
    { predicted: 'Customer retention campaign effective', actual: 'Churn reduced 8% in target segment', lesson: 'Proactive outreach before renewal window doubles retention rate' },
    { predicted: 'Hiring pipeline fills target roles', actual: 'Filled 80% of target roles — 2 remaining', lesson: 'Structured interview process reduces time-to-hire by 20%' },
    { predicted: 'OKR attainment reaches 80%', actual: 'OKR attainment at 76%', lesson: 'Quarterly OKR check-ins with calibration improve end-of-period attainment' },
    { predicted: 'Partnership deal closes', actual: 'Deal closed with modified terms', lesson: 'Flexibility on non-critical terms accelerates partnership closure' },
  ],
  sentra: [
    { predicted: 'Policy exception resolved within SLA', actual: 'Resolved in 20h — within 24h SLA', lesson: 'Pre-defined exception criteria reduce review time by 50%' },
    { predicted: 'Rollback executed cleanly', actual: 'Rollback successful — no service impact', lesson: 'Automated rollback scripts with pre-validated checkpoints are essential' },
    { predicted: 'Audit evidence gap closed', actual: 'Gap closed — 3 controls now have attestation', lesson: 'Continuous evidence collection prevents audit-time scrambles' },
    { predicted: 'Approval queue depth returns to normal', actual: 'Queue depth normalized within 48h', lesson: 'Auto-escalation for stale approvals prevents queue buildup' },
    { predicted: 'Policy contradiction resolved', actual: 'Contradiction resolved — unified policy issued', lesson: 'Cross-vertical policy review board prevents contradictions at creation time' },
    { predicted: 'Secret scanning coverage expanded', actual: 'Coverage expanded to all repositories', lesson: 'Automated secret scanning in CI/CD pipeline catches 95% of exposures' },
    { predicted: 'Governance SLA maintained', actual: 'SLA maintained — 99.1% compliance', lesson: 'SLA monitoring dashboards drive accountability without manual tracking' },
    { predicted: 'Emergency override audit completed', actual: 'Audit completed — all overrides justified', lesson: 'Real-time override justification capture simplifies retrospective audit' },
    { predicted: 'Policy version sync achieved', actual: 'All verticals on latest policy version', lesson: 'Automated policy distribution with acknowledgment tracking ensures coverage' },
    { predicted: 'Approval delegation chain repaired', actual: 'Chain repaired — backup reviewers assigned', lesson: 'Mandatory backup reviewer assignment prevents delegation chain failures' },
  ],
  atlas: [
    { predicted: 'FX hedge holds within band', actual: 'EUR/USD drifted 2.1% beyond band before rebalance', lesson: 'Tighten hedge rebalance triggers to 1.5% for major pairs' },
    { predicted: 'Liquidity coverage stays above 110%', actual: 'Coverage dipped to 104% — settlement timing', lesson: 'Stagger large settlements to protect intraday liquidity' },
    { predicted: 'Counterparty exposure reduced 20%', actual: 'Reduced 17% — one novation delayed', lesson: 'Start novation paperwork 10 days before quarter-end' },
    { predicted: 'Covenant headroom maintained', actual: 'Headroom held at 0.4x above trigger', lesson: 'Monthly covenant forecasting prevents surprise breaches' },
    { predicted: 'Opex variance within 3%', actual: 'Variance 4.5% — vendor price escalations', lesson: 'Index major vendor contracts to lock pricing bands' },
    { predicted: 'DSO improves to 42 days', actual: 'DSO improved to 45 — enterprise cohort lag', lesson: 'Segment collections cadence by customer tier' },
    { predicted: 'Refinancing closes at target spread', actual: 'Closed 15bps wide — market volatility', lesson: 'Pre-market refinancing windows reduce spread risk' },
    { predicted: 'VaR stays within limit', actual: 'VaR breached limit on 1 day — rate shock', lesson: 'Add rate-shock scenario to daily VaR overlay' },
    { predicted: 'Cash forecast accurate within 5%', actual: 'Forecast within 3% — model tuning effective', lesson: '13-week rolling model with actuals feedback improves accuracy' },
  ],
};

export const FABRIC_OUTCOMES: readonly FabricOutcome[] = VIDS.flatMap((vid) => {
  const templates = OUTCOME_TEMPLATES[vid];
  return templates.map((t, ti): FabricOutcome => {
    const predErr = Math.round(rng() * 25) / 100;
    const rBefore = Math.round((0.4 + rng() * 0.5) * 100) / 100;
    return {
      id: `out-${vid}-${String(ti + 1).padStart(3, '0')}`,
      verticalId: vid,
      twinId: TWIN_IDS[vid],
      originatingDecisionId: `dec-${vid}-${String(Math.min(ti + 1, DEC_TITLES[vid].length)).padStart(3, '0')}`,
      predictedOutcome: t.predicted,
      actualOutcome: t.actual,
      predictionError: predErr,
      rewardScore: Math.round((0.6 + rng() * 0.35) * 100) / 100,
      riskBefore: rBefore,
      riskAfter: Math.round(rBefore * (0.3 + rng() * 0.5) * 100) / 100,
      evidenceCompleteness: Math.round((0.8 + rng() * 0.18) * 100) / 100,
      operatorFeedback: rng() > 0.5 ? 'Outcome aligned with expectation' : 'Minor variance — acceptable',
      lessonLearned: t.lesson,
      policyUpdateCandidate: rng() > 0.6,
      reviewed: rng() > 0.3,
      route: `/fabric/outcomes?id=out-${vid}-${String(ti + 1).padStart(3, '0')}`,
    };
  });
});

const EV_TYPES: readonly EvidenceType[] = ['document', 'ticket', 'email_summary', 'system_event', 'scanner_result', 'inspection_note', 'legal_workflow_note', 'voyage_signal', 'vendor_update', 'executive_decision', 'approval_record', 'audit_event', 'policy_clause'];
const EV_SOURCES: readonly string[] = ['Internal system', 'Vendor portal', 'Court filing system', 'Port authority', 'Compliance platform', 'Manual entry', 'Automated collection', 'External audit'];
const EV_STATS: readonly EvidenceStatus[] = ['collected', 'verified', 'disputed', 'archived'];

export const FABRIC_EVIDENCE: readonly FabricEvidence[] = VIDS.flatMap((vid) => {
  const titles = EV_TITLES[vid];
  return titles.map((title, ti): FabricEvidence => ({
    id: `ev-${vid}-${String(ti + 1).padStart(3, '0')}`,
    verticalId: vid,
    title,
    evidenceType: pick(rng, EV_TYPES),
    sourceSystem: pick(rng, EV_SOURCES),
    summary: `${title}. Collected and anchored in the Proof Chain for auditability.`,
    authorityScore: Math.round((0.6 + rng() * 0.35) * 100) / 100,
    relatedSignals: [`sig-${vid}-${String(Math.min(ti + 1, SIGNAL_TITLES[vid].length)).padStart(3, '0')}`],
    relatedRisks: [`risk-${vid}-${String(Math.min(ti + 1, RISK_TITLES[vid].length)).padStart(3, '0')}`],
    relatedDecisions: [`dec-${vid}-${String(Math.min(ti + 1, DEC_TITLES[vid].length)).padStart(3, '0')}`],
    relatedOutcomes: [`out-${vid}-${String(Math.min(ti + 1, OUTCOME_TEMPLATES[vid].length)).padStart(3, '0')}`],
    proofChainAnchorId: `pca-${vid}-${String(ti + 1).padStart(3, '0')}`,
    status: pick(rng, EV_STATS),
    route: `/fabric/evidence?id=ev-${vid}-${String(ti + 1).padStart(3, '0')}`,
  }));
});
