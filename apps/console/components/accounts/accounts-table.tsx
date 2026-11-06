import React from 'react';
import { AccountItem } from '../../lib/types';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import { CopyButton } from '../ui/copy-button';
import { formatINR, truncateId } from '../../lib/format';

interface AccountsTableProps {
  accounts: AccountItem[];
  onOpenStatement: (account: AccountItem) => void;
  isLoading?: boolean;
}

export function AccountsTable({
  accounts,
  onOpenStatement,
  isLoading = false,
}: AccountsTableProps) {
  if (isLoading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', padding: '1rem' }}>
        {[1, 2, 3, 4, 5].map((i) => (
          <div
            key={i}
            className="skeleton-shimmer"
            style={{
              height: '52px',
              borderRadius: '10px',
              backgroundColor: 'rgba(255, 255, 255, 0.04)',
            }}
          />
        ))}
      </div>
    );
  }

  if (accounts.length === 0) {
    return (
      <div
        style={{
          padding: '3.5rem 1rem',
          textAlign: 'center',
          color: '#64748b',
          fontSize: '0.875rem',
        }}
      >
        No accounts found matching the current search and filter criteria.
      </div>
    );
  }

  return (
    <>
      {/* Desktop Table View */}
      <div className="signal-table-container hidden md:block">
        <table className="signal-table">
          <thead>
            <tr>
              <th>Account ID</th>
              <th>Customer ID</th>
              <th>Ledger</th>
              <th>Status</th>
              <th style={{ textAlign: 'right' }}>Posted Balance</th>
              <th style={{ textAlign: 'right' }}>Active Holds</th>
              <th style={{ textAlign: 'right' }}>Available Balance</th>
              <th style={{ textAlign: 'center', width: '110px' }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {accounts.map((acct) => (
              <tr key={acct.account_id}>
                <td>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
                    <span className="font-mono" style={{ color: '#0df2a6', fontWeight: 600, fontSize: '0.75rem' }}>
                      {truncateId(acct.account_id, 8, 4)}
                    </span>
                    <CopyButton text={acct.account_id} />
                  </div>
                </td>
                <td>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
                    <span className="font-mono" style={{ color: '#94a3b8', fontSize: '0.75rem' }}>
                      {truncateId(acct.customer_id, 8)}
                    </span>
                    <CopyButton text={acct.customer_id} />
                  </div>
                </td>
                <td>
                  <Badge variant={acct.ledger_id === 'ledger-1' ? 'blue' : 'neutral'} size="sm">
                    {acct.ledger_id}
                  </Badge>
                </td>
                <td>
                  <Badge
                    variant={
                      acct.status === 'ACTIVE'
                        ? 'mint'
                        : acct.status === 'FROZEN'
                        ? 'amber'
                        : 'rose'
                    }
                    size="sm"
                    dot={true}
                  >
                    {acct.status}
                  </Badge>
                </td>
                <td style={{ textAlign: 'right', fontWeight: 600 }}>
                  {formatINR(acct.posted_balance_minor)}
                </td>
                <td
                  style={{
                    textAlign: 'right',
                    fontWeight: 500,
                    color: acct.held_amount_minor > 0 ? '#fbbf24' : '#64748b',
                  }}
                >
                  {formatINR(acct.held_amount_minor)}
                </td>
                <td
                  style={{
                    textAlign: 'right',
                    fontWeight: 700,
                    color: '#0df2a6',
                  }}
                >
                  {formatINR(acct.available_balance_minor)}
                </td>
                <td style={{ textAlign: 'center' }}>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => onOpenStatement(acct)}
                  >
                    Statement
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Mobile Card View (Narrow screens) */}
      <div className="md:hidden" style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
        {accounts.map((acct) => (
          <div
            key={acct.account_id}
            style={{
              background: 'rgba(255, 255, 255, 0.02)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              borderRadius: '12px',
              padding: '1rem',
              display: 'flex',
              flexDirection: 'column',
              gap: '0.75rem',
            }}
          >
            {/* Top row */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                <span className="font-mono" style={{ color: '#0df2a6', fontWeight: 700, fontSize: '0.75rem' }}>
                  {truncateId(acct.account_id, 8, 4)}
                </span>
                <CopyButton text={acct.account_id} />
              </div>
              <div style={{ display: 'flex', gap: '0.4rem' }}>
                <Badge variant="blue" size="sm">
                  {acct.ledger_id}
                </Badge>
                <Badge
                  variant={
                    acct.status === 'ACTIVE'
                      ? 'mint'
                      : acct.status === 'FROZEN'
                      ? 'amber'
                      : 'rose'
                  }
                  size="sm"
                >
                  {acct.status}
                </Badge>
              </div>
            </div>

            {/* Financial balance triad */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(3, 1fr)',
                gap: '0.5rem',
                fontSize: '0.75rem',
                background: 'rgba(0, 0, 0, 0.25)',
                padding: '0.65rem',
                borderRadius: '8px',
              }}
            >
              <div>
                <div style={{ color: '#64748b', fontSize: '0.6875rem' }}>Posted</div>
                <div style={{ fontWeight: 600, color: '#f8fafc', marginTop: '0.1rem' }}>
                  {formatINR(acct.posted_balance_minor)}
                </div>
              </div>
              <div>
                <div style={{ color: '#64748b', fontSize: '0.6875rem' }}>Held</div>
                <div style={{ fontWeight: 600, color: acct.held_amount_minor > 0 ? '#fbbf24' : '#64748b', marginTop: '0.1rem' }}>
                  {formatINR(acct.held_amount_minor)}
                </div>
              </div>
              <div>
                <div style={{ color: '#0df2a6', fontSize: '0.6875rem' }}>Available</div>
                <div style={{ fontWeight: 700, color: '#0df2a6', marginTop: '0.1rem' }}>
                  {formatINR(acct.available_balance_minor)}
                </div>
              </div>
            </div>

            {/* Action */}
            <Button
              variant="secondary"
              size="sm"
              onClick={() => onOpenStatement(acct)}
              style={{ width: '100%', justifyContent: 'center' }}
            >
              Inspect Statement History
            </Button>
          </div>
        ))}
      </div>
    </>
  );
}
