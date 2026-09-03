#!/usr/bin/env python3
"""Retire unused Replit Vite dependencies from the a11oy/Sentra build.

The migration is deterministic, convergence-safe, and fail-closed. It accepts
known work that another protected writer has already completed, but rejects
unknown stub drift and incomplete runtime contracts.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

PLUGIN_KEYS = (
    "@replit/vite-plugin-cartographer",
    "@replit/vite-plugin-dev-banner",
    "@replit/vite-plugin-runtime-error-modal",
)

ROOT = Path(__file__).resolve().parents[2]


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"{path}: expected a JSON object")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def remove_manifest_dependencies(relative_path: str) -> None:
    path = ROOT / relative_path
    data = load_json(path)
    dev_dependencies = data.get("devDependencies")
    if not isinstance(dev_dependencies, dict):
        raise SystemExit(f"{path}: devDependencies object missing")

    removed = [name for name in PLUGIN_KEYS if name in dev_dependencies]
    for name in removed:
        del dev_dependencies[name]

    if removed:
        write_json(path, data)
        print(f"{relative_path}: removed {', '.join(removed)}")
    else:
        print(f"{relative_path}: retired dependencies already absent")


def remove_catalog_entries() -> None:
    path = ROOT / "organs/sentra/pnpm-workspace.yaml"
    lines = path.read_text(encoding="utf-8").splitlines()
    removed: set[str] = set()
    kept: list[str] = []

    for line in lines:
        stripped = line.strip()
        match = next(
            (name for name in PLUGIN_KEYS if stripped.startswith(f'"{name}":')),
            None,
        )
        if match is None:
            kept.append(line)
        else:
            removed.add(match)

    if removed:
        path.write_text("\n".join(kept) + "\n", encoding="utf-8")
        print(f"organs/sentra/pnpm-workspace.yaml: removed {', '.join(sorted(removed))}")
    else:
        print("organs/sentra/pnpm-workspace.yaml: retired catalog entries already absent")


def restore_api_client_stub() -> None:
    manifest_path = ROOT / "organs/sentra/stubs/api-client-react/package.json"
    manifest = load_json(manifest_path)
    dependencies = manifest.setdefault("dependencies", {})
    if not isinstance(dependencies, dict):
        raise SystemExit(f"{manifest_path}: dependencies must be an object")
    if dependencies.get("@tanstack/react-query") != "catalog:":
        dependencies["@tanstack/react-query"] = "catalog:"
        write_json(manifest_path, manifest)

    source_path = ROOT / "organs/sentra/stubs/api-client-react/index.ts"
    current = source_path.read_text(encoding="utf-8")
    canonical_markers = (
        "export function useStandardQuery",
        "export function useStandardMutation",
    )
    if all(marker in current for marker in canonical_markers):
        print("api-client-react stub: canonical wrappers already present")
        return
    if current.strip() != "export {};":
        raise SystemExit(f"{source_path}: unknown API-client stub drift")

    source_path.write_text(
        """import {
  type QueryKey,
  type UseMutationOptions,
  type UseQueryOptions,
  useMutation,
  useQuery,
} from '@tanstack/react-query';

const STANDARD_DEFAULTS = {
  staleTime: 60_000,
  gcTime: 5 * 60_000,
  refetchOnWindowFocus: false,
  retry: 1,
} as const;

export function useStandardQuery<
  TQueryFnData = unknown,
  TError = Error,
  TData = TQueryFnData,
  TQueryKey extends QueryKey = QueryKey,
>(options: UseQueryOptions<TQueryFnData, TError, TData, TQueryKey>) {
  return useQuery<TQueryFnData, TError, TData, TQueryKey>({
    ...STANDARD_DEFAULTS,
    ...options,
  });
}

export function useStandardMutation<
  TData = unknown,
  TError = Error,
  TVariables = void,
  TContext = unknown,
