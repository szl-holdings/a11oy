/**
 * Sentra Integration Adapter contracts + Stub adapters.
 *
 * All adapters are in-app stubs. No real outbound calls are made.
 * Every adapter returns the exact required string when not configured:
 *   "Integration not configured. No action executed."
 *
 * Safety Gate: all adapter action() calls must pass policy gate before execution.
 * Integration adapters only execute defensive read/trigger operations — no
 * offensive or retaliatory actions are implemented or callable.
 */

import type { ActionClass, OwnershipStatus } from './sentra-store';
import { runPolicyGate, SENTRA_DENIAL_MESSAGE, requiresApproval } from './policy-engine';
import { sentraStore } from './sentra-store';

// ─── Types ────────────────────────────────────────────────────────────────────

export type AdapterCategory =
  | 'EDR'
  | 'SIEM'
  | 'SOAR'
  | 'Identity'
  | 'Cloud'
  | 'Network'
  | 'Vulnerability'
  | 'Ticketing'
  | 'Threat Intelligence'
  | 'Email Security'
  | 'OT/SCADA'
  | 'Data Loss Prevention'
  | 'Deception';

export type AdapterStatus = 'configured' | 'not_configured' | 'error' | 'disabled';

export interface IntegrationMeta {
  id: string;
  name: string;
  vendor: string;
  category: AdapterCategory;
  description: string;
  icon: string;
  status: AdapterStatus;
  tenant_id: string | null;
  supported_actions: ActionClass[];
  created_at: string;
  updated_at: string;
  last_tested_at: string | null;
  test_result: { ok: boolean; latency_ms: number; message: string } | null;
  documentation_url: string;
  connection_fields: Array<{ key: string; label: string; sensitive: boolean; optional: boolean }>;
}

export interface AdapterActionResult {
  ok: boolean;
  executed: boolean;
  message: string;
  raw_response: Record<string, unknown> | null;
  policy_result: 'allow' | 'deny' | 'not_evaluated';
  denial_message?: string;
  latency_ms: number;
  integration_not_configured: boolean;
  executed_at: string;
}

export interface AdapterActionContext {
  action_class: ActionClass;
  target_asset_id: string;
  target_asset_name: string;
  target_ownership_status: OwnershipStatus;
  target_asset_tenant_id: string;
  requesting_tenant_id: string;
  approval_id?: string;
  approval_status?: 'approved' | 'pending' | 'rejected' | 'expired' | 'canceled';
  incident_id?: string;
  payload?: Record<string, unknown>;
}

export interface IntegrationAdapter {
  meta: IntegrationMeta;

  /**
   * Execute a defensive action through this integration.
   * All calls must pass the policy gate. If the integration is not configured,
   * returns the exact string: "Integration not configured. No action executed."
   */
  action(ctx: AdapterActionContext): Promise<AdapterActionResult>;

  /**
   * Test connectivity to the integration endpoint (stub).
   */
  test(): Promise<{ ok: boolean; latency_ms: number; message: string }>;

  /**
   * Fetch integration status (stub).
   */
  status(): Promise<{ ok: boolean; configured: boolean; message: string }>;
}

// ─── Integration Not Configured result ───────────────────────────────────────

const INTEGRATION_NOT_CONFIGURED_MESSAGE = 'Integration not configured. No action executed.';

function notConfiguredResult(): AdapterActionResult {
  return {
    ok: false,
    executed: false,
    message: INTEGRATION_NOT_CONFIGURED_MESSAGE,
    raw_response: null,
    policy_result: 'not_evaluated',
    latency_ms: 0,
    integration_not_configured: true,
    executed_at: new Date().toISOString(),
  };
}

function deniedResult(denial_message: string, reason: string): AdapterActionResult {
  return {
    ok: false,
    executed: false,
    message: reason,
    raw_response: null,
    policy_result: 'deny',
    denial_message,
    latency_ms: 1,
    integration_not_configured: false,
    executed_at: new Date().toISOString(),
  };
}

// ─── Base Stub Adapter ────────────────────────────────────────────────────────

abstract class BaseStubAdapter implements IntegrationAdapter {
  abstract meta: IntegrationMeta;

