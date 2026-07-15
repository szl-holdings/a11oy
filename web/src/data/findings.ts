// VENDORED FROM szl-holdings/platform@653b4ba95e6ae03630a922631139481875809d0b — artifacts/a11oy/src/data/findings.ts
// DO NOT EDIT HERE. Edit in the monorepo, then run scripts/sync_from_monorepo.sh sync.
export interface Finding {
  id: string;
  surface: string;
  category: 'contrast' | 'hit-target' | 'banned-term' | 'off-token';
  severity: 'critical' | 'high' | 'medium' | 'low';
  description: string;
  element?: string;
  currentValue?: string;
  requiredValue?: string;
  scriptedRecommendation: string;
}

export const findings: Finding[] = [
  {
    id: 'f-1',
    surface: 'Sentra - Dashboard',
    category: 'contrast',
    severity: 'critical',
    description: 'Insufficient contrast ratio for incident severity text.',
    element: '<span class="text-gray-400">Low</span>',
    currentValue: '3.2:1',
    requiredValue: '4.5:1',
    scriptedRecommendation: 'Update the text color to --color-a11oy-text-sub (#5e5e5e) to meet WCAG AA requirements.'
  },
  {
    id: 'f-2',
    surface: 'Counsel - Matter View',
    category: 'banned-term',
    severity: 'high',
    description: 'Deprecated terminology detected in matter summary.',
    element: '"...utilize the business telemetry platform..."',
    currentValue: 'business telemetry platform',
    requiredValue: 'execution fabric',
    scriptedRecommendation: 'Replace "business telemetry platform" with "execution fabric" and "utilize" with "use".'
  },
  {
    id: 'f-3',
    surface: 'Pulse - Executive Brief',
    category: 'hit-target',
    severity: 'medium',
    description: 'Action button touch target is too small for mobile viewport.',
    element: '<button class="h-6 w-6">',
    currentValue: '24x24px',
    requiredValue: '44x44px',
    scriptedRecommendation: 'Increase the padding on the icon button to ensure a minimum 44x44px touch target.'
  },
  {
    id: 'f-4',
    surface: 'Terra - Property Detail',
    category: 'off-token',
    severity: 'low',
    description: 'Hardcoded hex value used instead of design token for border.',
    element: 'border: 1px solid #1e2a3d',
    currentValue: '#1e2a3d',
    requiredValue: 'var(--color-a11oy-border)',
    scriptedRecommendation: 'Replace the hardcoded hex with the --color-a11oy-border CSS variable to ensure theme consistency.'
  },
  {
    id: 'f-5',
    surface: 'Aegis - Threat Map',
    category: 'contrast',
    severity: 'high',
    description: 'Map overlays lack sufficient contrast against dark water tiles.',
    element: '.overlay-polygon',
    currentValue: '1.8:1',
    requiredValue: '3.0:1 (UI Components)',
    scriptedRecommendation: 'Add a semi-transparent dark backing to the overlays or increase the opacity of the stroke color.'
  },
  {
    id: 'f-6',
    surface: 'Command - Overview',
    category: 'banned-term',
    severity: 'medium',
    description: 'Casual phrasing used in system error state.',
    element: '"Oops! Something went wrong."',
    currentValue: 'Oops!',
    requiredValue: 'N/A',
    scriptedRecommendation: 'Use professional, direct phrasing: "System error encountered. Refreshing state."'
  },
  {
    id: 'f-7',
    surface: 'Vessels - Route Panel',
    category: 'off-token',
    severity: 'medium',
    description: 'Legacy spacing utility class used instead of current token.',
    element: 'gap-4 (remnant from Tailwind default)',
    currentValue: '1rem',
    requiredValue: 'var(--space-md)',
    scriptedRecommendation: 'Update the grid gap to use the governed --space-md token for consistent rhythm.'
  }
];
