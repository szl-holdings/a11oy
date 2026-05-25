import { ArrowRight } from 'lucide-react';
import { getSeverityColor } from '../../lib/command/utils';
import type { IntelligenceCard } from '../types';

interface IntelligencePanelProps {
  cards: IntelligenceCard[];
}

export function IntelligencePanel({ cards }: IntelligencePanelProps) {
  return (
    <div className="flex flex-col gap-4">
      <h2
        className="text-xs font-bold tracking-widest uppercase px-1"
        style={{ color: 'var(--color-fg-muted)' }}
      >
        AI Correlation Intelligence
      </h2>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {cards.map((card) => {
          const severityColor = getSeverityColor(card.severity);
          return (
            <div
              key={card.id}
              className="rounded-xl p-5 flex flex-col gap-3"
              style={{
                backgroundColor: 'var(--color-bg-elevated)',
                border: `1px solid var(--color-surface-border)`,
                borderLeftWidth: '3px',
                borderLeftColor: severityColor,
              }}
              data-testid={`card-intelligence-${card.id}`}
            >
              <div className="flex items-start justify-between gap-4">
                <h3
                  className="font-bold text-sm leading-tight"
                  style={{ color: 'var(--color-fg-primary)' }}
                >
                  {card.title}
                </h3>
                <span
                  className="text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded shrink-0"
                  style={{
                    color: severityColor,
                    backgroundColor: `color-mix(in srgb, ${severityColor} 12%, transparent)`,
                  }}
                >
                  {card.severity}
                </span>
              </div>

              <p
                className="text-xs leading-relaxed flex-1"
                style={{ color: 'var(--color-fg-muted)' }}
              >
                {card.description}
              </p>

              <div className="flex flex-wrap gap-1.5">
                {card.entities.map((entity) => (
                  <span
                    key={entity}
                    className="text-[10px] uppercase tracking-wider font-mono px-2 py-0.5 rounded"
                    style={{
                      backgroundColor: 'var(--color-surface-base)',
                      border: '1px solid var(--color-surface-border)',
                      color: 'var(--color-fg-secondary)',
                    }}
                  >
                    {entity}
                  </span>
                ))}
              </div>

              <div
                className="mt-1 pt-3 flex items-center gap-2"
                style={{ borderTop: '1px solid var(--color-surface-border)' }}
              >
                <ArrowRight className="w-3 h-3 shrink-0" style={{ color: severityColor }} />
                <span className="text-xs font-medium" style={{ color: severityColor }}>
                  {card.action}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
