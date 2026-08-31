import { Settings as SettingsIcon, Bell, Shield, Globe, Palette, Check, Copy, RotateCcw } from 'lucide-react';
import { useEffect, useState, useCallback } from 'react';

type Prefs = {
  notifications: {
    syncFailures: boolean;
    partialRuns: boolean;
    connectionErrors: boolean;
    digestEmail: string;
  };
  access: {
    requireMfa: boolean;
    sessionMinutes: number;
    vaultPolicy: 'tight' | 'standard' | 'loose';
  };
  api: {
    keys: { id: string; label: string; created: string; preview: string }[];
    webhookUrl: string;
  };
  appearance: {
    density: 'compact' | 'comfortable' | 'spacious';
    accent: 'cyan' | 'blue' | 'amber' | 'emerald';
    reduceMotion: boolean;
  };
};

const DEFAULTS: Prefs = {
  notifications: { syncFailures: true, partialRuns: true, connectionErrors: true, digestEmail: '' },
  access: { requireMfa: false, sessionMinutes: 60, vaultPolicy: 'standard' },
  api: { keys: [], webhookUrl: '' },
  appearance: { density: 'comfortable', accent: 'cyan', reduceMotion: false },
};

const STORAGE_KEY = 'conduit.settings.v1';

function loadPrefs(): Prefs {
  if (typeof window === 'undefined') return DEFAULTS;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULTS;
    const parsed = JSON.parse(raw);
    return { ...DEFAULTS, ...parsed, notifications: { ...DEFAULTS.notifications, ...(parsed.notifications || {}) }, access: { ...DEFAULTS.access, ...(parsed.access || {}) }, api: { ...DEFAULTS.api, ...(parsed.api || {}) }, appearance: { ...DEFAULTS.appearance, ...(parsed.appearance || {}) } };
  } catch {
    return DEFAULTS;
  }
}

function savePrefs(p: Prefs) {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(p));
  } catch { /* quota or disabled — ignore */ }
}

function genKey() {
  const bytes = new Uint8Array(24);
  (globalThis.crypto || (window as any).crypto).getRandomValues(bytes);
  return 'cdu_' + Array.from(bytes).map((b) => b.toString(16).padStart(2, '0')).join('');
}

function Toggle({ checked, onChange, label, sub }: { checked: boolean; onChange: (v: boolean) => void; label: string; sub?: string }) {
  return (
    <label className="flex items-start gap-3 cursor-pointer select-none">
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={`mt-0.5 w-9 h-5 rounded-full border transition-colors flex-shrink-0 ${checked ? 'bg-primary/80 border-primary' : 'bg-muted border-border'}`}
      >
        <span className={`block w-3.5 h-3.5 rounded-full bg-white transition-transform ${checked ? 'translate-x-[18px]' : 'translate-x-[2px]'}`} />
      </button>
      <span className="text-sm">
        <span className="block font-medium">{label}</span>
        {sub ? <span className="block text-xs text-muted-foreground mt-0.5">{sub}</span> : null}
      </span>
    </label>
  );
}

function SavedBadge({ visible }: { visible: boolean }) {
  return (
    <span className={`text-[10px] inline-flex items-center gap-1 px-2 py-0.5 rounded-full border transition-opacity ${visible ? 'opacity-100 border-emerald-500/40 text-emerald-400 bg-emerald-500/10' : 'opacity-0 border-transparent'}`}>
      <Check className="w-3 h-3" /> Saved
    </span>
  );
}