  protected runGate(ctx: AdapterActionContext): ReturnType<typeof runPolicyGate> {
    // Validate asset existence against the live registry — not a hardcoded default.
    const assetInRegistry = sentraStore.getAsset(ctx.target_asset_id);
    const assetExists = !!assetInRegistry;
    // Use the adapter's registered tenant_id as the integration binding, not the caller's.
    const integrationTenantId = this.meta.tenant_id ?? ctx.requesting_tenant_id;
    return runPolicyGate({
      action_class: ctx.action_class,
      target_asset_id: ctx.target_asset_id,
      target_ownership_status: ctx.target_ownership_status,
      integration_tenant_id: integrationTenantId,
      requesting_tenant_id: ctx.requesting_tenant_id,
      asset_tenant_id: assetInRegistry?.tenant_id ?? ctx.target_asset_tenant_id,
      approval_status: ctx.approval_status,
      audit_logging_enabled: true,
      rollback_strategy_exists: true,
      asset_exists: assetExists,
    });
  }

  protected gatedAction(ctx: AdapterActionContext, fn: () => AdapterActionResult): AdapterActionResult {
    if (this.meta.status === 'not_configured') {
      return notConfiguredResult();
    }

    const gate = this.runGate(ctx);
    if (!gate.allowed) {
      return deniedResult(gate.denial_message ?? SENTRA_DENIAL_MESSAGE, gate.reason);
    }

    if (requiresApproval(ctx.action_class) && ctx.approval_status !== 'approved') {
      return deniedResult(
        SENTRA_DENIAL_MESSAGE,
        `Action '${ctx.action_class}' requires an approved approval record before execution`,
      );
    }

    return fn();
  }

  async action(ctx: AdapterActionContext): Promise<AdapterActionResult> {
    return this.gatedAction(ctx, () => ({
      ok: true,
      executed: true,
      message: `[STUB] ${ctx.action_class} executed via ${this.meta.name} — no real outbound call made`,
      raw_response: { stub: true, integration: this.meta.id, action: ctx.action_class, target: ctx.target_asset_id },
      policy_result: 'allow' as const,
      latency_ms: Math.floor(Math.random() * 200) + 50,
      integration_not_configured: false,
      executed_at: new Date().toISOString(),
    }));
  }

  async test(): Promise<{ ok: boolean; latency_ms: number; message: string }> {
    if (this.meta.status === 'not_configured') {
      return { ok: false, latency_ms: 0, message: INTEGRATION_NOT_CONFIGURED_MESSAGE };
    }
    return {
      ok: true,
      latency_ms: Math.floor(Math.random() * 80) + 20,
      message: `[STUB] ${this.meta.name} connectivity test passed — no real outbound call made`,
    };
  }

  async status(): Promise<{ ok: boolean; configured: boolean; message: string }> {
    return {
      ok: this.meta.status !== 'error',
      configured: this.meta.status === 'configured',
      message: `[STUB] ${this.meta.name} status: ${this.meta.status}`,
    };
  }
}

// ─── Microsoft Defender for Endpoint ─────────────────────────────────────────

export class MicrosoftDefenderAdapter extends BaseStubAdapter {
  meta: IntegrationMeta = {
    id: 'int-defender',
    name: 'Microsoft Defender for Endpoint',
    vendor: 'Microsoft',
    category: 'EDR',
    description: 'Endpoint Detection & Response — isolate, release, and investigate endpoints. Stub adapter returns simulated responses only.',
    icon: 'Shield',
    status: 'configured',
    tenant_id: 'tenant-001',
    supported_actions: ['contain_owned_asset', 'restore_owned_asset', 'enrich', 'detect', 'alert'],
    created_at: '2024-01-15T08:00:00Z',
    updated_at: '2025-03-01T08:00:00Z',
    last_tested_at: '2026-05-05T06:00:00Z',
    test_result: { ok: true, latency_ms: 45, message: '[STUB] API connectivity confirmed — stub adapter' },
    documentation_url: 'https://learn.microsoft.com/en-us/defender-endpoint/',
    connection_fields: [
      { key: 'tenant_id', label: 'Azure Tenant ID', sensitive: false, optional: false },
      { key: 'client_id', label: 'App Registration Client ID', sensitive: false, optional: false },
      { key: 'client_secret', label: 'Client Secret', sensitive: true, optional: false },
    ],
  };

