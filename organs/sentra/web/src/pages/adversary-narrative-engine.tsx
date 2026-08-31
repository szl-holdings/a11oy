// R7 minimalistic redesign (Series-A blocker, 2026-05-18T16:03:41Z):
// surface tokens realigned with a11oy/amaru palette in src/lib/theme.ts.
// No data wiring, no API calls, no copy were modified — visual texture only.

import { useStandardMutation } from '@szl-holdings/api-client-react';
import { toast } from '@szl-holdings/shared-ui/ui/sonner';
import { cn } from '@szl-holdings/shared-ui/utils';
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  BookOpen,
  Brain,
  CheckCircle,
  ChevronDown,
  Database,
  Download,
  Eye,
  FileText,
  Flag,
  Info,
  Layers,
  Link2,
  Lock,
  Network,
  Play,
  Shield,
  ShieldCheck,
  Terminal,
  User,
  X,
  Zap,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import { api } from '@/lib/api';

const API_BASE = import.meta.env.VITE_API_URL ?? '/api';

// ─── Types ────────────────────────────────────────────────────────────────────

export type MitreStageCoverage = 'evidenced' | 'inferred' | 'missing';

interface Observable {
  id: string;
  type: 'log' | 'alert' | 'network' | 'file' | 'process' | 'identity';
  source: string;
  rawRef: string;
  excerpt: string;
  timestamp: string;
  confidence: number;
}

interface NarrativeStep {
  seq: number;
  title: string;
  description: string;
  mitreStage: string;
  mitreTechnique: string;
  mitreTechniqueId: string;
  confidence: number;
  coverage: MitreStageCoverage;
  observables: Observable[];
  iocs: string[];
  recommendedAction?: {
    id: string;
    label: string;
    riskLevel: 'low' | 'medium' | 'high' | 'critical';
    requiresApproval: boolean;
    details: string;
  };
  timestamp: string;
}

export interface Incident {
  id: string;
  title: string;
  severity: 'critical' | 'high' | 'medium' | 'low';
  status: string;
  actor: string;
  confidence: number;
  businessImpact: string;
  executiveSummary: string;
  affectedSystems: string[];
  iocCount: number;
  stepsEvidenced: number;
  stepsInferred: number;
  stepsMissing: number;
  totalSteps: number;
  steps: NarrativeStep[];
}

// ─── Demo Data ────────────────────────────────────────────────────────────────