export default function Settings() {
  const [prefs, setPrefs] = useState<Prefs>(DEFAULTS);
  const [hydrated, setHydrated] = useState(false);
  const [savedAt, setSavedAt] = useState(0);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  useEffect(() => { setPrefs(loadPrefs()); setHydrated(true); }, []);

  const update = useCallback(<K extends keyof Prefs>(section: K, patch: Partial<Prefs[K]>) => {
    setPrefs((curr) => {
      const next = { ...curr, [section]: { ...curr[section], ...patch } };
      savePrefs(next);
      setSavedAt(Date.now());
      return next;
    });
  }, []);

  const showSaved = hydrated && Date.now() - savedAt < 1800;

  const issueKey = useCallback(() => {
    const full = genKey();
    const id = full.slice(0, 12);
    update('api', { keys: [...prefs.api.keys, { id, label: `key-${prefs.api.keys.length + 1}`, created: new Date().toISOString(), preview: full }] });
    void navigator.clipboard?.writeText(full).then(() => setCopiedKey(id)).catch(() => undefined);
    setTimeout(() => setCopiedKey(null), 2000);
  }, [prefs.api.keys, update]);

  const revokeKey = useCallback((id: string) => {
    update('api', { keys: prefs.api.keys.filter((k) => k.id !== id) });
  }, [prefs.api.keys, update]);

  const reset = useCallback(() => {
    if (typeof window !== 'undefined' && window.confirm('Reset all settings to defaults?')) {
      savePrefs(DEFAULTS);
      setPrefs(DEFAULTS);
      setSavedAt(Date.now());
    }
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-display font-bold tracking-tight">Settings</h1>
          <p className="text-sm text-muted-foreground mt-1">Global configuration for Amaru. Stored locally on this device.</p>
        </div>
        <div className="flex items-center gap-3">
          <SavedBadge visible={showSaved} />
          <button onClick={reset} className="text-xs flex items-center gap-1.5 px-2.5 py-1.5 rounded-md border border-border text-muted-foreground hover:text-foreground hover:border-foreground/30 transition-colors">
            <RotateCcw className="w-3 h-3" /> Reset
          </button>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <section className="conduit-card p-5 space-y-4">
          <header className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-md bg-primary/10 border border-primary/20 flex items-center justify-center"><Bell className="w-4 h-4 text-primary" /></div>
            <div><div className="font-semibold text-sm">Notifications</div><div className="text-xs text-muted-foreground">Alerts for sync failures, partial runs, connection errors.</div></div>
          </header>
          <div className="space-y-3 pt-1">
            <Toggle checked={prefs.notifications.syncFailures} onChange={(v) => update('notifications', { syncFailures: v })} label="Sync failures" sub="A destination push fails fully." />
            <Toggle checked={prefs.notifications.partialRuns} onChange={(v) => update('notifications', { partialRuns: v })} label="Partial runs" sub="Some destinations succeed and some fail in one run." />
            <Toggle checked={prefs.notifications.connectionErrors} onChange={(v) => update('notifications', { connectionErrors: v })} label="Connection errors" sub="A connector cannot reach its target." />
            <label className="block">
              <span className="block text-xs text-muted-foreground mb-1.5">Digest email (daily summary)</span>
              <input type="email" value={prefs.notifications.digestEmail} onChange={(e) => update('notifications', { digestEmail: e.target.value })} placeholder="ops@example.com" className="w-full px-3 py-2 text-sm rounded-md bg-muted border border-border focus:border-primary/60 focus:outline-none" />
            </label>
          </div>
        </section>

        <section className="conduit-card p-5 space-y-4">
          <header className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-md bg-primary/10 border border-primary/20 flex items-center justify-center"><Shield className="w-4 h-4 text-primary" /></div>
            <div><div className="font-semibold text-sm">Access Control</div><div className="text-xs text-muted-foreground">Operator session and credential vault policy.</div></div>
          </header>
          <div className="space-y-3 pt-1">
            <Toggle checked={prefs.access.requireMfa} onChange={(v) => update('access', { requireMfa: v })} label="Require MFA on sign-in" sub="Operators must present a second factor." />
            <label className="block">
              <span className="block text-xs text-muted-foreground mb-1.5">Session timeout — {prefs.access.sessionMinutes} minutes</span>
              <input type="range" min={15} max={480} step={15} value={prefs.access.sessionMinutes} onChange={(e) => update('access', { sessionMinutes: Number(e.target.value) })} className="w-full accent-[var(--color-conduit-cyan,#22d3ee)]" />
              <div className="flex justify-between text-[10px] text-muted-foreground mt-1"><span>15m</span><span>4h</span><span>8h</span></div>
            </label>
            <label className="block">
              <span className="block text-xs text-muted-foreground mb-1.5">Vault policy</span>
              <div className="grid grid-cols-3 gap-2">
                {(['tight', 'standard', 'loose'] as const).map((p) => (
                  <button key={p} onClick={() => update('access', { vaultPolicy: p })} className={`px-2 py-1.5 text-xs rounded-md border capitalize transition-colors ${prefs.access.vaultPolicy === p ? 'bg-primary/15 border-primary/50 text-primary' : 'bg-muted border-border text-muted-foreground hover:border-foreground/30'}`}>{p}</button>
                ))}
              </div>
            </label>
          </div>
        </section>

        <section className="conduit-card p-5 space-y-4">
          <header className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-md bg-primary/10 border border-primary/20 flex items-center justify-center"><Globe className="w-4 h-4 text-primary" /></div>
              <div><div className="font-semibold text-sm">API & Webhooks</div><div className="text-xs text-muted-foreground">Issue keys for external triggers and outbound webhooks.</div></div>
            </div>
            <button onClick={issueKey} className="text-xs px-2.5 py-1.5 rounded-md border border-primary/40 text-primary hover:bg-primary/10 transition-colors">+ Issue key</button>
          </header>
          <div className="space-y-3 pt-1">
            <label className="block">
              <span className="block text-xs text-muted-foreground mb-1.5">Outbound webhook URL</span>
              <input type="url" value={prefs.api.webhookUrl} onChange={(e) => update('api', { webhookUrl: e.target.value })} placeholder="https://your-system.example/hooks/conduit" className="w-full px-3 py-2 text-sm font-mono rounded-md bg-muted border border-border focus:border-primary/60 focus:outline-none" />
            </label>
            <div className="space-y-1.5">
              {prefs.api.keys.length === 0 ? (
                <div className="text-xs text-muted-foreground italic py-2">No keys issued yet. Issue one — it'll be copied to your clipboard once.</div>
              ) : (
                prefs.api.keys.map((k) => (
                  <div key={k.id} className="flex items-center gap-2 px-2.5 py-1.5 rounded-md bg-muted border border-border text-xs">
                    <span className="font-mono text-foreground/80 flex-1 truncate">{k.preview.slice(0, 16)}…{k.preview.slice(-4)}</span>
                    <button onClick={() => { void navigator.clipboard?.writeText(k.preview); setCopiedKey(k.id); setTimeout(() => setCopiedKey(null), 1500); }} className="text-muted-foreground hover:text-foreground" title="Copy">
                      {copiedKey === k.id ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                    </button>
                    <button onClick={() => revokeKey(k.id)} className="text-muted-foreground hover:text-red-400 px-1.5">Revoke</button>
                  </div>
                ))
              )}
            </div>
          </div>
        </section>

        <section className="conduit-card p-5 space-y-4">
          <header className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-md bg-primary/10 border border-primary/20 flex items-center justify-center"><Palette className="w-4 h-4 text-primary" /></div>
            <div><div className="font-semibold text-sm">Appearance</div><div className="text-xs text-muted-foreground">Theme and display preferences for this browser.</div></div>
          </header>
          <div className="space-y-3 pt-1">
            <label className="block">
              <span className="block text-xs text-muted-foreground mb-1.5">Density</span>
              <div className="grid grid-cols-3 gap-2">
                {(['compact', 'comfortable', 'spacious'] as const).map((d) => (
                  <button key={d} onClick={() => update('appearance', { density: d })} className={`px-2 py-1.5 text-xs rounded-md border capitalize transition-colors ${prefs.appearance.density === d ? 'bg-primary/15 border-primary/50 text-primary' : 'bg-muted border-border text-muted-foreground hover:border-foreground/30'}`}>{d}</button>
                ))}
              </div>
            </label>
            <label className="block">
              <span className="block text-xs text-muted-foreground mb-1.5">Accent</span>
              <div className="flex gap-2">
                {([
                  { id: 'cyan' as const, hex: '#22d3ee' },
                  { id: 'blue' as const, hex: '#60a5fa' },
                  { id: 'amber' as const, hex: '#fbbf24' },
                  { id: 'emerald' as const, hex: '#34d399' },
                ]).map((c) => (
                  <button key={c.id} onClick={() => update('appearance', { accent: c.id })} aria-label={c.id} className={`w-7 h-7 rounded-full border-2 transition-transform ${prefs.appearance.accent === c.id ? 'border-foreground scale-110' : 'border-transparent hover:border-foreground/40'}`} style={{ background: c.hex }} />
                ))}
              </div>
            </label>
            <Toggle checked={prefs.appearance.reduceMotion} onChange={(v) => update('appearance', { reduceMotion: v })} label="Reduce motion" sub="Disable animations and transitions." />
          </div>
        </section>
      </div>

      <div className="conduit-card p-5">
        <div className="flex items-center gap-3 mb-3">
          <SettingsIcon className="w-5 h-5 text-primary" />
          <h2 className="font-semibold">About Amaru</h2>
        </div>
        <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
          <dt className="text-muted-foreground">Version</dt><dd className="font-mono">1.0.0</dd>
          <dt className="text-muted-foreground">Environment</dt><dd className="font-mono">development</dd>
          <dt className="text-muted-foreground">API Base</dt><dd className="font-mono text-xs truncate">/api/amaru</dd>
          <dt className="text-muted-foreground">Destinations</dt><dd>13 supported</dd>
        </dl>
      </div>
    </div>
  );
}
