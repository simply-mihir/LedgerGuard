import React from 'react';
import { ReconciliationFinding } from '../../lib/types';
import { Badge } from '../ui/badge';
import { CopyButton } from '../ui/copy-button';

interface FindingsTableProps {
  findings: ReconciliationFinding[];
}

export function FindingsTable({ findings }: FindingsTableProps) {
  if (findings.length === 0) {
    return (
      <div
        style={{
          padding: '3rem 1.5rem',
          textAlign: 'center',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <div
          style={{
            width: '44px',
            height: '44px',
            borderRadius: '50%',
            backgroundColor: 'rgba(13, 242, 166, 0.12)',
            border: '1px solid rgba(13, 242, 166, 0.28)',
            color: '#0df2a6',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '1.25rem',
            marginBottom: '1rem',
          }}
        >
          ✓
        </div>
        <div style={{ fontSize: '1rem', fontWeight: 700, color: '#f8fafc', marginBottom: '0.35rem' }}>
          Zero Audit Discrepancies
        </div>
        <p style={{ fontSize: '0.8125rem', color: '#0df2a6', maxWidth: '580px', lineHeight: 1.5 }}>
          Clean audit: All double-entry journals balance, wallet caches match line sums, and inter-ledger clearing balances sum to zero.
        </p>
      </div>
    );
  }

  return (
    <div className="signal-table-container">
      <table className="signal-table">
        <thead>
          <tr>
            <th style={{ width: '100px' }}>Severity</th>
            <th>Check Name</th>
            <th>Resource ID</th>
            <th>Discrepancy Details</th>
          </tr>
        </thead>
        <tbody>
          {findings.map((f, idx) => (
            <tr key={idx}>
              <td>
                <Badge
                  variant={
                    f.severity === 'CRITICAL'
                      ? 'rose'
                      : f.severity === 'WARNING'
                      ? 'amber'
                      : 'blue'
                  }
                  size="sm"
                  dot={true}
                >
                  {f.severity}
                </Badge>
              </td>
              <td>
                <span className="font-mono" style={{ fontSize: '0.75rem', fontWeight: 600, color: '#f8fafc' }}>
                  {f.check_name}
                </span>
              </td>
              <td>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
                  <span className="font-mono" style={{ fontSize: '0.75rem', color: '#38bdf8' }}>
                    {f.resource_id}
                  </span>
                  <CopyButton text={f.resource_id} />
                </div>
              </td>
              <td style={{ fontSize: '0.8125rem', color: '#94a3b8' }}>
                {f.details}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
