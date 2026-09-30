import { createElement, type ReactNode } from 'react';

export type AutonomyMode = 'supervised' | 'autonomous' | 'hybrid' | 'recommend' | 'approved-act';
export type EvidenceSource = Record<string, unknown>;
export type PolicyState = string;
export type LeaderboardEntry = Record<string, any>;
export type EvalResultDetail = Record<string, any>;
export type SubmitScorePayload = Record<string, any>;

export const productAccent = {
  alloy: '#f5f5f5',
  lyte: '#60a5fa',
  terra: '#34d399',
  aegis: '#ef4444',
  vessels: '#38bdf8',
  counsel: '#a78bfa',
  carlota: '#f59e0b',
  sentra: '#ef4444',
} as const;

export const ProofEnvelope = (props: any) => createElement('div', props);
export const AtlasScenePanel = (_props: any) => null;
export const SubstrateWorkflowPanel = (_props: any) => null;
export const DecisionPanel = (_props: any) => null;
export const GovernancePanel = (_props: any) => null;
export const TrustPanel = (_props: any) => null;
export const PolicyPanel = (_props: any) => null;
export const BenchmarkCard = (_props: any) => null;
export const EvalBadge = (_props: any) => null;
export const LeaderboardTable = (_props: any) => null;
export const ResultDetailDrawer = (_props: any) => null;
export const SubmitScoreForm = (_props: any) => null;
export const Badge = (props: any) => createElement('span', props);
export const Card = (props: any) => createElement('div', props);
export const CardContent = (props: any) => createElement('div', props);
export const CardHeader = (props: any) => createElement('div', props);
export const CardTitle = (props: any) => createElement('h3', props);
export const Button = (props: any) => createElement('button', props);
export const Input = (props: any) => createElement('input', props);
export const Select = (props: any) => createElement('select', props);
export const Tabs = (props: any) => createElement('div', props);
export const TabsList = (props: any) => createElement('div', props);
export const TabsTrigger = (props: any) => createElement('button', props);
export const TabsContent = (props: any) => createElement('div', props);
