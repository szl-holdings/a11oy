export type ThreatActor = 'APT28' | 'APT41' | 'Lazarus' | 'MuddyWater' | 'CISA-Generic' | 'Insider';
export type AttackCategory = 'ransomware' | 'supply-chain' | 'insider' | 'ot-ics' | 'bec' | 'cloud' | 'deepfake' | 'multi-vector';
export type ScenarioRole = 'CISO' | 'Legal' | 'Comms' | 'CEO';
export type DecisionQuality = 'optimal' | 'suboptimal' | 'harmful';

export interface MitreTag {
  id: string;
  name: string;
  tactic: string;
}

export interface DecisionOption {
  id: string;
  label: string;
  description: string;
  quality: DecisionQuality;
  consequence: string;
  scoreDelta: number;
  nextPhaseId?: string;
  regComplianceImpact?: string;
}

export interface Inject {
  id: string;
  at_second: number;
  title: string;
  body: string;
  role?: ScenarioRole;
}

export interface DecisionPoint {
  id: string;
  phaseId: string;
  role: ScenarioRole;
  question: string;
  context: string;
  options: DecisionOption[];
  timeLimitSec: number;
}

export interface Phase {
  id: string;
  order: number;
  title: string;
  description: string;
  durationSec: number;
  injects: Inject[];
  decisionPoints: DecisionPoint[];
}

export interface CrisisScenario {
  id: string;
  title: string;
  subtitle: string;
  category: AttackCategory;
  threatActor: ThreatActor;
  adversaryProfile: string;
  sourceRef: string;
  difficulty: 'entry' | 'intermediate' | 'advanced' | 'nation-state';
  estimatedMinutes: number;
  roles: ScenarioRole[];
  phases: Phase[];
  mitreTags: MitreTag[];
  background: string;
}

const APT28_RANSOMWARE: CrisisScenario = {
  id: 'apt28-ransomware-campaign',
  title: 'Operation Phantom Grid',
  subtitle: 'APT28 Ransomware with Data Exfiltration',
  category: 'ransomware',
  threatActor: 'APT28',
  adversaryProfile: 'GRU Unit 26165 — targets NATO-aligned logistics, defense contractors, and government entities. Known for FANCY BEAR TTPs including spearphishing, credential harvesting via X-Agent, and deployment of NotPetya-variant wipers.',
  sourceRef: 'MITRE ATT&CK G0007 · NSA/CISA Advisory AA20-296A · FBI Flash MC-000126-MW',
  difficulty: 'nation-state',
  estimatedMinutes: 45,
  roles: ['CISO', 'Legal', 'Comms', 'CEO'],
  mitreTags: [
    { id: 'T1566.001', name: 'Spearphishing Attachment', tactic: 'Initial Access' },
    { id: 'T1486', name: 'Data Encrypted for Impact', tactic: 'Impact' },
    { id: 'T1041', name: 'Exfiltration Over C2 Channel', tactic: 'Exfiltration' },
    { id: 'T1078', name: 'Valid Accounts', tactic: 'Persistence' },
  ],
  background: 'Your organization, a NATO-aligned logistics firm, has been targeted. An employee in procurement opened a spearphishing email disguised as a DHL shipping document. Initial EDR alerts are firing on multiple endpoints.',
  phases: [
    {
      id: 'ph1-detection',
      order: 1,
      title: 'Initial Detection',
      description: 'EDR alerts indicate ransomware execution on 3 endpoints in the Warsaw logistics hub. Network segmentation may be compromised.',
      durationSec: 600,
      injects: [
        { id: 'inj1', at_second: 120, title: 'CRITICAL: Domain Controller Compromised', body: 'Intelligence confirms the domain controller at WA-DC-01 has been accessed using stolen credentials. Adversary has domain admin rights.', role: 'CISO' },
        { id: 'inj2', at_second: 300, title: 'Data Exfil Detected', body: '47 GB of procurement records and supplier contracts transferred to external Mega.nz account over the past 6 hours. Exfil appears to predate encryption.', role: 'Legal' },
      ],
      decisionPoints: [
        {
          id: 'dp1-contain',
          phaseId: 'ph1-detection',
          role: 'CISO',
          question: 'EDR has identified 3 encrypted endpoints and a compromised domain controller. What is your immediate containment decision?',
          context: 'You have 47 GB already exfiltrated. The ransomware is still propagating. Cutting all network access will halt operations for an estimated 8-12 hours.',
          timeLimitSec: 90,
          options: [
            { id: 'opt-a', label: 'Isolate affected segment immediately', description: 'Cut VLAN 42 (logistics hub) from corporate network. Accept operational impact.', quality: 'optimal', consequence: 'Propagation halted. Operational impact confirmed. 3 systems encrypted total.', scoreDelta: 25, nextPhaseId: 'ph2-escalation' },
            { id: 'opt-b', label: 'Monitor and gather more intel first', description: 'Continue observing for 30 minutes to map full scope before acting.', quality: 'suboptimal', consequence: 'Additional 12 systems encrypted during delay. Exfil reaches 89 GB.', scoreDelta: -10, nextPhaseId: 'ph2-escalation' },
            { id: 'opt-c', label: 'Shut down entire corporate network', description: 'Full network kill switch — halt all operations globally.', quality: 'suboptimal', consequence: 'Propagation stopped but $4.2M operational downtime initiated. Board escalation required.', scoreDelta: 0, nextPhaseId: 'ph2-escalation' },
          ],
        },
      ],
    },
    {
      id: 'ph2-escalation',
      order: 2,
      title: 'Crisis Escalation',
      description: 'Ransomware demand received. $4.2M in Monero within 72 hours or data published. Legal and comms implications emerge.',
      durationSec: 480,
      injects: [
        { id: 'inj3', at_second: 60, title: 'Ransomware Note Received', body: 'Threat actor demands $4.2M in Monero within 72 hours. Threatens to publish supplier contracts and personal data of 12,000 employees on their leak site "PhantomLeaks.onion".', role: 'CEO' },
        { id: 'inj4', at_second: 240, title: 'Media Inquiry', body: 'Reuters has contacted your PR team asking about "reports of a cyberattack affecting your Warsaw operations." You have 2 hours before they publish with or without comment.', role: 'Comms' },
      ],
      decisionPoints: [
        {
          id: 'dp2-ransom',
          phaseId: 'ph2-escalation',
          role: 'CEO',
          question: 'The ransomware demand is $4.2M. Your cyber insurance covers up to $3M. Do you engage with the threat actor?',
          context: 'CISA guidance advises against payment but does not prohibit it. FBI recommends immediate notification. OFAC sanctions may apply if actor is state-sponsored.',
          timeLimitSec: 120,
          options: [
            { id: 'opt-a', label: 'Do not pay — engage FBI and CISA immediately', description: 'Notify law enforcement, begin recovery from backups.', quality: 'optimal', consequence: 'FBI engaged. OFAC sanctions risk avoided. Recovery timeline 5-7 days. Data may be published.', scoreDelta: 30, regComplianceImpact: 'GDPR Art.33 72hr notification clock starts.' },
            { id: 'opt-b', label: 'Engage negotiator to buy time', description: 'Open back-channel with threat actor via negotiation firm to delay and gather intelligence.', quality: 'suboptimal', consequence: 'Buys 48hrs. Intelligence gathered on actor infrastructure. OFAC risk elevated.', scoreDelta: 5 },
            { id: 'opt-c', label: 'Pay ransom immediately', description: 'Transfer $4.2M to halt the clock.', quality: 'harmful', consequence: 'OFAC violation likely ($5M+ fine). No guarantee data not published. Encourages further attacks. FBI notified regardless.', scoreDelta: -40, regComplianceImpact: 'OFAC 31 CFR Part 578 potential violation.' },
          ],
        },
        {
          id: 'dp3-comms',
          phaseId: 'ph2-escalation',
          role: 'Comms',
          question: 'Reuters is 2 hours from publishing. What is your external communications strategy?',
          context: 'You have confirmed data exfiltration of employee PII. GDPR notification to DPA is required within 72 hours of awareness. You have not yet fully scoped the breach.',
          timeLimitSec: 90,
          options: [
            { id: 'opt-a', label: 'Proactive press statement with limited details', description: 'Issue statement acknowledging incident, outlining response, protecting employee data without scope details.', quality: 'optimal', consequence: 'Controls narrative. Demonstrates transparency. Regulatory credit for proactive disclosure.', scoreDelta: 20 },
            { id: 'opt-b', label: 'No comment until full scope known', description: 'Decline to comment until breach is fully scoped.', quality: 'suboptimal', consequence: 'Reuters publishes "company refuses to comment" story. Reputational damage escalates.', scoreDelta: -5 },
            { id: 'opt-c', label: 'Full transparency — share all known details', description: 'Issue detailed statement including number of records affected and ransom demand.', quality: 'harmful', consequence: 'Creates shareholder panic and additional media feeding frenzy. Board demands emergency meeting.', scoreDelta: -15 },
          ],
        },
      ],
    },
    {
      id: 'ph3-recovery',
      order: 3,
      title: 'Recovery & Regulatory Response',
      description: 'GDPR 72-hour notification window closing. Recovery operations underway. Board briefing required.',
      durationSec: 360,
      injects: [
        { id: 'inj5', at_second: 60, title: 'GDPR Clock — 68 Hours Elapsed', body: 'Your DPA notification deadline is in 4 hours. Legal has confirmed that 12,847 EU resident employee records were in the exfiltrated dataset.', role: 'Legal' },
        { id: 'inj6', at_second: 200, title: 'Backup Integrity Question', body: 'IT team reports that backups from the past 3 days are also encrypted. The most recent clean backup is 4 days old. Recovery will take 72 hours minimum.', role: 'CISO' },
      ],
      decisionPoints: [
        {
          id: 'dp4-gdpr',
          phaseId: 'ph3-recovery',
          role: 'Legal',
          question: 'With 4 hours remaining on GDPR notification, what is your regulatory response?',
          context: 'You have confirmed 12,847 EU resident records were exfiltrated. Full scope is not yet known. GDPR Article 33 requires notification to DPA within 72 hours of "becoming aware."',
          timeLimitSec: 90,
          options: [
            { id: 'opt-a', label: 'File preliminary GDPR notification now with available information', description: 'Notify DPA with known facts, commit to supplement within 72 hours.', quality: 'optimal', consequence: 'GDPR compliance maintained. DPA receptive to phased notification. Regulatory cooperation credit.', scoreDelta: 25, regComplianceImpact: 'GDPR Art.33 compliant. No fine exposure for late notification.' },
            { id: 'opt-b', label: 'Wait 3 more hours to complete scope assessment', description: 'Use remaining time to nail down full affected population before filing.', quality: 'suboptimal', consequence: 'Narrow window risks missing deadline. If missed, fine exposure €10M or 2% global revenue.', scoreDelta: -5 },
            { id: 'opt-c', label: 'Delay notification — claim uncertainty about "awareness" trigger date', description: 'Argue legally that the clock started later to buy more preparation time.', quality: 'harmful', consequence: 'DPA takes aggressive view. €18M fine + reputational damage as deliberate concealment narrative emerges.', scoreDelta: -35, regComplianceImpact: 'GDPR Art.83 maximum fine exposure + potential criminal referral.' },
          ],
        },
      ],
    },
  ],
};

