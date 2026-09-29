import * as React from 'react';

/* Founder .skeleton: surface -> surface-raised shimmer. */
export function Skeleton({ className = '', ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div aria-hidden="true" className={`skeleton ${className}`} {...props} />;
}