  async action(ctx: AdapterActionContext): Promise<AdapterActionResult> {
    return this.gatedAction(ctx, () => {
      const actions: Record<string, string> = {
        contain_owned_asset: `[STUB] MDE machine isolation triggered for ${ctx.target_asset_name} — machine ID queued for isolation`,
        restore_owned_asset: `[STUB] MDE machine release triggered for ${ctx.target_asset_name} — isolation removed`,
        enrich: `[STUB] MDE enrichment for ${ctx.target_asset_name} — threat intel, process tree, and network connections fetched`,
        detect: `[STUB] MDE alerts fetched for ${ctx.target_asset_name} — 3 active alerts returned`,
        alert: `[STUB] MDE custom alert created for ${ctx.target_asset_name}`,
      };
      return {
        ok: true,
        executed: true,
        message: actions[ctx.action_class] ?? `[STUB] MDE action ${ctx.action_class} acknowledged`,
        raw_response: { stub: true, machine: ctx.target_asset_name, action: ctx.action_class, status: 'Pending', requestId: `mde-req-${Date.now()}` },
        policy_result: 'allow',
        latency_ms: 67,
        integration_not_configured: false,
        executed_at: new Date().toISOString(),
      };
    });
  }
}

// ─── CrowdStrike Falcon ───────────────────────────────────────────────────────

export class CrowdStrikeAdapter extends BaseStubAdapter {
  meta: IntegrationMeta = {
    id: 'int-crowdstrike',
    name: 'CrowdStrike Falcon',
    vendor: 'CrowdStrike',
    category: 'EDR',
    description: 'EDR + threat intelligence platform — network containment, RTR session, and intelligence enrichment. Stub adapter.',
    icon: 'Zap',
    status: 'configured',
    tenant_id: 'tenant-001',
    supported_actions: ['contain_owned_asset', 'restore_owned_asset', 'enrich', 'detect', 'alert'],
    created_at: '2024-02-01T08:00:00Z',
    updated_at: '2025-03-01T08:00:00Z',
    last_tested_at: '2026-05-05T06:00:00Z',
    test_result: { ok: true, latency_ms: 38, message: '[STUB] Falcon API connectivity confirmed — stub adapter' },
    documentation_url: 'https://falcon.crowdstrike.com/documentation/',
    connection_fields: [
      { key: 'client_id', label: 'API Client ID', sensitive: false, optional: false },
      { key: 'client_secret', label: 'API Client Secret', sensitive: true, optional: false },
      { key: 'base_url', label: 'Base URL', sensitive: false, optional: true },
    ],
  };

  async action(ctx: AdapterActionContext): Promise<AdapterActionResult> {
    return this.gatedAction(ctx, () => ({
      ok: true,
      executed: true,
      message: `[STUB] CrowdStrike Falcon ${ctx.action_class} for ${ctx.target_asset_name} — RTR session queued`,
      raw_response: { stub: true, device_id: ctx.target_asset_id, action: ctx.action_class, session_id: `cs-session-${Date.now()}` },
      policy_result: 'allow',
      latency_ms: 42,
      integration_not_configured: false,
      executed_at: new Date().toISOString(),
    }));
  }
}

// ─── Microsoft Sentinel (SIEM) ────────────────────────────────────────────────

export class MicrosoftSentinelAdapter extends BaseStubAdapter {
  meta: IntegrationMeta = {
    id: 'int-sentinel',
    name: 'Microsoft Sentinel',
    vendor: 'Microsoft',
    category: 'SIEM',
    description: 'Cloud-native SIEM — alert ingestion, incident creation, KQL hunting queries. Stub adapter.',
    icon: 'Eye',
    status: 'configured',
    tenant_id: 'tenant-001',
    supported_actions: ['detect', 'alert', 'enrich', 'create_ticket', 'update_case'],
    created_at: '2024-01-15T08:00:00Z',
    updated_at: '2025-03-01T08:00:00Z',
    last_tested_at: '2026-05-05T06:00:00Z',
    test_result: { ok: true, latency_ms: 55, message: '[STUB] Sentinel API connectivity confirmed — stub adapter' },
    documentation_url: 'https://learn.microsoft.com/en-us/azure/sentinel/',
    connection_fields: [
      { key: 'workspace_id', label: 'Log Analytics Workspace ID', sensitive: false, optional: false },
      { key: 'workspace_key', label: 'Workspace Key', sensitive: true, optional: false },
      { key: 'subscription_id', label: 'Azure Subscription ID', sensitive: false, optional: false },
    ],
  };
}

// ─── Splunk SIEM ──────────────────────────────────────────────────────────────

