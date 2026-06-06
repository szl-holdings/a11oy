import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { registerWithA11oy } from '@workspace/a11oy-orchestration/client';
import App from './App';
import './index.css';

void registerWithA11oy({
  product: 'amaru',
  displayName: 'Amaru — The Andean Ouroboros',
  basePath: '/conduit/',
  accentColor: '#c9b787',
  capabilities: [
    { id: 'cycle_ledger', label: 'Cycle Ledger', governanceClass: 'observation' },
    { id: 'self_reflection', label: 'Self-Reflection Loop', governanceClass: 'recommendation' },
  ],
});

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
