// VENDORED FROM szl-holdings/platform@653b4ba95e6ae03630a922631139481875809d0b — artifacts/sentra/src/pages/compliance/vendor-risk.tsx
// DO NOT EDIT HERE. Edit in the monorepo, then run scripts/sync_from_monorepo.sh sync.
import { AlertTriangle, CheckCircle, Clock, Search, Shield } from 'lucide-react';
import { useState } from 'react';

const vendors = [
  {
    id: 'V-001',
    name: 'Salesforce',
    category: 'CRM / SaaS',
    risk: 'Low',
    tier: 'Critical',
    securityScore: 94,
    soc2: true,
    iso27001: true,
    lastAssessed: 'Nov 2025',
    dataTypes: ['Customer PII', 'Revenue Data'],
    issues: 0,
  },
  {
    id: 'V-002',
    name: 'AWS',
    category: 'Cloud Infrastructure',
    risk: 'Low',
    tier: 'Critical',
    securityScore: 97,
    soc2: true,
    iso27001: true,
    lastAssessed: 'Oct 2025',
    dataTypes: ['All Production Data'],
    issues: 0,
  },
  {
    id: 'V-003',
    name: 'Rippling',
    category: 'HRIS / Payroll',
    risk: 'Medium',
    tier: 'High',
    securityScore: 81,
    soc2: true,
    iso27001: false,
    lastAssessed: 'Jan 2026',
    dataTypes: ['Employee PII', 'Compensation Data'],
    issues: 2,
  },
  {
    id: 'V-004',
    name: 'DataBricks',
    category: 'Data Platform',
    risk: 'Medium',
    tier: 'High',
    securityScore: 86,
    soc2: true,
    iso27001: false,
    lastAssessed: 'Dec 2025',
    dataTypes: ['Analytics Data', 'ML Training Sets'],
    issues: 1,
  },
  {
    id: 'V-005',
    name: 'DocuSign',
    category: 'eSignature',
    risk: 'Low',
    tier: 'Medium',
    securityScore: 91,
    soc2: true,
    iso27001: false,
    lastAssessed: 'Feb 2026',
    dataTypes: ['Contract Data', 'Signature Data'],
    issues: 0,
  },
  {
    id: 'V-006',
    name: 'Legacy Vendor X',
    category: 'On-premise ERP',
    risk: 'High',
    tier: 'Critical',
    securityScore: 54,
    soc2: false,
    iso27001: false,
    lastAssessed: 'Mar 2024',
    dataTypes: ['Financial Records', 'Inventory', 'Employee Data'],
    issues: 7,
  },
];

const assessmentQueue = [
  { vendor: 'HubSpot', due: 'Apr 15, 2026', priority: 'High', reason: 'Annual reassessment' },
  { vendor: 'Zoom', due: 'Apr 30, 2026', priority: 'Medium', reason: 'SOC 2 renewal' },
  {
    vendor: 'Slack',
    due: 'May 10, 2026',
    priority: 'Medium',
    reason: 'New data sharing agreement',
  },
  { vendor: 'Snowflake', due: 'May 20, 2026', priority: 'High', reason: 'First-time assessment' },
];

const riskColor: Record<string, string> = {
  Low: 'text-[#c9b787] bg-[#c9b787]/10 border-[#c9b787]/20',
  Medium: 'text-[#c9b787] bg-[#c9b787]/10 border-[#c9b787]/20',
  High: 'text-[#f5f5f5] bg-[#f5f5f5]/10 border-[#f5f5f5]/20',
};

