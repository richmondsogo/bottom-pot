import React from 'react';

export interface ChipProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  active?: boolean;
  children: React.ReactNode;
}

export const Chip: React.FC<ChipProps> = ({
  active = false,
  className = '',
  children,
  ...props
}) => {
  return (
    <button
      type="button"
      aria-pressed={active}
      className={`chip ${active ? 'active' : ''} ${className}`.trim()}
      {...props}
    >
      {children}
    </button>
  );
};