export const NARRATIVE_INCIDENTS: Incident[] = [
  {
    id: 'INC-2041',
    title: 'APT41 Lateral Movement — Credential Harvest + LSASS Dump',
    severity: 'critical',
    status: 'in_progress',
    actor: 'APT41 (Winnti Group)',
    confidence: 94,
    businessImpact:
      'Active domain credential compromise with lateral movement to the primary domain controller. Risk of full domain takeover and ransomware staging. Estimated breach cost if uncontained: $4.2M–$8.7M.',
    executiveSummary:
      'A sophisticated nation-state actor (APT41) gained a foothold via credential theft on a workstation, then moved laterally to the domain controller using stolen hashes. Password hashes for privileged accounts were extracted from memory. The attacker is now positioned for full domain compromise. The threat has been partially contained — the initial workstation is isolated, and the domain controller is under active monitoring. Six service accounts have been rotated. Immediate executive action required: approve domain password reset across all privileged accounts.',
    affectedSystems: ['WS-PROD-012', 'DC-EAST-01', 'aws-prod-east'],
    iocCount: 14,
    stepsEvidenced: 5,
    stepsInferred: 2,
    stepsMissing: 1,
    totalSteps: 8,
    steps: [
      {
        seq: 1,
        title: 'Initial Access via Spearphishing Attachment',
        description:
          'A malicious DOCX file disguised as a vendor invoice was delivered to a finance team member. The document contained an obfuscated VBA macro that executed a Cobalt Strike stager upon enabling content.',
        mitreStage: 'Initial Access',
        mitreTechnique: 'Spearphishing Attachment',
        mitreTechniqueId: 'T1566.001',
        confidence: 97,
        coverage: 'evidenced',
        timestamp: '14:08:14',
        iocs: [
          'invoice_apr2026.docx (SHA256: a3f7c…e901)',
          'C2: 45.142.212[.]43:443',
          'User-Agent: Mozilla/5.0 (Cobalt Strike 4.x)',
        ],
        observables: [
          {
            id: 'obs-001',
            type: 'alert',
            source: 'Email Security Gateway',
            rawRef: 'ESG-ALERT-20260419-0041',
            excerpt:
              'BLOCKED → invoice_apr2026.docx | Macro detected | Sender: vendor-noreply@szl-invoice[.]com | Score: 98/100',
            timestamp: '14:08:14',
            confidence: 99,
          },
          {
            id: 'obs-002',
            type: 'log',
            source: 'Microsoft 365 Audit Log',
            rawRef: 'M365-AUD-20260419-112847',
            excerpt:
              'UserFileAccessed | User: j.moore@szlholdings.com | File: invoice_apr2026.docx | ContentEnabled: true',
            timestamp: '14:09:02',
            confidence: 97,
          },
          {
            id: 'obs-003',
            type: 'process',
            source: 'EDR — WS-PROD-012',
            rawRef: 'EDR-PROC-20260419-5592',
            excerpt:
              'WINWORD.EXE → cmd.exe → powershell.exe -enc JABzAD0ATgBlAHcALQBPAGIAag… | PID: 5592 | User: SZLH\\j.moore',
            timestamp: '14:09:11',
            confidence: 96,
          },
        ],
        recommendedAction: undefined,
      },
      {
        seq: 2,
        title: 'Execution — PowerShell Stager Drop',
        description:
          "The macro spawned an encoded PowerShell command that downloaded and executed a Cobalt Strike beacon DLL from the adversary's C2 infrastructure. The beacon established an encrypted HTTPS channel.",
        mitreStage: 'Execution',
        mitreTechnique: 'PowerShell Encoded Command',
        mitreTechniqueId: 'T1059.001',
        confidence: 96,
        coverage: 'evidenced',
        timestamp: '14:09:11',
        iocs: [
          'beacon.dll (SHA256: 9b2e1…f33a)',
          'C2 beacon: 45.142.212[.]43 (HTTPS/443)',
          'Named pipe: \\.pipemojo.5688.8052',
        ],
        observables: [
          {
            id: 'obs-004',
            type: 'network',
            source: 'NDR — Perimeter Sensor',
            rawRef: 'NDR-FLOW-20260419-00491',
            excerpt:
              'SRC: 10.12.5.22:54201 → DST: 45.142.212.43:443 | Proto: HTTPS | Bytes: 142KB | JA3: a0e9f5d64349fb1332... (Cobalt Strike fingerprint)',
            timestamp: '14:09:18',
            confidence: 95,
          },
          {
            id: 'obs-005',
            type: 'file',
            source: 'EDR — WS-PROD-012',
            rawRef: 'EDR-FILE-20260419-1102',
            excerpt:
              'FileCreated: C:\\Users\\j.moore\\AppData\\Roaming\\beacon.dll | Size: 208KB | Entropy: 7.9 (packed) | Signer: unsigned',
            timestamp: '14:09:15',
            confidence: 98,
          },
        ],
        recommendedAction: undefined,
      },
      {
        seq: 3,
        title: 'Persistence — Scheduled Task Creation',
        description:
          "The beacon created a scheduled task named 'MicrosoftEdgeUpdateTaskMachineCore' to survive reboots. Task executed the beacon DLL via rundll32.exe. This step was initially missed by behavioral rules.",
        mitreStage: 'Persistence',
        mitreTechnique: 'Scheduled Task/Job',
        mitreTechniqueId: 'T1053.005',
        confidence: 88,
        coverage: 'evidenced',
        timestamp: '14:11:44',
        iocs: [
          'Task: MicrosoftEdgeUpdateTaskMachineCore',
          'rundll32.exe beacon.dll,StartW',
          'HKLM\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\Schedule\\TaskCache',
        ],
        observables: [
          {
            id: 'obs-006',
            type: 'log',
            source: 'Windows Event Log — WS-PROD-012',
            rawRef: 'WEL-4698-20260419-001',
            excerpt:
              'EventID: 4698 | Task Created | TaskName: \\MicrosoftEdgeUpdateTaskMachineCore | Creator: SZLH\\j.moore | Command: rundll32.exe beacon.dll,StartW',
            timestamp: '14:11:44',
            confidence: 99,
          },
          {
            id: 'obs-007',
            type: 'process',
            source: 'EDR — WS-PROD-012',
            rawRef: 'EDR-PROC-20260419-5701',
            excerpt:
              'schtasks.exe /create /tn MicrosoftEdgeUpdateTaskMachineCore /tr rundll32.exe beacon.dll,StartW /sc onlogon /ru SYSTEM',
            timestamp: '14:11:45',
            confidence: 97,
          },
        ],
        recommendedAction: {
          id: 'act-001',
          label: 'Remove scheduled task from WS-PROD-012',
          riskLevel: 'low',
          requiresApproval: false,
          details:
            'Delete HKLM scheduled task entry and quarantine beacon.dll. EDR containment confirmed prior to action. Reversible.',
        },
      },
      {
        seq: 4,
        title: 'Credential Access — LSASS Memory Dump',
        description:
          'Mimikatz was used to dump NTLM password hashes from LSASS memory on WS-PROD-012. The EDR alerted on the LSASS access pattern, but the dump completed before the block was applied, resulting in partial credential extraction.',
        mitreStage: 'Credential Access',
        mitreTechnique: 'OS Credential Dumping: LSASS Memory',
        mitreTechniqueId: 'T1003.001',
        confidence: 99,
        coverage: 'evidenced',
        timestamp: '14:18:03',
        iocs: [
          'mimi.exe (SHA256: 4c7d3…a81b)',
          'LSASS PID 752 — access_handle: 0x1fffff',
          '6 NTLM hashes extracted (svc_backup, admin.liu, etc.)',
        ],
        observables: [
          {
            id: 'obs-008',
            type: 'alert',
            source: 'EDR — WS-PROD-012',
            rawRef: 'EDR-ALERT-20260419-LSASS-001',
            excerpt:
              'CRITICAL | Process mimi.exe (PID 9211) opened handle to lsass.exe (PID 752) with PROCESS_VM_READ | MiniDump write detected | Action: ALERT (partial block — dump completed before termination)',
            timestamp: '14:18:03',
            confidence: 99,
          },
          {
            id: 'obs-009',
            type: 'log',
            source: 'Windows Security Log — WS-PROD-012',
            rawRef: 'WEL-4656-20260419-001',
            excerpt:
              'EventID: 4656 | ObjectType: Process | ObjectName: lsass.exe | AccessMask: 0x1fffff | SubjectUserName: j.moore',
            timestamp: '14:18:03',
            confidence: 99,
          },
          {
            id: 'obs-010',
            type: 'file',
            source: 'EDR — WS-PROD-012',
            rawRef: 'EDR-FILE-20260419-1208',
            excerpt:
              'FileCreated: C:\\Temp\\lsass.dmp | Size: 41MB | Process: mimi.exe | Entropy: 6.1 | Immediately deleted after read',
            timestamp: '14:18:07',
            confidence: 97,
          },
        ],
        recommendedAction: {
          id: 'act-002',
          label: 'Force password reset — all 6 compromised accounts',
          riskLevel: 'high',
          requiresApproval: true,
          details:
            'Rotate NTLM hashes for svc_backup, admin.liu, svc_deploy, svc_monitor, adm.chen, svc_sql. Will terminate active sessions. Requires AD admin approval. Estimated downtime: 8 minutes for automated services.',
        },
      },
      {
        seq: 5,
        title: 'Lateral Movement — Pass-the-Hash to Domain Controller',
        description:
          "Using the extracted NTLM hash for 'admin.liu', the attacker authenticated to DC-EAST-01 via SMB without knowing the plaintext password. This lateral movement was not detected in real time — it was reconstructed from DC authentication logs.",
        mitreStage: 'Lateral Movement',
        mitreTechnique: 'Pass-the-Hash',
        mitreTechniqueId: 'T1550.002',
        confidence: 91,
        coverage: 'evidenced',
        timestamp: '14:22:31',
        iocs: [
          'Source: WS-PROD-012 (10.12.5.22)',
          'Target: DC-EAST-01 (10.1.0.5) port 445',
          'Auth hash: admin.liu NTLM (stolen from LSASS dump)',
        ],
        observables: [
          {
            id: 'obs-011',
            type: 'log',
            source: 'Domain Controller Security Log — DC-EAST-01',
            rawRef: 'DC-WEL-4624-20260419-001',
            excerpt:
              'EventID: 4624 | LogonType: 3 (Network) | SubjectUserName: admin.liu | WorkstationName: WS-PROD-012 | AuthPackage: NTLM | KeyLength: 0 [indicates PtH]',
            timestamp: '14:22:31',
            confidence: 93,
          },
          {
            id: 'obs-012',
            type: 'network',
            source: 'NDR — East Segment',
            rawRef: 'NDR-FLOW-20260419-00512',
            excerpt:
              'SMB lateral: 10.12.5.22:49202 → 10.1.0.5:445 | Auth: NTLM | SessionSetup success | Tree: IPC$ | Duration: 00:14:27',
            timestamp: '14:22:33',
            confidence: 89,
          },
        ],
        recommendedAction: {
          id: 'act-003',
          label: 'Isolate DC-EAST-01 from workstation VLAN',
          riskLevel: 'critical',
          requiresApproval: true,
          details:
            'Apply ACL to block SMB/LDAP from workstation VLAN (10.12.0.0/16) to domain controller segment. Will affect legitimate admin workflows. Estimated impact: 12 admin users will need jump-server access. Requires CISO approval.',
        },
      },
      {
        seq: 6,
        title: 'Discovery — Active Directory Reconnaissance',
        description:
          'From DC-EAST-01, the attacker performed extensive LDAP queries to enumerate all privileged groups, service accounts, and domain trusts. LDAP query volume 840× baseline — detected by UEBA.',
        mitreStage: 'Discovery',
        mitreTechnique: 'Domain Account Discovery',
        mitreTechniqueId: 'T1087.002',
        confidence: 87,
        coverage: 'evidenced',
        timestamp: '14:27:09',
        iocs: [
          'LDAP queries: 2,241 in 3 minutes (baseline: 2.7/min)',
          'Targets: Domain Admins, Enterprise Admins, svc_ accounts',
          'BloodHound-compatible output pattern detected',
        ],
        observables: [
          {
            id: 'obs-013',
            type: 'alert',
            source: 'UEBA — Identity Analytics',
            rawRef: 'UEBA-ALERT-20260419-0087',
            excerpt:
              'ANOMALY | admin.liu | LDAP query volume: 2241 queries/3min (840× peer baseline) | Query types: samAccountType=805306368, memberOf, adminCount=1 | Risk score: 98',
            timestamp: '14:27:09',
            confidence: 94,
          },
          {
            id: 'obs-014',
            type: 'log',
            source: 'DC-EAST-01 LDAP Audit Log',
            rawRef: 'DC-LDAP-20260419-001',
            excerpt:
              'Caller: admin.liu@szlholdings.com | Filter: (&(objectCategory=person)(memberOf=CN=Domain Admins,CN=Users,...)) | Objects returned: 18 | Time: 14:27:09–14:30:02',
            timestamp: '14:27:09',
            confidence: 91,
          },
        ],
        recommendedAction: undefined,
      },
      {
        seq: 7,
        title: 'Privilege Escalation — Kerberoasting Attack (Inferred)',
        description:
          'Based on six SPN-targeted Kerberos TGS requests from the compromised admin.liu session, Kerberoasting is inferred. Offline cracking of service account hashes is likely in progress. No cracked credential evidence yet observed — inference based on request pattern.',
        mitreStage: 'Privilege Escalation',
        mitreTechnique: 'Kerberoasting',
        mitreTechniqueId: 'T1558.003',
        confidence: 73,
        coverage: 'inferred',
        timestamp: '14:31:18',
        iocs: [
          'TGS-REQ for 6 SPNs (svc_sql, svc_backup, svc_deploy…)',
          'RC4-HMAC encryption (weaker cipher — roastable)',
          'Mimikatz kerberos::list pattern',
        ],
        observables: [
          {
            id: 'obs-015',
            type: 'log',
            source: 'DC-EAST-01 Kerberos Log',
            rawRef: 'DC-KRB-20260419-001',
            excerpt:
              'EventID: 4769 | TicketEncType: 0x17 (RC4-HMAC) | ServiceName: svc_sql/dc-east-01 | ClientAddress: 10.1.0.5 | Status: 0x0 (success) [×6 in 90s]',
            timestamp: '14:31:18',
            confidence: 88,
          },
        ],
        recommendedAction: {
          id: 'act-004',
          label: 'Pre-emptively reset all SPN-holding service account passwords',
          riskLevel: 'high',
          requiresApproval: true,
          details:
            'Reset passwords for svc_sql, svc_backup, svc_deploy, svc_monitor, svc_report, svc_api to 32-char random strings. Services will restart. Estimated downtime window: 15 minutes. Prevents offline crack from yielding valid credentials.',
        },
      },
      {
        seq: 8,
        title: 'Exfiltration / Impact — Stage Unconfirmed',
        description:
          "No exfiltration artifacts have been observed yet. This stage is absent from current evidence. The attacker's proximity to sensitive AD data and AWS credentials makes this a high-probability next step. Active monitoring is in place.",
        mitreStage: 'Exfiltration',
        mitreTechnique: 'Unobserved — Monitoring Active',
        mitreTechniqueId: 'TA0010',
        confidence: 0,
        coverage: 'missing',
        timestamp: '—',
        iocs: [],
        observables: [],
        recommendedAction: undefined,
      },
    ],
  },
  {
    id: 'INC-2039',
    title: 'Ransomware Staging — Encrypted Volume Mount + Shadow Copy Deletion',
    severity: 'critical',
    status: 'contained',
    actor: 'ALPHV/BlackCat (Affiliate)',
    confidence: 98,
    businessImpact:
      'Ransomware staging contained across 12 endpoints. Shadow copy deletion was blocked — recovery path preserved. Encrypted volume mount attempt also blocked. Business operations uninterrupted. Estimated avoided loss: $11M.',
    executiveSummary:
      'A ransomware operator (ALPHV/BlackCat affiliate) gained access via an unpatched vulnerability and began staging their payload. Two critical defensive mechanisms triggered: shadow copy deletion was blocked (preserving backup recovery options) and encrypted volume mount was prevented. The attacker spread to 11 additional endpoints before mass network containment was applied. All 12 systems are isolated and being remediated. No data was encrypted. Recovery is expected within 4–6 hours.',
    affectedSystems: ['FS-CLUSTER-03', 'FS-CLUSTER-04', 'NAS-PROD-01'],
    iocCount: 31,
    stepsEvidenced: 6,
    stepsInferred: 1,
    stepsMissing: 0,
    totalSteps: 7,
    steps: [
      {
        seq: 1,
        title: 'Initial Access — Exploitation of Unpatched VPN Appliance',
        description:
          "CVE-2024-21887 (Ivanti Connect Secure) exploited on the organization's external VPN gateway. Unauthenticated remote code execution gave the attacker a shell on the VPN appliance.",
        mitreStage: 'Initial Access',
        mitreTechnique: 'Exploit Public-Facing Application',
        mitreTechniqueId: 'T1190',
        confidence: 99,
        coverage: 'evidenced',
        timestamp: '11:51:04',
        iocs: ['CVE-2024-21887', 'Ivanti ICS (10.12.0.1)', 'Reverse shell: 185.220.101[.]52:4444'],
        observables: [
          {
            id: 'obs-r-001',
            type: 'log',
            source: 'Ivanti ICS — Access Log',
            rawRef: 'ICS-LOG-20260419-00041',
            excerpt:
              'POST /api/v1/totp/user-backup-code/../../dana/html/bypass.cgi HTTP/1.1 | 200 OK | Response: 41KB | IP: 185.220.101.52 | CVE-2024-21887 signature match',
            timestamp: '11:51:04',
            confidence: 99,
          },
        ],
        recommendedAction: undefined,
      },
      {
        seq: 2,
        title: 'Execution — Ransomware Binary Deployment',
        description:
          'BlackCat encryptor binary (ELF + Windows PE) pushed to the file server cluster via lateral file share access. Binary executed via WMI command invocation across the cluster.',
        mitreStage: 'Execution',
        mitreTechnique: 'Windows Management Instrumentation',
        mitreTechniqueId: 'T1047',
        confidence: 98,
        coverage: 'evidenced',
        timestamp: '12:03:17',
        iocs: [
          'blackcat_enc.exe (SHA256: 7f3a9…b20c)',
          'WMI: Win32_Process.Create',
          'C2: 185.220.101[.]52:8080',
        ],
        observables: [
          {
            id: 'obs-r-002',
            type: 'process',
            source: 'EDR — FS-CLUSTER-03',
            rawRef: 'EDR-PROC-20260419-7701',
            excerpt:
              'WmiPrvSE.exe → blackcat_enc.exe | PID: 7701 | Args: --access-token XXX --no-net --sleep 10 | Hash: 7f3a9…b20c | Blocked',
            timestamp: '12:03:17',
            confidence: 99,
          },
        ],
        recommendedAction: undefined,
      },
      {
        seq: 3,
        title: 'Defense Evasion — Shadow Copy Deletion Attempt (BLOCKED)',
        description:
          'BlackCat attempted to delete all Windows volume shadow copies to prevent recovery. The EDR behavioral rule blocked the vssadmin.exe deletion command before it completed. All shadow copies are intact.',
        mitreStage: 'Defense Evasion',
        mitreTechnique: 'Inhibit System Recovery',
        mitreTechniqueId: 'T1490',
        confidence: 99,
        coverage: 'evidenced',
        timestamp: '12:08:11',
        iocs: [
          'vssadmin.exe delete shadows /all /quiet',
          'wmic.exe shadowcopy delete',
          'bcdedit.exe /set recoveryenabled No',
        ],
        observables: [
          {
            id: 'obs-r-003',
            type: 'alert',
            source: 'EDR — FS-CLUSTER-03',
            rawRef: 'EDR-ALERT-20260419-VSS-001',
            excerpt:
              'BLOCKED | vssadmin.exe delete shadows /all /quiet | Parent: blackcat_enc.exe | Action: Process terminated | Shadow copies: PRESERVED (12/12 intact)',
            timestamp: '12:08:11',
            confidence: 100,
          },
        ],
        recommendedAction: undefined,
      },
      {
        seq: 4,
        title: 'Impact — Encrypted Volume Mount Attempt (BLOCKED)',
        description:
          'BlackCat mounted an encrypted virtual volume (VHD) to use as a staging area for file encryption operations, bypassing direct filesystem monitoring. The mount was detected and blocked by the endpoint sensor.',
        mitreStage: 'Impact',
        mitreTechnique: 'Data Encrypted for Impact',
        mitreTechniqueId: 'T1486',
        confidence: 97,
        coverage: 'evidenced',
        timestamp: '12:11:22',
        iocs: ['VHD mount: Z:\\ (encrypted container)', 'diskpart.exe automated script'],
        observables: [
          {
            id: 'obs-r-004',
            type: 'alert',
            source: 'EDR — FS-CLUSTER-03',
            rawRef: 'EDR-ALERT-20260419-VHD-001',
            excerpt:
              'BLOCKED | Virtual disk mount detected | Process: blackcat_enc.exe → diskpart.exe | VHD: C:\\Windows\\Temp\\data.vhd | Action: Mount prevented, file quarantined',
            timestamp: '12:11:22',
            confidence: 98,
          },
        ],
        recommendedAction: undefined,
      },
      {
        seq: 5,
        title: 'Lateral Movement — Worm Spread Across File Server Cluster',
        description:
          'BlackCat propagated autonomously to 11 additional endpoints using SMB shares and embedded credentials. The worm spread completed before network segmentation rules could be applied.',
        mitreStage: 'Lateral Movement',
        mitreTechnique: 'Lateral Tool Transfer',
        mitreTechniqueId: 'T1570',
        confidence: 95,
        coverage: 'evidenced',
        timestamp: '12:14:08',
        iocs: ['SMB write to \\\\*\\ADMIN$ shares', 'Embedded credential: svc_fileshare'],
        observables: [
          {
            id: 'obs-r-005',
            type: 'network',
            source: 'NDR — Storage VLAN',
            rawRef: 'NDR-FLOW-20260419-01104',
            excerpt:
              'SMB spray: FS-CLUSTER-03 → 11 hosts | Port 445 | Files dropped: blackcat_enc.exe | Duration: 00:01:47 | 11/11 successful drops',
            timestamp: '12:14:08',
            confidence: 96,
          },
        ],
        recommendedAction: {
          id: 'act-r-001',
          label: 'Apply emergency VLAN isolation — file server segment',
          riskLevel: 'critical',
          requiresApproval: true,
          details:
            'Block all SMB/CIFS traffic within storage VLAN (10.50.0.0/24) at the switch level. Will prevent further spread. File services unavailable during containment. Estimated impact: 340 users lose file access. Duration: ~2 hours. CISO and VP Engineering approval required.',
        },
      },
      {
        seq: 6,
        title: 'Containment Applied — Mass Isolation',
        description:
          'Automated containment policy triggered across all 12 affected endpoints. Network isolation applied at switch level. BlackCat binary quarantined on all systems. Incident is contained — no data encrypted.',
        mitreStage: 'Containment (Response)',
        mitreTechnique: 'N/A — Defensive Action',
        mitreTechniqueId: 'RS:C001',
        confidence: 100,
        coverage: 'evidenced',
        timestamp: '12:19:43',
        iocs: [],
        observables: [
          {
            id: 'obs-r-006',
            type: 'alert',
            source: 'SOAR — Response Orchestration',
            rawRef: 'SOAR-ACTION-20260419-CONTAIN-001',
            excerpt:
              'CONTAINMENT COMPLETE | 12/12 endpoints isolated | Binary quarantined: blackcat_enc.exe | Network segments blocked | Audit trail: AUDIT-C-20260419-001 | Approval: auto (policy: ransomware-staging → isolate)',
            timestamp: '12:19:43',
            confidence: 100,
          },
        ],
        recommendedAction: undefined,
      },
      {
        seq: 7,
        title: 'Family Attribution — ALPHV/BlackCat Variant (Inferred)',
        description:
          'Binary analysis, C2 infrastructure, and behavioral patterns match ALPHV/BlackCat ransomware-as-a-service. Intermittent encryption pattern (partial file encryption) is a known BlackCat v3 signature. Attribution confidence is high but not forensically confirmed.',
        mitreStage: 'Attribution (Intel)',
        mitreTechnique: 'Malware Attribution',
        mitreTechniqueId: 'INT:A001',
        confidence: 84,
        coverage: 'inferred',
        timestamp: '12:35:10',
        iocs: [
          'ALPHV ransom note template match',
          'C2 via Tor hidden service (partial)',
          'Golang binary structure',
        ],
        observables: [
          {
            id: 'obs-r-007',
            type: 'alert',
            source: 'Threat Intel — Fusion Engine',
            rawRef: 'INTEL-MATCH-20260419-0041',
            excerpt:
              'TTP cluster match: ALPHV/BlackCat (confidence: 84%) | IOC overlaps: 7/9 | C2 infrastructure overlap: partial | Ransom note template: BlackCat v3 (98% string similarity)',
            timestamp: '12:35:10',
            confidence: 84,
          },
        ],
        recommendedAction: undefined,
      },
    ],
  },
  // ─── INC-2038: Supply Chain Compromise ───────────────────────────────────────
  {
    id: 'INC-2038',
    title: 'Supply Chain Compromise — Malicious npm Package in CI Pipeline',
    severity: 'high',
    status: 'in_progress',
    actor: 'Supply Chain Threat (Unknown APT)',
    confidence: 81,
    businessImpact:
      'Malicious CI/CD dependency may have exfiltrated build secrets and environment variables. Estimated exposure: API keys, AWS credentials stored in CI environment. Potential for downstream artifact poisoning.',
    executiveSummary:
      'A malicious npm package (`react-utils-pro` v3.2.1) was discovered in the CI/CD pipeline. The package executed an obfuscated payload on the build server, establishing a DNS tunneling channel likely used to exfiltrate environment secrets. Build artifacts produced during the window of compromise should be considered untrusted.',
    affectedSystems: ['BUILD-SRV-02', 'CI-CD-PIPELINE'],
    iocCount: 6,
    stepsEvidenced: 2,
    stepsInferred: 2,
    stepsMissing: 0,
    totalSteps: 4,
    steps: [
      {
        seq: 1,
        title: 'Malicious npm Package Injection',
        description:
          'A threat actor published `react-utils-pro` v3.2.1 to the npm registry with an obfuscated payload hidden in a postinstall script. The package typosquatted a legitimate internal dependency and was automatically installed by the CI/CD pipeline.',
        mitreStage: 'Initial Access',
        mitreTechnique: 'Compromise Software Supply Chain',
        mitreTechniqueId: 'T1195.001',
        confidence: 94,
        coverage: 'evidenced',
        timestamp: '10:14:07',
        iocs: [
          'react-utils-pro@3.2.1 (npm SHA: b2e9f…c441)',
          'postinstall: node .scripts/util.js',
          'Registry: registry.npmjs.org (typosquat of internal pkg)',
        ],
        observables: [
          {
            id: 'obs-sc-001',
            type: 'alert',
            source: 'SCA Scanner — CI Pipeline',
            rawRef: 'SCA-ALERT-20260419-0038',
            excerpt:
              'CRITICAL | react-utils-pro@3.2.1 | Obfuscated postinstall script | Malware score: 97/100 | Build: #2041',
            timestamp: '10:14:07',
            confidence: 97,
          },
        ],
        recommendedAction: {
          id: 'sc-quarantine-build',
          label: 'Quarantine Build Artifacts & Rotate CI Secrets',
          riskLevel: 'high',
          requiresApproval: true,
          details:
            'Mark all artifacts from the compromised build window as untrusted. Rotate all secrets stored in CI/CD environment variables including AWS credentials and API tokens.',
        },
      },
      {
        seq: 2,
        title: 'CI/CD Pipeline Code Execution',
        description:
          'The postinstall script executed on BUILD-SRV-02 during npm install, running a base64-encoded payload that mapped the build environment and collected environment variables.',
        mitreStage: 'Execution',
        mitreTechnique: 'Command and Scripting Interpreter: Node.js',
        mitreTechniqueId: 'T1059.004',
        confidence: 89,
        coverage: 'evidenced',
        timestamp: '10:14:22',
        iocs: [
          'node .scripts/util.js',
          'base64-encoded payload (1.4 KB)',
          'Process: node PID 19283 spawned by npm',
        ],
        observables: [
          {
            id: 'obs-sc-002',
            type: 'process',
            source: 'EDR — BUILD-SRV-02',
            rawRef: 'EDR-PROC-20260419-1928',
            excerpt:
              'npm install → node .scripts/util.js | base64 decode exec | env dump → /tmp/.env.cache | PID: 19283',
            timestamp: '10:14:22',
            confidence: 91,
          },
        ],
        recommendedAction: undefined,
      },
      {
        seq: 3,
        title: 'DNS Tunneling Channel Established',
        description:
          'The payload established a covert DNS exfiltration channel using subdomain encoding. High-frequency TXT record queries to `d1x.cdn-worker[.]io` were observed from BUILD-SRV-02, consistent with DNS tunnel tooling.',
        mitreStage: 'Exfiltration',
        mitreTechnique: 'Exfiltration Over Alternative Protocol: DNS',
        mitreTechniqueId: 'T1048.003',
        confidence: 78,
        coverage: 'inferred',
        timestamp: '10:22:41',
        iocs: ['DNS: *.d1x.cdn-worker[.]io (TXT queries)', 'Exfil rate: ~12 queries/sec for 4 min'],
        observables: [
          {
            id: 'obs-sc-003',
            type: 'network',
            source: 'DNS Monitoring — BUILD-SRV-02',
            rawRef: 'DNS-LOG-20260419-1022',
            excerpt:
              'ANOMALY | 289 TXT queries in 4m | dst: *.d1x.cdn-worker[.]io | entropy: high | direction: outbound',
            timestamp: '10:22:41',
            confidence: 78,
          },
        ],
        recommendedAction: {
          id: 'sc-block-dns',
          label: 'Block DNS to cdn-worker[.]io & Capture Traffic',
          riskLevel: 'medium',
          requiresApproval: false,
          details:
            'Add DNS sinkhole rule for *.cdn-worker.io and capture last 15 minutes of DNS traffic from BUILD-SRV-02 for forensic analysis.',
        },
      },
      {
        seq: 4,
        title: 'Environment Secret Exfiltration (Suspected)',
        description:
          'Based on the DNS tunnel volume and the process behavior collecting environment variables, it is inferred that CI/CD secrets (AWS access keys, API tokens) were exfiltrated. The exact data transmitted cannot be confirmed from DNS logs alone.',
        mitreStage: 'Collection',
        mitreTechnique: 'Unsecured Credentials: Credentials In Files',
        mitreTechniqueId: 'T1552.001',
        confidence: 63,
        coverage: 'inferred',
        timestamp: '10:23:05',
        iocs: ['/tmp/.env.cache (collected env dump)', 'AWS_ACCESS_KEY_ID in CI env'],
        observables: [],
        recommendedAction: {
          id: 'sc-rotate-aws',
          label: 'Immediate AWS Credential Rotation',
          riskLevel: 'critical',
          requiresApproval: true,
          details:
            'Rotate all AWS IAM credentials stored in CI/CD environment. Audit AWS CloudTrail for any API calls using the compromised keys in the last 2 hours.',
        },
      },
    ],
  },
  // ─── INC-2037: BEC Attack ────────────────────────────────────────────────────
  {
    id: 'INC-2037',
    title: 'BEC Attack — Executive Impersonation + Wire Transfer Attempt',
    severity: 'high',
    status: 'resolved',
    actor: 'Financial Fraud Actor (BEC Group)',
    confidence: 89,
    businessImpact:
      'Wire transfer attempt of $240K blocked by finance team vigilance. No financial loss occurred. Attacker had access to organizational structure — continued targeting is likely.',
    executiveSummary:
      'A business email compromise (BEC) attack targeted the CFO using a CEO lookalike domain. The attacker requested an urgent $240K wire transfer. The finance team identified the spoofed domain before executing the transfer. Incident is resolved; enhanced email authentication (DMARC enforcement) is recommended.',
    affectedSystems: ['cfo@szlholdings.com', 'Email Infrastructure'],
    iocCount: 4,
    stepsEvidenced: 3,
    stepsInferred: 1,
    stepsMissing: 0,
    totalSteps: 3,
    steps: [
      {
        seq: 1,
        title: 'Lookalike Domain Registration',
        description:
          "Attacker registered `szlho1dings.com` (with numeral '1' replacing 'l'), a typosquat of the legitimate `szlholdings.com`. The domain was registered 3 days before the attack and configured with SPF/DKIM to pass basic email security checks.",
        mitreStage: 'Resource Development',
        mitreTechnique: 'Acquire Infrastructure: Domain',
        mitreTechniqueId: 'T1583.001',
        confidence: 91,
        coverage: 'evidenced',
        timestamp: '3 days prior',
        iocs: [
          'szlho1dings.com (registered 3d prior)',
          'MX: mail.szlho1dings.com',
          'SPF record configured',
        ],
        observables: [
          {
            id: 'obs-bec-001',
            type: 'alert',
            source: 'Domain Monitoring',
            rawRef: 'DOM-ALERT-20260416-0037',
            excerpt:
              'TYPOSQUAT DETECTED | szlho1dings.com | Registered: 2026-04-16 | Similar to: szlholdings.com | Registrar: NameCheap',
            timestamp: '2026-04-16 09:22',
            confidence: 97,
          },
        ],
        recommendedAction: undefined,
      },
      {
        seq: 2,
        title: 'Executive Impersonation via Spearphishing Email',
        description:
          'Attacker sent an email from `ceo@szlho1dings.com` to the CFO, impersonating the CEO. The email referenced an authentic-sounding acquisition scenario to create urgency and justify the wire transfer without standard approval processes.',
        mitreStage: 'Initial Access',
        mitreTechnique: 'Phishing: Spearphishing Link',
        mitreTechniqueId: 'T1566.002',
        confidence: 97,
        coverage: 'evidenced',
        timestamp: '08:47:14',
        iocs: [
          'From: ceo@szlho1dings.com',
          'Subject: URGENT — Acquisition wire (confidential)',
          'No attachment — social engineering only',
        ],
        observables: [
          {
            id: 'obs-bec-002',
            type: 'alert',
            source: 'Email Security Gateway',
            rawRef: 'ESG-ALERT-20260419-0037',
            excerpt:
              'HIGH | Lookalike sender domain | ceo@szlho1dings[.]com → cfo@szlholdings.com | No malicious payload | Social engineering flagged',
            timestamp: '08:47:14',
            confidence: 95,
          },
        ],
        recommendedAction: undefined,
      },
      {
        seq: 3,
        title: 'Wire Transfer Fraud Blocked',
        description:
          "The CFO forwarded the request to the finance team for processing. A finance analyst noticed the sender domain discrepancy ('szlho1dings' vs 'szlholdings') before initiating the $240K transfer. SOC was alerted and incident opened. Attacker domain was null-routed.",
        mitreStage: 'Impact',
        mitreTechnique: 'Financial Theft',
        mitreTechniqueId: 'T1657',
        confidence: 99,
        coverage: 'evidenced',
        timestamp: '09:12:33',
        iocs: [
          'Requested amount: $240,000 USD',
          'Destination account: Cayman Islands intermediary',
        ],
        observables: [
          {
            id: 'obs-bec-003',
            type: 'log',
            source: 'Finance System Audit Log',
            rawRef: 'FIN-AUD-20260419-0037',
            excerpt:
              'TRANSFER BLOCKED | Requested by: CFO (forwarded from suspicious email) | Amount: $240,000 | Blocked by: K. Rivera (analyst review) | Reason: Sender domain mismatch',
            timestamp: '09:12:33',
            confidence: 100,
          },
        ],
        recommendedAction: {
          id: 'bec-dmarc-enforce',
          label: 'Enforce DMARC Reject Policy on szlholdings.com',
          riskLevel: 'medium',
          requiresApproval: false,
          details:
            "Update DMARC record from 'quarantine' to 'reject' policy to prevent future spoofing. Also enroll executive email accounts in advanced anti-impersonation scanning.",
        },
      },
    ],
  },
  // ─── INC-2035: Cloud IAM Escalation ─────────────────────────────────────────
  {
    id: 'INC-2035',
    title: 'Cloud IAM Escalation — Overprivileged Role Assumption in AWS',
    severity: 'medium',
    status: 'resolved',
    actor: 'Overprivileged Service Account (Internal)',
    confidence: 76,
    businessImpact:
      'Service account assumed administrator-equivalent role across 3 AWS regions. Broad read access to production S3 buckets and EC2 instances was exercised. No data was exfiltrated — intent appears to be misconfiguration rather than malicious insider.',
    executiveSummary:
      'An internal service account (`svc-terraform`) exploited overly permissive IAM trust relationships to assume a role with broad production access across 3 AWS regions. CloudTrail logs show DescribeInstances and ListBuckets calls across sensitive production environments. The role has been revoked and trust policies hardened. No exfiltration was detected.',
    affectedSystems: ['aws-prod-west', 'aws-prod-east', 'aws-prod-eu'],
    iocCount: 5,
    stepsEvidenced: 2,
    stepsInferred: 1,
    stepsMissing: 0,
    totalSteps: 3,
    steps: [
      {
        seq: 1,
        title: 'Overprivileged IAM Role Assumption',
        description:
          'Service account `svc-terraform` used `sts:AssumeRole` to assume `arn:aws:iam::ACCOUNT:role/ProdAdminRole`, which was configured with an overly permissive trust policy allowing any principal in the account to assume it. The role grants AdministratorAccess.',
        mitreStage: 'Privilege Escalation',
        mitreTechnique: 'Valid Accounts: Cloud Accounts',
        mitreTechniqueId: 'T1078.004',
        confidence: 91,
        coverage: 'evidenced',
        timestamp: '2026-04-18 22:14:05',
        iocs: [
          'Principal: arn:aws:iam::ACCOUNT:user/svc-terraform',
          'Assumed role: arn:aws:iam::ACCOUNT:role/ProdAdminRole',
          'Region: us-east-1 (initial assumption)',
        ],
        observables: [
          {
            id: 'obs-iam-001',
            type: 'log',
            source: 'AWS CloudTrail',
            rawRef: 'CT-EVENT-20260418-224014',
            excerpt:
              'AssumeRole | User: svc-terraform | RoleArn: ProdAdminRole | ResponseStatus: 200 | SourceIP: 10.0.14.22 | UserAgent: aws-cli/2.x',
            timestamp: '22:14:05',
            confidence: 98,
          },
        ],
        recommendedAction: {
          id: 'iam-revoke-role',
          label: 'Revoke ProdAdminRole Trust Policy & Audit Assumptions',
          riskLevel: 'high',
          requiresApproval: true,
          details:
            'Immediately restrict the trust policy on ProdAdminRole to only allow assumption from specific service principals with MFA. Audit all AssumeRole events in the last 30 days.',
        },
      },
      {
        seq: 2,
        title: 'Cloud Resource Enumeration Across Regions',
        description:
          'Using the assumed admin role, the service account performed broad enumeration: DescribeInstances (3 regions, 847 instances), ListBuckets (67 buckets), and DescribeSecurityGroups. Access patterns are consistent with automated tooling rather than manual exploration.',
        mitreStage: 'Discovery',
        mitreTechnique: 'Cloud Infrastructure Discovery',
        mitreTechniqueId: 'T1580',
        confidence: 88,
        coverage: 'evidenced',
        timestamp: '22:14:09',
        iocs: [
          'DescribeInstances: 847 instances across 3 regions',
          'ListBuckets: 67 S3 buckets enumerated',
        ],
        observables: [
          {
            id: 'obs-iam-002',
            type: 'log',
            source: 'AWS CloudTrail',
            rawRef: 'CT-MULTI-20260418-2214',
            excerpt:
              'DescribeInstances | 3 regions | 847 instances | ListBuckets | 67 buckets | DescribeSecurityGroups | Duration: 4s | Automated pattern',
            timestamp: '22:14:09',
            confidence: 88,
          },
        ],
        recommendedAction: undefined,
      },
      {
        seq: 3,
        title: 'Sensitive Bucket Access (Inferred)',
        description:
          'Given the enumeration of 67 S3 buckets including `szl-prod-configs` and `szl-terraform-state`, it is inferred that read access to sensitive configuration and infrastructure state files may have been exercised. CloudTrail S3 data events were not enabled — this cannot be confirmed.',
        mitreStage: 'Collection',
        mitreTechnique: 'Data from Cloud Storage',
        mitreTechniqueId: 'T1530',
        confidence: 58,
        coverage: 'inferred',
        timestamp: '22:14:15',
        iocs: [
          's3://szl-prod-configs (contains API keys)',
          's3://szl-terraform-state (contains infrastructure map)',
        ],
        observables: [],
        recommendedAction: {
          id: 'iam-enable-s3-logging',
          label: 'Enable S3 Data Event Logging & Review Bucket Access',
          riskLevel: 'medium',
          requiresApproval: false,
          details:
            'Enable CloudTrail S3 data event logging for all production buckets. Review access logs for `szl-prod-configs` and `szl-terraform-state` immediately.',
        },
      },
    ],
  },
];

