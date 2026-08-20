import type React from 'react';

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  accent?: string;
  padding?: string | number;
  radius?: number;
}

export function Card({ children, accent, padding = '16px 20px', radius = 8, style, ...rest }: CardProps) {
  return (
    <div
      style={{
        border: `1px solid ${accent ? `${accent}40` : 'rgba(255,255,255,0.08)'}`,
        borderRadius: radius,
        background: 'rgba(255,255,255,0.025)',
        padding,
        ...style,
      }}
      {...rest}
    >
      {children}
    </div>
  );
}
