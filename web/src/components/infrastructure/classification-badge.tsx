import type { Classification } from '../../lib/infrastructure/imperium-data';
import { cn } from '../../lib/infrastructure/utils';
import { AlertTriangle, Globe, Lock, Shield } from 'lucide-react';
import type React from 'react';

const CONFIG: Record<
  Classification,
  { label: string; icon: React.ElementType; className: string }
> = {
  OPEN: { label: 'OPEN', icon: Globe, className: 'classification-open' },
  RESTRICTED: { label: 'RESTRICTED', icon: AlertTriangle, className: 'classification-restricted' },
  CONFIDENTIAL: { label: 'CONFIDENTIAL', icon: Lock, className: 'classification-confidential' },
  SOVEREIGN: { label: 'SOVEREIGN', icon: Shield, className: 'classification-sovereign' },
};

export function ClassificationBadge({
  classification,
  size = 'sm',
}: {
  classification: Classification;
  size?: 'xs' | 'sm' | 'md';
}) {
  const cfg = CONFIG[classification];
  const Icon = cfg.icon;
  const textSize = size === 'xs' ? 'text-[9px]' : size === 'sm' ? 'text-[10px]' : 'text-xs';
  const iconSize = size === 'xs' ? 'w-2.5 h-2.5' : size === 'sm' ? 'w-3 h-3' : 'w-3.5 h-3.5';
  const padding = size === 'xs' ? 'px-1.5 py-0.5' : size === 'sm' ? 'px-2 py-0.5' : 'px-2.5 py-1';

  return (
    <div
      className={cn(
        'inline-flex items-center gap-1 rounded border font-mono tracking-widest font-semibold',
        textSize,
        padding,
        cfg.className,
      )}
    >
      <Icon className={iconSize} />
      {cfg.label}
    </div>
  );
}
