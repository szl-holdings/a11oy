// VENDORED FROM szl-holdings/platform@ed400a4f378330becd53346420b4d89ae8281dc5 — artifacts/a11oy/src/components/ui/Badge.tsx
// DO NOT EDIT HERE. Edit in the monorepo, then run scripts/sync_from_monorepo.sh sync.
import { cn } from '@szl-holdings/design-system';

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: 'default' | 'critical' | 'warn' | 'ok' | 'info' | 'outline' | 'ghost';
  size?: 'sm' | 'md';
}

export function Badge({ 
  children, 
  variant = 'default', 
  size = 'md',
  className, 
  ...props 
}: BadgeProps) {
  return (
    <span 
      className={cn(
        "inline-flex items-center justify-center font-medium rounded-full",
        size === 'sm' ? "text-[10px] px-2 py-0.5" : "text-xs px-2.5 py-0.5",
        variant === 'default' && "bg-[var(--color-a11oy-muted)] text-[var(--color-a11oy-text)]",
        variant === 'critical' && "bg-[var(--color-a11oy-critical)]/15 text-[var(--color-a11oy-critical)] border border-[var(--color-a11oy-critical)]/20",
        variant === 'warn' && "bg-[var(--color-a11oy-warn)]/15 text-[var(--color-a11oy-warn)] border border-[var(--color-a11oy-warn)]/20",
        variant === 'ok' && "bg-[var(--color-a11oy-ok)]/15 text-[var(--color-a11oy-ok)] border border-[var(--color-a11oy-ok)]/20",
        variant === 'info' && "bg-[var(--color-a11oy-info)]/15 text-[var(--color-a11oy-info)] border border-[var(--color-a11oy-info)]/20",
        variant === 'outline' && "border border-[var(--color-a11oy-border)] text-[var(--color-a11oy-text-sub)]",
        variant === 'ghost' && "bg-transparent text-[var(--color-a11oy-text-ghost)]",
        className
      )}
      {...props}
    >
      {children}
    </span>
  );
}