export class SplunkAdapter extends BaseStubAdapter {
  meta: IntegrationMeta = {
    id: 'int-splunk',
    name: 'Splunk Enterprise Security',
    vendor: 'Splunk',
    category: 'SIEM',
    description: 'Enterprise SIEM — alert ingestion, correlation rules, threat hunting. Stub adapter — not configured.',
    icon: 'Search',
    status: 'not_configured',
    tenant_id: null,
    supported_actions: ['detect', 'alert', 'enrich', 'update_case'],
    created_at: '2024-01-15T08:00:00Z',
    updated_at: '2024-01-15T08:00:00Z',
    last_tested_at: null,
    test_result: null,
    documentation_url: 'https://docs.splunk.com/Documentation/ES',
    connection_fields: [
      { key: 'host', label: 'Splunk Host', sensitive: false, optional: false },
      { key: 'port', label: 'Port', sensitive: false, optional: false },
      { key: 'token', label: 'API Token', sensitive: true, optional: false },
    ],
  };
}

// ─── Microsoft Entra ID ───────────────────────────────────────────────────────

export class MicrosoftEntraAdapter extends BaseStubAdapter {
  meta: IntegrationMeta = {
    id: 'int-entra',
    name: 'Microsoft Entra ID',
    vendor: 'Microsoft',
    category: 'Identity',
    description: 'Identity & access management — disable accounts, revoke sessions, rotate credentials. Stub adapter.',
    icon: 'User',
    status: 'configured',
    tenant_id: 'tenant-001',
    supported_actions: ['revoke_owned_access', 'rotate_owned_secret', 'enrich', 'restore_owned_asset'],
    created_at: '2024-01-15T08:00:00Z',
    updated_at: '2025-03-01T08:00:00Z',
    last_tested_at: '2026-05-05T06:00:00Z',
    test_result: { ok: true, latency_ms: 32, message: '[STUB] Entra ID API connectivity confirmed — stub adapter' },
    documentation_url: 'https://learn.microsoft.com/en-us/entra/',
    connection_fields: [
      { key: 'tenant_id', label: 'Azure Tenant ID', sensitive: false, optional: false },
      { key: 'client_id', label: 'App Registration Client ID', sensitive: false, optional: false },
      { key: 'client_secret', label: 'Client Secret', sensitive: true, optional: false },
    ],
  };

  async action(ctx: AdapterActionContext): Promise<AdapterActionResult> {
    return this.gatedAction(ctx, () => {
      const actions: Record<string, string> = {
        revoke_owned_access: `[STUB] Entra ID: account disabled + all refresh tokens revoked for ${ctx.target_asset_name}`,
        rotate_owned_secret: `[STUB] Entra ID: password reset + MFA forced for ${ctx.target_asset_name}`,
        enrich: `[STUB] Entra ID: sign-in risk score, group memberships, and recent activity fetched for ${ctx.target_asset_name}`,
        restore_owned_asset: `[STUB] Entra ID: account re-enabled for ${ctx.target_asset_name}`,
      };
      return {
        ok: true,
        executed: true,
        message: actions[ctx.action_class] ?? `[STUB] Entra ID action ${ctx.action_class} acknowledged`,
        raw_response: { stub: true, user_id: ctx.target_asset_id, action: ctx.action_class, status: 'Completed', requestId: `entra-req-${Date.now()}` },
        policy_result: 'allow',
        latency_ms: 35,
        integration_not_configured: false,
        executed_at: new Date().toISOString(),
      };
    });
  }
}

// ─── AWS Security Hub ─────────────────────────────────────────────────────────

export class AWSSecurityHubAdapter extends BaseStubAdapter {
  meta: IntegrationMeta = {
    id: 'int-aws',
    name: 'AWS Security Hub',
    vendor: 'Amazon Web Services',
    category: 'Cloud',
    description: 'Cloud security posture + GuardDuty findings — finding ingestion, isolation via VPC, IAM revocation. Stub adapter.',
    icon: 'Cloud',
    status: 'configured',
    tenant_id: 'tenant-001',
    supported_actions: ['detect', 'alert', 'contain_owned_asset', 'revoke_owned_access', 'enrich', 'rotate_owned_secret'],
    created_at: '2024-01-15T08:00:00Z',
    updated_at: '2025-03-01T08:00:00Z',
    last_tested_at: '2026-05-05T06:00:00Z',
    test_result: { ok: true, latency_ms: 61, message: '[STUB] AWS Security Hub connectivity confirmed — stub adapter' },
    documentation_url: 'https://docs.aws.amazon.com/securityhub/',
    connection_fields: [
      { key: 'access_key_id', label: 'AWS Access Key ID', sensitive: false, optional: false },
      { key: 'secret_access_key', label: 'AWS Secret Access Key', sensitive: true, optional: false },
      { key: 'region', label: 'AWS Region', sensitive: false, optional: false },
    ],
  };
}

