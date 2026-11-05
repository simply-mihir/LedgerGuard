import React from 'react';

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  interactive?: boolean;
  accent?: 'none' | 'mint' | 'amber' | 'rose' | 'blue' | 'cobalt';
}

export function Card({
  children,
  interactive = false,
  accent = 'none',
  className = '',
  style,
  ...props
}: CardProps) {
  const accentBorder = {
    none: 'rgba(255, 255, 255, 0.08)',
    mint: 'rgba(16, 185, 129, 0.30)',
    amber: 'rgba(245, 158, 11, 0.30)',
    rose: 'rgba(239, 68, 68, 0.30)',
    blue: 'rgba(56, 189, 248, 0.30)',
    cobalt: 'rgba(59, 130, 246, 0.35)',
  }[accent];

  return (
    <div
      className={`signal-card ${interactive ? 'signal-card-interactive' : ''} ${className}`}
      style={{
        background: 'rgba(14, 20, 33, 0.76)',
        backdropFilter: 'blur(20px)',
        WebkitBackdropFilter: 'blur(20px)',
        border: `1px solid ${accentBorder}`,
        borderRadius: 'var(--radius-secondary, 20px)',
        boxShadow: '0 12px 32px -8px rgba(0, 0, 0, 0.55), inset 0 1px 0 rgba(255, 255, 255, 0.08)',
        transition: 'transform 0.22s cubic-bezier(0.16, 1, 0.3, 1), border-color 0.22s ease, box-shadow 0.22s ease',
        ...style,
      }}
      {...props}
    >
      {children}
    </div>
  );
}

export function CardHeader({
  children,
  className = '',
  style,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={`card-header ${className}`}
      style={{
        padding: '1.25rem 1.5rem',
        borderBottom: '1px solid rgba(255, 255, 255, 0.06)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        ...style,
      }}
      {...props}
    >
      {children}
    </div>
  );
}

export function CardTitle({
  children,
  className = '',
  style,
  ...props
}: React.HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h3
      className={`card-title ${className}`}
      style={{
        fontSize: '1rem',
        fontWeight: 600,
        color: '#f8fafc',
        letterSpacing: '-0.01em',
        lineHeight: 1.3,
        ...style,
      }}
      {...props}
    >
      {children}
    </h3>
  );
}

export function CardDescription({
  children,
  className = '',
  style,
  ...props
}: React.HTMLAttributes<HTMLParagraphElement>) {
  return (
    <p
      className={`card-desc ${className}`}
      style={{
        fontSize: '0.8125rem',
        color: '#94a3b8',
        marginTop: '0.25rem',
        lineHeight: 1.4,
        ...style,
      }}
      {...props}
    >
      {children}
    </p>
  );
}

export function CardContent({
  children,
  className = '',
  style,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={`card-content ${className}`}
      style={{
        padding: '1.5rem',
        ...style,
      }}
      {...props}
    >
      {children}
    </div>
  );
}

export function CardFooter({
  children,
  className = '',
  style,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={`card-footer ${className}`}
      style={{
        padding: '1rem 1.5rem',
        borderTop: '1px solid rgba(255, 255, 255, 0.06)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        ...style,
      }}
      {...props}
    >
      {children}
    </div>
  );
}