// ─── MITRE Stage Config ────────────────────────────────────────────────────────

const MITRE_STAGE_ORDER = [
  'Reconnaissance',
  'Resource Development',
  'Initial Access',
  'Execution',
  'Persistence',
  'Privilege Escalation',
  'Defense Evasion',
  'Credential Access',
  'Discovery',
  'Lateral Movement',
  'Collection',
  'Command and Control',
  'Exfiltration',
  'Impact',
];

const COVERAGE_CONFIG: Record<
  MitreStageCoverage,
  { label: string; color: string; bg: string; border: string; icon: typeof CheckCircle }
> = {
  evidenced: {
    label: 'Evidenced',
    color: '#c9b787',
    bg: 'rgba(201,183,135,0.08)',
    border: 'rgba(201,183,135,0.25)',
    icon: CheckCircle,
  },
  inferred: {
    label: 'Inferred',
    color: '#c9b787',
    bg: 'rgba(201,183,135,0.08)',
    border: 'rgba(201,183,135,0.25)',
    icon: Brain,
  },
  missing: {
    label: 'Missing',
    color: 'var(--gi-text-muted)',
    bg: 'rgba(100,116,139,0.05)',
    border: 'rgba(100,116,139,0.15)',
    icon: Info,
  },
};

const SEV_CONFIG: Record<string, { color: string; bg: string; border: string }> = {
  critical: { color: '#f5f5f5', bg: 'rgba(245,245,245,0.08)', border: 'rgba(245,245,245,0.25)' },
  high: { color: '#c9b787', bg: 'rgba(201,183,135,0.08)', border: 'rgba(201,183,135,0.25)' },
  medium: { color: '#8a8a8a', bg: 'rgba(138,138,138,0.08)', border: 'rgba(138,138,138,0.25)' },
  low: { color: '#c9b787', bg: 'rgba(201,183,135,0.08)', border: 'rgba(201,183,135,0.25)' },
};

