import React from 'react';
import { StatementEntry } from '../../lib/types';
import { Badge } from '../ui/badge';
import { formatDateTime, formatINR } from '../../lib/format';

interface StatementTableProps {
  entries: StatementEntry[];
  isLoading?: boolean;
}

export function StatementTable({ entries, isLoading = false }: StatementTableProps) {
  if (isLoading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', padding: '1rem 0' }}>
        {[1, 2, 3].map((i) => (
          <div
            key={i}
            className="skeleton-shimmer"
            style={{
              height: '48px',
              borderRadius: '8px',
              backgroundColor: 'rgba(255, 255, 255, 0.04)',
            }}
          />
        ))}
      </div>
    );
  }

  if (entries.length === 0) {
    return (
      <div
        style={{
          padding: '2.5rem 1rem',
          textAlign: 'center',
          color: '#64748b',
          fontSize: '0.8125rem',
        }}
      >
        No immutable journal lines recorded for this account.
      </div>
    );
  }

  return (
    <div className="signal-table-container">
      <table className="signal-table">
        <thead>
          <tr>
            <th style={{ width: '60px' }}>Seq #</th>
            <th>Operation</th>
            <th>Side</th>
            <th style={{ textAlign: 'right' }}>Amount</th>
            <th>Description</th>
            <th>Timestamp</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((e) => {
            const isCredit = e.side === 'CREDIT';
            return (
              <tr key={`${e.journal_id}-${e.line_no}`}>
                <td className="font-mono" style={{ color: '#94a3b8', fontSize: '0.75rem' }}>
                  #{e.account_sequence}
                </td>
                <td>
                  <Badge variant="blue" size="sm">
                    {e.operation_type}
                  </Badge>
                </td>
                <td>
                  <span
                    style={{
                      fontSize: '0.75rem',
                      fontWeight: 700,
                      color: isCredit ? '#0df2a6' : '#fb7185',
                    }}
                  >
                    {isCredit ? '+ CREDIT' : '- DEBIT'}
                  </span>
                </td>
                <td
                  style={{
                    textAlign: 'right',
                    fontWeight: 600,
                    color: isCredit ? '#0df2a6' : '#f8fafc',
                  }}
                >
                  {formatINR(e.amount_minor)}
                </td>
                <td style={{ color: '#94a3b8', fontSize: '0.75rem', maxWidth: '200px' }}>
                  {e.description || '—'}
                </td>
                <td style={{ color: '#64748b', fontSize: '0.6875rem', whiteSpace: 'nowrap' }}>
                  {formatDateTime(e.created_at)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
