import React from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '../ui/card';
import { TransferItem } from '../../lib/types';
import { formatNumber } from '../../lib/format';

interface TransferActivityCardProps {
  settledCount: number;
  pendingCount: number;
  totalCount: number;
  recentTransfers: TransferItem[];
}

export function TransferActivityCard({
  settledCount,
  pendingCount,
  totalCount,
  recentTransfers,
}: TransferActivityCardProps) {
  const settledRatio = totalCount > 0 ? (settledCount / totalCount) * 100 : 100;
  const pendingRatio = totalCount > 0 ? (pendingCount / totalCount) * 100 : 0;
  const otherRatio = Math.max(0, 100 - settledRatio - pendingRatio);

  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>Transfer Settlement Distribution</CardTitle>
          <div style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '0.15rem' }}>
            Two-phase business commit throughput
          </div>
        </div>
        <div className="font-mono" style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
          {formatNumber(totalCount)} Total Transfers
        </div>
      </CardHeader>

      <CardContent style={{ padding: '1.25rem 1.5rem' }}>
        {/* Native Segmented Bar */}
        <div
          style={{
            height: '10px',
            width: '100%',
            borderRadius: '9999px',
            backgroundColor: 'rgba(255, 255, 255, 0.05)',
            display: 'flex',
            overflow: 'hidden',
            marginBottom: '1rem',
          }}
        >
          <div
            title={`Settled: ${settledCount} (${settledRatio.toFixed(1)}%)`}
            style={{
              width: `${settledRatio}%`,
              backgroundColor: '#0df2a6',
              transition: 'width 0.5s ease',
            }}
          />
          <div
            title={`Pending: ${pendingCount} (${pendingRatio.toFixed(1)}%)`}
            style={{
              width: `${pendingRatio}%`,
              backgroundColor: '#f59e0b',
              transition: 'width 0.5s ease',
            }}
          />
          {otherRatio > 0 && (
            <div
              title={`Cancelled / Other: ${otherRatio.toFixed(1)}%`}
              style={{
                width: `${otherRatio}%`,
                backgroundColor: '#f43f5e',
                transition: 'width 0.5s ease',
              }}
            />
          )}
        </div>

        {/* Legend */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(3, 1fr)',
            gap: '0.75rem',
            fontSize: '0.75rem',
            color: '#94a3b8',
          }}
        >
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', color: '#64748b' }}>
              <span style={{ width: '8px', height: '8px', borderRadius: '2px', backgroundColor: '#0df2a6' }} />
              <span>Settled</span>
            </div>
            <span style={{ fontSize: '1.125rem', fontWeight: 700, color: '#f8fafc', marginTop: '0.2rem' }}>
              {settledCount}
            </span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', color: '#64748b' }}>
              <span style={{ width: '8px', height: '8px', borderRadius: '2px', backgroundColor: '#f59e0b' }} />
              <span>In-Flight TCC</span>
            </div>
            <span style={{ fontSize: '1.125rem', fontWeight: 700, color: '#f8fafc', marginTop: '0.2rem' }}>
              {pendingCount}
            </span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', color: '#64748b' }}>
              <span style={{ width: '8px', height: '8px', borderRadius: '2px', backgroundColor: '#38bdf8' }} />
              <span>Recovery Gate</span>
            </div>
            <span style={{ fontSize: '1.125rem', fontWeight: 700, color: '#f8fafc', marginTop: '0.2rem' }}>
              100% Forward
            </span>
          </div>
        </div>

        {/* SVG Mini Sparkline Curve */}
        <div style={{ marginTop: '1.25rem', paddingTop: '1rem', borderTop: '1px solid rgba(255, 255, 255, 0.05)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.6875rem', color: '#64748b', marginBottom: '0.4rem' }}>
            <span>Settlement Momentum</span>
            <span className="font-mono" style={{ color: '#0df2a6' }}>Durable Commit Log</span>
          </div>
          <svg width="100%" height="32" viewBox="0 0 300 32" fill="none" preserveAspectRatio="none">
            <path
              d="M 0 24 C 40 22, 70 28, 110 18 C 150 8, 180 14, 220 6 C 260 2, 280 8, 300 4"
              stroke="#0df2a6"
              strokeWidth="2"
              strokeLinecap="round"
            />
            <path
              d="M 0 24 C 40 22, 70 28, 110 18 C 150 8, 180 14, 220 6 C 260 2, 280 8, 300 4 L 300 32 L 0 32 Z"
              fill="url(#sparkline-grad)"
              opacity="0.25"
            />
            <defs>
              <linearGradient id="sparkline-grad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#0df2a6" />
                <stop offset="100%" stopColor="#0df2a6" stopOpacity="0" />
              </linearGradient>
            </defs>
          </svg>
        </div>
      </CardContent>
    </Card>
  );
}