// ─── Azure Security Center ────────────────────────────────────────────────────

export class AzureDefenderAdapter extends BaseStubAdapter {
  meta: IntegrationMeta = {
    id: 'int-azure',
    name: 'Microsoft Defender for Cloud',
    vendor: 'Microsoft',
    category: 'Cloud',
    description: 'Cloud security posture management — security alerts, recommendations, and JIT access control. Stub adapter.',
    icon: 'CloudLightning',
    status: 'configured',
    tenant_id: 'tenant-001',
    supported_actions: ['detect', 'alert', 'contain_owned_asset', 'enrich'],
    created_at: '2024-01-15T08:00:00Z',
    updated_at: '2025-03-01T08:00:00Z',
    last_tested_at: '2026-05-05T06:00:00Z',
    test_result: { ok: true, latency_ms: 48, message: '[STUB] Azure Defender for Cloud connectivity confirmed — stub adapter' },
    documentation_url: 'https://learn.microsoft.com/en-us/azure/defender-for-cloud/',
    connection_fields: [
      { key: 'subscription_id', label: 'Azure Subscription ID', sensitive: false, optional: false },
      { key: 'client_id', label: 'Client ID', sensitive: false, optional: false },
      { key: 'client_secret', label: 'Client Secret', sensitive: true, optional: false },
    ],
  };
}

// ─── GitHub Advanced Security ──────────────────────────────────────────────────

export class GitHubAdvancedSecurityAdapter extends BaseStubAdapter {
  meta: IntegrationMeta = {
    id: 'int-github',
    name: 'GitHub Advanced Security',
    vendor: 'GitHub',
    category: 'Vulnerability',
    description: 'SAST, SCA, secret scanning — code scanning alerts, secret revocation triggers. Stub adapter.',
    icon: 'GitBranch',
    status: 'configured',
    tenant_id: 'tenant-001',
    supported_actions: ['detect', 'alert', 'enrich', 'rotate_owned_secret'],
    created_at: '2024-01-15T08:00:00Z',
    updated_at: '2025-03-01T08:00:00Z',
    last_tested_at: '2026-05-05T06:00:00Z',
    test_result: { ok: true, latency_ms: 29, message: '[STUB] GitHub Advanced Security connectivity confirmed — stub adapter' },
    documentation_url: 'https://docs.github.com/en/code-security',
    connection_fields: [
      { key: 'token', label: 'GitHub Personal Access Token', sensitive: true, optional: false },
      { key: 'org', label: 'GitHub Organization', sensitive: false, optional: false },
    ],
  };
}

// ─── Cloudflare WAF ───────────────────────────────────────────────────────────

export class CloudflareAdapter extends BaseStubAdapter {
  meta: IntegrationMeta = {
    id: 'int-cloudflare',
    name: 'Cloudflare WAF + Firewall',
    vendor: 'Cloudflare',
    category: 'Network',
    description: 'WAF rules, IP blocking, DDoS mitigation — defensive network containment only. Stub adapter.',
    icon: 'Globe',
    status: 'configured',
    tenant_id: 'tenant-001',
    supported_actions: ['contain_owned_asset', 'alert', 'enrich', 'detect'],
    created_at: '2024-01-15T08:00:00Z',
    updated_at: '2025-03-01T08:00:00Z',
    last_tested_at: '2026-05-05T06:00:00Z',
    test_result: { ok: true, latency_ms: 24, message: '[STUB] Cloudflare API connectivity confirmed — stub adapter' },
    documentation_url: 'https://developers.cloudflare.com/waf/',
    connection_fields: [
      { key: 'api_token', label: 'API Token', sensitive: true, optional: false },
      { key: 'zone_id', label: 'Zone ID', sensitive: false, optional: false },
    ],
  };
}

// ─── PagerDuty ────────────────────────────────────────────────────────────────

