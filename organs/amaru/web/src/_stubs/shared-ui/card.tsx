import * as React from 'react';

/* Founder .card / .card-title. */
export function Card({ className = '', ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={`card p-0 ${className}`} {...props} />;
}

export function CardHeader({ className = '', ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={`flex flex-col gap-1.5 p-6 ${className}`} {...props} />;
}

export function CardTitle({ className = '', ...props }: React.HTMLAttributes<HTMLHeadingElement>) {
  return <h3 className={`card-title ${className}`} {...props} />;
}

export function CardContent({ className = '', ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={`p-6 pt-0 text-sm ${className}`} {...props} />;
}
