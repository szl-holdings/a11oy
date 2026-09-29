import * as React from 'react';

interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: 'default' | 'secondary' | 'destructive' | 'outline';
}

/* Founder .badge: neutral pill; a status tone only tints it and always travels with a word. */
export function Badge({ className = '', variant = 'default', ...props }: BadgeProps) {
  const variants: Record<string, string> = {
    default: '',
    secondary: '',
    destructive: 'conduit-badge-error',
    outline: '', // callers set the tone (text-*/border-*/bg-*) themselves
  };
  return <div className={`badge ${variants[variant] || ''} ${className}`} {...props} />;
}