const OBSERVABLE_TYPE_CONFIG: Record<string, { color: string; icon: typeof FileText }> = {
  log: { color: '#c9b787', icon: FileText },
  alert: { color: '#f5f5f5', icon: AlertTriangle },
  network: { color: '#c9b787', icon: Network },
  file: { color: '#c9b787', icon: Database },
  process: { color: '#c9b787', icon: Terminal },
  identity: { color: '#8a8a8a', icon: User },
};

const RISK_CONFIG: Record<string, { color: string; label: string }> = {
  low: { color: '#c9b787', label: 'Low Risk' },
  medium: { color: '#c9b787', label: 'Medium Risk' },
  high: { color: '#c9b787', label: 'High Risk' },
  critical: { color: '#f5f5f5', label: 'Critical Risk' },
};

// ─── Sub-components ────────────────────────────────────────────────────────────

function DemoLabel() {
  return (
    <span
      className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[9px] font-bold tracking-widest uppercase border"
      style={{
        color: '#c9b787',
        borderColor: 'rgba(201,183,135,0.3)',
        background: 'rgba(201,183,135,0.08)',
      }}
    >
      <Flag className="w-2.5 h-2.5" /> DEMO DATA
    </span>
  );
}

function ConfidenceBadge({ value, size = 'sm' }: { value: number; size?: 'sm' | 'xs' }) {
  const color =
    value >= 90 ? '#c9b787' : value >= 75 ? '#c9b787' : value >= 50 ? '#c9b787' : 'var(--gi-text-muted)';
  return (
    <span
      className={cn('font-bold font-mono', size === 'xs' ? 'text-[9px]' : 'text-[11px]')}
      style={{ color }}
    >
      {value > 0 ? `${value}%` : '—'}
    </span>
  );
}

