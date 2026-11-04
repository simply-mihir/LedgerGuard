import React from 'react';
import { Card } from '../ui/card';

interface KpiCardProps {
  label: string;
  value: React.ReactNode;
  subtext?: React.ReactNode;
  trend?: React.ReactNode;
  icon?: React.ReactNode;
  accent?: 'none' | 'mint' | 'amber' | 'rose' | 'blue';
}

export function KpiCard({
  label,
  value,
  subtext,
  trend,
  icon,
  accent = 'none',
}: KpiCardProps) {
  return (
    <Card accent={accent} style={{ padding: '1.25rem 1.4rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.65rem' }}>
        <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#94a3b8', letterSpacing: '0.02em', textTransform: 'uppercase' }}>
          {label}
        </span>
        {icon && <span style={{ color: '#64748b' }}>{icon}</span>}
      </div>

      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: '0.5rem' }}>
        <div style={{ fontSize: '1.75rem', fontWeight: 700, letterSpacing: '-0.03em', color: '#f8fafc', lineHeight: 1.15 }}>
          {value}
        </div>
        {trend && <div>{trend}</div>}
      </div>

      {subtext && (
        <div style={{ marginTop: '0.5rem', fontSize: '0.75rem', color: '#64748b', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
          {subtext}
        </div>
      )}
    </Card>
  );
}