export default function VendorRisk() {
  const [search, setSearch] = useState('');
  const filtered = vendors.filter(
    (v) =>
      v.name.toLowerCase().includes(search.toLowerCase()) ||
      v.category.toLowerCase().includes(search.toLowerCase()),
  );

  return (
    <div className="space-y-5">
      <div>
        <h1 className="font-display text-lg font-bold text-[#c9b787] flex items-center gap-2">
          <Shield className="w-5 h-5 text-[#c9b787]" /> Vendor Risk Management
        </h1>
        <p className="text-xs text-[#c9b787]/50 mt-0.5">
          Third-party security assessments, vendor risk scoring, and supply chain monitoring
        </p>
      </div>

      <div className="grid grid-cols-4 gap-4">
        {[
          {
            label: 'High Risk Vendors',
            value: vendors.filter((v) => v.risk === 'High').length,
            color: 'text-[#f5f5f5]',
          },
          {
            label: 'Assessments Due (30d)',
            value: assessmentQueue.length,
            color: 'text-[#c9b787]',
          },
          {
            label: 'Compliant Vendors',
            value: vendors.filter((v) => v.risk === 'Low').length,
            color: 'text-[#c9b787]',
          },
          {
            label: 'Open Issues',
            value: vendors.reduce((a, v) => a + v.issues, 0),
            color: 'text-[#c9b787]',
          },
        ].map(({ label, value, color }) => (
          <div key={label} className="bg-[#c9b787]/5 border border-[#c9b787]/10 rounded-xl p-4">
            <p className="text-[10px] text-[#c9b787]/40">{label}</p>
            <p className={`text-2xl font-bold font-display ${color}`}>{value}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <div className="lg:col-span-2 space-y-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[#c9b787]/40" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search vendors..."
              className="w-full pl-9 pr-4 py-2 text-xs bg-[#c9b787]/5 rounded-lg border border-[#c9b787]/10 text-[#c9b787] placeholder:text-[#c9b787]/30 focus:outline-none focus:ring-1 focus:ring-orange-500/30"
            />
          </div>
          <div className="space-y-2">
            {filtered.map((v) => (
              <div
                key={v.id}
                className={`bg-[#c9b787]/5 border rounded-xl p-4 ${v.risk === 'High' ? 'border-[#f5f5f5]/20' : 'border-[#c9b787]/10'}`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-semibold text-xs text-[#c9b787]">{v.name}</span>
                      <span className="text-[10px] px-1.5 py-0.5 rounded border border-[#c9b787]/20 text-[#c9b787]/60">
                        {v.category}
                      </span>
                      <span
                        className={`text-[10px] px-1.5 py-0.5 rounded border ${riskColor[v.risk]}`}
                      >
                        {v.risk} Risk
                      </span>
                      <span className="text-[10px] px-1.5 py-0.5 rounded border border-[#c9b787]/10 text-[#c9b787]/40">
                        Tier: {v.tier}
                      </span>
                    </div>
                    <div className="flex items-center gap-3 mt-1.5 text-[10px]">
                      <span
                        className={`flex items-center gap-1 ${v.soc2 ? 'text-[#c9b787]' : 'text-[#f5f5f5]'}`}
                      >
                        {v.soc2 ? (
                          <CheckCircle className="w-2.5 h-2.5" />
                        ) : (
                          <AlertTriangle className="w-2.5 h-2.5" />
                        )}
                        SOC 2
                      </span>
                      <span
                        className={`flex items-center gap-1 ${v.iso27001 ? 'text-[#c9b787]' : 'text-[#c9b787]/40'}`}
                      >
                        {v.iso27001 ? (
                          <CheckCircle className="w-2.5 h-2.5" />
                        ) : (
                          <AlertTriangle className="w-2.5 h-2.5" />
                        )}
                        ISO 27001
                      </span>
                      <span className="text-[#c9b787]/40 flex items-center gap-1">
                        <Clock className="w-2.5 h-2.5" />
                        Assessed: {v.lastAssessed}
                      </span>
                      {v.issues > 0 && <span className="text-[#f5f5f5]">{v.issues} open issues</span>}
                    </div>
                    <div className="flex flex-wrap gap-1 mt-1.5">
                      {v.dataTypes.map((d) => (
                        <span
                          key={d}
                          className="text-[10px] bg-[#c9b787]/5 px-1.5 py-0.5 rounded text-[#c9b787]/40 border border-[#c9b787]/10"
                        >
                          {d}
                        </span>
                      ))}
                    </div>
                  </div>
                  <div className="text-right shrink-0">
                    <p
                      className={`text-xl font-bold font-display ${v.securityScore >= 85 ? 'text-[#c9b787]' : v.securityScore >= 70 ? 'text-[#c9b787]' : 'text-[#f5f5f5]'}`}
                    >
                      {v.securityScore}
                    </p>
                    <p className="text-[10px] text-[#c9b787]/40">Security Score</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="space-y-3">
          <div className="bg-[#c9b787]/5 border border-[#c9b787]/10 rounded-xl p-4">
            <h3 className="text-xs font-semibold text-[#c9b787] mb-3">Assessment Queue</h3>
            <div className="space-y-2.5">
              {assessmentQueue.map((a) => (
                <div
                  key={a.vendor}
                  className="p-3 rounded-lg bg-[#c9b787]/5 border border-[#c9b787]/10"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-[#c9b787]">{a.vendor}</span>
                    <span
                      className={`text-[10px] px-1.5 py-0.5 rounded border ${a.priority === 'High' ? 'text-[#f5f5f5] bg-[#f5f5f5]/10 border-[#f5f5f5]/20' : 'text-[#c9b787] bg-[#c9b787]/10 border-[#c9b787]/20'}`}
                    >
                      {a.priority}
                    </span>
                  </div>
                  <p className="text-[10px] text-[#c9b787]/40 mt-1">{a.reason}</p>
                  <p className="text-[10px] text-[#8a8a8a] mt-0.5 flex items-center gap-1">
                    <Clock className="w-2.5 h-2.5" />
                    Due: {a.due}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
