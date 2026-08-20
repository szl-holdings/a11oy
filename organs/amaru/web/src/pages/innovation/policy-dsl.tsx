import { useState, useMemo, useEffect } from 'react';
import { Link } from 'wouter';
import { RELAY_POLICIES, RELAY_MAPPINGS, RELAY_MODELS, RELAY_DESTINATIONS } from '@/data/fabric';
import { useInnovationStore } from '@/lib/innovation-store';
import { validateDslRule, parseDslRules as parseDslRulesShared } from '@/lib/agentic';
import { FabricHeader, FabricCard, FabricStat, SeverityChip } from '@/components/fabric/primitives';
import { Badge, Button } from '@/components/ui';
import { ArrowLeft, Play, CheckCircle, XCircle, AlertTriangle, History, Code, LayoutGrid, Plus, Trash2 } from 'lucide-react';

type Enforcement = 'block' | 'warn' | 'redact' | 'quarantine' | 'notify';
type Mode = 'dsl' | 'visual';

interface DslVersion {
  readonly version: number;
  readonly content: string;
  readonly savedAt: string;
  readonly description: string;
}

interface VisualRule {
  id: string;
  field: string;
  operator: '==' | '!=' | '>' | '<' | '>=' | '<=';
  value: string;
  enforcement: Enforcement;
}

interface EvalResult {
  readonly ruleId: string;
  readonly ruleName: string;
  readonly mappingId: string;
  readonly mappingName: string;
  readonly triggered: boolean;
  readonly enforcement: Enforcement;
  readonly reason: string;
}

const SEED_DSL = `# Amaru Policy DSL v1.0 — Activation governance rules
# Syntax: \`RULE "<name>" WHEN <condition> THEN <action>\`
# Conditions: fields.pii_class, destination.piiAllowed, model.qualityScore, mapping.confidence
# Actions: block, warn, redact, quarantine, notify

RULE "PII to non-PII destination"
  WHEN fields.pii_class IN [financial, health, gov_id]
    AND destination.piiAllowed = false
  THEN block
  WITH reason = "Sensitive PII fields cannot flow to this destination contract"

RULE "Low quality model gate"
  WHEN model.qualityScore < 80
  THEN warn
  WITH reason = "Source model quality below activation threshold"

RULE "High-confidence mapping required for prod"
  WHEN mapping.confidence < 0.75
    AND destination.category IN [crm, erp]
  THEN quarantine
  WITH reason = "Mapping confidence insufficient for production CRM/ERP"

RULE "Auth expiry pre-flight"
  WHEN destination.authState IN [expired, rotation_required]
  THEN block
  WITH reason = "Destination credentials require rotation before activation"

RULE "Red governance gate"
  WHEN model.governanceState = red
    OR destination.governanceState = red
  THEN block
  WITH reason = "Red governance state — activation blocked pending remediation"`;

const VERSION_HISTORY: readonly DslVersion[] = [
  { version: 1, content: '# Initial policy set\nRULE "PII gate"\n  WHEN fields.pii_class IN [health, gov_id]\n    AND destination.piiAllowed = false\n  THEN block\n  WITH reason = "PII not permitted"', savedAt: '2026-04-20T10:00:00Z', description: 'Initial PII gate' },
  { version: 2, content: '# Added quality gate\n# ...(prior rules)\n\nRULE "Quality gate"\n  WHEN model.qualityScore < 75\n  THEN warn\n  WITH reason = "Low quality"', savedAt: '2026-04-28T14:30:00Z', description: 'Added quality and confidence gates' },
  { version: 3, content: SEED_DSL, savedAt: '2026-05-03T09:15:00Z', description: 'Full governance ruleset — 5 rules' },
];

function fnv1a(s: string): number {
  let h = 0x811c9dc5;
  for (const c of s) { h ^= c.charCodeAt(0); h = Math.imul(h, 0x01000193) >>> 0; }
  return h >>> 0;
}

function parseDslRules(dsl: string): { name: string; when: string; then: Enforcement }[] {
  return parseDslRulesShared(dsl).map((r) => ({ name: r.name, when: r.when, then: r.then as Enforcement }));
}

