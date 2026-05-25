export type DriftType = 'token' | 'voice' | 'none';

export interface Activity {
  date: string;
  action: string;
  actor: string;
  surface: string;
}

export interface BrandDetail {
  tokenConformance: number;
  voiceConformance: number;
  a11yScore: number;
  recentActivity: Activity[];
}

export interface Brand {
  id: string;
  name: string;
  tagline: string;
  color: string;
  healthScore: number;
  lastAudit: string;
  drift: DriftType;
  owner: string;
  surfaces: number;
  detail: BrandDetail;
}

const mockActivity = [
  { date: '2 hours ago', action: 'Token update applied', actor: 'System', surface: 'Web App' },
  { date: '1 day ago', action: 'Voice audit completed', actor: 'Brand Ops', surface: 'Marketing Site' },
  { date: '3 days ago', action: 'New component adopted', actor: 'Dev Team', surface: 'Web App' },
  { date: '1 week ago', action: 'A11y remediation', actor: 'System', surface: 'Mobile App' },
  { date: '2 weeks ago', action: 'Design review passed', actor: 'Brand Ops', surface: 'Web App' }
];

export const brandsData: Record<string, Brand[]> = {
  szl: [
    { id: 'sentra', name: 'TENAX', tagline: 'TENAX — Cyber Resilience Command', color: '#8a8a8a', healthScore: 87, lastAudit: '2026-04-20', drift: 'none', owner: 'Brand Ops', surfaces: 4, detail: { tokenConformance: 92, voiceConformance: 85, a11yScore: 84, recentActivity: mockActivity } },
    { id: 'counsel', name: 'Counsel', tagline: 'Legal Matter Command', color: '#8a8a8a', healthScore: 74, lastAudit: '2026-04-15', drift: 'token', owner: 'Legal Tech', surfaces: 3, detail: { tokenConformance: 68, voiceConformance: 80, a11yScore: 74, recentActivity: mockActivity } },
    { id: 'pulse', name: 'LUMINA', tagline: 'LUMINA — AI Executive Briefing', color: '#c9b787', healthScore: 91, lastAudit: '2026-04-22', drift: 'none', owner: 'Executive', surfaces: 2, detail: { tokenConformance: 95, voiceConformance: 90, a11yScore: 88, recentActivity: mockActivity } },
    { id: 'terra', name: 'DOMAINE', tagline: 'DOMAINE — Real Estate Intelligence', color: '#8a8a8a', healthScore: 68, lastAudit: '2026-04-10', drift: 'voice', owner: 'Property', surfaces: 5, detail: { tokenConformance: 75, voiceConformance: 60, a11yScore: 69, recentActivity: mockActivity } },
    { id: 'vessels', name: 'SEXTANT', tagline: 'SEXTANT — Maritime Intelligence', color: '#c9b787', healthScore: 82, lastAudit: '2026-04-18', drift: 'none', owner: 'Maritime', surfaces: 3, detail: { tokenConformance: 85, voiceConformance: 82, a11yScore: 79, recentActivity: mockActivity } },
    { id: 'aegis', name: 'PARAGON', tagline: 'PARAGON — Defense & Intelligence', color: '#8a8a8a', healthScore: 79, lastAudit: '2026-04-12', drift: 'token', owner: 'Defense', surfaces: 6, detail: { tokenConformance: 72, voiceConformance: 85, a11yScore: 80, recentActivity: mockActivity } },
    { id: 'carlotajo', name: 'Carlota Jo', tagline: 'Private Advisory', color: '#c9b787', healthScore: 95, lastAudit: '2026-04-21', drift: 'none', owner: 'Advisory', surfaces: 2, detail: { tokenConformance: 98, voiceConformance: 94, a11yScore: 93, recentActivity: mockActivity } },
    { id: 'command', name: 'Command', tagline: 'Unified Command', color: '#c9b787', healthScore: 71, lastAudit: '2026-04-08', drift: 'voice', owner: 'Platform', surfaces: 4, detail: { tokenConformance: 80, voiceConformance: 65, a11yScore: 68, recentActivity: mockActivity } }
  ],
  acme: [
    { id: 'acme-1', name: 'Acme Core', tagline: 'Core Infrastructure', color: '#8a8a8a', healthScore: 88, lastAudit: '2026-04-19', drift: 'none', owner: 'Platform', surfaces: 3, detail: { tokenConformance: 90, voiceConformance: 88, a11yScore: 86, recentActivity: mockActivity } },
    { id: 'acme-2', name: 'Acme Edge', tagline: 'Edge Computing', color: '#c9b787', healthScore: 62, lastAudit: '2026-04-05', drift: 'token', owner: 'Edge Team', surfaces: 2, detail: { tokenConformance: 55, voiceConformance: 70, a11yScore: 61, recentActivity: mockActivity } },
    { id: 'acme-3', name: 'Acme PRAXIS', tagline: 'Integration Hub', color: '#8a8a8a', healthScore: 94, lastAudit: '2026-04-23', drift: 'none', owner: 'Integration', surfaces: 1, detail: { tokenConformance: 96, voiceConformance: 95, a11yScore: 91, recentActivity: mockActivity } }
  ],
  northwind: [
    { id: 'nw-1', name: 'Northwind Traders', tagline: 'B2B Commerce', color: '#8a8a8a', healthScore: 76, lastAudit: '2026-04-14', drift: 'voice', owner: 'Commerce', surfaces: 5, detail: { tokenConformance: 82, voiceConformance: 68, a11yScore: 78, recentActivity: mockActivity } },
    { id: 'nw-2', name: 'Northwind Logistics', tagline: 'Supply Chain', color: '#8a8a8a', healthScore: 89, lastAudit: '2026-04-21', drift: 'none', owner: 'Logistics', surfaces: 4, detail: { tokenConformance: 91, voiceConformance: 86, a11yScore: 90, recentActivity: mockActivity } },
    { id: 'nw-3', name: 'Northwind Analytics', tagline: 'Data Insights', color: '#8a8a8a', healthScore: 72, lastAudit: '2026-04-11', drift: 'token', owner: 'Data Team', surfaces: 2, detail: { tokenConformance: 65, voiceConformance: 80, a11yScore: 71, recentActivity: mockActivity } }
  ]
};
