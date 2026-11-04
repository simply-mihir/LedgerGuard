import React from 'react';

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  interactive?: boolean;
  accent?: 'none' | 'mint' | 'amber' | 'rose' | 'blue';
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
    mint: 'rgba(13, 242, 166, 0.35)',
    amber: 'rgba(245, 158, 11, 0.35)',
    rose: 'rgba(244, 63, 94, 0.35)',
    blue: 'rgba(56, 189, 248, 0.35)',
  }[accent];

  return (
    <div
      className={`signal-card ${interactive ? 'signal-card-interactive' : ''} ${className}`}
      style={{
        background: 'rgba(19, 22, 27, 0.75)',
        backdropFilter: 'blur(16px)',
        WebkitBackdropFilter: 'blur(16px)',
        border: `1px solid ${accentBorder}`,
        borderRadius: '16px',
        boxShadow: '0 4px 20px -2px rgba(0, 0, 0, 0.5), 0 1px 3px rgba(0, 0, 0, 0.3)',
        transition: 'transform 0.18s ease, border-color 0.18s ease, box-shadow 0.18s ease',
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