export class PagerDutyAdapter extends BaseStubAdapter {
  meta: IntegrationMeta = {
    id: 'int-pagerduty',
    name: 'PagerDuty',
    vendor: 'PagerDuty',
    category: 'SOAR',
    description: 'On-call alerting and incident escalation — notify responders, create incidents, auto-escalate. Stub adapter.',
    icon: 'Bell',
    status: 'configured',
    tenant_id: 'tenant-001',
    supported_actions: ['notify', 'alert', 'create_ticket', 'update_case'],
    created_at: '2024-01-15T08:00:00Z',
    updated_at: '2025-03-01T08:00:00Z',
    last_tested_at: '2026-05-05T06:00:00Z',
    test_result: { ok: true, latency_ms: 33, message: '[STUB] PagerDuty API connectivity confirmed — stub adapter' },
    documentation_url: 'https://developer.pagerduty.com/',
    connection_fields: [
      { key: 'api_key', label: 'API Key', sensitive: true, optional: false },
      { key: 'service_id', label: 'Service ID', sensitive: false, optional: false },
    ],
  };
}

// ─── Jira Service Management ──────────────────────────────────────────────────

export class JiraAdapter extends BaseStubAdapter {
  meta: IntegrationMeta = {
    id: 'int-jira',
    name: 'Jira Service Management',
    vendor: 'Atlassian',
    category: 'Ticketing',
    description: 'Ticketing and ITSM — create, update, and close security tickets. Stub adapter.',
    icon: 'FileText',
    status: 'not_configured',
    tenant_id: null,
    supported_actions: ['create_ticket', 'update_case', 'notify'],
    created_at: '2024-01-15T08:00:00Z',
    updated_at: '2024-01-15T08:00:00Z',
    last_tested_at: null,
    test_result: null,
    documentation_url: 'https://developer.atlassian.com/cloud/jira/',
    connection_fields: [
      { key: 'base_url', label: 'Jira Base URL', sensitive: false, optional: false },
      { key: 'email', label: 'Email', sensitive: false, optional: false },
      { key: 'api_token', label: 'API Token', sensitive: true, optional: false },
      { key: 'project_key', label: 'Project Key', sensitive: false, optional: false },
    ],
  };
}

// ─── ServiceNow ───────────────────────────────────────────────────────────────

export class ServiceNowAdapter extends BaseStubAdapter {
  meta: IntegrationMeta = {
    id: 'int-servicenow',
    name: 'ServiceNow SecOps',
    vendor: 'ServiceNow',
    category: 'SOAR',
    description: 'Security Operations — incident response orchestration, change management, CMDB sync. Stub adapter — not configured.',
    icon: 'Settings',
    status: 'not_configured',
    tenant_id: null,
    supported_actions: ['create_ticket', 'update_case', 'notify', 'generate_report'],
    created_at: '2024-01-15T08:00:00Z',
    updated_at: '2024-01-15T08:00:00Z',
    last_tested_at: null,
    test_result: null,
    documentation_url: 'https://developer.servicenow.com/',
    connection_fields: [
      { key: 'instance_url', label: 'ServiceNow Instance URL', sensitive: false, optional: false },
      { key: 'username', label: 'Username', sensitive: false, optional: false },
      { key: 'password', label: 'Password', sensitive: true, optional: false },
    ],
  };
}

// ─── GCP Security Command Center ─────────────────────────────────────────────

export class GCPSecurityAdapter extends BaseStubAdapter {
  meta: IntegrationMeta = {
    id: 'int-gcp',
    name: 'GCP Security Command Center',
    vendor: 'Google Cloud',
    category: 'Cloud',
    description: 'Cloud-native security for GCP — finding ingestion, IAM revocation, workload isolation. Stub adapter.',
    icon: 'Shield',
    status: 'configured',
    tenant_id: 'tenant-001',
    supported_actions: ['detect', 'alert', 'enrich', 'revoke_owned_access'],
    created_at: '2024-03-01T08:00:00Z',
    updated_at: '2025-03-01T08:00:00Z',
    last_tested_at: '2026-05-05T06:00:00Z',
    test_result: { ok: true, latency_ms: 53, message: '[STUB] GCP SCC API connectivity confirmed — stub adapter' },
    documentation_url: 'https://cloud.google.com/security-command-center',
    connection_fields: [
      { key: 'project_id', label: 'GCP Project ID', sensitive: false, optional: false },
      { key: 'service_account_key', label: 'Service Account JSON Key', sensitive: true, optional: false },
    ],
  };
}