>(options: UseMutationOptions<TData, TError, TVariables, TContext>) {
  return useMutation<TData, TError, TVariables, TContext>(options);
}
""",
        encoding="utf-8",
    )
    print("api-client-react stub: restored canonical wrappers")


def restore_shared_ui_operational_contract() -> None:
    path = ROOT / "organs/sentra/stubs/shared-ui/index.ts"
    current = path.read_text(encoding="utf-8")
    if "export const OperationalOwnerChip" in current:
        print("shared-ui stub: operational contract already present")
        return

    contract = r'''

// Canonical operational-primitives contract for the self-contained offline build.
export type OperationalStatus = string;
export type RiskLevel = 'low' | 'medium' | 'high' | 'critical';
export type ApprovalState = 'none' | 'pending' | 'approved' | 'rejected' | 'expired';
export type ActorType = 'user' | 'system' | 'agent';
export type OperationalOwner = {
  userId?: string | number;
  name?: string;
  email?: string;
  role?: string;
  assignedAt?: string;
};
export type EvidenceItem = {
  id: string;
  label: string;
  value: string;
  source?: string;
  confidence?: number;
  timestamp?: string;
};
export type AuditHistoryEntry = Record<string, unknown>;
export type EscalationPath = Record<string, unknown>;
export type NextAction = Record<string, unknown>;
export type OperationalEntity = Record<string, unknown> & { id: string | number };
export type StatusConfig = {
  label: string;
  color: string;
  bg: string;
  dotColor?: string;
  terminal?: boolean;
};

export const STATUS_CONFIGS: Record<string, StatusConfig> = {};
export const RISK_CONFIGS: Record<string, { label: string; color: string; bg: string; score: number }> = {};
export const APPROVAL_CONFIGS: Record<string, { label: string; color: string; bg: string }> = {};

export function getStatusConfig(status: string): StatusConfig {
  return { label: status, color: '#7c85a0', bg: 'rgba(124,133,160,0.08)' };
}

export function getRiskConfig(level: string) {
  return { label: level, color: '#7c85a0', bg: 'rgba(124,133,160,0.08)', score: 0 };
}

export function getApprovalConfig(state: string) {
  return { label: state, color: '#7c85a0', bg: 'rgba(124,133,160,0.08)' };
}

export function riskScoreToLevel(score: number): RiskLevel {
  if (score >= 0.85) return 'critical';
  if (score >= 0.65) return 'high';
  if (score >= 0.35) return 'medium';
  return 'low';
}

export function severityToRiskLevel(severity: string): RiskLevel {
  return severity === 'critical' || severity === 'high' || severity === 'medium'
    ? severity
    : 'low';
}

export function isTerminalStatus(status: string): boolean {
  return ['completed', 'succeeded', 'failed', 'cancelled', 'rejected', 'resolved', 'closed'].includes(status);
}

export function formatAgo(value?: string): string {
  return value || '—';
}

export function formatDuration(startedAt?: string, completedAt?: string): string {
  return startedAt && completedAt ? `${startedAt} – ${completedAt}` : '—';
}

export const OperationalStatusBadge = NoopComponent;
export const OperationalRiskBadge = NoopComponent;
export const OperationalApprovalBadge = NoopComponent;
export const OperationalOwnerChip = NoopComponent;
export const OperationalEvidencePanel = NoopComponent;
export const OperationalAuditTimeline = NoopComponent;
export const OperationalEscalationPanel = NoopComponent;
export const OperationalDetailPane = NoopComponent;
export const OperationalQueueRow = NoopComponent;
'''
    path.write_text(current.rstrip() + contract + "\n", encoding="utf-8")
    print("shared-ui stub: restored operational contract")


def collect_runtime_named_imports() -> set[str]:
    # Excluding braces prevents a multiline match from crossing import
    # declarations and creating false positives from unrelated packages.
    import_pattern = re.compile(
        r"^[ \t]*(?:import|export)[ \t]*(?:type[ \t]+)?\{"
        r"(?P<names>[^{}]*)\}[ \t\r\n]*from[ \t\r\n]*['\"]"
        r"@szl-holdings/shared-ui(?:/[^'\"]*)?['\"]",
        re.MULTILINE,
    )

    required: set[str] = set()
    source_root = ROOT / "organs/sentra/web/src"
    for source_path in sorted(source_root.rglob("*")):
        if source_path.suffix not in {".ts", ".tsx"}:
            continue
        source = source_path.read_text(encoding="utf-8")
        for match in import_pattern.finditer(source):
            names = re.sub(r"/\*.*?\*/", "", match.group("names"), flags=re.DOTALL)
            for raw_name in names.split(","):
                name = raw_name.strip()
                if not name or name.startswith("type "):
                    continue
                original = re.split(r"\s+as\s+", name, maxsplit=1)[0].strip()
                if re.fullmatch(r"[A-Za-z_$][\w$]*", original):
                    required.add(original)
    return required


def collect_exported_runtime_values(source: str) -> set[str]:
    return set(
        re.findall(
            r"export\s+(?:async\s+)?(?:const|let|var|function|class)\s+"
            r"([A-Za-z_$][\w$]*)",
            source,
        )
    )


def audit_shared_ui_contract() -> None:
    path = ROOT / "organs/sentra/stubs/shared-ui/index.ts"
    exported = collect_exported_runtime_values(path.read_text(encoding="utf-8"))
    required = collect_runtime_named_imports()
    missing = sorted(required - exported)
    if missing:
        raise SystemExit(
            "shared-ui offline stub is missing runtime named exports: "
            + ", ".join(missing)
        )
    print(f"shared-ui runtime export audit passed for {len(required)} named imports")


def main() -> None:
    remove_manifest_dependencies("web/package.json")
    remove_manifest_dependencies("organs/sentra/web/package.json")
    remove_catalog_entries()
    restore_api_client_stub()
    restore_shared_ui_operational_contract()
    audit_shared_ui_contract()
    print("Replit Vite retirement migration prepared successfully")


if __name__ == "__main__":
    main()
