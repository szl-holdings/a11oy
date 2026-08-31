import { ConstellationGraph } from '@szl-holdings/shared-ui/constellation-graph';

const ACCENT = '#f5f5f5';

export default function ConstellationPage() {
  return (
    <div style={{ padding: '28px 28px 40px', maxWidth: 1280, margin: '0 auto' }}>
      <div style={{ marginBottom: 18 }}>
        <h1 style={{ fontSize: '1.5rem', fontWeight: 600, color: '#e8edf8', margin: 0 }}>
          Constellation
        </h1>
        <p style={{ fontSize: '0.85rem', color: '#94a3b8', marginTop: 4 }}>
          Live view of cases, threats, persons, and organizations across PARAGON and Counsel —
          and how they connect to the rest of the SZL ecosystem.
        </p>
      </div>
      <ConstellationGraph domain="aegis" accentColor={ACCENT} height={520} />
    </div>
  );
}
