// VENDORED FROM szl-holdings/platform@653b4ba95e6ae03630a922631139481875809d0b — artifacts/a11oy/src/data/releases.ts
// DO NOT EDIT HERE. Edit in the monorepo, then run scripts/sync_from_monorepo.sh sync.
export type ReleaseStatus = 'Drafted' | 'In Review' | 'Approved' | 'Shipped';

export interface Reviewer {
  name: string;
  avatarInitials: string;
  approved: boolean;
}

export interface Release {
  id: string;
  version: string;
  title: string;
  summary: string;
  status: ReleaseStatus;
  createdAt: string;
  updatedAt: string;
  reviewers: Reviewer[];
  changes: string[];
  targetBrands: string[];
}

export const releases: Release[] = [
  {
    id: 'r-1',
    version: 'v4.5.0',
    title: 'Spring Data Grid Refresh',
    summary: 'Major update to DenseTable with improved virtual scrolling and new filter capabilities.',
    status: 'Shipped',
    createdAt: '2026-03-01',
    updatedAt: '2026-03-15',
    reviewers: [
      { name: 'Stephen Lutar', avatarInitials: 'SL', approved: true },
      { name: 'Design Ops', avatarInitials: 'DO', approved: true }
    ],
    changes: ['DenseTable v4.2.0', 'FilterBar v3.0.0'],
    targetBrands: ['Sentra', 'Vessels', 'Aegis']
  },
  {
    id: 'r-2',
    version: 'v4.6.0',
    title: 'A11y Contrast Improvements',
    summary: 'Adjusted primary blue tokens to meet WCAG AAA requirements for text contrast.',
    status: 'Shipped',
    createdAt: '2026-03-20',
    updatedAt: '2026-04-05',
    reviewers: [
      { name: 'A11y Lead', avatarInitials: 'AL', approved: true }
    ],
    changes: ['color-primary token updated to #1d4ed8', 'color-text updated'],
    targetBrands: ['All Brands']
  },
  {
    id: 'r-3',
    version: 'v4.7.0',
    title: 'Voice Guideline Updates',
    summary: 'Deprecated casual terminology across professional services platforms.',
    status: 'Approved',
    createdAt: '2026-04-10',
    updatedAt: '2026-04-22',
    reviewers: [
      { name: 'Brand Lead', avatarInitials: 'BL', approved: true },
      { name: 'Legal', avatarInitials: 'LG', approved: true }
    ],
    changes: ['Added "seamless" to banned terms', 'Added "cutting-edge" to banned terms'],
    targetBrands: ['Counsel', 'Carlota Jo']
  },
  {
    id: 'r-4',
    version: 'v4.8.0',
    title: 'Timeline & Narrative Enhancements',
    summary: 'Promoting TimelineLane and NarrativePanel to stable.',
    status: 'In Review',
    createdAt: '2026-04-24',
    updatedAt: '2026-04-25',
    reviewers: [
      { name: 'Design Ops', avatarInitials: 'DO', approved: false },
      { name: 'Dev Lead', avatarInitials: 'DL', approved: true }
    ],
    changes: ['TimelineLane v1.1.0', 'NarrativePanel v3.1.0'],
    targetBrands: ['Pulse', 'Aegis']
  },
  {
    id: 'r-5',
    version: 'v4.9.0',
    title: 'Maritime Specific Data Viz',
    summary: 'New experimental components for geo-spatial tracking.',
    status: 'Drafted',
    createdAt: '2026-04-26',
    updatedAt: '2026-04-26',
    reviewers: [
      { name: 'Product - Vessels', avatarInitials: 'PV', approved: false }
    ],
    changes: ['VesselTracker v2.1.0-alpha', 'ThreatMap v0.9.1'],
    targetBrands: ['Vessels', 'Aegis']
  }
];