function evaluateAgainstMappings(rules: { name: string; when: string; then: Enforcement }[]): EvalResult[] {
  const results: EvalResult[] = [];
  RELAY_MAPPINGS.slice(0, 6).forEach((m) => {
    const model = RELAY_MODELS.find((mo) => mo.id === m.modelId);
    const dest = RELAY_DESTINATIONS.find((d) => d.id === m.destinationId);
    if (!model || !dest) return;
    rules.forEach((rule) => {
      const when = rule.when;
      let triggered = false;
      let reason = rule.name;
      if (when.includes('pii_class') && when.includes('piiAllowed') && !dest.piiAllowed && model.piiScore > 0.3) { triggered = true; reason = 'PII mismatch between model and destination contract'; }
      else if (when.includes('qualityScore < 80') && model.qualityScore < 80) { triggered = true; reason = `Model quality ${model.qualityScore} < 80`; }
      else if (when.includes('confidence < 0.75') && m.confidence < 0.75) { triggered = true; reason = `Mapping confidence ${m.confidence} < 0.75`; }
      else if (when.includes('authState') && (dest.authState === 'expired' || dest.authState === 'rotation_required')) { triggered = true; reason = `Auth state: ${dest.authState}`; }
      else if (when.includes('red') && (model.governanceState === 'red' || dest.governanceState === 'red')) { triggered = true; reason = 'Red governance detected'; }
      if (triggered) {
        results.push({ ruleId: `rule-${fnv1a(rule.name).toString(16).slice(0, 6)}`, ruleName: rule.name, mappingId: m.id, mappingName: m.name, triggered, enforcement: rule.then, reason });
      }
    });
  });
  return results;
}

const ENFORCEMENT_BADGE: Record<Enforcement, 'failed' | 'partial' | 'paused' | 'default'> = {
  block: 'failed', warn: 'partial', redact: 'partial', quarantine: 'paused', notify: 'default',
};

