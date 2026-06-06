// R7 minimalistic redesign (Series-A blocker, 2026-05-18T16:03:41Z):
// surface tokens realigned with a11oy/amaru palette in src/lib/theme.ts.
// No data wiring, no API calls, no copy were modified — visual texture only.

import {
  CheckCircle,
  FileText,
  Printer,
  Shield,
} from 'lucide-react';
import { useCallback, useRef, useState } from 'react';

interface ExportSection {
  id: string;
  label: string;
  included: boolean;
}

const EXPORT_SECTIONS: ExportSection[] = [
  { id: 'executive-summary', label: 'Executive Summary', included: true },
  { id: 'threat-posture', label: 'Threat Posture Overview', included: true },
  { id: 'incident-timeline', label: 'Incident Timeline (90d)', included: true },
  { id: 'compliance-scorecard', label: 'Compliance Scorecard', included: true },
  { id: 'mitre-coverage', label: 'MITRE ATT&CK Coverage', included: true },
  { id: 'risk-scoring', label: 'Risk Scoring Detail', included: false },
  { id: 'fund-summary', label: 'Multi-Fund Security Summary', included: false },
  { id: 'recovery-drills', label: 'Chaos Drill Results', included: false },
  { id: 'federated-privacy', label: 'Federated Privacy Report', included: false },
];

interface ReportMetric {
  label: string;
  value: string;
  change?: string;
  status: 'good' | 'warn' | 'critical';
}

const REPORT_METRICS: ReportMetric[] = [
  { label: 'Overall Posture Score', value: '74 / 100', change: '+3 from last quarter', status: 'warn' },
  { label: 'Active Incidents', value: '1', status: 'warn' },
  { label: 'Critical CVEs Unpatched', value: '0', status: 'good' },
  { label: 'MITRE Coverage', value: '68%', change: '+5% from last quarter', status: 'warn' },
  { label: 'Mean Time to Detect', value: '4.2h', change: '−22% improvement', status: 'good' },
  { label: 'Mean Time to Respond', value: '18h', change: '−14% improvement', status: 'good' },
  { label: 'Compliance Score', value: '97%', status: 'good' },
  { label: 'Zero Trust Maturity', value: 'Level 3', status: 'good' },
];

const INCIDENT_DATA = [
  { date: 'Jan 2026', count: 5, critical: 1, resolved: 5 },
  { date: 'Feb 2026', count: 3, critical: 0, resolved: 3 },
  { date: 'Mar 2026', count: 7, critical: 2, resolved: 6 },
  { date: 'Apr 2026', count: 2, critical: 1, resolved: 1 },
];