const APT41_SUPPLY_CHAIN: CrisisScenario = {
  id: 'apt41-supply-chain-backdoor',
  title: 'Operation Jade Mirror',
  subtitle: 'APT41 Supply Chain Backdoor via Trusted Vendor',
  category: 'supply-chain',
  threatActor: 'APT41',
  adversaryProfile: 'MSS-affiliated dual espionage/financial threat actor. Targets software supply chains, healthcare, telecoms, and financial services. Known for HIGHNOON implant, POISONPLUG backdoors, and signed malware via compromised build servers.',
  sourceRef: 'MITRE ATT&CK G0096 · CISA AA21-048A · DOJ Indictment 2020 · ATT&CK T1195.002',
  difficulty: 'nation-state',
  estimatedMinutes: 40,
  roles: ['CISO', 'Legal', 'CEO'],
  mitreTags: [
    { id: 'T1195.002', name: 'Compromise Software Supply Chain', tactic: 'Initial Access' },
    { id: 'T1553.002', name: 'Code Signing', tactic: 'Defense Evasion' },
    { id: 'T1071.001', name: 'Web Protocols C2', tactic: 'Command and Control' },
    { id: 'T1213', name: 'Data from Information Repositories', tactic: 'Collection' },
  ],
  background: 'CISA has issued a flash advisory that a widely-used enterprise HR software vendor (TalentraHR) has had its build server compromised. A malicious update (v4.7.2) was pushed to 2,300 organizations including yours 18 days ago. Your SecOps team has confirmed the update is installed on 340 endpoints.',
  phases: [
    {
      id: 'ph1-triage',
      order: 1,
      title: 'Vendor Compromise Confirmed',
      description: 'CISA advisory confirmed. Your vendor installed the backdoor 18 days ago. APT41 has had persistent access for 18 days. Scope unknown.',
      durationSec: 540,
      injects: [
        { id: 'inj1', at_second: 90, title: 'Backdoor C2 Traffic Identified', body: 'Threat hunting team has identified C2 beaconing from the HR software process on 12 finance department workstations to a known APT41 infrastructure cluster (104.21.x.x). HR data access logs show bulk export of employee compensation and benefits data 9 days ago.', role: 'CISO' },
        { id: 'inj2', at_second: 300, title: 'Vendor Notification Received', body: 'TalentraHR has issued a breach notification citing "unauthorized access to their build pipeline." They are offering a "clean" v4.7.3 update. They deny any customer data exfiltration.', role: 'Legal' },
      ],
      decisionPoints: [
        {
          id: 'dp1-vendor',
          phaseId: 'ph1-triage',
          role: 'CISO',
          question: 'TalentraHR has released a "clean" update v4.7.3 and is urging all customers to upgrade immediately. Your threat hunting team has not completed their investigation. Do you apply the update?',
          context: 'Applying a vendor update from a vendor with a compromised build pipeline carries risk. Not applying leaves known-backdoored software running on 340 endpoints.',
          timeLimitSec: 90,
          options: [
            { id: 'opt-a', label: 'Quarantine all endpoints running TalentraHR — do not apply update', description: 'Isolate affected systems. Verify v4.7.3 hash against CISA indicators before any update.', quality: 'optimal', consequence: 'HR operations halted but second-stage compromise prevented. CISA confirms v4.7.3 is clean 6 hours later.', scoreDelta: 30, nextPhaseId: 'ph2-scope' },
            { id: 'opt-b', label: 'Apply vendor update to trusted finance systems only', description: 'Partial remediation of highest-risk systems while maintaining business continuity on others.', quality: 'suboptimal', consequence: 'Partial risk reduction. APT41 pivots from remaining non-updated systems. Investigation ongoing.', scoreDelta: 5, nextPhaseId: 'ph2-scope' },
            { id: 'opt-c', label: 'Apply v4.7.3 update across all 340 endpoints immediately', description: 'Follow vendor guidance to remediate quickly.', quality: 'harmful', consequence: 'CISA later confirms v4.7.3 also contains a secondary payload. Full re-infection of 340 endpoints.', scoreDelta: -45, nextPhaseId: 'ph2-scope' },
          ],
        },
      ],
    },
    {
      id: 'ph2-scope',
      order: 2,
      title: 'Scope & Data Assessment',
      description: 'Forensics reveals 18 days of access. Compensation data, M&A deal documents, and employee records confirmed exfiltrated.',
      durationSec: 420,
      injects: [
        { id: 'inj3', at_second: 120, title: 'M&A Documents in Scope', body: 'Digital forensics confirms APT41 accessed the CFO\'s SharePoint folder containing draft acquisition term sheets for Project Helios ($340M deal). Deal is 6 weeks from public announcement.', role: 'CEO' },
        { id: 'inj4', at_second: 280, title: 'SEC Disclosure Question Raised', body: 'General Counsel raises that if M&A documents were exfiltrated by a nation-state actor, SEC cybersecurity disclosure rules (17 CFR 229.106) may require 8-K filing if the incident is "material."', role: 'Legal' },
      ],
      decisionPoints: [
        {
          id: 'dp2-sec',
          phaseId: 'ph2-scope',
          role: 'Legal',
          question: 'M&A deal documents have been confirmed exfiltrated. The deal is 6 weeks from public announcement. Is this a material cybersecurity incident requiring SEC 8-K disclosure?',
          context: 'SEC Rule 13a-15 requires disclosure of material cybersecurity incidents within 4 business days of determining materiality. "Material" is facts a reasonable investor would consider important to investment decisions.',
          timeLimitSec: 120,
          options: [
            { id: 'opt-a', label: 'Engage outside securities counsel immediately — treat as potentially material', description: 'Start 4-day clock, prepare draft 8-K, brief Board Audit Committee.', quality: 'optimal', consequence: 'SEC filing made on day 4. Proactive disclosure earns regulatory credit. Deal proceeds with informed market.', scoreDelta: 25, regComplianceImpact: 'SEC 17 CFR 229.106 compliant. No enforcement action.' },
            { id: 'opt-b', label: 'Delay assessment — argue materiality unclear pending full scope', description: 'Buy time to complete investigation before making materiality determination.', quality: 'suboptimal', consequence: 'SEC later views delay as deliberate. Wells Notice issued. Deal announcement creates obvious retroactive materiality.', scoreDelta: -10, regComplianceImpact: 'SEC enforcement risk: retroactive materiality finding.' },
            { id: 'opt-c', label: 'Do not disclose — M&A confidentiality supersedes', description: 'Treat incident as confidential M&A information protected from disclosure.', quality: 'harmful', consequence: 'SEC subpoena issued 60 days after deal closes. Class action securities fraud lawsuit filed.', scoreDelta: -50, regComplianceImpact: 'SEC Rule 10b-5 securities fraud exposure. Executive criminal liability.' },
          ],
        },
      ],
    },
  ],
};

