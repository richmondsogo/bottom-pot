import React from 'react';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'text' | 'default';
  children: React.ReactNode;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = 'default', className = '', children, ...props }, ref) => {
    let variantClass = '';
    if (variant === 'primary') variantClass = 'btn-primary';
    else if (variant === 'secondary') variantClass = 'btn-secondary';
    else if (variant === 'text') variantClass = 'btn-text';

    return (
      <button
        ref={ref}
        className={`btn ${variantClass} ${className}`.trim()}
        {...props}
      >
        {children}
      </button>
    );
  }
);

Button.displayName = 'Button';
