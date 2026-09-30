import React from 'react';
import { cn } from '@/lib/utils';
import { Loader2 } from 'lucide-react';

/* Founder KANCHAY v1.1.1 controls: .btn, .input/.select (szl-console.css), .badge + an
   honest status word. Inside the operator shell the view's one coral moment is the sidebar's
   active-nav marker, so the default (primary) action is .btn-solid — a neutral solid defined
   in index.css — never .btn-primary. Focus is never restyled here: the vendored rules draw it
   (the 1.1.1 base outline; .input/.select turn their edge --focus). */

const BTN_VARIANT = {
  default: 'btn-solid',
  outline: 'btn-secondary',
  ghost: 'btn-ghost',
  destructive: 'bg-destructive text-destructive-foreground border-destructive hover:bg-destructive/90',
} as const;

const BTN_SIZE = {
  default: '',
  sm: 'btn-sm',
  lg: 'btn-lg',
  icon: 'p-0 w-9 h-9',
} as const;

export const Button = React.forwardRef<HTMLButtonElement, React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'default' | 'outline' | 'ghost' | 'destructive', size?: 'default' | 'sm' | 'lg' | 'icon', isLoading?: boolean }>(
  ({ className, variant = 'default', size = 'default', isLoading, children, disabled, ...props }, ref) => {
    return (
      <button
        ref={ref}
        disabled={disabled || isLoading}
        className={cn('btn', BTN_VARIANT[variant], BTN_SIZE[size], className)}
        {...props}
      >
        {isLoading && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
        {children}
      </button>
    );
  }
);
Button.displayName = "Button";

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, type, ...props }, ref) => {
    return <input type={type} className={cn('input placeholder:text-ink-sub', className)} ref={ref} {...props} />;
  }
);
Input.displayName = "Input";

export const Select = React.forwardRef<HTMLSelectElement, React.SelectHTMLAttributes<HTMLSelectElement>>(
  ({ className, ...props }, ref) => {
    return <select className={cn('select', className)} ref={ref} {...props} />;
  }
);
Select.displayName = "Select";

export const Badge = ({ className, variant = 'default', children }: { className?: string, variant?: 'default' | 'active' | 'error' | 'running' | 'success' | 'failed' | 'partial' | 'draft' | 'paused', children: React.ReactNode }) => {
  return (
    <div className={cn(
      'badge',
      {
        'conduit-badge-active': variant === 'active',
        'conduit-badge-error': variant === 'error',
        'conduit-badge-running': variant === 'running',
        'conduit-badge-success': variant === 'success',
        'conduit-badge-failed': variant === 'failed',
        'conduit-badge-partial': variant === 'partial',
        'conduit-badge-draft': variant === 'draft' || variant === 'default',
        'conduit-badge-paused': variant === 'paused',
      },
      className
    )}>
      {children}
    </div>
  );
};