// ─── Dragos (OT/SCADA) ────────────────────────────────────────────────────────

export class DragosAdapter extends BaseStubAdapter {
  meta: IntegrationMeta = {
    id: 'int-dragos',
    name: 'Dragos Platform',
    vendor: 'Dragos',
    category: 'OT/SCADA',
    description: 'OT/ICS threat detection and visibility — asset discovery, threat intelligence, OT incident detection. Stub adapter — not configured.',
    icon: 'Cpu',
    status: 'not_configured',
    tenant_id: null,
    supported_actions: ['detect', 'alert', 'enrich'],
    created_at: '2024-01-15T08:00:00Z',
    updated_at: '2024-01-15T08:00:00Z',
    last_tested_at: null,
    test_result: null,
    documentation_url: 'https://www.dragos.com/platform/',
    connection_fields: [
      { key: 'host', label: 'Dragos Host', sensitive: false, optional: false },
      { key: 'api_token', label: 'API Token', sensitive: true, optional: false },
    ],
  };
}

// ─── Tenable Vulnerability Management ─────────────────────────────────────────

export class TenableAdapter extends BaseStubAdapter {
  meta: IntegrationMeta = {
    id: 'int-tenable',
    name: 'Tenable Vulnerability Management',
    vendor: 'Tenable',
    category: 'Vulnerability',
    description: 'Continuous vulnerability assessment — scan assets, ingest findings, prioritize remediation. Stub adapter — not configured.',
    icon: 'AlertTriangle',
    status: 'not_configured',
    tenant_id: null,
    supported_actions: ['detect', 'enrich', 'alert'],
    created_at: '2024-01-15T08:00:00Z',
    updated_at: '2024-01-15T08:00:00Z',
    last_tested_at: null,
    test_result: null,
    documentation_url: 'https://docs.tenable.com/',
    connection_fields: [
      { key: 'access_key', label: 'Access Key', sensitive: true, optional: false },
      { key: 'secret_key', label: 'Secret Key', sensitive: true, optional: false },
    ],
  };
}

// ─── Proofpoint Email Security ─────────────────────────────────────────────────

export class ProofpointAdapter extends BaseStubAdapter {
  meta: IntegrationMeta = {
    id: 'int-proofpoint',
    name: 'Proofpoint Email Security',
    vendor: 'Proofpoint',
    category: 'Email Security',
    description: 'Email threat protection — phishing detection, BEC alerts, URL rewrite analysis. Stub adapter — not configured.',
    icon: 'Mail',
    status: 'not_configured',
    tenant_id: null,
    supported_actions: ['detect', 'alert', 'enrich'],
    created_at: '2024-01-15T08:00:00Z',
    updated_at: '2024-01-15T08:00:00Z',
    last_tested_at: null,
    test_result: null,
    documentation_url: 'https://help.proofpoint.com/',
    connection_fields: [
      { key: 'principal', label: 'Service Principal', sensitive: false, optional: false },
      { key: 'secret', label: 'Service Secret', sensitive: true, optional: false },
    ],
  };
}

// ─── Registry ─────────────────────────────────────────────────────────────────

export const ADAPTERS: IntegrationAdapter[] = [
  new MicrosoftDefenderAdapter(),
  new CrowdStrikeAdapter(),
  new MicrosoftSentinelAdapter(),
  new SplunkAdapter(),
  new MicrosoftEntraAdapter(),
  new AWSSecurityHubAdapter(),
  new AzureDefenderAdapter(),
  new GitHubAdvancedSecurityAdapter(),
  new CloudflareAdapter(),
  new PagerDutyAdapter(),
  new JiraAdapter(),
  new ServiceNowAdapter(),
  new GCPSecurityAdapter(),
  new DragosAdapter(),
  new TenableAdapter(),
  new ProofpointAdapter(),
];

export function getAdapter(id: string): IntegrationAdapter | undefined {
  return ADAPTERS.find(a => a.meta.id === id);
}

export const ADAPTERS_BY_CATEGORY = ADAPTERS.reduce(
  (acc, a) => {
    const cat = a.meta.category;
    if (!acc[cat]) acc[cat] = [];
    acc[cat].push(a);
    return acc;
  },
  {} as Record<AdapterCategory, IntegrationAdapter[]>,
);
