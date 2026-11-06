import React from 'react';
import { AccountItem, StatementEntry } from '../../lib/types';
import { Sheet } from '../ui/sheet';
import { Badge } from '../ui/badge';
import { CopyButton } from '../ui/copy-button';
import { formatINR } from '../../lib/format';
import { StatementTable } from './statement-table';

interface AccountDetailSheetProps {
  account: AccountItem | null;
  onClose: () => void;
  statementEntries: StatementEntry[];
  isLoadingStatement?: boolean;
  nextCursor?: number | null;
  onLoadMore?: () => void;
  isLoadingMore?: boolean;
}

export function AccountDetailSheet({
  account,
  onClose,
  statementEntries,
  isLoadingStatement = false,
  nextCursor = null,
  onLoadMore,
  isLoadingMore = false,
}: AccountDetailSheetProps) {
  if (!account) return null;

  return (
    <Sheet
      isOpen={Boolean(account)}
      onClose={onClose}
      width="620px"
      title={
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
          <span>Account Statement & Audit</span>
          <Badge
            variant={
              account.status === 'ACTIVE'
                ? 'mint'
                : account.status === 'FROZEN'
                ? 'amber'
                : 'rose'
            }
            size="sm"
          >
            {account.status}
          </Badge>
        </div>
      }
      subtitle={
        <span className="font-mono" style={{ color: '#0df2a6' }}>
          {account.ledger_id.toUpperCase()} • Route v{account.routing_version}
        </span>
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
        {/* Identifiers Card */}
        <div
          style={{
            background: 'rgba(255, 255, 255, 0.03)',
            border: '1px solid rgba(255, 255, 255, 0.08)',
            borderRadius: '12px',
            padding: '1rem 1.25rem',
            display: 'flex',
            flexDirection: 'column',
            gap: '0.65rem',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: '0.75rem', color: '#64748b' }}>Account ID</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span className="font-mono" style={{ fontSize: '0.8125rem', color: '#f8fafc' }}>
                {account.account_id}
              </span>
              <CopyButton text={account.account_id} />
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: '0.75rem', color: '#64748b' }}>Customer ID</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span className="font-mono" style={{ fontSize: '0.8125rem', color: '#94a3b8' }}>
                {account.customer_id}
              </span>
              <CopyButton text={account.customer_id} />
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: '0.75rem', color: '#64748b' }}>Provisioning State</span>
            <Badge variant="neutral" size="sm">
              {account.provisioning_state}
            </Badge>
          </div>
        </div>

        {/* Financial Balance Triad */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(3, 1fr)',
            gap: '0.75rem',
          }}
        >
          <div
            style={{
              background: 'rgba(255, 255, 255, 0.02)',
              border: '1px solid rgba(255, 255, 255, 0.06)',
              borderRadius: '10px',
              padding: '0.875rem',
            }}
          >
            <div style={{ fontSize: '0.6875rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>
              Posted Balance
            </div>
            <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#f8fafc', marginTop: '0.25rem' }}>
              {formatINR(account.posted_balance_minor)}
            </div>
          </div>

          <div
            style={{
              background: 'rgba(255, 255, 255, 0.02)',
              border: '1px solid rgba(255, 255, 255, 0.06)',
              borderRadius: '10px',
              padding: '0.875rem',
            }}
          >
            <div style={{ fontSize: '0.6875rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>
              Active Holds
            </div>
            <div
              style={{
                fontSize: '1.25rem',
                fontWeight: 700,
                color: account.held_amount_minor > 0 ? '#fbbf24' : '#64748b',
                marginTop: '0.25rem',
              }}
            >
              {formatINR(account.held_amount_minor)}
            </div>
          </div>

          <div
            style={{
              background: 'rgba(13, 242, 166, 0.06)',
              border: '1px solid rgba(13, 242, 166, 0.25)',
              borderRadius: '10px',
              padding: '0.875rem',
            }}
          >
            <div style={{ fontSize: '0.6875rem', color: '#0df2a6', textTransform: 'uppercase', fontWeight: 600 }}>
              Available
            </div>
            <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#0df2a6', marginTop: '0.25rem' }}>
              {formatINR(account.available_balance_minor)}
            </div>
          </div>
        </div>

        {/* Immutable Journal History Section */}
        <div>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginBottom: '0.75rem',
            }}
          >
            <span style={{ fontSize: '0.875rem', fontWeight: 700, color: '#f8fafc' }}>
              Immutable Journal Statements
            </span>
            <span className="font-mono" style={{ fontSize: '0.6875rem', color: '#64748b' }}>
              Append-Only • Trigger Protected
            </span>
          </div>

          <StatementTable entries={statementEntries} isLoading={isLoadingStatement} />

          {nextCursor !== null && nextCursor !== undefined && onLoadMore && (
            <div style={{ marginTop: '0.75rem', textAlign: 'center' }}>
              <button
                type="button"
                onClick={onLoadMore}
                disabled={isLoadingMore}
                style={{
                  background: 'rgba(255, 255, 255, 0.04)',
                  border: '1px solid rgba(255, 255, 255, 0.12)',
                  color: '#f8fafc',
                  borderRadius: '8px',
                  padding: '0.5rem 1rem',
                  fontSize: '0.75rem',
                  fontWeight: 600,
                  cursor: isLoadingMore ? 'not-allowed' : 'pointer',
                  opacity: isLoadingMore ? 0.6 : 1,
                  transition: 'all 0.15s ease',
                }}
              >
                {isLoadingMore ? 'Loading next page...' : `Load more entries (Cursor: ${nextCursor})`}
              </button>
            </div>
          )}
        </div>
      </div>
    </Sheet>
  );
}