export default function PolicyDslPage() {
  const { recordDslVersion, setDslActiveRuleCount } = useInnovationStore();
  const [mode, setMode] = useState<Mode>('dsl');
  const [dslContent, setDslContent] = useState(SEED_DSL);
  const [versions, setVersions] = useState<DslVersion[]>([...VERSION_HISTORY]);
  const [evalResults, setEvalResults] = useState<EvalResult[] | null>(null);
  const [evalLoading, setEvalLoading] = useState(false);
  const [parseError, setParseError] = useState<string | null>(null);
  const [saveDescription, setSaveDescription] = useState('');
  const [showHistory, setShowHistory] = useState(false);
  const [visualRules, setVisualRules] = useState<VisualRule[]>([
    { id: 'vr-1', field: 'model.qualityScore', operator: '<', value: '80', enforcement: 'warn' },
    { id: 'vr-2', field: 'destination.authState', operator: '==', value: 'expired', enforcement: 'block' },
  ]);

  const parsedRules = useMemo(() => {
    try {
      const rules = parseDslRules(dslContent);
      setParseError(null);
      return rules;
    } catch {
      setParseError('Parse error — check RULE/WHEN/THEN syntax');
      return [];
    }
  }, [dslContent]);

  const runEval = () => {
    setEvalLoading(true);
    setTimeout(() => {
      setEvalResults(evaluateAgainstMappings(parsedRules));
      setEvalLoading(false);
    }, 600);
  };

  const validationErrors = useMemo(() => {
    const errs: string[] = [];
    for (const r of parsedRules) {
      const v = validateDslRule(r);
      if (!v.ok) errs.push(`"${r.name}": ${v.reason}`);
    }
    return errs;
  }, [parsedRules]);

  const saveVersion = () => {
    if (validationErrors.length > 0) return;
    const desc = saveDescription.trim() || `Version ${versions.length + 1}`;
    const nextVersion = versions.length + 1;
    setVersions((prev) => [...prev, { version: nextVersion, content: dslContent, savedAt: '2026-05-05T03:55:00Z', description: desc }]);
    recordDslVersion({ version: nextVersion, description: desc, savedAt: '2026-05-05T03:55:00Z', ruleCount: parsedRules.length, content: dslContent });
    setSaveDescription('');
  };

  useEffect(() => {
    setDslActiveRuleCount(parsedRules.length);
  }, [parsedRules.length, setDslActiveRuleCount]);

  const restoreVersion = (v: DslVersion) => { setDslContent(v.content); setShowHistory(false); setEvalResults(null); };

  const addVisualRule = () => {
    setVisualRules((prev) => [...prev, { id: `vr-${prev.length + 1}-${fnv1a(`visual:${prev.length}`).toString(16).slice(0, 6)}`, field: 'model.qualityScore', operator: '<', value: '80', enforcement: 'warn' }]);
  };
  const removeVisualRule = (id: string) => setVisualRules((prev) => prev.filter((r) => r.id !== id));
  const updateVisualRule = (id: string, patch: Partial<VisualRule>) => setVisualRules((prev) => prev.map((r) => r.id === id ? { ...r, ...patch } : r));

  /**
   * Compiles the visual-builder rules into the executable DSL grammar so
   * they participate in `runCoalition` exactly like hand-authored rules.
   * Wired into the "Compile to DSL" action below.
   */
  const compileVisualRulesToDsl = (): string => {
    if (visualRules.length === 0) return '';
    const lines = visualRules.map((r, i) => {
      const op = r.operator;
      const valueIsNum = !Number.isNaN(Number(r.value));
      const rhs = valueIsNum ? r.value : r.value;
      return `RULE "Visual rule ${i + 1}"\n  WHEN ${r.field} ${op} ${rhs}\n  THEN ${r.enforcement}`;
    });
    return `# Compiled from visual builder\n\n${lines.join('\n\n')}`;
  };

  const compileToDslAndSwitch = () => {
    const compiled = compileVisualRulesToDsl();
    if (!compiled) return;
    setDslContent((prev) => `${prev.trimEnd()}\n\n${compiled}\n`);
    setMode('dsl');
  };

  const triggered = evalResults?.filter((r) => r.triggered).length ?? 0;

  return (
    <div>
      <FabricHeader
        eyebrow="ONE-OF-ONE · 10"
        title="Policy-as-Code DSL"
        blurb="A small A11oy-native policy language for expressing activation governance rules. Visual rule-builder for non-technical operators. Version history and Sentra-anchored audit. Evaluated against next sync before any byte moves."
        trailing={
          <Link href="/innovation" className="flex items-center gap-1.5 text-[11px] text-[#c9b787] hover:underline">
            <ArrowLeft className="w-3 h-3" /> Innovation Brief
          </Link>
        }
      />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <FabricStat label="DSL rules" value={parsedRules.length} tone="gold" />
        <FabricStat label="Existing policies" value={RELAY_POLICIES.length} />
        <FabricStat label="Versions saved" value={versions.length} />
        {evalResults && <FabricStat label="Eval hits" value={triggered} tone={triggered > 0 ? 'warn' : 'good'} />}
      </div>

      <div className="flex items-center justify-between mb-4">
        <div className="flex gap-2">
          <button onClick={() => setMode('dsl')} className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[12px] font-mono border transition-all ${mode === 'dsl' ? 'border-[#c9b787] text-[#c9b787] bg-[rgba(201,183,135,0.08)]' : 'border-[rgba(255,255,255,0.08)] text-[#666]'}`}>
            <Code className="w-3.5 h-3.5" /> DSL Editor
          </button>
          <button onClick={() => setMode('visual')} className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[12px] font-mono border transition-all ${mode === 'visual' ? 'border-[#c9b787] text-[#c9b787] bg-[rgba(201,183,135,0.08)]' : 'border-[rgba(255,255,255,0.08)] text-[#666]'}`}>
            <LayoutGrid className="w-3.5 h-3.5" /> Visual Builder
          </button>
        </div>
        <button onClick={() => setShowHistory(!showHistory)} className="flex items-center gap-1.5 text-[11px] text-[#666] hover:text-[#c9b787] transition-colors">
          <History className="w-3.5 h-3.5" /> Version history ({versions.length})
        </button>
      </div>

      {showHistory && (
        <FabricCard title="VERSION HISTORY" className="mb-4 animate-scale-in">
          <div className="space-y-2">
            {[...versions].reverse().map((v) => (
              <div key={v.version} className="flex items-center justify-between p-2 rounded text-[12px]" style={{ background: '#0e0e0e' }}>
                <div className="flex items-center gap-3">
                  <span className="font-mono text-[#c9b787] w-12">v{v.version}</span>
                  <div>
                    <div className="text-[#f5f5f5]">{v.description}</div>
                    <div className="text-[10px] text-[#555]">{new Date(v.savedAt).toLocaleDateString()}</div>
                  </div>
                </div>
                <Button size="sm" variant="outline" onClick={() => restoreVersion(v)}>Restore</Button>
              </div>
            ))}
          </div>
        </FabricCard>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {mode === 'dsl' ? (
          <FabricCard title="DSL EDITOR">
            {parseError && (
              <div className="mb-2 p-2 rounded text-[11px] text-[#b85450]" style={{ background: 'rgba(184,84,80,0.08)' }}>
                <XCircle className="w-3 h-3 inline mr-1" /> {parseError}
              </div>
            )}
            <textarea
              value={dslContent}
              onChange={(e) => { setDslContent(e.target.value); setEvalResults(null); }}
              rows={18}
              className="w-full font-mono text-[11px] bg-[#0a0a0a] text-[#f5f5f5] border border-[rgba(255,255,255,0.08)] rounded-lg p-3 resize-y focus:outline-none focus:border-[#c9b787] leading-relaxed"
              spellCheck={false}
            />
            <div className="flex gap-2 mt-2">
              <input value={saveDescription} onChange={(e) => setSaveDescription(e.target.value)} placeholder="Version description…" className="flex-1 h-8 rounded-md border border-input bg-transparent px-2 text-xs" />
              <Button size="sm" variant="outline" onClick={saveVersion}>Save version</Button>
            </div>
            <div className="mt-2 text-[11px] text-[#555]">{parsedRules.length} rule{parsedRules.length !== 1 ? 's' : ''} parsed · {parseError ? '⚠ parse error' : '✓ syntax ok'}</div>
          </FabricCard>
        ) : (
          <FabricCard title="VISUAL RULE BUILDER">
            <div className="space-y-3">
              {visualRules.map((rule) => (
                <div key={rule.id} className="p-3 rounded border border-[rgba(255,255,255,0.06)]" style={{ background: '#0a0a0a' }}>
                  <div className="flex items-center gap-2 flex-wrap">
                    <select value={rule.field} onChange={(e) => updateVisualRule(rule.id, { field: e.target.value })} className="h-7 rounded border border-input bg-transparent px-2 text-xs font-mono">
                      {['model.qualityScore', 'model.governanceState', 'model.piiScore', 'destination.piiAllowed', 'destination.authState', 'destination.governanceState', 'mapping.confidence', 'mapping.governanceState'].map((f) => <option key={f} value={f}>{f}</option>)}
                    </select>
                    <select value={rule.operator} onChange={(e) => updateVisualRule(rule.id, { operator: e.target.value as VisualRule['operator'] })} className="h-7 rounded border border-input bg-transparent px-2 text-xs font-mono w-20">
                      {(['==', '!=', '>', '<', '>=', '<='] as const).map((op) => <option key={op} value={op}>{op}</option>)}
                    </select>
                    <input value={rule.value} onChange={(e) => updateVisualRule(rule.id, { value: e.target.value })} className="h-7 w-20 rounded border border-input bg-transparent px-2 text-xs font-mono" />

                    <span className="text-[11px] text-[#666]">THEN</span>
                    <select value={rule.enforcement} onChange={(e) => updateVisualRule(rule.id, { enforcement: e.target.value as Enforcement })} className="h-7 rounded border border-input bg-transparent px-2 text-xs font-mono">
                      {(['block', 'warn', 'redact', 'quarantine', 'notify'] as const).map((e) => <option key={e} value={e}>{e}</option>)}
                    </select>
                    <button onClick={() => removeVisualRule(rule.id)} className="ml-auto p-1 text-[#666] hover:text-[#b85450]"><Trash2 className="w-3.5 h-3.5" /></button>
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-3 flex items-center gap-2 flex-wrap">
              <Button size="sm" variant="outline" onClick={addVisualRule}>
                <Plus className="w-3.5 h-3.5 mr-1" /> Add rule
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={compileToDslAndSwitch}
                disabled={visualRules.length === 0}
                title="Append visual rules as executable DSL and switch to DSL editor"
              >
                Compile to DSL ({visualRules.length})
              </Button>
              <span className="text-[11px] text-[#666] font-mono">
                Visual rules are not enforced until compiled to DSL.
              </span>
            </div>
          </FabricCard>
        )}

        <div className="space-y-4">
          <FabricCard title="PARSED RULES">
            <div className="space-y-2">
              {parsedRules.length === 0 && <div className="text-[12px] text-[#555]">No rules parsed yet. Check DSL syntax.</div>}
              {parsedRules.map((rule, i) => (
                <div key={i} className="flex items-start gap-2 p-2 rounded text-[11px]" style={{ background: '#0e0e0e' }}>
                  <Badge variant={ENFORCEMENT_BADGE[rule.then]}>{rule.then}</Badge>
                  <div className="flex-1 min-w-0">
                    <div className="text-[#f5f5f5] font-medium">{rule.name}</div>
                    <div className="font-mono text-[#666] text-[10px] truncate">{rule.when.replace(/\n/g, ' ')}</div>
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-3 pt-3 border-t border-[rgba(255,255,255,0.04)]">
              <Button onClick={runEval} isLoading={evalLoading} disabled={parsedRules.length === 0} className="w-full">
                <Play className="w-3.5 h-3.5 mr-1.5" /> Evaluate against next sync
              </Button>
            </div>
          </FabricCard>

          <FabricCard title="EXISTING POLICY REGISTRY">
            <div className="space-y-2 max-h-52 overflow-y-auto">
              {RELAY_POLICIES.slice(0, 8).map((p) => (
                <div key={p.id} className="flex items-center gap-2 text-[11px] p-2 rounded" style={{ background: '#0e0e0e' }}>
                  <SeverityChip level={p.severity} />
                  <div className="flex-1 min-w-0">
                    <div className="text-[#f5f5f5] truncate">{p.name}</div>
                    <div className="font-mono text-[#555] text-[10px] truncate">{p.condition}</div>
                  </div>
                  <Badge variant={ENFORCEMENT_BADGE[p.enforcement as Enforcement]}>{p.enforcement}</Badge>
                </div>
              ))}
            </div>
            <Link href="/policies" className="block mt-2 text-[11px] text-[#c9b787] hover:underline">View all policies →</Link>
          </FabricCard>
        </div>
      </div>

      {evalResults && (
        <FabricCard title={`EVALUATION RESULTS — ${triggered} HIT${triggered !== 1 ? 'S' : ''} ACROSS ${RELAY_MAPPINGS.slice(0, 6).length} MAPPINGS`} className="mb-4 animate-scale-in">
          {triggered === 0 && (
            <div className="flex items-center gap-2 text-[12px] text-[#5a8a6e] mb-4">
              <CheckCircle className="w-4 h-4" /> All syncs pass — no policy violations detected
            </div>
          )}
          <div className="space-y-2">
            {evalResults.map((r, i) => (
              <div key={i} className="flex items-start gap-3 p-3 rounded text-[12px]" style={{ background: '#0e0e0e', border: `1px solid ${r.enforcement === 'block' ? 'rgba(184,84,80,0.15)' : r.enforcement === 'warn' ? 'rgba(212,168,83,0.15)' : 'rgba(255,255,255,0.04)'}` }}>
                {r.enforcement === 'block' ? <XCircle className="w-4 h-4 text-[#b85450] shrink-0 mt-0.5" /> : r.enforcement === 'warn' ? <AlertTriangle className="w-4 h-4 text-[#d4a853] shrink-0 mt-0.5" /> : <CheckCircle className="w-4 h-4 text-[#5a8a6e] shrink-0 mt-0.5" />}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-0.5">
                    <span className="text-[#f5f5f5] font-medium">{r.mappingName}</span>
                    <Badge variant={ENFORCEMENT_BADGE[r.enforcement]}>{r.enforcement}</Badge>
                  </div>
                  <div className="text-[#666] text-[10px]">{r.ruleName} · {r.reason}</div>
                </div>
              </div>
            ))}
          </div>
        </FabricCard>
      )}
    </div>
  );
}
