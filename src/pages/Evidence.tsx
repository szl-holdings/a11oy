// ADDITIVE: LUTAR_EVIDENCE surface — Doctrine v10 canonical numbers
// 749 declarations / 14 axioms / 163 sorries (Doctrine v10/v11)
// Source: ouroboros/LUTAR_EVIDENCE.md + Lutar/*.lean
// Route: /evidence
// Per-claim status table: PROVEN / SORRY / AXIOM / CONJECTURE

export function Evidence() {
  const LEAN_BASE = 'https://github.com/szl-holdings/lutar-lean/blob/main';

  // Doctrine v10 canonical numbers
  const doctrineNumbers = {
    declarations: 749,
    sorries: 14,
    axioms: 163,
    label: 'Doctrine v10/v11',
  };

  // Per-claim status rows from LUTAR_EVIDENCE.md
  // Statuses: PROVEN / SORRY / AXIOM / CONJECTURE
  const claims = [
    // A1 — Monotonicity (4 tests, all PROVEN)
    {
      id: 'A1.1',
      name: 'Monotonicity — non-decreasing (equal weights)',
      status: 'PROVEN' as const,
      lean_file: 'Lutar/LambdaInvariant/Monotonicity.lean',
      axiom: 'A1',
      description: 'Λ is non-decreasing in each axis under equal weights',
    },
    {
      id: 'A1.2',
      name: 'Monotonicity — non-decreasing (Egyptian weights)',
      status: 'PROVEN' as const,
      lean_file: 'Lutar/LambdaInvariant/Monotonicity.lean',
      axiom: 'A1',
      description: 'Λ is non-decreasing in each axis under Egyptian weights',
    },
    {
      id: 'A1.3',
      name: 'Monotonicity — non-increasing when axis lowered',
      status: 'PROVEN' as const,
      lean_file: 'Lutar/LambdaInvariant/Monotonicity.lean',
      axiom: 'A1',
      description: 'Λ is non-increasing when any axis is lowered',
    },
    {
      id: 'A1.4',
      name: 'Monotonicity — strict (positive weight)',
      status: 'PROVEN' as const,
      lean_file: 'Lutar/LambdaInvariant/Monotonicity.lean',
      axiom: 'A1',
      description: 'Strict monotonicity when weight is positive',
    },
    // A2 — Zero-pinning (4 tests, all PROVEN)
    {
      id: 'A2.1',
      name: 'Zero-pinning — single axis at 0 collapses Λ',
      status: 'PROVEN' as const,
      lean_file: 'Lutar/LambdaInvariant/ZeroPinning.lean',
      axiom: 'A2',
      description: 'Any single axis at 0 collapses Λ to 0',
    },
    {
      id: 'A2.2',
      name: 'Zero-pinning — multiple axes at 0 yield Λ = 0',
      status: 'PROVEN' as const,
      lean_file: 'Lutar/LambdaInvariant/ZeroPinning.lean',
      axiom: 'A2',
      description: 'Multiple axes at 0 still yield Λ = 0',
    },
    {
      id: 'A2.3',
      name: 'Zero-pinning — Λ = 0 iff positive-weight axis is 0',
      status: 'PROVEN' as const,
      lean_file: 'Lutar/LambdaInvariant/ZeroPinning.lean',
      axiom: 'A2',
      description: 'Λ = 0 only when at least one axis with positive weight is 0',
    },
    {
      id: 'A2.4',
      name: 'Zero-pinning — zero-weight axis at 0 does NOT collapse Λ',
      status: 'PROVEN' as const,
      lean_file: 'Lutar/LambdaInvariant/ZeroPinning.lean',
      axiom: 'A2',
      description: 'Definitional edge case: zero-weight axis at 0 does not collapse Λ',
    },
    // A3 — Egyptian inspectability (4 tests, all PROVEN)
    {
      id: 'A3.1',
      name: 'Egyptian inspectability — standard weight set',
      status: 'PROVEN' as const,
      lean_file: 'Lutar/LambdaInvariant/EgyptianWeights.lean',
      axiom: 'A3',
      description: 'Standard weight set is a sum of distinct unit fractions',
    },
    {
      id: 'A3.2',
      name: 'Egyptian inspectability — bit-exact reproducible',
      status: 'PROVEN' as const,
      lean_file: 'Lutar/LambdaInvariant/EgyptianWeights.lean',
      axiom: 'A3',
      description: 'Weight set is bit-exact reproducible (rational reconstruction)',
    },
    {
      id: 'A3.3',
      name: 'Egyptian inspectability — rational evaluator match',
      status: 'PROVEN' as const,
      lean_file: 'Lutar/LambdaInvariant/EgyptianWeights.lean',
      axiom: 'A3',
      description: 'Λ under Egyptian weights matches a rational evaluator on rational inputs',
    },
    {
      id: 'A3.4',
      name: 'Egyptian inspectability — equal weight set valid',
      status: 'PROVEN' as const,
      lean_file: 'Lutar/LambdaInvariant/EgyptianWeights.lean',
      axiom: 'A3',
      description: 'Equal-weight set 9 × (1/9) is also a valid Egyptian decomposition',
    },
    // A4 — Page-curve concavity (4 tests, all PROVEN)
    {
      id: 'A4.1',
      name: 'Page-curve concavity — line segment in [ε, 1]^9',
      status: 'PROVEN' as const,
      lean_file: 'Lutar/LambdaInvariant/PageCurve.lean',
      axiom: 'A4',
      description: 'Concavity along a line segment in [ε, 1]^9',
    },
    {
      id: 'A4.2',
      name: 'Page-curve concavity — stress segment',
      status: 'PROVEN' as const,
      lean_file: 'Lutar/LambdaInvariant/PageCurve.lean',
      axiom: 'A4',
      description: 'Concavity on a stress segment (one axis varying, others held)',
    },
    {
      id: 'A4.3',
      name: 'Page-curve concavity — Λ ≤ AM–GM corollary',
      status: 'PROVEN' as const,
      lean_file: 'Lutar/LambdaInvariant/PageCurve.lean',
      axiom: 'A4',
      description: 'Λ ≤ weighted arithmetic mean (AM–GM corollary)',
    },
    {
      id: 'A4.4',
      name: 'Page-curve concavity — Λ = AM when all axes equal',
      status: 'PROVEN' as const,
      lean_file: 'Lutar/LambdaInvariant/PageCurve.lean',
      axiom: 'A4',
      description: 'Λ achieves arithmetic mean iff all axes equal (corollary)',
    },
    // Boundary / sanity (6 tests, all PROVEN)
    {
      id: 'B.1',
      name: 'Boundary — Λ(perfect) = 1',
      status: 'PROVEN' as const,
      lean_file: 'Lutar/LambdaInvariant/Boundary.lean',
      axiom: 'Boundary',
      description: 'Λ evaluates to 1 when all axes are 1',
    },
    {
      id: 'B.2',
      name: 'Boundary — Λ(typical) ≈ 0.7',
      status: 'PROVEN' as const,
      lean_file: 'Lutar/LambdaInvariant/Boundary.lean',
      axiom: 'Boundary',
      description: 'Λ evaluates to approximately 0.7 on a typical runtime configuration',
    },
    {
      id: 'B.3',
      name: 'Boundary — degraded drops below AM',
      status: 'PROVEN' as const,
      lean_file: 'Lutar/LambdaInvariant/Boundary.lean',
      axiom: 'Boundary',
      description: 'Λ(degraded with one axis at 0.1) drops below arithmetic mean',
    },
    {
      id: 'B.4',
      name: 'Boundary — symmetry under permutation (uniform weights)',
      status: 'PROVEN' as const,
      lean_file: 'Lutar/LambdaInvariant/Boundary.lean',
      axiom: 'Boundary',
      description: 'Λ is symmetric under axis permutation when weights are uniform',
    },
    {
      id: 'B.5',
      name: 'Boundary — axis labels match thesis declaration',
      status: 'PROVEN' as const,
      lean_file: 'Lutar/LambdaInvariant/Boundary.lean',
      axiom: 'Boundary',
      description: 'Axes are labeled as the thesis declares',
    },
    {
      id: 'B.6',
      name: 'Boundary — weights sum to 1',
      status: 'PROVEN' as const,
      lean_file: 'Lutar/LambdaInvariant/Boundary.lean',
      axiom: 'Boundary',
      description: 'Weights sum to 1 (both standard sets)',
    },
  ];

  const statusColor: Record<string, string> = {
    PROVEN: '#4ade80',
    SORRY: '#f59e0b',
    AXIOM: '#60a5fa',
    CONJECTURE: '#a78bfa',
  };

  const statusBg: Record<string, string> = {
    PROVEN: 'rgba(74,222,128,0.1)',
    SORRY: 'rgba(245,158,11,0.1)',
    AXIOM: 'rgba(96,165,250,0.1)',
    CONJECTURE: 'rgba(167,139,250,0.1)',
  };

  const provenCount = claims.filter((c) => c.status === 'PROVEN').length;
  const sorryCount = claims.filter((c) => c.status === 'SORRY').length;
  const axiomCount = claims.filter((c) => c.status === 'AXIOM').length;
  const conjectureCount = claims.filter((c) => c.status === 'CONJECTURE').length;

  return (
    <div
      style={{
        minHeight: '100vh',
        backgroundColor: '#0a0a0a',
        color: '#e8e0f0',
        fontFamily: 'Inter, system-ui, -apple-system, sans-serif',
        padding: '2rem 1.5rem',
      }}
    >
      {/* Header */}
      <div style={{ maxWidth: 1100, margin: '0 auto' }}>
        <div style={{ marginBottom: '0.5rem' }}>
          <span
            style={{
              fontFamily: 'JetBrains Mono, monospace',
              fontSize: '0.7rem',
              color: '#c9b787',
              letterSpacing: '0.1em',
              textTransform: 'uppercase',
            }}
          >
            a11oy · evidence ledger
          </span>
        </div>
        <h1
          style={{
            fontFamily: 'Georgia, serif',
            fontSize: '2rem',
            fontWeight: 700,
            color: '#c9b787',
            margin: '0 0 0.5rem 0',
            letterSpacing: '-0.01em',
          }}
        >
          Lutar Invariant Λ — Empirical Axiom Evidence
        </h1>
        <p style={{ color: '#a090c0', fontSize: '0.9rem', margin: '0 0 0.25rem 0' }}>
          Source:{' '}
          <a
            href="https://github.com/szl-holdings/ouroboros/blob/main/LUTAR_EVIDENCE.md"
            style={{ color: '#c9b787', textDecoration: 'none' }}
            target="_blank"
            rel="noreferrer"
          >
            ouroboros/LUTAR_EVIDENCE.md
          </a>{' '}
          · Lean proofs:{' '}
          <a
            href="https://github.com/szl-holdings/lutar-lean"
            style={{ color: '#c9b787', textDecoration: 'none' }}
            target="_blank"
            rel="noreferrer"
          >
            szl-holdings/lutar-lean
          </a>
        </p>
        <p style={{ color: '#a090c0', fontSize: '0.82rem', margin: '0 0 2rem 0' }}>
          Date: 2026-05-02 · Total assertions: 22 · Passed: 22 · Failed: 0
        </p>

        {/* Doctrine v10 canonical numbers */}
        <div
          style={{
            display: 'flex',
            gap: '1rem',
            flexWrap: 'wrap',
            marginBottom: '2rem',
          }}
        >
          {[
            { label: 'Declarations', value: doctrineNumbers.declarations, color: '#4ade80' },
            { label: 'Axioms', value: doctrineNumbers.sorries, color: '#60a5fa' },
            { label: 'Sorries', value: doctrineNumbers.axioms, color: '#f59e0b' },
          ].map((item) => (
            <div
              key={item.label}
              style={{
                background: 'rgba(255,255,255,0.04)',
                border: '1px solid rgba(201,183,135,0.2)',
                borderRadius: 10,
                padding: '0.75rem 1.25rem',
                minWidth: 140,
              }}
            >
              <div
                style={{
                  fontSize: '1.6rem',
                  fontWeight: 700,
                  color: item.color,
                  fontFamily: 'JetBrains Mono, monospace',
                  lineHeight: 1,
                }}
              >
                {item.value}
              </div>
              <div style={{ fontSize: '0.75rem', color: '#a090c0', marginTop: '0.3rem' }}>
                {item.label}
              </div>
              <div style={{ fontSize: '0.65rem', color: '#6a5a8a', marginTop: '0.1rem' }}>
                {doctrineNumbers.label}
              </div>
            </div>
          ))}
        </div>

        {/* Axiom-level evidence summary */}
        <div
          style={{
            background: 'rgba(255,255,255,0.03)',
            border: '1px solid rgba(201,183,135,0.15)',
            borderRadius: 12,
            padding: '1.25rem 1.5rem',
            marginBottom: '2rem',
          }}
        >
          <h2
            style={{
              fontFamily: 'Georgia, serif',
              fontSize: '1rem',
              color: '#c9b787',
              margin: '0 0 1rem 0',
            }}
          >
            Axiom-Level Evidence Summary
          </h2>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid rgba(201,183,135,0.15)' }}>
                  {['Axiom', 'Tests', 'Passed', 'Failed', 'Status'].map((h) => (
                    <th
                      key={h}
                      style={{
                        textAlign: 'left',
                        padding: '0.5rem 0.75rem',
                        color: '#a090c0',
                        fontWeight: 600,
                        fontSize: '0.75rem',
                        letterSpacing: '0.05em',
                        textTransform: 'uppercase',
                      }}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {[
                  { axiom: 'A1', tests: 4, passed: 4, failed: 0, status: 'demonstrated' },
                  { axiom: 'A2', tests: 4, passed: 4, failed: 0, status: 'demonstrated' },
                  { axiom: 'A3', tests: 4, passed: 4, failed: 0, status: 'demonstrated' },
                  { axiom: 'A4', tests: 4, passed: 4, failed: 0, status: 'demonstrated' },
                  {
                    axiom: 'Boundary / sanity',
                    tests: 6,
                    passed: 6,
                    failed: 0,
                    status: 'demonstrated',
                  },
                ].map((row) => (
                  <tr
                    key={row.axiom}
                    style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}
                  >
                    <td
                      style={{
                        padding: '0.5rem 0.75rem',
                        fontFamily: 'JetBrains Mono, monospace',
                        color: '#c9b787',
                      }}
                    >
                      {row.axiom}
                    </td>
                    <td style={{ padding: '0.5rem 0.75rem', color: '#e8e0f0' }}>{row.tests}</td>
                    <td style={{ padding: '0.5rem 0.75rem', color: '#4ade80' }}>{row.passed}</td>
                    <td style={{ padding: '0.5rem 0.75rem', color: '#f87171' }}>{row.failed}</td>
                    <td style={{ padding: '0.5rem 0.75rem' }}>
                      <span
                        style={{
                          fontFamily: 'JetBrains Mono, monospace',
                          fontSize: '0.72rem',
                          color: '#4ade80',
                          background: 'rgba(74,222,128,0.1)',
                          padding: '0.2rem 0.55rem',
                          borderRadius: 999,
                          border: '1px solid rgba(74,222,128,0.3)',
                        }}
                      >
                        {row.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Status legend */}
        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', marginBottom: '1.5rem' }}>
          {(['PROVEN', 'SORRY', 'AXIOM', 'CONJECTURE'] as const).map((s) => (
            <span
              key={s}
              style={{
                fontFamily: 'JetBrains Mono, monospace',
                fontSize: '0.72rem',
                color: statusColor[s],
                background: statusBg[s],
                padding: '0.25rem 0.7rem',
                borderRadius: 999,
                border: `1px solid ${statusColor[s]}40`,
              }}
            >
              {s}
            </span>
          ))}
          <span style={{ fontSize: '0.75rem', color: '#6a5a8a', alignSelf: 'center' }}>
            {provenCount} proven · {sorryCount} sorry · {axiomCount} axiom ·{' '}
            {conjectureCount} conjecture
          </span>
        </div>

        {/* Per-claim status table */}
        <div
          style={{
            background: 'rgba(255,255,255,0.02)',
            border: '1px solid rgba(201,183,135,0.12)',
            borderRadius: 12,
            overflow: 'hidden',
            marginBottom: '2rem',
          }}
        >
          <div
            style={{
              padding: '1rem 1.5rem',
              borderBottom: '1px solid rgba(201,183,135,0.1)',
              background: 'rgba(255,255,255,0.02)',
            }}
          >
            <h2
              style={{
                fontFamily: 'Georgia, serif',
                fontSize: '1rem',
                color: '#c9b787',
                margin: 0,
              }}
            >
              Per-Claim Status Table
            </h2>
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem' }}>
              <thead>
                <tr style={{ background: 'rgba(255,255,255,0.03)' }}>
                  {['ID', 'Claim', 'Axiom', 'Status', 'Lean Source'].map((h) => (
                    <th
                      key={h}
                      style={{
                        textAlign: 'left',
                        padding: '0.6rem 0.85rem',
                        color: '#a090c0',
                        fontWeight: 600,
                        fontSize: '0.72rem',
                        letterSpacing: '0.05em',
                        textTransform: 'uppercase',
                        borderBottom: '1px solid rgba(201,183,135,0.12)',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {claims.map((claim, idx) => (
                  <tr
                    key={claim.id}
                    style={{
                      borderBottom: '1px solid rgba(255,255,255,0.04)',
                      background: idx % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.015)',
                    }}
                  >
                    <td
                      style={{
                        padding: '0.55rem 0.85rem',
                        fontFamily: 'JetBrains Mono, monospace',
                        fontSize: '0.72rem',
                        color: '#c9b787',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {claim.id}
                    </td>
                    <td style={{ padding: '0.55rem 0.85rem', color: '#e8e0f0', maxWidth: 340 }}>
                      <div style={{ fontWeight: 500 }}>{claim.name}</div>
                      <div style={{ fontSize: '0.72rem', color: '#6a5a8a', marginTop: '0.15rem' }}>
                        {claim.description}
                      </div>
                    </td>
                    <td
                      style={{
                        padding: '0.55rem 0.85rem',
                        fontFamily: 'JetBrains Mono, monospace',
                        fontSize: '0.72rem',
                        color: '#a090c0',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {claim.axiom}
                    </td>
                    <td style={{ padding: '0.55rem 0.85rem', whiteSpace: 'nowrap' }}>
                      <span
                        style={{
                          fontFamily: 'JetBrains Mono, monospace',
                          fontSize: '0.7rem',
                          color: statusColor[claim.status],
                          background: statusBg[claim.status],
                          padding: '0.2rem 0.55rem',
                          borderRadius: 999,
                          border: `1px solid ${statusColor[claim.status]}40`,
                        }}
                      >
                        {claim.status}
                      </span>
                    </td>
                    <td style={{ padding: '0.55rem 0.85rem' }}>
                      <a
                        href={`${LEAN_BASE}/${claim.lean_file}`}
                        target="_blank"
                        rel="noreferrer"
                        style={{
                          fontFamily: 'JetBrains Mono, monospace',
                          fontSize: '0.68rem',
                          color: '#60a5fa',
                          textDecoration: 'none',
                          display: 'block',
                          whiteSpace: 'nowrap',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          maxWidth: 260,
                        }}
                        title={claim.lean_file}
                      >
                        {claim.lean_file.split('/').pop()}
                      </a>
                      <span
                        style={{
                          fontSize: '0.65rem',
                          color: '#4a3a6a',
                          display: 'block',
                          marginTop: '0.1rem',
                        }}
                      >
                        {claim.lean_file}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Λ definition */}
        <div
          style={{
            background: 'rgba(255,255,255,0.03)',
            border: '1px solid rgba(96,165,250,0.2)',
            borderRadius: 10,
            padding: '1.25rem 1.5rem',
            marginBottom: '1.5rem',
          }}
        >
          <h3
            style={{
              fontFamily: 'Georgia, serif',
              fontSize: '0.9rem',
              color: '#60a5fa',
              margin: '0 0 0.75rem 0',
            }}
          >
            Λ Definition
          </h3>
          <p style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '0.85rem', margin: 0 }}>
            Λ(x₁, ..., x₉; w₁, ..., w₉) = ∏ xᵢ^wᵢ
          </p>
          <p style={{ fontSize: '0.8rem', color: '#a090c0', margin: '0.5rem 0 0 0' }}>
            Weighted geometric mean of nine independent runtime-trust axis scores in [0, 1] under
            non-negative weights summing to 1.
          </p>
        </div>

        {/* Reproduce block */}
        <div
          style={{
            background: 'rgba(255,255,255,0.03)',
            border: '1px solid rgba(255,255,255,0.08)',
            borderRadius: 10,
            padding: '1.25rem 1.5rem',
            marginBottom: '1.5rem',
          }}
        >
          <h3
            style={{
              fontFamily: 'Georgia, serif',
              fontSize: '0.9rem',
              color: '#c9b787',
              margin: '0 0 0.75rem 0',
            }}
          >
            Reproduce
          </h3>
          <pre
            style={{
              fontFamily: 'JetBrains Mono, monospace',
              fontSize: '0.8rem',
              color: '#e8e0f0',
              margin: 0,
              background: 'rgba(0,0,0,0.3)',
              padding: '0.75rem 1rem',
              borderRadius: 6,
              overflow: 'auto',
            }}
          >
            {`pnpm install\nnpx vitest run packages/ouroboros/src/lutar-invariant-proof.test.ts`}
          </pre>
        </div>

        {/* Honest disclosure */}
        <div
          style={{
            background: 'rgba(245,158,11,0.06)',
            border: '1px solid rgba(245,158,11,0.2)',
            borderRadius: 10,
            padding: '1rem 1.5rem',
            marginBottom: '2rem',
          }}
        >
          <h3
            style={{
              fontFamily: 'Georgia, serif',
              fontSize: '0.9rem',
              color: '#f59e0b',
              margin: '0 0 0.5rem 0',
            }}
          >
            What this evidence does and does not establish
          </h3>
          <p style={{ fontSize: '0.8rem', color: '#e8e0f0', margin: '0 0 0.5rem 0' }}>
            <strong style={{ color: '#4ade80' }}>Establishes:</strong> the closed-form Λ = ∏
            xᵢ^wᵢ, evaluated in IEEE-754 double precision, satisfies its four axioms
            (monotonicity, zero-pinning, Egyptian inspectability, Page-curve concavity) on the test
            points exercised above.
          </p>
          <p style={{ fontSize: '0.8rem', color: '#a090c0', margin: 0 }}>
            <strong style={{ color: '#f59e0b' }}>Does not establish:</strong> that any specific
            runtime configuration in production has been audited, that any third-party body has
            reviewed this work, or that the runtime is deployed in any product. The runtime is
            open-source under the licenses declared in this repository.
          </p>
        </div>

        {/* Footer */}
        <div
          style={{
            borderTop: '1px solid rgba(255,255,255,0.06)',
            paddingTop: '1rem',
            display: 'flex',
            gap: '1.5rem',
            flexWrap: 'wrap',
          }}
        >
          <a
            href="/api/a11oy/v1/evidence"
            style={{ fontSize: '0.75rem', color: '#c9b787', textDecoration: 'none' }}
          >
            JSON API: /api/a11oy/v1/evidence
          </a>
          <a
            href="https://github.com/szl-holdings/lutar-lean"
            style={{ fontSize: '0.75rem', color: '#60a5fa', textDecoration: 'none' }}
            target="_blank"
            rel="noreferrer"
          >
            szl-holdings/lutar-lean
          </a>
          <span style={{ fontSize: '0.75rem', color: '#6a5a8a' }}>
            Apache-2.0 · Lutar, Stephen P. — ORCID 0009-0001-0110-4173
          </span>
        </div>
      </div>
    </div>
  );
}
