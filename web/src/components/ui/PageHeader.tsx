import { Link } from 'wouter';

const MONO = 'var(--font-mono, monospace)';

export interface BreadcrumbItem {
  label: string;
  href?: string;
}

export interface PageHeaderProps {
  breadcrumbs?: BreadcrumbItem[];
  title: string;
  description?: string;
}

export function PageHeader({ breadcrumbs, title, description }: PageHeaderProps) {
  return (
    <div style={{ marginBottom: 8 }}>
      {breadcrumbs && breadcrumbs.length > 0 && (
        <div style={{
          fontSize: 9,
          fontFamily: MONO,
          letterSpacing: '0.15em',
          color: '#5e5e5e',
          textTransform: 'uppercase',
          marginBottom: 6,
          display: 'flex',
          gap: 4,
          alignItems: 'center',
          flexWrap: 'wrap',
        }}>
          {breadcrumbs.map((b, i) => (
            <span key={b.label} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              {i > 0 && <span style={{ color: '#3a3a3a' }}>/</span>}
              {b.href
                ? <Link href={b.href} style={{ color: '#5e5e5e', textDecoration: 'none' }}>{b.label}</Link>
                : <span>{b.label}</span>
              }
            </span>
          ))}
        </div>
      )}
      <h1 style={{ fontSize: 22, fontWeight: 600, color: '#f5f5f5', margin: 0, letterSpacing: '-0.02em' }}>
        {title}
      </h1>
      {description && (
        <p style={{ fontSize: 13, color: '#8a8a8a', margin: '6px 0 0', lineHeight: 1.6 }}>
          {description}
        </p>
      )}
    </div>
  );
}