const LAZARUS_CRYPTO: CrisisScenario = {
  id: 'lazarus-crypto-heist',
  title: 'Operation Silent Thunder',
  subtitle: 'Lazarus Group Cryptocurrency Heist Pivot to Corporate Network',
  category: 'multi-vector',
  threatActor: 'Lazarus',
  adversaryProfile: 'DPRK RGB Bureau 121. Financially motivated nation-state actor funding sanctions-evading programs. Known for AppleJeus malware, fake trading platforms, and pivoting from crypto theft to corporate espionage. $3B stolen in crypto since 2022.',
  sourceRef: 'MITRE ATT&CK G0032 · FBI/CISA/NSA Advisory AA23-129A · OFAC designation SDN List · US-CERT Alert TA21-048A',
  difficulty: 'nation-state',
  estimatedMinutes: 35,
  roles: ['CISO', 'Legal', 'CEO'],
  mitreTags: [
    { id: 'T1566.003', name: 'Spearphishing via Service', tactic: 'Initial Access' },
    { id: 'T1059.005', name: 'Visual Basic Script', tactic: 'Execution' },
    { id: 'T1496', name: 'Resource Hijacking', tactic: 'Impact' },
    { id: 'T1657', name: 'Financial Theft', tactic: 'Impact' },
  ],
  background: 'Your head of corporate treasury received a LinkedIn message from a fake Bloomberg recruiter with an attached "compensation study" Excel file. The file executed a macro. Your treasury workstation now shows unauthorized outbound connections. $2.4M in corporate FX forwards accounts may be accessible.',
  phases: [
    {
      id: 'ph1-breach',
      order: 1,
      title: 'Treasury System Breach Detected',
      description: 'Lazarus implant active on treasury workstation. Financial system access confirmed. Race against clock to freeze accounts.',
      durationSec: 480,
      injects: [
        { id: 'inj1', at_second: 60, title: 'Bank Transfer Initiated', body: 'Your corporate bank has flagged an unusual SWIFT transfer attempt of $890,000 to a shell company in Singapore (registered 3 weeks ago). Transfer is pending authorization.', role: 'CEO' },
        { id: 'inj2', at_second: 240, title: 'Second Transfer Attempt', body: 'A second SWIFT transfer of $1.5M has been initiated from a secondary treasury account. Destination: Malta-registered entity. Bank compliance team is calling.', role: 'CISO' },
      ],
      decisionPoints: [
        {
          id: 'dp1-bank',
          phaseId: 'ph1-breach',
          role: 'CEO',
          question: 'Your bank has flagged a pending $890K SWIFT transfer. The treasury workstation is confirmed compromised. How do you respond in the next 15 minutes?',
          context: 'SWIFT transfers can be recalled if caught before settlement. Once settled (typically 2-4 hours), recovery requires international law enforcement cooperation. The adversary controls the treasury workstation.',
          timeLimitSec: 90,
          options: [
            { id: 'opt-a', label: 'Call bank fraud line immediately — freeze all outbound transfers', description: 'Direct bank contact to halt pending transfers and freeze corporate accounts pending investigation.', quality: 'optimal', consequence: '$890K transfer blocked. Accounts frozen. $1.5M second transfer also blocked. Full forensic investigation begins.', scoreDelta: 35, nextPhaseId: 'ph2-lazarus-regulatory' },
            { id: 'opt-b', label: 'Revoke workstation credentials — let transfer process to trace actor', description: 'Allow transfer to proceed to identify money mule network for law enforcement.', quality: 'harmful', consequence: '$890K lost. Actor identity not confirmed via transfer. FBI declines to pursue given non-US jurisdiction destination.', scoreDelta: -30, nextPhaseId: 'ph2-lazarus-regulatory' },
            { id: 'opt-c', label: 'Escalate to CISO for investigation before acting on bank transfer', description: 'Wait for CISO confirmation of compromise before bank call.', quality: 'suboptimal', consequence: '22-minute delay results in transfer settling before freeze request reaches bank.', scoreDelta: -20, nextPhaseId: 'ph2-lazarus-regulatory' },
          ],
        },
      ],
    },
    {
      id: 'ph2-lazarus-regulatory',
      order: 2,
      title: 'FBI Engagement & FinCEN Reporting',
      description: 'Forensics confirm Lazarus Group TTP signatures. SEC, FBI Cyber Division, and FinCEN reporting obligations are now active. The adversary may still be persistent.',
      durationSec: 480,
      injects: [
        { id: 'inj3', at_second: 60, title: 'Lazarus Fingerprint Confirmed', body: 'FBI Cyber Division confirms the malware signature matches Lazarus Group tools used in the 2016 Bangladesh Bank $81M heist. This is now a national security investigation. FBI wants to embed an agent on-site.', role: 'CISO' },
        { id: 'inj4', at_second: 300, title: 'FinCEN SAR Filing Deadline', body: 'Bank compliance team confirms a Suspicious Activity Report (SAR) must be filed with FinCEN within 30 days. Material false statements in a SAR carry criminal penalties. Your CFO is asking who signs the SAR.', role: 'Legal' },
      ],
      decisionPoints: [
        {
          id: 'dp2-lazarus-fbi',
          phaseId: 'ph2-lazarus-regulatory',
          role: 'Legal',
          question: 'FBI Cyber Division wants to embed an agent in your SOC for the duration of the investigation. This would give the US government real-time access to all your network activity. How do you respond?',
          context: 'FBI cooperation may aid in criminal prosecution and asset recovery. However, it grants extensive government access to your intellectual property, client data, and internal communications. Your board is divided.',
          timeLimitSec: 90,
          options: [
            { id: 'opt-a', label: 'Cooperate fully — embed FBI agent with scoped access', description: 'Welcome FBI with contractual scope limitations. Get DOJ voluntary cooperation credit.', quality: 'optimal', consequence: 'FBI identifies secondary Lazarus persistence mechanism missed by IR team. Asset recovery proceedings initiated in Singapore.', scoreDelta: 25, regComplianceImpact: 'DOJ voluntary cooperation credit obtained. Asset recovery case opened.' },
            { id: 'opt-b', label: 'Provide logs remotely — no on-site FBI access', description: 'Cooperate via secure data share only. No on-site presence.', quality: 'suboptimal', consequence: 'FBI recovers less evidence remotely. Asset recovery case weaker. Secondary backdoor not found for 3 additional weeks.', scoreDelta: 5 },
            { id: 'opt-c', label: 'Decline FBI access — engage private forensics only', description: 'Protect corporate confidentiality. Use private forensics firm.', quality: 'harmful', consequence: 'FBI opens grand jury investigation. Subpoenas issued. Forced disclosure with no cooperation credit. Press reports on non-cooperation.', scoreDelta: -30, regComplianceImpact: 'Grand jury subpoena issued. No voluntary cooperation credit.' },
          ],
        },
      ],
    },
  ],
};

const MUDDYWATER_OT: CrisisScenario = {
  id: 'muddywater-ot-ics',
  title: 'Operation Iron Veil',
  subtitle: 'MuddyWater OT/ICS Infiltration & Operational Disruption',
  category: 'ot-ics',
  threatActor: 'MuddyWater',
  adversaryProfile: 'Iran MOIS cyber unit. Targets critical infrastructure, government, telecoms, defense contractors. Active in Middle East, Europe, and North America. Uses POWERSTATS, SHARPSTATS, and custom SILENTTRINITY frameworks. Recently linked to CISA AA22-055A advisory targeting water and energy sectors.',
  sourceRef: 'CISA AA22-055A · FBI/CISA Joint Advisory 2022 · MITRE ATT&CK G0069 · ICS-CERT Advisory ICSA-22-131-01',
  difficulty: 'advanced',
  estimatedMinutes: 40,
  roles: ['CISO', 'CEO', 'Legal'],
  mitreTags: [
    { id: 'T0817', name: 'Drive-by Compromise (ICS)', tactic: 'Initial Access' },
    { id: 'T0800', name: 'Activate Firmware Update Mode', tactic: 'Inhibit Response Function' },
    { id: 'T0881', name: 'Service Stop', tactic: 'Inhibit Response Function' },
    { id: 'T0813', name: 'Denial of Control', tactic: 'Impair Process Control' },
  ],
  background: 'Your manufacturing facility\'s OT network has been breached via a compromised engineering workstation. The attacker has SCADA access to your assembly line PLCs. Production is currently running. The adversary has been present for 11 days.',
  phases: [
    {
      id: 'ph1-ot-breach',
      order: 1,
      title: 'OT Network Compromise',
      description: 'SCADA system access confirmed. PLCs potentially compromised. Production line at risk of physical damage.',
      durationSec: 600,
      injects: [
        { id: 'inj1', at_second: 90, title: 'PLC Firmware Modification Detected', body: 'Engineering team reports anomalous firmware parameters on 3 assembly line PLCs. Temperature setpoints have been altered beyond safe operating ranges. Physical damage possible if production continues.', role: 'CISO' },
        { id: 'inj2', at_second: 360, title: 'Regulatory Notification Requirement', body: 'Legal confirms your facility is classified as critical infrastructure. CISA must be notified of OT incidents under CIRCIA within 72 hours.', role: 'Legal' },
      ],
      decisionPoints: [
        {
          id: 'dp1-ot',
          phaseId: 'ph1-ot-breach',
          role: 'CEO',
          question: 'Engineering reports PLC firmware has been modified. Continuing production risks equipment damage and potential worker safety incident. Stopping costs $180K/hour in lost production. What is your decision?',
          context: 'Physical damage to PLCs could take 6-8 weeks to repair given supply chain constraints. Worker safety is a non-negotiable. Your largest customer contract has a $2M/day penalty clause for missed deliveries.',
          timeLimitSec: 90,
          options: [
            { id: 'opt-a', label: 'Emergency production shutdown — worker safety is non-negotiable', description: 'Halt all production immediately. Manual inspection of all PLC firmware before restart.', quality: 'optimal', consequence: 'No safety incidents. $1.8M production loss. Customer notified. Contract force majeure clause invoked.', scoreDelta: 30, nextPhaseId: 'ph2-ot-cisa' },
            { id: 'opt-b', label: 'Slow production and continue monitoring', description: 'Reduce line speed 50% while forensics team investigates.', quality: 'harmful', consequence: 'PLC temperature excursion causes motor burnout in 2 units. $3.4M equipment damage. OSHA investigation triggered.', scoreDelta: -40, nextPhaseId: 'ph2-ot-cisa' },
            { id: 'opt-c', label: 'Revert PLCs to last known-good firmware backup', description: 'IT team pushes firmware rollback to all affected PLCs while production continues.', quality: 'suboptimal', consequence: 'Firmware reverted successfully but network access not removed. Adversary reinfects within 6 hours.', scoreDelta: 0, nextPhaseId: 'ph2-ot-cisa' },
          ],
        },
      ],
    },
    {
      id: 'ph2-ot-cisa',
      order: 2,
      title: 'CIRCIA Notification & OT Network Hardening',
      description: 'CIRCIA 72-hour reporting clock is running. ICS-CERT and CISA want a briefing. OT network segmentation must be redesigned to prevent future IT/OT bridge attacks.',
      durationSec: 480,
      injects: [
        { id: 'inj3', at_second: 90, title: 'CISA ICS-CERT On-Site Request', body: 'CISA ICS-CERT offers to deploy an on-site team under their Hunt and Incident Response Program (HIRP). They can assist with OT forensics and hardening at no cost but require full network access.', role: 'CISO' },
        { id: 'inj4', at_second: 300, title: 'Insurance Underwriter OT Exclusion Flag', body: 'Your cyber insurance underwriter has flagged your OT network as potentially excluded under the war/nation-state exclusion clause (the policy has a MuddyWater/MOIS carve-out). Coverage dispute may reduce recovery by $2.1M.', role: 'Legal' },
      ],
      decisionPoints: [
        {
          id: 'dp2-ot-rebuild',
          phaseId: 'ph2-ot-cisa',
          role: 'CISO',
          question: 'Post-incident, your OT and IT networks share a network segment. The quick fix is a firewall rule. The correct fix is full Purdue Model segmentation — costing $380K and 6 weeks. Which do you recommend to the CEO?',
          context: 'The same IT/OT bridge that MuddyWater exploited exists in 4 other facilities. Quick fix protects this site only. Full segmentation protects all 5. Your largest customer is auditing your security posture next month.',
          timeLimitSec: 90,
          options: [
            { id: 'opt-a', label: 'Recommend full Purdue Model segmentation across all 5 facilities', description: 'Enterprise-wide correct fix. 6 weeks, $380K, but eliminates the attack vector globally.', quality: 'optimal', consequence: 'All 5 facilities hardened. Customer audit passes. Insurance underwriter removes exclusion flag.', scoreDelta: 30, regComplianceImpact: 'CIRCIA compliant. ICS-CERT remediation plan accepted. Insurance exclusion removed.' },
            { id: 'opt-b', label: 'Quick firewall rule for this facility — defer enterprise project', description: 'Immediate protection for breached facility only. Submit budget request for full project.', quality: 'suboptimal', consequence: 'This facility protected. Facility 3 breached 8 weeks later using identical vector.', scoreDelta: 0 },
            { id: 'opt-c', label: 'Outsource OT security to the same MSP that manages IT', description: 'Cost-effective — leverage existing MSP relationship for OT monitoring.', quality: 'harmful', consequence: 'MSP does not have ICS-CERT certified OT expertise. Inadequate segmentation. OSHA issues $450K citation for inadequate safety controls.', scoreDelta: -30 },
          ],
        },
      ],
    },
  ],
};