export default function AegisPdfExport() {
  const [sections, setSections] = useState<ExportSection[]>(EXPORT_SECTIONS);
  const [isGenerating, setIsGenerating] = useState(false);
  const [format, setFormat] = useState<'pdf' | 'executive-brief'>('pdf');
  const printRef = useRef<HTMLDivElement>(null);

  const toggleSection = useCallback((id: string) => {
    setSections((prev) =>
      prev.map((s) => (s.id === id ? { ...s, included: !s.included } : s)),
    );
  }, []);

  const handlePrint = useCallback(async () => {
    setIsGenerating(true);
    await new Promise((r) => setTimeout(r, 800));
    window.print();
    setIsGenerating(false);
  }, []);

  const _STATUS_COLORS: Record<ReportMetric['status'], string> = {
    good: '#c9b787',
    warn: '#c9b787',
    critical: '#f5f5f5',
  };

  return (
    <>
      {/* Print stylesheet */}
      <style>{`
        @media print {
          body * { visibility: hidden; }
          #aegis-print-area, #aegis-print-area * { visibility: visible; }
          #aegis-print-area {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            font-family: 'Helvetica Neue', Arial, sans-serif;
            color: var(--gi-bg-base);
            background: white;
          }
          .no-print { display: none !important; }
          .print-break { page-break-after: always; }
          .print-section { padding: 24px 32px; }
          .metric-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }
          .metric-card { border: 1px solid var(--gi-text-primary); border-radius: 8px; padding: 12px 16px; }
          .metric-label { font-size: 10px; color: var(--gi-text-muted); text-transform: uppercase; letter-spacing: 0.05em; }
          .metric-value { font-size: 20px; font-weight: 700; margin-top: 4px; }
          .incident-table { width: 100%; border-collapse: collapse; font-size: 12px; }
          .incident-table th { background: #f8fafc; padding: 8px 12px; text-align: left; border-bottom: 2px solid var(--gi-text-primary); font-size: 10px; text-transform: uppercase; letter-spacing: 0.05em; color: var(--gi-text-muted); }
          .incident-table td { padding: 8px 12px; border-bottom: 1px solid #f1f5f9; }
        }
      `}</style>

      <div className="h-full overflow-auto bg-[#080510] text-[#f5f5f5]" style={{ fontFamily: 'ui-monospace, monospace' }}>
        <div className="max-w-6xl mx-auto px-6 py-8">
          {/* Header */}
          <div className="mb-8 no-print">
            <div className="flex items-center gap-3 mb-2">
              <div className="p-2 rounded-lg bg-[#f5f5f5]/10 border border-[#f5f5f5]/20">
                <FileText className="w-5 h-5 text-[#f5f5f5]" />
              </div>
              <div>
                <h1 className="text-xl font-bold text-[#f5f5f5]">PDF Export</h1>
                <p className="text-xs text-[#f5f5f5]/60 mt-0.5">Pixel-perfect investor & board reports · Print-ready layout matches web exactly</p>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 no-print">
            {/* Config Panel */}
            <div className="space-y-4">
              <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-4">
                <h3 className="text-xs font-mono uppercase tracking-wider text-[#f5f5f5]/60 mb-3">Report Format</h3>
                <div className="space-y-2">
                  {([['pdf', 'Full Board Report', 'Complete security posture package (all sections, ~12 pages)'], ['executive-brief', 'Executive Brief', 'Condensed 2-page summary for C-suite distribution']] as const).map(([v, label, desc]) => (
                    <button
                      key={v}
                      onClick={() => setFormat(v)}
                      className={`w-full text-left p-3 rounded-lg border transition-all ${format === v ? 'border-[#f5f5f5]/40 bg-[#f5f5f5]/10' : 'border-white/[0.06] bg-white/[0.02] hover:border-[#f5f5f5]/20'}`}
                    >
                      <p className="text-xs font-semibold text-[#f5f5f5]">{label}</p>
                      <p className="text-[10px] text-[#f5f5f5]/50 mt-0.5">{desc}</p>
                    </button>
                  ))}
                </div>
              </div>

              <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-4">
                <h3 className="text-xs font-mono uppercase tracking-wider text-[#f5f5f5]/60 mb-3">Sections</h3>
                <div className="space-y-2">
                  {sections.map((section) => (
                    <label key={section.id} className="flex items-center gap-2 cursor-pointer group">
                      <div
                        onClick={() => toggleSection(section.id)}
                        className={`w-4 h-4 rounded border flex items-center justify-center flex-shrink-0 transition-all ${
                          section.included ? 'bg-[#f5f5f5]/80 border-[#f5f5f5]' : 'border-white/[0.2] bg-white/[0.04]'
                        }`}
                      >
                        {section.included && <CheckCircle className="w-2.5 h-2.5 text-white" />}
                      </div>
                      <span className="text-[11px] text-[#f5f5f5]/70 group-hover:text-[#f5f5f5]/90 transition-colors">{section.label}</span>
                    </label>
                  ))}
                </div>
              </div>

              <button
                onClick={handlePrint}
                disabled={isGenerating}
                className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl bg-[#f5f5f5] hover:bg-[#f5f5f5] text-white text-sm font-semibold transition-all disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isGenerating ? (
                  <>
                    <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    Generating…
                  </>
                ) : (
                  <>
                    <Printer className="w-4 h-4" />
                    Export to PDF
                  </>
                )}
              </button>
            </div>

            {/* Print Preview */}
            <div className="lg:col-span-2">
              <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-4">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-xs font-mono uppercase tracking-wider text-[#f5f5f5]/60">Preview</h3>
                  <span className="text-[10px] text-[#f5f5f5]/40">{sections.filter((s) => s.included).length} sections included</span>
                </div>

                {/* Print Preview area */}
                <div
                  id="aegis-print-area"
                  ref={printRef}
                  style={{
                    background: 'white',
                    color: 'var(--gi-bg-base)',
                    fontFamily: "'Helvetica Neue', Arial, sans-serif",
                    borderRadius: '8px',
                    overflow: 'hidden',
                    transform: 'scale(0.85)',
                    transformOrigin: 'top left',
                    width: '117%',
                  }}
                >
                  {/* Cover Page */}
                  <div style={{ padding: '40px 48px 32px', background: '#080510', color: 'white' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '24px' }}>
                      <div style={{ width: '40px', height: '40px', borderRadius: '10px', background: '#f5f5f5', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        <Shield style={{ width: '20px', height: '20px', color: 'white' }} />
                      </div>
                      <div>
                        <div style={{ fontSize: '20px', fontWeight: 700, color: '#fef2f2' }}>PARAGON</div>
                        <div style={{ fontSize: '11px', color: '#fca5a5', opacity: 0.7 }}>Defense & Intelligence Command</div>
                      </div>
                    </div>
                    <div style={{ borderTop: '1px solid rgba(255,255,255,0.1)', paddingTop: '24px' }}>
                      <div style={{ fontSize: '28px', fontWeight: 700, color: '#fef2f2', lineHeight: 1.2 }}>
                        {format === 'executive-brief' ? 'Executive Security Brief' : 'Board Security Report'}
                      </div>
                      <div style={{ fontSize: '13px', color: '#fca5a5', opacity: 0.7, marginTop: '8px' }}>Q2 2026 · Prepared April 26, 2026 · CONFIDENTIAL</div>
                    </div>
                  </div>

                  {/* Metrics Grid */}
                  {sections.find((s) => s.id === 'executive-summary' && s.included) && (
                    <div style={{ padding: '28px 48px', borderBottom: '1px solid #f1f5f9' }}>
                      <div style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--gi-text-muted)', marginBottom: '16px' }}>
                        Executive Summary
                      </div>
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '12px' }}>
                        {REPORT_METRICS.slice(0, 4).map((m) => (
                          <div key={m.label} style={{ border: '1px solid var(--gi-text-primary)', borderRadius: '8px', padding: '12px 14px' }}>
                            <div style={{ fontSize: '9px', color: 'var(--gi-text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{m.label}</div>
                            <div style={{ fontSize: '18px', fontWeight: 700, marginTop: '4px', color: m.status === 'good' ? '#c9b787' : m.status === 'warn' ? '#d97706' : '#f5f5f5' }}>
                              {m.value}
                            </div>
                            {m.change && <div style={{ fontSize: '9px', color: '#94a3b8', marginTop: '2px' }}>{m.change}</div>}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Threat Posture */}
                  {sections.find((s) => s.id === 'threat-posture' && s.included) && (
                    <div style={{ padding: '24px 48px', borderBottom: '1px solid #f1f5f9' }}>
                      <div style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--gi-text-muted)', marginBottom: '12px' }}>
                        Threat Posture
                      </div>
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '10px' }}>
                        {REPORT_METRICS.slice(4).map((m) => (
                          <div key={m.label} style={{ border: '1px solid var(--gi-text-primary)', borderRadius: '6px', padding: '10px 12px' }}>
                            <div style={{ fontSize: '9px', color: 'var(--gi-text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>{m.label}</div>
                            <div style={{ fontSize: '15px', fontWeight: 700, marginTop: '4px', color: m.status === 'good' ? '#c9b787' : m.status === 'warn' ? '#d97706' : '#f5f5f5' }}>
                              {m.value}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Incident Timeline */}
                  {sections.find((s) => s.id === 'incident-timeline' && s.included) && (
                    <div style={{ padding: '24px 48px', borderBottom: '1px solid #f1f5f9' }}>
                      <div style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--gi-text-muted)', marginBottom: '12px' }}>
                        Incident Timeline
                      </div>
                      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '11px' }}>
                        <thead>
                          <tr>
                            {['Period', 'Total Incidents', 'Critical', 'Resolved'].map((h) => (
                              <th key={h} style={{ padding: '8px 12px', textAlign: 'left', background: '#f8fafc', borderBottom: '2px solid var(--gi-text-primary)', fontSize: '9px', textTransform: 'uppercase', color: 'var(--gi-text-muted)', letterSpacing: '0.05em' }}>{h}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {INCIDENT_DATA.map((row, i) => (
                            <tr key={i} style={{ borderBottom: '1px solid #f1f5f9' }}>
                              <td style={{ padding: '8px 12px', fontWeight: 600 }}>{row.date}</td>
                              <td style={{ padding: '8px 12px', color: '#374151' }}>{row.count}</td>
                              <td style={{ padding: '8px 12px', color: row.critical > 0 ? '#f5f5f5' : '#c9b787', fontWeight: row.critical > 0 ? 700 : 400 }}>{row.critical}</td>
                              <td style={{ padding: '8px 12px', color: row.resolved === row.count ? '#c9b787' : '#d97706' }}>{row.resolved}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}

                  {/* Footer */}
                  <div style={{ padding: '16px 48px', background: '#f8fafc', borderTop: '1px solid #e2e8f0', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <span style={{ fontSize: '9px', color: '#94a3b8' }}>PARAGON — Defense & Intelligence Command · CONFIDENTIAL · Q2 2026</span>
                    <span style={{ fontSize: '9px', color: '#94a3b8' }}>Generated by PARAGON Governed AI Platform</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
