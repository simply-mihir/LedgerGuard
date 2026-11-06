import React from 'react';

interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {
  width?: string | number;
  height?: string | number;
  borderRadius?: string;
}

export function Skeleton({
  width = '100%',
  height = '1rem',
  borderRadius = '8px',
  className = '',
  style,
  ...props
}: SkeletonProps) {
  return (
    <div
      className={`skeleton-shimmer ${className}`}
      style={{
        width,
        height,
        borderRadius,
        background: 'rgba(255, 255, 255, 0.04)',
        ...style,
      }}
      {...props}
    />
  );
}