const BEC_WIRE_FRAUD: CrisisScenario = {
  id: 'bec-wire-fraud',
  title: 'Operation Wire Whisper',
  subtitle: 'Business Email Compromise with CEO Wire Fraud',
  category: 'bec',
  threatActor: 'CISA-Generic',
  adversaryProfile: 'Organized cybercriminal group using BEC techniques. Spoofed executive email compromise targeting CFO/finance staff. FBI IC3 reports $2.7B in BEC losses in 2022. Often combined with SIM swapping and VoIP spoofing to defeat MFA.',
  sourceRef: 'CISA AA22-249A · FBI IC3 Advisory 2023 · MITRE ATT&CK T1534 · FinCEN Advisory FIN-2022-A001',
  difficulty: 'intermediate',
  estimatedMinutes: 30,
  roles: ['CISO', 'Legal', 'CEO'],
  mitreTags: [
    { id: 'T1534', name: 'Internal Spearphishing', tactic: 'Lateral Movement' },
    { id: 'T1586.002', name: 'Email Accounts', tactic: 'Resource Development' },
    { id: 'T1657', name: 'Financial Theft', tactic: 'Impact' },
  ],
  background: 'Your CFO received an email apparently from the CEO (spoofed domain: acme-corp.co vs acme-corp.com) requesting urgent wire transfer of $2.1M to a "confidential M&A escrow account" before market open. The CFO has initiated the wire.',
  phases: [
    {
      id: 'ph1-bec',
      order: 1,
      title: 'BEC Transfer Identified',
      description: 'CFO has initiated $2.1M wire based on spoofed CEO email. 90-minute window to recall before settlement.',
      durationSec: 540,
      injects: [
        { id: 'inj1', at_second: 60, title: 'CFO Confirms Email Was Spoofed', body: 'CEO denies sending any wire request. CFO confirms they did not verbally verify. Wire transfer department confirms funds are in transit. Window for recall: ~75 minutes.', role: 'CEO' },
        { id: 'inj2', at_second: 300, title: 'FinCEN SAR Obligation', body: 'Bank compliance confirms that once they file for wire recall, they are required to submit a Suspicious Activity Report (SAR) to FinCEN. This becomes a permanent regulatory record.', role: 'Legal' },
      ],
      decisionPoints: [
        {
          id: 'dp1-recall',
          phaseId: 'ph1-bec',
          role: 'CEO',
          question: 'You have confirmed the CEO email was spoofed. $2.1M is in transit. You have a 75-minute window to request recall. What is your immediate action?',
          context: 'Wire recalls are not guaranteed but success rates are approximately 60-70% if initiated within the recall window. The FBI has a dedicated BEC Recovery Asset Team (RAT) for active recovery.',
          timeLimitSec: 60,
          options: [
            { id: 'opt-a', label: 'Call bank fraud hotline immediately + submit FBI IC3 complaint', description: 'Parallel tracking: bank recall + FBI RAT engagement for asset recovery.', quality: 'optimal', consequence: '$2.1M successfully recalled (62% success case). FBI RAT identifies money mule account. Criminal referral filed.', scoreDelta: 35, nextPhaseId: 'ph2-bec-controls' },
            { id: 'opt-b', label: 'Escalate to CISO for investigation first', description: 'Document the attack before contacting the bank.', quality: 'suboptimal', consequence: '45-minute delay. Wire settles before recall request. $2.1M lost. FBI recovery attempt from settled funds — 12% success rate.', scoreDelta: -25, nextPhaseId: 'ph2-bec-controls' },
            { id: 'opt-c', label: 'Contact CEO\'s personal attorney to advise on liability', description: 'Determine legal exposure before acting.', quality: 'harmful', consequence: 'Wire settles. $2.1M lost. D&O insurance claim filed. Board audit committee investigates CFO decision-making.', scoreDelta: -40, nextPhaseId: 'ph2-bec-controls' },
          ],
        },
      ],
    },
    {
      id: 'ph2-bec-controls',
      order: 2,
      title: 'Board Accountability & BEC Prevention Policy',
      description: 'The wire has been addressed. The board demands immediate controls to prevent repeat attacks. CFO liability and verification protocol reform are now on the agenda.',
      durationSec: 420,
      injects: [
        { id: 'inj3', at_second: 60, title: 'CFO Liability — D&O Insurer Investigating', body: 'Your D&O insurer has retained outside counsel to assess whether the CFO breached fiduciary duty by failing to verbally verify a wire request per your own internal policy. Policy violation may void coverage.', role: 'Legal' },
        { id: 'inj4', at_second: 240, title: 'Second BEC Attempt Detected', body: 'Your email gateway has flagged a second spoofed CEO email to the CFO assistant requesting a different $450K wire. The attacker knows your wire authorization chain and is trying again.', role: 'CISO' },
      ],
      decisionPoints: [
        {
          id: 'dp2-bec-policy',
          phaseId: 'ph2-bec-controls',
          role: 'CISO',
          question: 'You must implement an immediate anti-BEC control that can be deployed in 24 hours. Which control provides the highest signal with the least operational disruption?',
          context: 'Your organization processes ~50 legitimate wire transfers per month. False positives cause operational friction but false negatives cost millions. The attacker has your org chart and email patterns.',
          timeLimitSec: 90,
          options: [
            { id: 'opt-a', label: 'Mandatory out-of-band voice verification for all wires over $50K', description: 'Dual-control via phone call to registered number — cannot be spoofed by email or Teams.', quality: 'optimal', consequence: 'Second attack attempt blocked. Zero false negatives in next 90 days. CFO audit passes. Insurer satisfied.', scoreDelta: 25, regComplianceImpact: 'FinCEN SAR supplemental note filed. Fraud controls satisfy insurer audit.' },
            { id: 'opt-b', label: 'Email DMARC enforcement + wire approval workflow in ERP only', description: 'Technical controls only — no process change required.', quality: 'suboptimal', consequence: 'DMARC blocks domain spoofing but attacker pivots to lookalike domain (acme-finance.com). Second attempt still reaches CFO.', scoreDelta: 0 },
            { id: 'opt-c', label: 'Suspend all wire transfers for 30 days pending review', description: 'Halt all wires to eliminate risk while controls are designed.', quality: 'harmful', consequence: 'Vendor payments missed. $340K in late payment penalties. Three key suppliers place accounts on credit hold.', scoreDelta: -20 },
          ],
        },
      ],
    },
  ],
};