interface ApprovalModalProps {
  action: NonNullable<NarrativeStep['recommendedAction']>;
  stepTitle: string;
  incidentId: string;
  onApprove: (approvalRef: string) => void;
  onDeny: (approvalRef: string) => void;
  onClose: () => void;
}

function ApprovalModal({
  action,
  stepTitle,
  incidentId,
  onApprove,
  onDeny,
  onClose,
}: ApprovalModalProps) {
  const risk = RISK_CONFIG[action.riskLevel];

  // Create approval request then immediately review it (approve or deny)
  const submitMutation = useStandardMutation({
    mutationFn: async (decision: 'approved' | 'rejected') => {
      // Step 1: create the approval request in the policy engine
      const createRes = await fetch(`${API_BASE}/approvals`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          resourceType: 'narrative-response-action',
          resourceId: action.id,
          title: action.label,
          description: `${action.details}\n\nNarrative step: ${stepTitle} | Incident: ${incidentId}`,
          actionClass: 'response_action',
          priority: action.riskLevel,
          requiredApproverRole: action.riskLevel === 'critical' ? 'admin' : 'ops',
        }),
      });
      const createData = await createRes.json().catch(() => ({}));
      const approvalId: number | undefined = createData?.data?.id ?? createData?.id;

      // Step 2: record the review decision (approve or deny).
      // This write MUST succeed — if it fails, the action must not be marked approved/denied
      // because the policy audit record would be missing.
      if (approvalId) {
        const reviewRes = await fetch(`${API_BASE}/approvals/${approvalId}/review`, {
          method: 'POST',
          credentials: 'include',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            decision,
            note: `Analyst decision via Adversary Narrative Engine — incident ${incidentId}`,
          }),
        });
        if (!reviewRes.ok) {
          throw new Error(`Policy engine review write failed (HTTP ${reviewRes.status})`);
        }
      } else {
        // No approval ID means create also failed — throw so onError handles it
        throw new Error('Policy engine unreachable — approval not created');
      }

      return { approvalId, decision };
    },
    onSuccess: ({ approvalId, decision }) => {
      const ref = approvalId
        ? `APRV-${approvalId}`
        : `APRV-${action.id.toUpperCase()}-${Date.now().toString().slice(-6)}`;
      if (decision === 'approved') onApprove(ref);
      else onDeny(ref);
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : 'Policy engine error';
      toast.error(`${msg} — retry or contact SOC admin`);
      // Do NOT call onApprove or onDeny: the action remains pending until audit trail is confirmed
      onClose();
    },
  });

  const isLoading = submitMutation.isPending;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-6"
      style={{ background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(4px)' }}
    >
      <div
        className="w-full max-w-lg rounded-2xl border p-6 space-y-5"
        style={{ background: '#070f1c', borderColor: 'rgba(245,245,245,0.2)' }}
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Shield className="w-4 h-4 text-[#f5f5f5]" />
              <h3 className="text-sm font-bold text-white">Policy Approval Required</h3>
            </div>
            <p className="text-[11px] text-white/40">
              This action requires human authorization before execution
            </p>
          </div>
          <button
            onClick={onClose}
            disabled={isLoading}
            className="text-white/30 hover:text-white/60 transition-colors disabled:opacity-40"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div
          className="rounded-xl p-4 space-y-3 border"
          style={{ borderColor: `${risk.color}25`, background: `${risk.color}06` }}
        >
          <div className="flex items-center gap-2">
            <span
              className="text-[10px] font-bold px-2 py-0.5 rounded border"
              style={{
                color: risk.color,
                borderColor: `${risk.color}30`,
                background: `${risk.color}12`,
              }}
            >
              {risk.label}
            </span>
            <span className="text-[9px] text-white/30">Narrative Step: {stepTitle}</span>
          </div>
          <p className="text-sm font-semibold text-white">{action.label}</p>
          <p className="text-[11px] text-white/50 leading-relaxed">{action.details}</p>
        </div>

        <div
          className="rounded-lg p-3 border text-[10px] text-white/40 space-y-1"
          style={{ borderColor: 'rgba(255,255,255,0.06)', background: 'rgba(255,255,255,0.02)' }}
        >
          <p className="flex items-center gap-1.5">
            <Lock className="w-3 h-3" /> Decision will be written to the policy engine audit trail
            via <span className="font-mono text-white/50">POST /approvals</span>
          </p>
          <p className="flex items-center gap-1.5">
            <ShieldCheck className="w-3 h-3" /> Policy:{' '}
            <span className="font-mono text-white/60">
              response-actions.{action.riskLevel}.requires-human
            </span>
          </p>
          <p className="flex items-center gap-1.5">
            <Activity className="w-3 h-3" /> Approval record bound to incident{' '}
            <span className="font-mono text-white/60">{incidentId}</span>
          </p>
        </div>

        <div className="flex items-center gap-3 pt-1">
          <button
            onClick={() => submitMutation.mutate('rejected')}
            disabled={isLoading}
            className="flex-1 py-2 rounded-xl text-xs font-semibold border transition-all hover:bg-white/5 disabled:opacity-40"
            style={{ borderColor: 'rgba(255,255,255,0.1)', color: 'rgba(255,255,255,0.5)' }}
          >
            {isLoading ? 'Recording…' : 'Deny Action'}
          </button>
          <button
            onClick={() => submitMutation.mutate('approved')}
            disabled={isLoading}
            className="flex-1 py-2 rounded-xl text-xs font-bold border transition-all disabled:opacity-40"
            style={{
              background: 'rgba(201,183,135,0.12)',
              borderColor: 'rgba(201,183,135,0.3)',
              color: '#c9b787',
            }}
          >
            {isLoading ? 'Submitting to policy engine…' : 'Approve & Execute'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────

export default function AdversaryNarrativeEngine() {
  const [incidents, setIncidents] = useState<Incident[]>(NARRATIVE_INCIDENTS);
  const [selectedIncidentId, setSelectedIncidentId] = useState<string>(() => {
    const param = new URLSearchParams(window.location.search).get('incident');
    return param && NARRATIVE_INCIDENTS.some((i) => i.id === param)
      ? param
      : NARRATIVE_INCIDENTS[0].id;
  });
  const [mode, setMode] = useState<'analyst' | 'executive'>('analyst');
  const [activeTab, setActiveTab] = useState<'narrative' | 'mitre' | 'evidence'>('narrative');
  const [expandedStep, setExpandedStep] = useState<number | null>(1);
  const [pendingAction, setPendingAction] = useState<{
    action: NonNullable<NarrativeStep['recommendedAction']>;
    stepTitle: string;
  } | null>(null);
  const [approvedActions, setApprovedActions] = useState<Map<string, string>>(new Map()); // actionId → approvalRef
  const [deniedActions, setDeniedActions] = useState<Map<string, string>>(new Map()); // actionId → approvalRef

  useEffect(() => {
    api.narrativeEngine.narratives(20).then((data) => {
      if (data?.narratives?.length) {
        type NarrativeRow = {
          id: string; title: string; severity: string; status: string; actor: string;
          confidence?: number; businessImpact?: string; executiveSummary?: string;
          affectedSystems?: string[]; iocCount?: number; stepsEvidenced?: number;
          stepsInferred?: number; stepsMissing?: number; totalSteps?: number;
          steps?: NarrativeStep[];
        };
        const mapped: Incident[] = data.narratives.map((n: NarrativeRow) => ({
          id: n.id,
          title: n.title,
          severity: n.severity as Incident['severity'],
          status: n.status,
          actor: n.actor,
          confidence: n.confidence ?? 80,
          businessImpact: n.businessImpact ?? '',
          executiveSummary: n.executiveSummary ?? '',
          affectedSystems: (n.affectedSystems as string[]) ?? [],
          iocCount: n.iocCount ?? 0,
          stepsEvidenced: n.stepsEvidenced ?? 0,
          stepsInferred: n.stepsInferred ?? 0,
          stepsMissing: n.stepsMissing ?? 0,
          totalSteps: n.totalSteps ?? 0,
          steps: (n.steps as NarrativeStep[]) ?? [],
        }));
        setIncidents(mapped);
        const param = new URLSearchParams(window.location.search).get('incident');
        const validId = param && mapped.some((i) => i.id === param) ? param : mapped[0]?.id;
        if (validId) setSelectedIncidentId(validId);
      }
    }).catch(() => { /* leave incidents as-is on error */ });
  }, []);

  const incident =
    incidents.find((i) => i.id === selectedIncidentId) ?? incidents[0] ?? NARRATIVE_INCIDENTS[0];
  const sev = SEV_CONFIG[incident.severity];

  const handleApprove = (approvalRef: string) => {
    if (!pendingAction) return;
    setApprovedActions((prev) => new Map(prev).set(pendingAction.action.id, approvalRef));
    setPendingAction(null);
    toast.success(`Action approved — policy record ${approvalRef} written`, {
      description: pendingAction.action.label,
    });
  };

  const handleDeny = (approvalRef: string) => {
    if (!pendingAction) return;
    setDeniedActions((prev) => new Map(prev).set(pendingAction.action.id, approvalRef));
    setPendingAction(null);
    toast.error(`Action denied — policy record ${approvalRef} written`, {
      description: pendingAction.action.label,
    });
  };

  const handleExportExecutiveSummary = () => {
    toast.success('Executive summary exported', {
      description: 'PDF generation queued — available in Reports',
    });
  };

  // Build MITRE stage map from incident steps
  const mitreStageMap = new Map<
    string,
    { coverage: MitreStageCoverage; confidence: number; stepSeq: number }
  >();
  incident.steps.forEach((step) => {
    if (!mitreStageMap.has(step.mitreStage)) {
      mitreStageMap.set(step.mitreStage, {
        coverage: step.coverage,
        confidence: step.confidence,
        stepSeq: step.seq,
      });
    }
  });

  return (
    <div className="h-full flex flex-col overflow-hidden" style={{ background: '#050d18' }}>
      {/* Approval Modal */}
      {pendingAction && (
        <ApprovalModal
          action={pendingAction.action}
          stepTitle={pendingAction.stepTitle}
          incidentId={incident.id}
          onApprove={handleApprove}
          onDeny={handleDeny}
          onClose={() => setPendingAction(null)}
        />
      )}

      {/* Header */}
      <div
        className="px-6 py-4 border-b shrink-0 flex items-center justify-between"
        style={{ borderColor: 'rgba(255,255,255,0.06)' }}
      >
        <div className="flex items-center gap-3">
          <div
            className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0"
            style={{
              background: 'rgba(138,138,138,0.12)',
              border: '1px solid rgba(138,138,138,0.25)',
            }}
          >
            <BookOpen className="w-4 h-4 text-[#8a8a8a]" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-sm font-bold text-white">Adversary Narrative Engine</h1>
              <DemoLabel />
            </div>
            <p className="text-[10px] text-white/30">
              Evidence-backed attack storyline · MITRE ATT&CK mapped · Analyst & Executive modes
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Mode Toggle */}
          <div
            className="flex items-center gap-2 px-3 py-1.5 rounded-xl border"
            style={{ borderColor: 'rgba(255,255,255,0.08)', background: 'rgba(255,255,255,0.02)' }}
          >
            <button
              onClick={() => setMode('analyst')}
              className={cn(
                'flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[11px] font-medium transition-all',
                mode === 'analyst' ? 'text-[#8a8a8a]' : 'text-white/30 hover:text-white/50',
              )}
              style={
                mode === 'analyst'
                  ? {
                      background: 'rgba(138,138,138,0.15)',
                      border: '1px solid rgba(138,138,138,0.25)',
                    }
                  : {}
              }
            >
              <Terminal className="w-3 h-3" /> Analyst
            </button>
            <button
              onClick={() => setMode('executive')}
              className={cn(
                'flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[11px] font-medium transition-all',
                mode === 'executive' ? 'text-[#c9b787]' : 'text-white/30 hover:text-white/50',
              )}
              style={
                mode === 'executive'
                  ? {
                      background: 'rgba(201,183,135,0.15)',
                      border: '1px solid rgba(201,183,135,0.25)',
                    }
                  : {}
              }
            >
              <Eye className="w-3 h-3" /> Executive
            </button>
          </div>

          <button
            onClick={handleExportExecutiveSummary}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-[11px] font-medium border transition-all hover:bg-white/5"
            style={{ borderColor: 'rgba(255,255,255,0.1)', color: 'rgba(255,255,255,0.5)' }}
          >
            <Download className="w-3 h-3" /> Export
          </button>
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* Left Sidebar — Incident Selector */}
        <div
          className="w-64 shrink-0 border-r flex flex-col overflow-hidden"
          style={{ borderColor: 'rgba(255,255,255,0.05)' }}
        >
          <div className="p-3 border-b shrink-0" style={{ borderColor: 'rgba(255,255,255,0.05)' }}>
            <p className="text-[9px] uppercase tracking-widest font-bold text-white/25 mb-2">
              Active Incidents
            </p>
          </div>
          <div className="flex-1 overflow-y-auto">
            {incidents.map((inc) => {
              const s = SEV_CONFIG[inc.severity];
              const isSelected = inc.id === selectedIncidentId;
              return (
                <button
                  key={inc.id}
                  onClick={() => {
                    setSelectedIncidentId(inc.id);
                    setExpandedStep(1);
                    setActiveTab('narrative');
                  }}
                  className="w-full text-left p-3 border-b transition-all"
                  style={{
                    borderColor: 'rgba(255,255,255,0.04)',
                    background: isSelected ? s.bg : 'transparent',
                    borderLeft: isSelected ? `2px solid ${s.color}` : '2px solid transparent',
                  }}
                >
                  <div className="flex items-center justify-between gap-2 mb-1">
                    <span className="text-[9px] font-mono" style={{ color: s.color }}>
                      {inc.id}
                    </span>
                    <span
                      className="text-[9px] px-1.5 py-0.5 rounded font-bold border"
                      style={{ color: s.color, borderColor: s.border, background: s.bg }}
                    >
                      {inc.severity.toUpperCase()}
                    </span>
                  </div>
                  <p className="text-[11px] text-white/75 font-medium leading-tight mb-1.5 line-clamp-2">
                    {inc.title}
                  </p>
                  <div className="flex items-center gap-2 text-[9px] text-white/30">
                    <span className="flex items-center gap-0.5">
                      <CheckCircle className="w-2.5 h-2.5 text-[#c9b787]" /> {inc.stepsEvidenced}
                    </span>
                    <span className="flex items-center gap-0.5">
                      <Brain className="w-2.5 h-2.5 text-[#c9b787]" /> {inc.stepsInferred}
                    </span>
                    <span className="flex items-center gap-0.5">
                      <Info className="w-2.5 h-2.5 text-slate-500" /> {inc.stepsMissing}
                    </span>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Main Panel */}
        <div className="flex-1 overflow-hidden flex flex-col">
          {/* Incident Header */}
          <div
            className="p-5 border-b shrink-0 space-y-4"
            style={{ borderColor: 'rgba(255,255,255,0.05)' }}
          >
            {/* Executive Mode — Summary Banner */}
            {mode === 'executive' ? (
              <div className="space-y-3">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                      <span className="text-[9px] font-mono text-white/30">{incident.id}</span>
                      <span
                        className="px-2 py-0.5 rounded text-[9px] font-bold border"
                        style={{ color: sev.color, borderColor: sev.border, background: sev.bg }}
                      >
                        {incident.severity.toUpperCase()}
                      </span>
                      <span className="text-[9px] text-white/30">{incident.actor}</span>
                      <span className="text-[9px] text-white/30">
                        Confidence: <ConfidenceBadge value={incident.confidence} size="xs" />
                      </span>
                    </div>
                    <h2 className="text-base font-bold text-white mb-2">{incident.title}</h2>
                  </div>
                </div>
                <div
                  className="rounded-xl p-4 border"
                  style={{
                    borderColor: 'rgba(201,183,135,0.15)',
                    background: 'rgba(201,183,135,0.04)',
                  }}
                >
                  <p className="text-[10px] font-bold text-[#c9b787] uppercase tracking-widest mb-2">
                    Executive Summary
                  </p>
                  <p className="text-[12px] text-white/70 leading-relaxed">
                    {incident.executiveSummary}
                  </p>
                </div>
                <div
                  className="rounded-xl p-3 border"
                  style={{ borderColor: `${sev.color}25`, background: sev.bg }}
                >
                  <p
                    className="text-[10px] font-bold uppercase tracking-widest mb-1"
                    style={{ color: sev.color }}
                  >
                    Business Impact
                  </p>
                  <p className="text-[12px] text-white/70 leading-relaxed">
                    {incident.businessImpact}
                  </p>
                </div>
              </div>
            ) : (
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                    <span className="text-[9px] font-mono text-white/30">{incident.id}</span>
                    <span
                      className="px-2 py-0.5 rounded text-[9px] font-bold border"
                      style={{ color: sev.color, borderColor: sev.border, background: sev.bg }}
                    >
                      {incident.severity.toUpperCase()}
                    </span>
                    <span className="text-[9px] text-white/30">{incident.actor}</span>
                  </div>
                  <h2 className="text-base font-bold text-white mb-1">{incident.title}</h2>
                  <p className="text-[11px] text-white/40 leading-relaxed">
                    {incident.executiveSummary.slice(0, 180)}…
                  </p>
                </div>
                <div className="grid grid-cols-4 gap-3 shrink-0 text-center">
                  {[
                    { label: 'Confidence', value: `${incident.confidence}%`, color: '#c9b787' },
                    { label: 'Evidenced', value: incident.stepsEvidenced, color: '#c9b787' },
                    { label: 'Inferred', value: incident.stepsInferred, color: '#c9b787' },
                    { label: 'IOCs', value: incident.iocCount, color: '#f5f5f5' },
                  ].map(({ label, value, color }) => (
                    <div
                      key={label}
                      className="rounded-xl p-2.5 border"
                      style={{
                        borderColor: 'rgba(255,255,255,0.06)',
                        background: 'rgba(255,255,255,0.02)',
                      }}
                    >
                      <p className="text-base font-bold" style={{ color }}>
                        {value}
                      </p>
                      <p className="text-[9px] text-white/30">{label}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Tabs — only in analyst mode */}
            {mode === 'analyst' && (
              <div className="flex items-center gap-1">
                {(
                  [
                    { id: 'narrative', label: 'Narrative', icon: BookOpen },
                    { id: 'mitre', label: 'MITRE Stages', icon: Layers },
                    { id: 'evidence', label: 'Evidence', icon: Link2 },
                  ] as { id: typeof activeTab; label: string; icon: typeof BookOpen }[]
                ).map((tab) => (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id)}
                    className={cn(
                      'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] font-medium transition-all border',
                      activeTab === tab.id
                        ? 'text-[#8a8a8a]'
                        : 'text-white/35 hover:text-white/55 border-transparent',
                    )}
                    style={
                      activeTab === tab.id
                        ? {
                            background: 'rgba(138,138,138,0.1)',
                            borderColor: 'rgba(138,138,138,0.25)',
                          }
                        : {}
                    }
                  >
                    <tab.icon className="w-3 h-3" />
                    {tab.label}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Tab Content */}
          <div className="flex-1 overflow-y-auto">
            {/* EXECUTIVE MODE — shows narrative in simplified form */}
            {mode === 'executive' && (
              <div className="p-5 space-y-3">
                <p className="text-[10px] text-white/30 uppercase tracking-widest font-bold mb-3">
                  Attack Storyline — Plain Language
                </p>
                {incident.steps.map((step) => {
                  const cov = COVERAGE_CONFIG[step.coverage];
                  const CovIcon = cov.icon;
                  return (
                    <div key={step.seq} className="flex gap-4 items-start">
                      <div className="flex flex-col items-center shrink-0">
                        <div
                          className="w-7 h-7 rounded-full flex items-center justify-center"
                          style={{ background: cov.bg, border: `2px solid ${cov.color}` }}
                        >
                          <CovIcon className="w-3.5 h-3.5" style={{ color: cov.color }} />
                        </div>
                        {step.seq < incident.steps.length && (
                          <div
                            className="w-px flex-1 my-1 min-h-[20px]"
                            style={{ background: 'rgba(255,255,255,0.06)' }}
                          />
                        )}
                      </div>
                      <div className="flex-1 pb-3">
                        <div className="flex items-center gap-2 mb-1">
                          <span
                            className="text-[10px] px-1.5 py-0.5 rounded border font-medium"
                            style={{
                              color: cov.color,
                              borderColor: cov.border,
                              background: cov.bg,
                            }}
                          >
                            {cov.label}
                          </span>
                          <span className="text-[10px] text-white/30">{step.mitreStage}</span>
                          {step.confidence > 0 && (
                            <span className="text-[9px] text-white/25">
                              · conf <ConfidenceBadge value={step.confidence} size="xs" />
                            </span>
                          )}
                        </div>
                        <p className="text-[13px] font-semibold text-white/85 mb-1">{step.title}</p>
                        <p className="text-[11px] text-white/45 leading-relaxed">
                          {step.description}
                        </p>
                        {step.recommendedAction && (
                          <div
                            className="mt-2 flex items-start gap-2 rounded-lg p-2.5 border"
                            style={{
                              borderColor: `${RISK_CONFIG[step.recommendedAction.riskLevel].color}25`,
                              background: `${RISK_CONFIG[step.recommendedAction.riskLevel].color}06`,
                            }}
                          >
                            <Zap
                              className="w-3 h-3 mt-0.5 shrink-0"
                              style={{ color: RISK_CONFIG[step.recommendedAction.riskLevel].color }}
                            />
                            <div className="flex-1">
                              <p className="text-[10px] font-semibold text-white/70">
                                {step.recommendedAction.label}
                              </p>
                            </div>
                            {step.recommendedAction.requiresApproval && (
                              <button
                                onClick={() => {
                                  if (approvedActions.has(step.recommendedAction?.id ?? '')) {
                                    toast.info('Action already approved');
                                    return;
                                  }
                                  if (deniedActions.has(step.recommendedAction?.id ?? '')) {
                                    toast.info('Action was denied — re-submit to reconsider');
                                    return;
                                  }
                                  setPendingAction({
                                    action: step.recommendedAction!,
                                    stepTitle: step.title,
                                  });
                                }}
                                className="shrink-0 text-[9px] px-2 py-0.5 rounded border font-bold transition-all"
                                style={
                                  approvedActions.has(step.recommendedAction.id)
                                    ? {
                                        color: '#c9b787',
                                        borderColor: 'rgba(201,183,135,0.3)',
                                        background: 'rgba(201,183,135,0.1)',
                                      }
                                    : deniedActions.has(step.recommendedAction.id)
                                      ? {
                                          color: 'var(--gi-text-muted)',
                                          borderColor: 'rgba(100,116,139,0.2)',
                                          background: 'rgba(100,116,139,0.06)',
                                        }
                                      : {
                                          color: '#c9b787',
                                          borderColor: 'rgba(201,183,135,0.3)',
                                          background: 'rgba(201,183,135,0.08)',
                                        }
                                }
                              >
                                {approvedActions.has(step.recommendedAction.id)
                                  ? '✓ Approved'
                                  : deniedActions.has(step.recommendedAction.id)
                                    ? '✗ Denied'
                                    : 'Approve →'}
                              </button>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            {/* ANALYST MODE — Narrative Tab */}
            {mode === 'analyst' && activeTab === 'narrative' && (
              <div className="p-5 space-y-0">
                {incident.steps.map((step, idx) => {
                  const cov = COVERAGE_CONFIG[step.coverage];
                  const CovIcon = cov.icon;
                  const isExpanded = expandedStep === step.seq;
                  const isLast = idx === incident.steps.length - 1;
                  const action = step.recommendedAction;

                  return (
                    <div key={step.seq} className="flex gap-4 items-start">
                      {/* Timeline spine */}
                      <div className="flex flex-col items-center shrink-0 pt-4">
                        <div
                          className="w-8 h-8 rounded-full flex items-center justify-center z-10 shrink-0 border-2"
                          style={{ background: cov.bg, borderColor: cov.color }}
                        >
                          <CovIcon className="w-3.5 h-3.5" style={{ color: cov.color }} />
                        </div>
                        {!isLast && (
                          <div
                            className="w-px flex-1 my-1 min-h-[24px]"
                            style={{ background: `${cov.color}30` }}
                          />
                        )}
                      </div>

                      {/* Step Card */}
                      <div className="flex-1 pb-3">
                        <button
                          onClick={() => setExpandedStep(isExpanded ? null : step.seq)}
                          className="w-full text-left rounded-xl border p-4 transition-all hover:bg-white/[0.01]"
                          style={{
                            borderColor: isExpanded ? `${cov.color}30` : 'rgba(255,255,255,0.06)',
                            background: isExpanded ? cov.bg : 'rgba(255,255,255,0.01)',
                          }}
                        >
                          <div className="flex items-start gap-3">
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 mb-1 flex-wrap">
                                <span
                                  className="text-[10px] px-1.5 py-0.5 rounded border"
                                  style={{
                                    color: cov.color,
                                    borderColor: cov.border,
                                    background: cov.bg,
                                  }}
                                >
                                  {cov.label}
                                </span>
                                <span
                                  className="text-[10px] font-mono px-1.5 py-0.5 rounded"
                                  style={{ color: '#c9b787', background: 'rgba(138,138,138,0.1)' }}
                                >
                                  {step.mitreTechniqueId}
                                </span>
                                <span className="text-[9px] text-white/25">{step.mitreStage}</span>
                                {step.timestamp !== '—' && (
                                  <span className="text-[9px] font-mono text-white/25">
                                    {step.timestamp}
                                  </span>
                                )}
                              </div>
                              <p className="text-[13px] font-semibold text-white/90 mb-1">
                                {step.title}
                              </p>
                              <p className="text-[11px] text-white/45 leading-relaxed">
                                {step.description}
                              </p>
                            </div>
                            <div className="flex items-center gap-2 shrink-0">
                              <div className="text-right">
                                <ConfidenceBadge value={step.confidence} />
                                <p className="text-[8px] text-white/25">conf</p>
                              </div>
                              {step.observables.length > 0 && (
                                <span
                                  className="text-[9px] px-1.5 py-0.5 rounded border"
                                  style={{
                                    color: '#c9b787',
                                    borderColor: 'rgba(96,165,250,0.2)',
                                    background: 'rgba(96,165,250,0.06)',
                                  }}
                                >
                                  {step.observables.length} obs
                                </span>
                              )}
                              <ChevronDown
                                className={cn(
                                  'w-3.5 h-3.5 text-white/25 transition-transform',
                                  isExpanded && 'rotate-180',
                                )}
                              />
                            </div>
                          </div>
                        </button>

                        {/* Expanded Detail */}
                        {isExpanded && (
                          <div
                            className="mt-2 rounded-xl border p-4 space-y-4"
                            style={{
                              borderColor: `${cov.color}15`,
                              background: 'rgba(255,255,255,0.01)',
                            }}
                          >
                            {/* Technique detail */}
                            <div>
                              <p className="text-[9px] uppercase tracking-widest text-white/25 mb-1.5">
                                Technique
                              </p>
                              <p className="text-[12px] text-white/70">
                                {step.mitreTechnique}{' '}
                                <span className="font-mono text-[#8a8a8a] text-[10px]">
                                  ({step.mitreTechniqueId})
                                </span>
                              </p>
                            </div>

                            {/* IOCs */}
                            {step.iocs.length > 0 && (
                              <div>
                                <p className="text-[9px] uppercase tracking-widest text-white/25 mb-1.5">
                                  Indicators of Compromise
                                </p>
                                <div className="flex flex-col gap-1">
                                  {step.iocs.map((ioc, i) => (
                                    <div
                                      key={i}
                                      className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-[10px] font-mono"
                                      style={{
                                        background: 'rgba(245,245,245,0.05)',
                                        border: '1px solid rgba(245,245,245,0.12)',
                                      }}
                                    >
                                      <AlertTriangle className="w-3 h-3 text-[#f5f5f5]/60 shrink-0" />
                                      <span className="text-[#f5f5f5]/70 break-all">{ioc}</span>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}

                            {/* Observables */}
                            {step.observables.length > 0 && (
                              <div>
                                <p className="text-[9px] uppercase tracking-widest text-white/25 mb-1.5">
                                  Evidence — Triggering Observables
                                </p>
                                <div className="space-y-2">
                                  {step.observables.map((obs) => {
                                    const ot =
                                      OBSERVABLE_TYPE_CONFIG[obs.type] ??
                                      OBSERVABLE_TYPE_CONFIG.log;
                                    const OtIcon = ot.icon;
                                    return (
                                      <div
                                        key={obs.id}
                                        className="rounded-lg border p-3 space-y-2"
                                        style={{
                                          borderColor: `${ot.color}18`,
                                          background: `${ot.color}05`,
                                        }}
                                      >
                                        <div className="flex items-center justify-between gap-2">
                                          <div className="flex items-center gap-1.5">
                                            <OtIcon
                                              className="w-3 h-3 shrink-0"
                                              style={{ color: ot.color }}
                                            />
                                            <span
                                              className="text-[10px] font-semibold"
                                              style={{ color: ot.color }}
                                            >
                                              {obs.type.toUpperCase()}
                                            </span>
                                            <span className="text-[10px] text-white/40">
                                              {obs.source}
                                            </span>
                                          </div>
                                          <div className="flex items-center gap-2">
                                            <span className="text-[9px] font-mono text-white/25">
                                              {obs.rawRef}
                                            </span>
                                            <span className="text-[9px] font-mono text-white/25">
                                              {obs.timestamp}
                                            </span>
                                            <ConfidenceBadge value={obs.confidence} size="xs" />
                                          </div>
                                        </div>
                                        <pre
                                          className="text-[10px] text-white/55 font-mono leading-relaxed whitespace-pre-wrap break-all p-2 rounded"
                                          style={{ background: 'rgba(0,0,0,0.3)' }}
                                        >
                                          {obs.excerpt}
                                        </pre>
                                      </div>
                                    );
                                  })}
                                </div>
                              </div>
                            )}

                            {/* Missing Evidence note */}
                            {step.coverage === 'missing' && (
                              <div
                                className="flex items-start gap-2.5 rounded-lg p-3 border"
                                style={{
                                  borderColor: 'rgba(100,116,139,0.2)',
                                  background: 'rgba(100,116,139,0.05)',
                                }}
                              >
                                <Info className="w-4 h-4 text-slate-400 shrink-0 mt-0.5" />
                                <p className="text-[11px] text-slate-400 leading-relaxed">
                                  No observables available for this stage. Active monitoring is in
                                  place. The absence of evidence is not evidence of absence — this
                                  stage may not have occurred, or detection coverage may be
                                  insufficient.
                                </p>
                              </div>
                            )}

                            {/* Inferred note */}
                            {step.coverage === 'inferred' && (
                              <div
                                className="flex items-start gap-2.5 rounded-lg p-3 border"
                                style={{
                                  borderColor: 'rgba(201,183,135,0.2)',
                                  background: 'rgba(201,183,135,0.05)',
                                }}
                              >
                                <Brain className="w-4 h-4 text-[#c9b787] shrink-0 mt-0.5" />
                                <p className="text-[11px] text-[#c9b787]/70 leading-relaxed">
                                  This step is <strong>inferred</strong> from behavioral patterns
                                  and correlated signals — not yet confirmed by direct observable
                                  evidence. Confidence is lower and should be treated as a working
                                  hypothesis.
                                </p>
                              </div>
                            )}

                            {/* Recommended Action */}
                            {action && (
                              <div>
                                <p className="text-[9px] uppercase tracking-widest text-white/25 mb-1.5">
                                  Recommended Response Action
                                </p>
                                <div
                                  className="rounded-lg border p-3 space-y-2.5"
                                  style={{
                                    borderColor: `${RISK_CONFIG[action.riskLevel].color}25`,
                                    background: `${RISK_CONFIG[action.riskLevel].color}06`,
                                  }}
                                >
                                  <div className="flex items-start justify-between gap-3">
                                    <div className="flex-1">
                                      <div className="flex items-center gap-2 mb-1">
                                        <span
                                          className="text-[9px] px-1.5 py-0.5 rounded border font-bold"
                                          style={{
                                            color: RISK_CONFIG[action.riskLevel].color,
                                            borderColor: `${RISK_CONFIG[action.riskLevel].color}30`,
                                            background: `${RISK_CONFIG[action.riskLevel].color}12`,
                                          }}
                                        >
                                          {RISK_CONFIG[action.riskLevel].label}
                                        </span>
                                        {action.requiresApproval && (
                                          <span
                                            className="text-[9px] px-1.5 py-0.5 rounded border"
                                            style={{
                                              color: '#c9b787',
                                              borderColor: 'rgba(138,138,138,0.25)',
                                              background: 'rgba(138,138,138,0.08)',
                                            }}
                                          >
                                            Requires Approval
                                          </span>
                                        )}
                                      </div>
                                      <p className="text-[12px] font-semibold text-white/80 mb-1">
                                        {action.label}
                                      </p>
                                      <p className="text-[10px] text-white/40 leading-relaxed">
                                        {action.details}
                                      </p>
                                    </div>
                                    <button
                                      onClick={() => {
                                        if (approvedActions.has(action.id)) {
                                          toast.info('Already approved');
                                          return;
                                        }
                                        if (deniedActions.has(action.id)) {
                                          toast.info('Action denied — re-open to reconsider');
                                          return;
                                        }
                                        if (action.requiresApproval) {
                                          setPendingAction({ action, stepTitle: step.title });
                                        } else {
                                          setApprovedActions((prev) =>
                                            new Map(prev).set(
                                              action.id,
                                              `DIRECT-${action.id.toUpperCase()}`,
                                            ),
                                          );
                                          toast.success('Action approved and queued');
                                        }
                                      }}
                                      className="shrink-0 flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] font-bold border transition-all"
                                      style={
                                        approvedActions.has(action.id)
                                          ? {
                                              color: '#c9b787',
                                              borderColor: 'rgba(201,183,135,0.3)',
                                              background: 'rgba(201,183,135,0.1)',
                                            }
                                          : deniedActions.has(action.id)
                                            ? {
                                                color: 'var(--gi-text-muted)',
                                                borderColor: 'rgba(100,116,139,0.2)',
                                                background: 'rgba(100,116,139,0.06)',
                                              }
                                            : {
                                                color: '#c9b787',
                                                borderColor: 'rgba(201,183,135,0.3)',
                                                background: 'rgba(201,183,135,0.08)',
                                              }
                                      }
                                    >
                                      {approvedActions.has(action.id) ? (
                                        <>
                                          <CheckCircle className="w-3 h-3" /> Approved
                                        </>
                                      ) : deniedActions.has(action.id) ? (
                                        <>
                                          <X className="w-3 h-3" /> Denied
                                        </>
                                      ) : action.requiresApproval ? (
                                        <>
                                          <Shield className="w-3 h-3" /> Approve
                                        </>
                                      ) : (
                                        <>
                                          <Play className="w-3 h-3" /> Execute
                                        </>
                                      )}
                                    </button>
                                  </div>
                                  {(approvedActions.has(action.id) ||
                                    deniedActions.has(action.id)) && (
                                    <div
                                      className="flex items-center gap-1.5 text-[9px] pt-1 border-t"
                                      style={{
                                        borderColor: 'rgba(255,255,255,0.06)',
                                        color: 'rgba(255,255,255,0.3)',
                                      }}
                                    >
                                      <Lock className="w-3 h-3" />
                                      Decision written to policy engine · Approval record:{' '}
                                      <span className="font-mono">
                                        {approvedActions.get(action.id) ??
                                          deniedActions.get(action.id)}
                                      </span>
                                    </div>
                                  )}
                                </div>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            {/* ANALYST MODE — MITRE Stages Tab */}
            {mode === 'analyst' && activeTab === 'mitre' && (
              <div className="p-5 space-y-4">
                <div className="flex items-center justify-between mb-2">
                  <div>
                    <p className="text-xs font-bold text-white/80 mb-0.5">
                      MITRE ATT&CK — Stage Coverage
                    </p>
                    <p className="text-[10px] text-white/30">
                      Which stages are evidenced, inferred, or not yet observed for {incident.id}
                    </p>
                  </div>
                  <div className="flex items-center gap-3">
                    {(['evidenced', 'inferred', 'missing'] as MitreStageCoverage[]).map((c) => {
                      const cfg = COVERAGE_CONFIG[c];
                      const CfgIcon = cfg.icon;
                      return (
                        <div
                          key={c}
                          className="flex items-center gap-1.5 text-[10px]"
                          style={{ color: cfg.color }}
                        >
                          <CfgIcon className="w-3 h-3" />
                          {cfg.label}
                        </div>
                      );
                    })}
                  </div>
                </div>

                <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-3">
                  {MITRE_STAGE_ORDER.map((stageName) => {
                    const stageData = mitreStageMap.get(stageName);
                    const coverage: MitreStageCoverage = stageData?.coverage ?? 'missing';
                    const cfg = COVERAGE_CONFIG[coverage];
                    const CfgIcon = cfg.icon;
                    const incidentStep = incident.steps.find((s) => s.mitreStage === stageName);

                    return (
                      <div
                        key={stageName}
                        className="rounded-xl border p-4 transition-all"
                        style={{
                          borderColor: stageData ? cfg.border : 'rgba(255,255,255,0.06)',
                          background: stageData ? cfg.bg : 'rgba(255,255,255,0.01)',
                          opacity: stageData ? 1 : 0.5,
                        }}
                      >
                        <div className="flex items-start justify-between gap-2 mb-2">
                          <CfgIcon
                            className="w-4 h-4 shrink-0 mt-0.5"
                            style={{ color: cfg.color }}
                          />
                          <span
                            className="text-[9px] font-bold uppercase tracking-widest px-1.5 py-0.5 rounded border shrink-0"
                            style={{
                              color: cfg.color,
                              borderColor: cfg.border,
                              background: cfg.bg,
                            }}
                          >
                            {cfg.label}
                          </span>
                        </div>
                        <p className="text-[12px] font-semibold text-white/80 mb-1">{stageName}</p>
                        {incidentStep ? (
                          <>
                            <p className="text-[10px] text-white/35 leading-tight mb-2 line-clamp-2">
                              {incidentStep.mitreTechnique}
                            </p>
                            <div className="flex items-center justify-between">
                              <span className="text-[9px] font-mono text-[#8a8a8a]/70">
                                {incidentStep.mitreTechniqueId}
                              </span>
                              <ConfidenceBadge value={incidentStep.confidence} size="xs" />
                            </div>
                            {/* Confidence bar */}
                            {incidentStep.confidence > 0 && (
                              <div
                                className="mt-2 h-1 rounded-full"
                                style={{ background: 'rgba(255,255,255,0.06)' }}
                              >
                                <div
                                  className="h-full rounded-full transition-all"
                                  style={{
                                    width: `${incidentStep.confidence}%`,
                                    background: cfg.color,
                                    opacity: 0.7,
                                  }}
                                />
                              </div>
                            )}
                          </>
                        ) : (
                          <p className="text-[10px] text-white/20 leading-tight">
                            No activity observed in this incident
                          </p>
                        )}
                      </div>
                    );
                  })}
                </div>

                {/* Coverage summary */}
                <div
                  className="rounded-xl border p-4 grid grid-cols-3 gap-4 text-center mt-2"
                  style={{
                    borderColor: 'rgba(255,255,255,0.06)',
                    background: 'rgba(255,255,255,0.01)',
                  }}
                >
                  {(['evidenced', 'inferred', 'missing'] as MitreStageCoverage[]).map((c) => {
                    const cfg = COVERAGE_CONFIG[c];
                    const count = incident.steps.filter((s) => s.coverage === c).length;
                    return (
                      <div key={c}>
                        <p className="text-lg font-bold" style={{ color: cfg.color }}>
                          {count}
                        </p>
                        <p className="text-[10px] text-white/30">{cfg.label} stages</p>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* ANALYST MODE — Evidence Tab */}
            {mode === 'analyst' && activeTab === 'evidence' && (
              <div className="p-5 space-y-4">
                <div>
                  <p className="text-xs font-bold text-white/80 mb-0.5">
                    All Observables — {incident.id}
                  </p>
                  <p className="text-[10px] text-white/30">
                    Complete list of evidence artifacts. Click any record to view the raw excerpt
                    and trace back to the narrative step.
                  </p>
                </div>

                {incident.steps
                  .filter((s) => s.observables.length > 0)
                  .map((step) => (
                    <div key={step.seq} className="space-y-2">
                      <div className="flex items-center gap-2 py-1">
                        <ArrowRight className="w-3 h-3 text-white/25" />
                        <span className="text-[10px] font-bold text-white/50">
                          Step {step.seq}: {step.title}
                        </span>
                        <span className="text-[9px] font-mono text-[#8a8a8a]/60">
                          {step.mitreTechniqueId}
                        </span>
                      </div>
                      {step.observables.map((obs) => {
                        const ot = OBSERVABLE_TYPE_CONFIG[obs.type] ?? OBSERVABLE_TYPE_CONFIG.log;
                        const OtIcon = ot.icon;
                        return (
                          <div
                            key={obs.id}
                            className="rounded-xl border p-4 space-y-2"
                            style={{
                              borderColor: `${ot.color}15`,
                              background: 'rgba(255,255,255,0.01)',
                            }}
                          >
                            <div className="flex items-start justify-between gap-3">
                              <div className="flex items-center gap-2">
                                <div
                                  className="w-6 h-6 rounded-lg flex items-center justify-center shrink-0"
                                  style={{
                                    background: `${ot.color}12`,
                                    border: `1px solid ${ot.color}25`,
                                  }}
                                >
                                  <OtIcon className="w-3 h-3" style={{ color: ot.color }} />
                                </div>
                                <div>
                                  <div className="flex items-center gap-1.5">
                                    <span
                                      className="text-[10px] font-bold"
                                      style={{ color: ot.color }}
                                    >
                                      {obs.type.toUpperCase()}
                                    </span>
                                    <span className="text-[10px] text-white/40">{obs.source}</span>
                                  </div>
                                  <div className="flex items-center gap-2 text-[9px] text-white/25 font-mono">
                                    <span>{obs.rawRef}</span>
                                    <span>·</span>
                                    <span>{obs.timestamp}</span>
                                  </div>
                                </div>
                              </div>
                              <div className="flex items-center gap-2 shrink-0">
                                <div className="text-right">
                                  <ConfidenceBadge value={obs.confidence} size="xs" />
                                  <p className="text-[8px] text-white/20">confidence</p>
                                </div>
                                <span
                                  className="text-[8px] px-1.5 py-0.5 rounded border"
                                  style={{
                                    color: '#c9b787',
                                    borderColor: 'rgba(96,165,250,0.2)',
                                    background: 'rgba(96,165,250,0.06)',
                                  }}
                                >
                                  {obs.id}
                                </span>
                              </div>
                            </div>
                            <pre
                              className="text-[10px] text-white/55 font-mono leading-relaxed whitespace-pre-wrap break-all p-2.5 rounded"
                              style={{ background: 'rgba(0,0,0,0.35)' }}
                            >
                              {obs.excerpt}
                            </pre>
                            <div className="flex items-center gap-1.5 text-[9px] text-white/25">
                              <Link2 className="w-3 h-3" />
                              <span>
                                Linked to narrative step {step.seq}:{' '}
                                <span className="text-white/40">{step.title}</span>
                              </span>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
