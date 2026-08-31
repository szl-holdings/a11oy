import { registerWithA11oy } from '@workspace/a11oy-orchestration/client';
import { configurePlausible } from '@szl-holdings/analytics';
import { GraphQLProvider } from '@szl-holdings/graphql-client/provider';
import { initAnalytics, initSentry, initWebVitals } from '@szl-holdings/observability/react';
import { ErrorBoundary } from '@szl-holdings/shared-ui/error-boundary';
import { OmniaShellProvider } from '@szl-holdings/omnia-shell/provider';
import { createRoot } from 'react-dom/client';
import App from './App';
import './index.css';

configurePlausible({
  domain: import.meta.env.VITE_PLAUSIBLE_DOMAIN || 'sentra.szlholdings.com',
  debugMode: import.meta.env.DEV,
  trackLocalhost: false,
});

initSentry({ appSlug: 'sentra', tracesSampleRate: 0.2 });
initWebVitals('sentra', '/api/');
initAnalytics({ appSlug: 'sentra' });

// Register with the A11oy orchestration backbone so the conductor knows the
// product is alive, what capabilities it exposes, and where to deep-link back.
void registerWithA11oy({
  product: 'sentra',
  displayName: 'Sentra — Cyber Resilience Command',
  basePath: '/sentra/',
  accentColor: '#22c55e',
  capabilities: [
    { id: 'threat_hunt', label: 'Threat Hunt', governanceClass: 'recommendation' },
    { id: 'remediation', label: 'Remediation Playbook', governanceClass: 'mutation' },
    { id: 'siem_export', label: 'SIEM Export', governanceClass: 'external_action' },
  ],
});

if ('serviceWorker' in navigator && !import.meta.env.DEV) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sentra/sw.js', { scope: '/sentra/' }).catch((_err) => {
    });
  });
}

createRoot(document.getElementById('root')!).render(
  <ErrorBoundary appName="Sentra Cyber Resilience Command" accentColor="#22c55e">
    <GraphQLProvider>
      <OmniaShellProvider config={{ artifactId: 'sentra', accentColor: '#22c55e' }}>
        <App />
      </OmniaShellProvider>
    </GraphQLProvider>
  </ErrorBoundary>,
);