const INSIDER_THREAT: CrisisScenario = {
  id: 'insider-threat-exfil',
  title: 'Operation Shadow Harvest',
  subtitle: 'Malicious Insider Data Exfiltration Before Departure',
  category: 'insider',
  threatActor: 'Insider',
  adversaryProfile: 'Disgruntled senior engineer with privileged access. Pre-departure exfiltration targeting IP, customer lists, and product roadmaps. Classic CERT insider threat pattern: access spike + USB activity + personal cloud uploads in final weeks of employment.',
  sourceRef: 'CERT Insider Threat Center 2023 Report · CISA Insider Threat Mitigation Guide · MITRE ATT&CK T1052 · DOJ Criminal Case examples',
  difficulty: 'intermediate',
  estimatedMinutes: 35,
  roles: ['CISO', 'Legal', 'CEO'],
  mitreTags: [
    { id: 'T1052.001', name: 'Exfiltration over USB', tactic: 'Exfiltration' },
    { id: 'T1537', name: 'Transfer Data to Cloud Account', tactic: 'Exfiltration' },
    { id: 'T1078', name: 'Valid Accounts', tactic: 'Defense Evasion' },
  ],
  background: 'Your DLP system flagged a senior ML engineer (Alex Chen, giving 2-week notice) uploading 14 GB of files to a personal Google Drive. The files include model weights, training datasets, and undisclosed product roadmaps. You have the evidence. The employee is still on-site.',
  phases: [
    {
      id: 'ph1-insider',
      order: 1,
      title: 'Insider Exfiltration Confirmed',
      description: 'DLP confirms 14 GB exfiltrated to personal cloud. Employee still on payroll. Trade secret theft potential.',
      durationSec: 480,
      injects: [
        { id: 'inj1', at_second: 90, title: 'Employee Job Posting Discovered', body: 'LinkedIn shows Alex Chen accepted a position at a direct competitor (InferenceAI) starting in 3 weeks. The competitor is actively developing a competing ML model.', role: 'Legal' },
        { id: 'inj2', at_second: 300, title: 'HR Alert — Offboarding in 3 Days', body: 'HR confirms Alex Chen\'s last day is in 3 days. Standard offboarding checklist has not yet revoked cloud credentials.', role: 'CISO' },
      ],
      decisionPoints: [
        {
          id: 'dp1-insider',
          phaseId: 'ph1-insider',
          role: 'Legal',
          question: 'You have DLP evidence of exfiltration. The employee is going to a competitor. Do you confront Alex Chen immediately or conduct a covert investigation first?',
          context: 'Immediate confrontation: risk of evidence destruction and cloud data deletion. Covert investigation: preserves evidence chain of custody but allows 3 more days of potential exfiltration.',
          timeLimitSec: 90,
          options: [
            { id: 'opt-a', label: 'Preserve evidence first — immediately revoke cloud access without alerting employee', description: 'Silently revoke Google Drive API access to freeze the exfiltrated data in place. Engage external forensics.', quality: 'optimal', consequence: 'Exfil frozen. Chain of custody preserved. Legal hold issued. Litigation position strong.', scoreDelta: 30, nextPhaseId: 'ph2-insider-tro' },
            { id: 'opt-b', label: 'Confront employee immediately in HR meeting', description: 'Call employee to HR with security present. Request return of data.', quality: 'suboptimal', consequence: 'Employee deletes Google Drive files before HR meeting concludes. Evidence partially destroyed.', scoreDelta: -10, nextPhaseId: 'ph2-insider-tro' },
            { id: 'opt-c', label: 'Do nothing pending legal advice — D&O exposure concern', description: 'Wait 24 hours for outside counsel to advise on wrongful termination risk.', quality: 'harmful', consequence: 'Employee uploads additional 8 GB. Last day arrives. Criminal referral timeline complicated.', scoreDelta: -30, nextPhaseId: 'ph2-insider-tro' },
          ],
        },
      ],
    },
    {
      id: 'ph2-insider-tro',
      order: 2,
      title: 'TRO & Trade Secret Litigation',
      description: 'Evidence preserved. Now the question is whether to pursue a Temporary Restraining Order against Alex Chen and InferenceAI to prevent use of the stolen IP.',
      durationSec: 420,
      injects: [
        { id: 'inj3', at_second: 90, title: 'InferenceAI Uses Stolen Model in Demo', body: 'LinkedIn shows InferenceAI showcased features at a startup event that appear to use your proprietary model architecture. A former colleague attended and recognized the output signatures. This is your first evidence of actual misuse.', role: 'Legal' },
        { id: 'inj4', at_second: 270, title: 'DOJ Trade Secret Referral Option', body: 'FBI Economic Espionage Unit has contacted you — they are building a case against Alex Chen under the Defend Trade Secrets Act (DTSA). They want your evidence package and a criminal referral. This path is public.', role: 'CEO' },
      ],
      decisionPoints: [
        {
          id: 'dp2-insider-legal',
          phaseId: 'ph2-insider-tro',
          role: 'Legal',
          question: 'You have strong evidence of trade secret theft. Do you pursue an emergency TRO to stop InferenceAI from using the IP, file a civil DTSA lawsuit, or refer to the DOJ for criminal prosecution?',
          context: 'TRO: fast (24 hrs), but requires public filing and alerts InferenceAI. Civil DTSA: compensatory + punitive damages but 12-18 month timeline. DOJ criminal referral: maximum deterrence but you lose control of the case.',
          timeLimitSec: 90,
          options: [
            { id: 'opt-a', label: 'Emergency TRO + civil DTSA simultaneously', description: 'Immediate injunctive relief blocks IP use while full lawsuit proceeds.', quality: 'optimal', consequence: 'TRO granted. InferenceAI product launch delayed 6 months. $4.2M damages awarded in civil settlement. Alex Chen departs InferenceAI.', scoreDelta: 30, regComplianceImpact: 'DTSA civil claim filed. Trade secret protection maintained.' },
            { id: 'opt-b', label: 'DOJ criminal referral only — let federal prosecution lead', description: 'Transfer the case to DOJ and cooperate fully with DTSA criminal prosecution.', quality: 'suboptimal', consequence: 'Criminal case takes 2 years. InferenceAI continues using IP during that time. No civil damages recovered.', scoreDelta: 5 },
            { id: 'opt-c', label: 'Settle confidentially with Alex Chen — avoid public exposure', description: 'Negotiate NDA and data deletion in exchange for no prosecution.', quality: 'harmful', consequence: 'InferenceAI keeps the IP (not party to settlement). Alex Chen signs NDA but is no longer in possession. IP continues to be used.', scoreDelta: -25 },
          ],
        },
      ],
    },
  ],
};

