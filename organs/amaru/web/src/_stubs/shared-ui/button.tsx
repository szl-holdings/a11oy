import * as React from 'react';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'default' | 'destructive' | 'outline' | 'secondary' | 'ghost' | 'link';
  size?: 'default' | 'sm' | 'lg' | 'icon';
}

/* Founder .btn. Default is .btn-solid (neutral solid, index.css): these stubs render inside
   the operator shell, whose one coral moment is the sidebar's active-nav marker. */
export function Button({ className = '', variant = 'default', size = 'default', ...props }: ButtonProps) {
  const variants: Record<string, string> = {
    default: 'btn btn-solid',
    destructive: 'btn bg-destructive text-destructive-foreground border-destructive hover:bg-destructive/90',
    outline: 'btn btn-secondary',
    secondary: 'btn btn-secondary',
    ghost: 'btn btn-ghost',
    link: 'bg-transparent p-0 border-0 text-link hover:text-link-hover underline-offset-4 hover:underline cursor-pointer',
  };
  const sizes: Record<string, string> = {
    default: '',
    sm: 'btn-sm',
    lg: 'btn-lg',
    icon: 'p-0 w-10 h-10',
  };
  return <button className={`${variants[variant] || variants.default} ${variant === 'link' ? '' : sizes[size] || ''} ${className}`} {...props} />;
}
