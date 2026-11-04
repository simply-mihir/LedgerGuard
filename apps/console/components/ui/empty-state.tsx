import React from 'react';

interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
  style?: React.CSSProperties;
}

export function EmptyState({
  icon,
  title,
  description,
  action,
  className = '',
  style,
}: EmptyStateProps) {
  return (
    <div
      className={`empty-state-box ${className}`}
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        textAlign: 'center',
        padding: '3rem 2rem',
        borderRadius: '16px',
        border: '1px dashed rgba(255, 255, 255, 0.10)',
        background: 'rgba(255, 255, 255, 0.02)',
        color: '#94a3b8',
        ...style,
      }}
    >
      {icon && (
        <div
          style={{
            marginBottom: '1rem',
            width: '44px',
            height: '44px',
            borderRadius: '12px',
            background: 'rgba(255, 255, 255, 0.04)',
            border: '1px solid rgba(255, 255, 255, 0.08)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#64748b',
          }}
        >
          {icon}
        </div>
      )}
      <h4
        style={{
          fontSize: '0.9375rem',
          fontWeight: 600,
          color: '#e2e8f0',
          marginBottom: '0.25rem',
        }}
      >
        {title}
      </h4>
      {description && (
        <p
          style={{
            fontSize: '0.8125rem',
            color: '#64748b',
            maxWidth: '380px',
            lineHeight: 1.5,
            marginBottom: action ? '1.25rem' : 0,
          }}
        >
          {description}
        </p>
      )}
      {action && <div>{action}</div>}
    </div>
  );
}