const CLOUD_ACCOUNT_COMPROMISE: CrisisScenario = {
  id: 'cloud-account-compromise',
  title: 'Operation Stratus Gate',
  subtitle: 'Cloud Account Takeover & Credential Chain Compromise',
  category: 'cloud',
  threatActor: 'APT41',
  adversaryProfile: 'Financially motivated cloud-targeting threat actor leveraging stolen OAuth tokens, misconfigured service accounts, and SSRF vulnerabilities in cloud-native workloads. APT41 sub-cluster focused on cloud asset monetization and data theft.',
  sourceRef: 'CISA AA23-131A Cloud Security Advisory · CIS Cloud Controls v8 · MITRE ATT&CK T1078.004 · NSA CSI "Securing Cloud Storage Objects"',
  difficulty: 'advanced',
  estimatedMinutes: 35,
  roles: ['CISO', 'Legal'],
  mitreTags: [
    { id: 'T1078.004', name: 'Cloud Accounts', tactic: 'Persistence' },
    { id: 'T1530', name: 'Data from Cloud Storage', tactic: 'Collection' },
    { id: 'T1098.001', name: 'Additional Cloud Credentials', tactic: 'Persistence' },
  ],
  background: 'Your AWS CloudTrail logs show a service account (sa-analytics-prod) generating 140,000 API calls in 4 hours, accessing S3 buckets containing customer PII. The service account credentials were exposed in a public GitHub commit 6 weeks ago.',
  phases: [
    {
      id: 'ph1-cloud',
      order: 1,
      title: 'Cloud Account Takeover Active',
      description: 'Compromised service account actively exfiltrating from S3. Customer PII at risk. Credential chain exposure unknown.',
      durationSec: 480,
      injects: [
        { id: 'inj1', at_second: 120, title: 'Additional IAM Role Assumed', body: 'CloudTrail confirms the compromised service account assumed a higher-privilege IAM role (InfrastructureAdmin) 2 hours ago. RDS database snapshots of customer records are being exported.', role: 'CISO' },
        { id: 'inj2', at_second: 300, title: 'Customer PII Scope Confirmed', body: 'S3 access logs confirm 2.3M customer records (name, email, encrypted payment methods) were accessed. California CCPA 30-day notification clock is now running.', role: 'Legal' },
      ],
      decisionPoints: [
        {
          id: 'dp1-cloud',
          phaseId: 'ph1-cloud',
          role: 'CISO',
          question: 'The compromised service account now has InfrastructureAdmin privileges. Revoking immediately stops the exfil but may cause cascading service failures. What is your decision?',
          context: 'The sa-analytics-prod service account is used by 14 production microservices. Immediate revocation will break these services until credentials are rotated — estimated 2-4 hours downtime.',
          timeLimitSec: 90,
          options: [
            { id: 'opt-a', label: 'Revoke credentials immediately — accept service disruption', description: 'Immediate revocation. Begin emergency credential rotation. Accept 2-4 hour partial outage.', quality: 'optimal', consequence: 'Exfil stopped. Services degraded 3.1 hours. Customer impact minimal. 2.3M records compromised — no more.', scoreDelta: 30, nextPhaseId: 'ph2-cloud-notify' },
            { id: 'opt-b', label: 'Rate-limit the service account API calls while rotating credentials', description: 'Apply AWS IAM conditions to slow the exfil while preparing credential rotation.', quality: 'suboptimal', consequence: 'Attacker detects throttling and switches to a secondary stolen credential. Exfil continues at reduced rate.', scoreDelta: -5, nextPhaseId: 'ph2-cloud-notify' },
            { id: 'opt-c', label: 'Continue monitoring for 2 hours to capture full attack chain', description: 'Let the attack continue to build a complete forensic picture before acting.', quality: 'harmful', consequence: 'Additional 1.8M records exfiltrated. Total exposure: 4.1M records. CCPA fine exposure doubles.', scoreDelta: -40, nextPhaseId: 'ph2-cloud-notify' },
          ],
        },
      ],
    },
    {
      id: 'ph2-cloud-notify',
      order: 2,
      title: 'CCPA / GDPR Notification & Cloud Hardening',
      description: '2.3M customer records compromised. California CCPA 30-day and EU GDPR 72-hour notification clocks are running. Cloud IAM architecture must be redesigned.',
      durationSec: 480,
      injects: [
        { id: 'inj3', at_second: 90, title: 'GDPR 72-Hour Clock Confirmed', body: 'Legal confirms 340,000 of the 2.3M records belong to EU data subjects under GDPR. The 72-hour notification window to your lead supervisory authority (CNIL) started when you became aware. You have 48 hours left.', role: 'Legal' },
        { id: 'inj4', at_second: 300, title: 'GitHub Secrets Scan — 12 More Exposed Keys', body: 'Your automated GitHub secrets scan has found 12 additional API keys and IAM credentials committed to private repos over the past 18 months. None have been rotated. The APT41 actor may have all of them.', role: 'CISO' },
      ],
      decisionPoints: [
        {
          id: 'dp2-cloud-disclosure',
          phaseId: 'ph2-cloud-notify',
          role: 'Legal',
          question: 'GDPR requires notifying your lead supervisory authority within 72 hours "without undue delay." You have 48 hours left. Forensics says scope confirmation will take 36 more hours. Do you notify now with incomplete information or wait for complete scope?',
          context: 'Early notification with incomplete data is allowed under GDPR Article 33(4) — you can supplement later. Late notification triggers fines up to 2% of global revenue. Your revenue: $180M annually.',
          timeLimitSec: 90,
          options: [
            { id: 'opt-a', label: 'Notify supervisory authority now — supplement when forensics completes', description: 'GDPR-compliant early notification with best-known facts. Supplement with Article 33(4) addendum.', quality: 'optimal', consequence: 'CNIL accepts early notification. No fine imposed. Supplemental notice filed 36 hours later. DPA audit completed without penalty.', scoreDelta: 30, regComplianceImpact: 'GDPR Article 33 compliant. CCPA 30-day notice sent. No regulatory fine.' },
            { id: 'opt-b', label: 'Wait 36 hours for complete scope — submit accurate single notification', description: 'File one complete accurate notification rather than two.', quality: 'suboptimal', consequence: 'Notification submitted 4 hours after GDPR deadline. CNIL issues €540K fine for late notification.', scoreDelta: -15, regComplianceImpact: 'GDPR late notification fine €540K. CCPA notice on time.' },
            { id: 'opt-c', label: 'Notify only California customers per CCPA — evaluate GDPR applicability separately', description: 'Dispute whether GDPR applies to these data subjects. Consult Brussels counsel first.', quality: 'harmful', consequence: 'GDPR deadline missed while in legal consultation. €3.6M GDPR fine (2% revenue). Class action filed in California.', scoreDelta: -40, regComplianceImpact: 'GDPR violation €3.6M fine. CCPA class action filed.' },
          ],
        },
      ],
    },
  ],
};

const VENDOR_BREACH_CASCADE: CrisisScenario = {
  id: 'vendor-breach-cascade',
  title: 'Operation Shattered Chain',
  subtitle: 'Third-Party Vendor Breach Cascade to Customer Data',
  category: 'supply-chain',
  threatActor: 'CISA-Generic',
  adversaryProfile: 'Financially motivated threat actor targeting managed service providers (MSPs) as force multipliers. One MSP breach can cascade to hundreds of downstream customer organizations. Pattern documented in CISA AA22-131A advisory on MSP targeting.',
  sourceRef: 'CISA AA22-131A · MS-ISAC Advisory 2023-043 · MITRE ATT&CK T1199 · FTC Safeguards Rule',
  difficulty: 'intermediate',
  estimatedMinutes: 30,
  roles: ['CISO', 'Legal', 'CEO'],
  mitreTags: [
    { id: 'T1199', name: 'Trusted Relationship', tactic: 'Initial Access' },
    { id: 'T1021.001', name: 'Remote Desktop Protocol', tactic: 'Lateral Movement' },
    { id: 'T1482', name: 'Domain Trust Discovery', tactic: 'Discovery' },
  ],
  background: 'Your IT managed service provider (TechForce MSP) has notified you of a breach of their remote management platform. They had administrative access to your network for 18 months. The breach window is unknown. TechForce serves 340 clients.',
  phases: [
    {
      id: 'ph1-msp',
      order: 1,
      title: 'MSP Breach Notification Received',
      description: 'Your MSP has been breached. Attacker had your domain admin credentials via the MSP management plane. Scope unknown.',
      durationSec: 480,
      injects: [
        { id: 'inj1', at_second: 120, title: 'RMM Agent Activity Detected', body: 'Your EDR shows the MSP Remote Monitoring and Management (RMM) agent executing PowerShell commands on 89 systems over the past 72 hours. Commands include credential dumping and lateral movement enumeration.', role: 'CISO' },
        { id: 'inj2', at_second: 300, title: 'Customer Data in Scope', body: 'Forensics confirms that customer financial records stored on a file server accessible via MSP RMM have been accessed and potentially exfiltrated. FTC Safeguards Rule notification obligations may apply.', role: 'Legal' },
      ],
      decisionPoints: [
        {
          id: 'dp1-msp',
          phaseId: 'ph1-msp',
          role: 'CISO',
          question: 'The MSP RMM agent is the attack vector. Do you immediately remove MSP access and take over management yourself, accepting operational disruption?',
          context: 'Removing MSP access will break 23 managed IT workflows including patch management and backup monitoring. Your internal IT team has capacity to absorb approximately 40% of the MSP workload immediately.',
          timeLimitSec: 90,
          options: [
            { id: 'opt-a', label: 'Immediately revoke all MSP access and quarantine RMM agents', description: 'Emergency breach of MSP contract. Accept operational gaps. Build internal capacity.', quality: 'optimal', consequence: 'Attack vector removed. 23 managed processes disrupted. Recovery takes 2 weeks but breach contained.', scoreDelta: 25, nextPhaseId: 'ph2-msp-customer' },
            { id: 'opt-b', label: 'Request MSP disable compromised account — keep RMM operational', description: 'Work with MSP to disable the specific compromised credential while maintaining RMM.', quality: 'suboptimal', consequence: 'MSP confirms 3 additional service accounts were also compromised. Partial fix insufficient.', scoreDelta: -10, nextPhaseId: 'ph2-msp-customer' },
            { id: 'opt-c', label: 'Continue MSP relationship with enhanced monitoring', description: 'Add logging and monitoring to MSP activity while continuing service.', quality: 'harmful', consequence: 'Attacker detects enhanced monitoring and escalates activity before next window. Additional data exfiltrated.', scoreDelta: -35, nextPhaseId: 'ph2-msp-customer' },
          ],
        },
      ],
    },
    {
      id: 'ph2-msp-customer',
      order: 2,
      title: 'Customer Disclosure & FTC Safeguards Compliance',
      description: 'Your customers\' financial records were potentially accessed through the MSP breach. FTC Safeguards Rule, state breach notification laws, and customer relationship obligations are in tension.',
      durationSec: 420,
      injects: [
        { id: 'inj3', at_second: 90, title: 'Downstream Customer Has Detected Anomaly', body: 'One of your top-10 customers (accounting for $8.4M revenue) has contacted you — their security team detected suspicious PowerShell activity originating from your systems. They are demanding a full breach disclosure within 4 hours or they will terminate the contract.', role: 'CEO' },
        { id: 'inj4', at_second: 270, title: 'TechForce MSP Files for Bankruptcy', body: 'TechForce MSP has filed for Chapter 11 bankruptcy protection. Your contractual breach liability claims against them are now stayed. Cyber insurance subrogation against them is uncertain. The $2.3M recovery estimate may not materialize.', role: 'Legal' },
      ],
      decisionPoints: [
        {
          id: 'dp2-msp-disclosure',
          phaseId: 'ph2-msp-customer',
          role: 'CEO',
          question: 'Your top customer is threatening contract termination unless you disclose within 4 hours. Your legal team says FTC Safeguards requires notification but you haven\'t scoped all affected customers yet. What do you do?',
          context: '$8.4M revenue at risk. Full customer list notification before scope is confirmed risks over-notification. But delayed notification risks regulatory violation and contract breach across all customers.',
          timeLimitSec: 90,
          options: [
            { id: 'opt-a', label: 'Proactive disclosure to all customers — with current known facts', description: 'Notify all customers now with best-available information. Demonstrate transparency.', quality: 'optimal', consequence: 'Top customer retains relationship. 3 smaller customers terminate but 12 renew citing trust. FTC commends proactive disclosure.', scoreDelta: 25, regComplianceImpact: 'FTC Safeguards Rule compliant. State breach notification laws satisfied in all 50 states.' },
            { id: 'opt-b', label: 'Notify only confirmed-affected customers — scope confirmation first', description: 'Wait for forensics to confirm per-customer exposure before notifying.', quality: 'suboptimal', consequence: 'Top customer terminates ($8.4M loss). FTC issues civil investigative demand. Class action filed.', scoreDelta: -15, regComplianceImpact: 'FTC civil investigative demand issued. Late notification finding.' },
            { id: 'opt-c', label: 'Notify only the demanding customer — manage others case-by-case', description: 'Prioritize the relationship threatening termination. Handle others reactively.', quality: 'harmful', consequence: 'News of selective disclosure leaks. All customers demand equal treatment. Class action filed. FTC investigation. $4.2M settlement.', scoreDelta: -40, regComplianceImpact: 'Discriminatory disclosure findings. FTC $4.2M consent decree.' },
          ],
        },
      ],
    },
  ],
};

