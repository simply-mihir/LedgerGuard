import React from 'react';

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger';
export type ButtonSize = 'sm' | 'md' | 'lg';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  isLoading?: boolean;
  icon?: React.ReactNode;
}

export function Button({
  children,
  variant = 'secondary',
  size = 'md',
  isLoading = false,
  icon,
  disabled,
  className = '',
  style,
  ...props
}: ButtonProps) {
  const isDisabled = disabled || isLoading;

  // Base sizing
  const sizeStyles: Record<ButtonSize, React.CSSProperties> = {
    sm: {
      padding: '0.35rem 0.65rem',
      fontSize: '0.75rem',
      borderRadius: '8px',
      gap: '0.35rem',
    },
    md: {
      padding: '0.5rem 0.9rem',
      fontSize: '0.8125rem',
      borderRadius: '10px',
      gap: '0.45rem',
    },
    lg: {
      padding: '0.65rem 1.25rem',
      fontSize: '0.875rem',
      borderRadius: '12px',
      gap: '0.5rem',
    },
  };

  // Variants
  const variantStyles: Record<ButtonVariant, React.CSSProperties> = {
    primary: {
      background: 'linear-gradient(180deg, #10f4a8 0%, #08d68f 100%)',
      color: '#041d13',
      border: '1px solid rgba(16, 244, 168, 0.4)',
      boxShadow: '0 2px 8px rgba(13, 242, 166, 0.25), 0 1px 2px rgba(0, 0, 0, 0.2)',
      fontWeight: 600,
    },
    secondary: {
      background: 'rgba(255, 255, 255, 0.04)',
      color: '#f1f5f9',
      border: '1px solid rgba(255, 255, 255, 0.10)',
      boxShadow: '0 1px 2px rgba(0, 0, 0, 0.2)',
      fontWeight: 500,
    },
    ghost: {
      background: 'transparent',
      color: '#94a3b8',
      border: '1px solid transparent',
      fontWeight: 500,
    },
    danger: {
      background: 'rgba(244, 63, 94, 0.12)',
      color: '#fb7185',
      border: '1px solid rgba(244, 63, 94, 0.3)',
      fontWeight: 500,
    },
  };

  return (
    <button
      disabled={isDisabled}
      className={`btn-interactive ${className}`}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontFamily: 'inherit',
        cursor: isDisabled ? 'not-allowed' : 'pointer',
        opacity: isDisabled ? 0.6 : 1,
        transition: 'all 0.15s cubic-bezier(0.16, 1, 0.3, 1)',
        userSelect: 'none',
        whiteSpace: 'nowrap',
        ...sizeStyles[size],
        ...variantStyles[variant],
        ...style,
      }}
      {...props}
    >
      {isLoading ? (
        <span
          style={{
            width: '12px',
            height: '12px',
            borderRadius: '50%',
            border: '2px solid currentColor',
            borderTopColor: 'transparent',
            animation: 'spin 0.6s linear infinite',
            display: 'inline-block',
          }}
        />
      ) : (
        icon && <span style={{ display: 'inline-flex', alignItems: 'center' }}>{icon}</span>
      )}
      <span>{children}</span>
    </button>
  );
}
