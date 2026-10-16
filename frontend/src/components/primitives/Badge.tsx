import React from 'react';

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: 'remote' | 'hybrid' | 'onsite' | 'unspecified' | 'source' | 'default';
  children: React.ReactNode;
}

export const Badge: React.FC<BadgeProps> = ({
  variant = 'default',
  className = '',
  children,
  ...props
}) => {
  let variantClass = '';
  if (variant === 'remote') variantClass = 'badge-remote';
  else if (variant === 'hybrid') variantClass = 'badge-hybrid';
  else if (variant === 'onsite') variantClass = 'badge-onsite';
  else if (variant === 'unspecified') variantClass = 'badge-unspecified';
  else if (variant === 'source') variantClass = 'badge-source';

  return (
    <span className={`badge ${variantClass} ${className}`.trim()} {...props}>
      {children}
    </span>
  );
};