const DEEPFAKE_SOCIAL_ENG: CrisisScenario = {
  id: 'deepfake-social-engineering',
  title: 'Operation Voice Clone',
  subtitle: 'AI-Generated Deepfake Social Engineering Attack',
  category: 'deepfake',
  threatActor: 'CISA-Generic',
  adversaryProfile: 'Next-generation social engineering using AI voice cloning and video deepfakes. Criminals can clone executive voice from as little as 30 seconds of audio. FBI has issued warnings about AI-enabled BEC with deepfake voice/video calls. Growing trend since 2023.',
  sourceRef: 'FBI IC3 Advisory 2023 · CISA AI Security Guide · MITRE ATT&CK T1534 · UK NCSC AI Threats Report 2024',
  difficulty: 'advanced',
  estimatedMinutes: 30,
  roles: ['CISO', 'Legal', 'CEO'],
  mitreTags: [
    { id: 'T1534', name: 'Internal Spearphishing', tactic: 'Lateral Movement' },
    { id: 'T1598', name: 'Phishing for Information', tactic: 'Reconnaissance' },
  ],
  background: 'Your CFO received a video call that appeared to be the CEO on a Teams call requesting emergency wire transfer authorization. The video quality was slightly degraded but "the CEO" cited poor connection. $3.5M wire was authorized. The real CEO was in an off-site meeting with phone off.',
  phases: [
    {
      id: 'ph1-deepfake',
      order: 1,
      title: 'Deepfake Attack Identified',
      description: 'CFO discovers the CEO video call was a deepfake. $3.5M wire has been sent. Immediate response required.',
      durationSec: 480,
      injects: [
        { id: 'inj1', at_second: 90, title: 'Video Analysis Confirms Deepfake', body: 'Your CISO\'s team has confirmed using frame analysis that the Teams video call was a deepfake. Facial micro-expression analysis shows 94% probability of AI generation. The voice was cloned from an investor day recording.', role: 'CISO' },
        { id: 'inj2', at_second: 300, title: 'Board Demands Policy Response', body: 'Your board chair is demanding a same-day briefing on how this happened and what controls prevented it from happening again. They are questioning whether D&O insurance covers CFO liability.', role: 'Legal' },
      ],
      decisionPoints: [
        {
          id: 'dp1-deepfake',
          phaseId: 'ph1-deepfake',
          role: 'CEO',
          question: 'The deepfake attack has succeeded. $3.5M is in transit. What is your crisis response priority order?',
          context: 'You have simultaneous crises: financial recovery attempt, board communications, media risk, and an internal investigation into verification failure. You can only do one thing in the next 15 minutes.',
          timeLimitSec: 90,
          options: [
            { id: 'opt-a', label: 'Bank recall + FBI immediately — financial recovery first', description: 'Wire recall has the shortest window. Initiate simultaneously with FBI IC3 complaint.', quality: 'optimal', consequence: '$3.5M recall initiated. 55% success probability. FBI BEC Recovery team engaged. Bank freezes receiving account.', scoreDelta: 30, nextPhaseId: 'ph2-deepfake-policy' },
            { id: 'opt-b', label: 'Internal investigation first — understand full scope before acting', description: 'Convene incident response team to understand what data the attackers may also have accessed.', quality: 'suboptimal', consequence: 'Wire recall window missed. $3.5M settled. Recovery from settled accounts: 12% success rate.', scoreDelta: -25, nextPhaseId: 'ph2-deepfake-policy' },
            { id: 'opt-c', label: 'Brief board immediately — governance response first', description: 'Board briefing takes priority to manage stakeholder relationships.', quality: 'harmful', consequence: 'Wire settles while in board meeting. CFO not yet cleared of liability. D&O insurer contacts board independently.', scoreDelta: -35, nextPhaseId: 'ph2-deepfake-policy' },
          ],
        },
      ],
    },
    {
      id: 'ph2-deepfake-policy',
      order: 2,
      title: 'Board Briefing & Deepfake Verification Policy',
      description: 'Financial response is underway. Now the board demands a same-day policy to prevent the next deepfake attack. The verification gap is systemic.',
      durationSec: 420,
      injects: [
        { id: 'inj3', at_second: 90, title: 'Media Has the Story', body: 'TechCrunch is reporting on "a major AI deepfake wire fraud attack against an unnamed US company." They have enough details to confirm it\'s your organization. Your Communications VP has 30 minutes to decide on a public statement.', role: 'Comms' },
        { id: 'inj4', at_second: 270, title: 'Second Deepfake Detected — CFO Assistant Targeted', body: 'Your security team has detected a second deepfake attack attempt — this time targeting your CFO\'s executive assistant via a WhatsApp video call. The attack was caught before funds were moved. The adversary has profiled your approval chain.', role: 'CISO' },
      ],
      decisionPoints: [
        {
          id: 'dp2-deepfake-verify',
          phaseId: 'ph2-deepfake-policy',
          role: 'CISO',
          question: 'You must immediately implement a deepfake verification protocol that works across all communication channels. Which approach stops deepfake attacks without crippling executive communications?',
          context: 'Executives conduct ~40 sensitive calls/week. Any verification protocol must be low-friction for legitimate use but impossible to spoof. The attacker has access to 3+ years of the CEO\'s video and audio content.',
          timeLimitSec: 90,
          options: [
            { id: 'opt-a', label: 'Shared secret code-word system + out-of-band callback to known number', description: 'Every financial request requires a rotating code-word (changed weekly) + a callback to the pre-registered number — not the number in the request.', quality: 'optimal', consequence: 'Second attack attempt fails at code-word step. Zero false positives in next 60 days. Board approves the protocol as the enterprise standard.', scoreDelta: 30, regComplianceImpact: 'D&O insurer accepts protocol as reasonable controls. Coverage preserved.' },
            { id: 'opt-b', label: 'AI deepfake detection tool on all video calls', description: 'Deploy a commercial deepfake detection product on all Teams/Zoom calls.', quality: 'suboptimal', consequence: 'Tool has 87% detection rate. Next attacker uses newer GAN model that evades detection. False sense of security.', scoreDelta: 5 },
            { id: 'opt-c', label: 'Ban all video-based financial authorizations — email only with digital signature', description: 'Move all financial approvals to email with S/MIME digital signatures.', quality: 'harmful', consequence: 'Executives circumvent policy using personal devices within 2 weeks. Attacker pivots to email spoofing. Controls ineffective.', scoreDelta: -15 },
          ],
        },
      ],
    },
  ],
};

