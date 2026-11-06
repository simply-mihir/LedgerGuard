import React from 'react';

export type BadgeVariant =
  | 'mint'
  | 'emerald'
  | 'amber'
  | 'rose'
  | 'blue'
  | 'slate'
  | 'neutral'
  | 'active'
  | 'settled'
  | 'pending'
  | 'frozen'
  | 'closed';

interface BadgeProps {
  children: React.ReactNode;
  variant?: BadgeVariant;
  size?: 'sm' | 'md';
  dot?: boolean;
  className?: string;
  style?: React.CSSProperties;
}

const variantStyles: Record<BadgeVariant, { bg: string; text: string; border: string; dotColor: string }> = {
  mint: {
    bg: 'rgba(13, 242, 166, 0.12)',
    text: '#0df2a6',
    border: 'rgba(13, 242, 166, 0.28)',
    dotColor: '#0df2a6',
  },
  emerald: {
    bg: 'rgba(16, 185, 129, 0.12)',
    text: '#34d399',
    border: 'rgba(16, 185, 129, 0.25)',
    dotColor: '#10b981',
  },
  amber: {
    bg: 'rgba(245, 158, 11, 0.12)',
    text: '#fbbf24',
    border: 'rgba(245, 158, 11, 0.25)',
    dotColor: '#f59e0b',
  },
  rose: {
    bg: 'rgba(244, 63, 94, 0.12)',
    text: '#fb7185',
    border: 'rgba(244, 63, 94, 0.25)',
    dotColor: '#f43f5e',
  },
  blue: {
    bg: 'rgba(56, 189, 248, 0.12)',
    text: '#38bdf8',
    border: 'rgba(56, 189, 248, 0.25)',
    dotColor: '#38bdf8',
  },
  slate: {
    bg: 'rgba(148, 163, 184, 0.10)',
    text: '#94a3b8',
    border: 'rgba(148, 163, 184, 0.20)',
    dotColor: '#94a3b8',
  },
  neutral: {
    bg: 'rgba(255, 255, 255, 0.05)',
    text: '#cbd5e1',
    border: 'rgba(255, 255, 255, 0.10)',
    dotColor: '#94a3b8',
  },
  active: {
    bg: 'rgba(13, 242, 166, 0.12)',
    text: '#0df2a6',
    border: 'rgba(13, 242, 166, 0.28)',
    dotColor: '#0df2a6',
  },
  settled: {
    bg: 'rgba(13, 242, 166, 0.12)',
    text: '#0df2a6',
    border: 'rgba(13, 242, 166, 0.28)',
    dotColor: '#0df2a6',
  },
  pending: {
    bg: 'rgba(245, 158, 11, 0.12)',
    text: '#fbbf24',
    border: 'rgba(245, 158, 11, 0.25)',
    dotColor: '#f59e0b',
  },
  frozen: {
    bg: 'rgba(245, 158, 11, 0.14)',
    text: '#fbbf24',
    border: 'rgba(245, 158, 11, 0.28)',
    dotColor: '#f59e0b',
  },
  closed: {
    bg: 'rgba(244, 63, 94, 0.12)',
    text: '#fb7185',
    border: 'rgba(244, 63, 94, 0.25)',
    dotColor: '#f43f5e',
  },
};

export function Badge({
  children,
  variant = 'neutral',
  size = 'md',
  dot = false,
  className = '',
  style,
}: BadgeProps) {
  const v = variantStyles[variant] || variantStyles.neutral;
  const isSm = size === 'sm';

  return (
    <span
      className={`inline-flex items-center font-medium tracking-wide uppercase ${className}`}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: isSm ? '0.25rem' : '0.375rem',
        padding: isSm ? '0.15rem 0.45rem' : '0.25rem 0.625rem',
        borderRadius: '9999px',
        fontSize: isSm ? '0.6875rem' : '0.75rem',
        fontWeight: 600,
        letterSpacing: '0.04em',
        background: v.bg,
        color: v.text,
        border: `1px solid ${v.border}`,
        lineHeight: 1,
        whiteSpace: 'nowrap',
        ...style,
      }}
    >
      {dot && (
        <span
          style={{
            width: isSm ? '5px' : '6px',
            height: isSm ? '5px' : '6px',
            borderRadius: '50%',
            backgroundColor: v.dotColor,
            flexShrink: 0,
          }}
        />
      )}
      {children}
    </span>
  );
}
