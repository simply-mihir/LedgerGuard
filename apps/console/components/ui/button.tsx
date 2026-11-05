import React from 'react';

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'cyan';
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

  // Base sizing with modern rounded controls
  const sizeStyles: Record<ButtonSize, React.CSSProperties> = {
    sm: {
      padding: '0.4rem 0.8rem',
      fontSize: '0.75rem',
      borderRadius: 'var(--radius-sm, 10px)',
      gap: '0.375rem',
    },
    md: {
      padding: '0.55rem 1.05rem',
      fontSize: '0.8125rem',
      borderRadius: 'var(--radius-control, 14px)',
      gap: '0.5rem',
    },
    lg: {
      padding: '0.75rem 1.4rem',
      fontSize: '0.875rem',
      borderRadius: 'var(--radius-control, 14px)',
      gap: '0.55rem',
    },
  };

  // Variants with restrained cobalt, cyan, and glassmorphic depth
  const variantStyles: Record<ButtonVariant, React.CSSProperties> = {
    primary: {
      background: 'linear-gradient(180deg, #2563EB 0%, #1D4ED8 100%)',
      color: '#FFFFFF',
      border: '1px solid rgba(255, 255, 255, 0.20)',
      boxShadow: '0 4px 14px rgba(29, 78, 216, 0.35), inset 0 1px 0 rgba(255, 255, 255, 0.25)',
      fontWeight: 600,
    },
    cyan: {
      background: 'linear-gradient(180deg, #06B6D4 0%, #0891B2 100%)',
      color: '#FFFFFF',
      border: '1px solid rgba(255, 255, 255, 0.20)',
      boxShadow: '0 4px 14px rgba(6, 182, 212, 0.35), inset 0 1px 0 rgba(255, 255, 255, 0.25)',
      fontWeight: 600,
    },
    secondary: {
      background: 'rgba(255, 255, 255, 0.06)',
      backdropFilter: 'blur(10px)',
      WebkitBackdropFilter: 'blur(10px)',
      color: '#F1F5F9',
      border: '1px solid rgba(255, 255, 255, 0.12)',
      boxShadow: '0 2px 8px rgba(0, 0, 0, 0.20), inset 0 1px 0 rgba(255, 255, 255, 0.06)',
      fontWeight: 500,
    },
    ghost: {
      background: 'transparent',
      color: '#94A3B8',
      border: '1px solid transparent',
      fontWeight: 500,
    },
    danger: {
      background: 'rgba(220, 38, 38, 0.15)',
      backdropFilter: 'blur(10px)',
      WebkitBackdropFilter: 'blur(10px)',
      color: '#FCA5A5',
      border: '1px solid rgba(220, 38, 38, 0.35)',
      boxShadow: '0 2px 8px rgba(220, 38, 38, 0.20)',
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
        transition: 'transform 0.18s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.18s ease, background 0.18s ease',
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