const MULTI_VECTOR_COMBINED: CrisisScenario = {
  id: 'multi-vector-combined',
  title: 'Operation Convergence Storm',
  subtitle: 'Simultaneous Multi-Vector Nation-State Attack',
  category: 'multi-vector',
  threatActor: 'APT28',
  adversaryProfile: 'Coordinated multi-front attack combining physical intrusion, ransomware, and BEC in a single campaign. Models documented nation-state "full-spectrum" targeting. Based on documented joint FBI/CISA/NSA advisory patterns for sophisticated persistent threats against critical infrastructure.',
  sourceRef: 'NSA/CISA/FBI Joint Advisory AA22-257A · MITRE ATT&CK Campaign C0028 · CISA Top 10 Misconfigs AA23-278A · FCEB Red Team Findings AA24-193A',
  difficulty: 'nation-state',
  estimatedMinutes: 55,
  roles: ['CISO', 'Legal', 'Comms', 'CEO'],
  mitreTags: [
    { id: 'T1566', name: 'Phishing', tactic: 'Initial Access' },
    { id: 'T1486', name: 'Data Encrypted for Impact', tactic: 'Impact' },
    { id: 'T1565', name: 'Data Manipulation', tactic: 'Impact' },
    { id: 'T1657', name: 'Financial Theft', tactic: 'Impact' },
    { id: 'T1490', name: 'Inhibit System Recovery', tactic: 'Impact' },
  ],
  background: 'At 06:47 this morning, three simultaneous events triggered: (1) Ransomware began encrypting your London data center, (2) Your CFO received a deepfake call requesting $4.8M wire, (3) An unknown physical intruder was caught on CCTV in your server room at 02:00 AM. This is a coordinated nation-state attack.',
  phases: [
    {
      id: 'ph1-triage',
      order: 1,
      title: 'Multi-Vector Attack — Triage',
      description: 'Three simultaneous attack vectors active. Limited team bandwidth. Prioritization is critical.',
      durationSec: 480,
      injects: [
        { id: 'inj1', at_second: 60, title: 'Physical Intruder — Hardware Implant Suspected', body: 'CCTV shows unidentified individual with access to the server room at 02:00 AM. Badge logs show no authorized access. Physical device may have been planted on core switching infrastructure.', role: 'CISO' },
        { id: 'inj2', at_second: 180, title: 'CFO Has Already Wired $4.8M', body: 'CFO confirms wire transfer completed before attack was identified as coordinated. The deepfake call was the first vector they encountered this morning.', role: 'CEO' },
        { id: 'inj3', at_second: 360, title: 'National Security Threshold — FBI Counterintelligence', body: 'FBI Counterintelligence Division has called — they believe this is a GRU-linked operation and have jurisdiction. They want to run the investigation. Your company lawyer is asking about your CISA reporting obligations under CIRCIA.', role: 'Legal' },
      ],
      decisionPoints: [
        {
          id: 'dp1-priority',
          phaseId: 'ph1-triage',
          role: 'CISO',
          question: 'Three simultaneous attack vectors are active and you have limited IR bandwidth for the first 30 minutes. What is your prioritization order?',
          context: 'Available resources: 4 IR analysts, 1 forensics specialist, 1 network engineer. You cannot fully address all three simultaneously in the first wave.',
          timeLimitSec: 120,
          options: [
            { id: 'opt-a', label: 'Network containment first → financial freeze → physical investigation', description: 'Stop active ransomware propagation (highest immediate damage), trigger bank freeze (narrow time window), then investigate hardware implant.', quality: 'optimal', consequence: 'Ransomware contained at 23 systems. Bank freeze initiated ($4.8M unrecoverable but future transfers blocked). Hardware implant found and removed in 4 hours.', scoreDelta: 35 },
            { id: 'opt-b', label: 'Financial recovery first → ransomware → physical', description: 'Prioritize the recoverable financial loss first.', quality: 'suboptimal', consequence: 'Wire recall missed (outside window). Ransomware spreads to 89 additional systems during delay. Hardware implant active for 6+ hours.', scoreDelta: -10 },
            { id: 'opt-c', label: 'Escalate to CEO and wait for executive direction', description: 'This decision requires executive authorization.', quality: 'harmful', consequence: '18-minute escalation delay allows ransomware to encrypt core database servers. $2.8M additional recovery costs.', scoreDelta: -45 },
          ],
        },
        {
          id: 'dp2-fbi',
          phaseId: 'ph1-triage',
          role: 'Legal',
          question: 'FBI Counterintelligence wants to lead the investigation. CISA wants a briefing under CIRCIA. Your insurance carrier wants to send their own forensics team. How do you coordinate?',
          context: 'FBI involvement may restrict your ability to communicate publicly. CIRCIA imposes 72-hour notification obligations. Insurance forensics team has contractual right to examine affected systems.',
          timeLimitSec: 120,
          options: [
            { id: 'opt-a', label: 'Designate FBI as lead with CISA notified per CIRCIA — brief insurance separately', description: 'Structured multi-party coordination with clear lead designation.', quality: 'optimal', consequence: 'Clean chain of command. CIRCIA compliance. Insurance coverage preserved. FBI investigation progresses without conflict.', scoreDelta: 25, regComplianceImpact: 'CIRCIA compliant. Full insurance cooperation maintained.', nextPhaseId: 'ph2-multivec-attribution' },
            { id: 'opt-b', label: 'Let all three run parallel investigations independently', description: 'Avoid picking favorites among government agencies and insurer.', quality: 'suboptimal', consequence: 'Evidence contamination. FBI and insurance forensics teams conflict over chain of custody. Prosecution case weakened.', scoreDelta: -10, nextPhaseId: 'ph2-multivec-attribution' },
            { id: 'opt-c', label: 'Restrict FBI access — prioritize insurance investigation to protect coverage', description: 'Insurance counsel advises that FBI access could create evidence that voids policy exclusions.', quality: 'harmful', consequence: 'FBI obtains court order for access. Obstruction of justice risk. CIRCIA violation fine ($100K/day). Insurance coverage dispute escalates.', scoreDelta: -50, regComplianceImpact: 'CIRCIA violation + potential obstruction of justice referral.', nextPhaseId: 'ph2-multivec-attribution' },
          ],
        },
      ],
    },
    {
      id: 'ph2-multivec-attribution',
      order: 2,
      title: 'Attribution Confirmed — National Security Response',
      description: 'NSA confirms GRU Unit 26165 attribution. This is now a matter of national security. Government expects a coordinated response. Public disclosure pressure is building.',
      durationSec: 540,
      injects: [
        { id: 'inj4', at_second: 90, title: 'NSA Attribution — APT28 Confirmed', body: 'NSA Cybersecurity Directorate has formally attributed the attack to APT28/GRU Unit 26165. The hardware implant is a classified Russian intelligence collection device. FBI counterintelligence is now primary. NSA requests you do not disclose the hardware implant finding publicly.', role: 'CEO' },
        { id: 'inj5', at_second: 300, title: 'Reuters Story Going Live in 2 Hours', body: 'Reuters has obtained breach details from an unnamed source. Their story goes live in 2 hours. The article attributes the attack to a "foreign state actor" and quotes your largest customer expressing concern. Your communications team needs a statement.', role: 'Comms' },
        { id: 'inj6', at_second: 450, title: 'OFAC Sanctions Compliance Check', body: 'Your CFO asks: before paying any ransom demand (if received), do you need OFAC sanctions clearance? GRU-linked entities are on the OFAC SDN list. Paying a sanctioned actor carries civil penalties up to $1M per transaction regardless of intent.', role: 'Legal' },
      ],
      decisionPoints: [
        {
          id: 'dp3-multivec-disclosure',
          phaseId: 'ph2-multivec-attribution',
          role: 'CEO',
          question: 'Reuters is publishing in 2 hours. NSA has asked you not to confirm the hardware implant. The board wants full transparency. Your stock is halted pending material disclosure. What is your public statement strategy?',
          context: 'SEC 8-K material event disclosure is required if this is material. NSA national security request may conflict with SEC obligations. Your outside counsel says both obligations are real and you must navigate them simultaneously.',
          timeLimitSec: 120,
          options: [
            { id: 'opt-a', label: 'Issue factual 8-K confirming a cyberattack and FBI investigation — without hardware implant detail', description: 'SEC-compliant disclosure that omits classified details per NSA request. Outside counsel approves.', quality: 'optimal', consequence: 'SEC accepts disclosure. Stock reopens. NSA satisfied. Reuters story is accurate but incomplete. Board protected.', scoreDelta: 30, regComplianceImpact: 'SEC 8-K filed timely. NSA national security coordination preserved. CIRCIA final report submitted.' },
            { id: 'opt-b', label: 'Full public disclosure including hardware implant — complete transparency', description: 'Disclose everything to customers, SEC, and public despite NSA request.', quality: 'harmful', consequence: 'NSA classifies your company as a security risk. Government contracts terminated. DOJ criminal referral for unauthorized disclosure of classified information.', scoreDelta: -50, regComplianceImpact: 'Potential criminal liability for classified disclosure. Government contracts at risk.' },
            { id: 'opt-c', label: 'Issue no public statement — let NSA handle all communications', description: 'Defer entirely to government communications on the attack.', quality: 'suboptimal', consequence: 'Reuters publishes unflattering story citing your silence. Stock declines 18%. SEC opens inquiry into delayed disclosure. Class action filed.', scoreDelta: -20, regComplianceImpact: 'SEC late disclosure inquiry opened. Potential 10b-5 securities violation.' },
          ],
        },
      ],
    },
  ],
};

export const CRISIS_SCENARIOS: CrisisScenario[] = [
  APT28_RANSOMWARE,
  APT41_SUPPLY_CHAIN,
  LAZARUS_CRYPTO,
  MUDDYWATER_OT,
  BEC_WIRE_FRAUD,
  INSIDER_THREAT,
  CLOUD_ACCOUNT_COMPROMISE,
  VENDOR_BREACH_CASCADE,
  DEEPFAKE_SOCIAL_ENG,
  MULTI_VECTOR_COMBINED,
];

export const SCENARIO_CATEGORY_LABELS: Record<AttackCategory, string> = {
  ransomware: 'Ransomware',
  'supply-chain': 'Supply Chain',
  insider: 'Insider Threat',
  'ot-ics': 'OT / ICS',
  bec: 'BEC / Fraud',
  cloud: 'Cloud Compromise',
  deepfake: 'AI Deepfake',
  'multi-vector': 'Multi-Vector',
};

export const THREAT_ACTOR_LABELS: Record<ThreatActor, string> = {
  APT28: 'APT28 · Russia GRU',
  APT41: 'APT41 · China MSS',
  Lazarus: 'Lazarus · DPRK RGB',
  MuddyWater: 'MuddyWater · Iran MOIS',
  'CISA-Generic': 'Criminal / Generic',
  Insider: 'Insider Threat',
};

export interface SimulationRecord {
  scenarioId: string;
  startedAt: string;
  completedAt?: string;
  decisions: Array<{
    decisionPointId: string;
    selectedOptionId: string;
    timestampSec: number;
    quality: DecisionQuality;
    scoreDelta: number;
  }>;
  totalScore: number;
  maxScore: number;
  letterGrade: 'AAA' | 'AA' | 'A' | 'BBB' | 'BB' | 'B' | 'CCC' | 'C';
  completed: boolean;
}

export function calculateLetterGrade(score: number, maxScore: number): SimulationRecord['letterGrade'] {
  if (maxScore === 0) return 'BBB';
  const pct = score / maxScore;
  if (pct >= 0.92) return 'AAA';
  if (pct >= 0.84) return 'AA';
  if (pct >= 0.74) return 'A';
  if (pct >= 0.62) return 'BBB';
  if (pct >= 0.50) return 'BB';
  if (pct >= 0.38) return 'B';
  if (pct >= 0.24) return 'CCC';
  return 'C';
}

export function getGradeColor(grade: SimulationRecord['letterGrade']): string {
  if (grade === 'AAA' || grade === 'AA') return '#4ade80';
  if (grade === 'A') return '#86efac';
  if (grade === 'BBB' || grade === 'BB') return '#c9b787';
  if (grade === 'B') return '#f5f5f5';
  return '#ef4444';
}
