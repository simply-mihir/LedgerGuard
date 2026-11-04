import React from 'react';

interface StatusDotProps {
  status: 'active' | 'warning' | 'danger' | 'neutral' | boolean;
  size?: number;
  pulse?: boolean;
  style?: React.CSSProperties;
}

export function StatusDot({
  status,
  size = 7,
  pulse = false,
  style,
}: StatusDotProps) {
  let color = '#94a3b8';
  if (status === true || status === 'active') color = '#0df2a6';
  else if (status === false || status === 'danger') color = '#f43f5e';
  else if (status === 'warning') color = '#f59e0b';

  return (
    <span
      style={{
        position: 'relative',
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        width: `${size * 2}px`,
        height: `${size * 2}px`,
        ...style,
      }}
    >
      {pulse && (
        <span
          className="signal-pulse-ring"
          style={{
            position: 'absolute',
            width: `${size * 2}px`,
            height: `${size * 2}px`,
            borderRadius: '50%',
            backgroundColor: color,
            opacity: 0.35,
          }}
        />
      )}
      <span
        style={{
          width: `${size}px`,
          height: `${size}px`,
          borderRadius: '50%',
          backgroundColor: color,
          boxShadow: `0 0 6px ${color}80`,
        }}
      />
    </span>
  );
}
