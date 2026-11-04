import React, { useState, useMemo } from 'react';
import { AccountItem, StatementEntry } from '../../lib/types';
import { Card } from '../ui/card';
import { Button } from '../ui/button';
import { AccountsTable } from './accounts-table';
import { AccountDetailSheet } from './account-detail-sheet';
import { formatINR } from '../../lib/format';

interface AccountsScreenProps {
  accounts: AccountItem[];
  onRefresh: () => void;
  isRefreshing?: boolean;
  selectedAccount: AccountItem | null;
  onSelectAccount: (account: AccountItem | null) => void;
  statementEntries: StatementEntry[];
  isLoadingStatement?: boolean;
}

export function AccountsScreen({
  accounts,
  onRefresh,
  isRefreshing = false,
  selectedAccount,
  onSelectAccount,
  statementEntries,
  isLoadingStatement = false,
}: AccountsScreenProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [ledgerFilter, setLedgerFilter] = useState<'all' | 'ledger-1' | 'ledger-2'>('all');
  const [statusFilter, setStatusFilter] = useState<'all' | 'ACTIVE' | 'FROZEN' | 'CLOSED'>('all');

  const filteredAccounts = useMemo(() => {
    return accounts.filter((a) => {
      const matchesSearch =
        searchQuery.trim() === '' ||
        a.account_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
        a.customer_id.toLowerCase().includes(searchQuery.toLowerCase());

      const matchesLedger = ledgerFilter === 'all' || a.ledger_id === ledgerFilter;
      const matchesStatus = statusFilter === 'all' || a.status === statusFilter;

      return matchesSearch && matchesLedger && matchesStatus;
    });
  }, [accounts, searchQuery, ledgerFilter, statusFilter]);

  const totalAvailable = useMemo(() => {
    return filteredAccounts.reduce((acc, a) => acc + a.available_balance_minor, 0);
  }, [filteredAccounts]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Top Filter Bar & Controls */}
      <Card style={{ padding: '1.25rem 1.5rem' }}>
        <div
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '1rem',
          }}
        >
          {/* Search Input */}
          <div style={{ position: 'relative', minWidth: '260px', flex: 1, maxWidth: '420px' }}>
            <input
              type="text"
              placeholder="Search by Account or Customer ID..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{
                width: '100%',
                padding: '0.55rem 0.85rem 0.55rem 2.2rem',
                borderRadius: '10px',
                background: 'rgba(255, 255, 255, 0.04)',
                border: '1px solid rgba(255, 255, 255, 0.10)',
                color: '#f8fafc',
                fontSize: '0.8125rem',
              }}
            />
            <span
              style={{
                position: 'absolute',
                left: '0.75rem',
                top: '50%',
                transform: 'translateY(-50%)',
                color: '#64748b',
                fontSize: '0.875rem',
              }}
            >
              🔍
            </span>
            {searchQuery && (
              <button
                onClick={() => setSearchQuery('')}
                style={{
                  position: 'absolute',
                  right: '0.75rem',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  background: 'none',
                  border: 'none',
                  color: '#64748b',
                  cursor: 'pointer',
                }}
              >
                ✕
              </button>
            )}
          </div>

          {/* Filters: Ledger & Status */}
          <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.75rem' }}>
            {/* Ledger Filter */}
            <div
              style={{
                display: 'inline-flex',
                background: 'rgba(255, 255, 255, 0.04)',
                borderRadius: '8px',
                padding: '0.2rem',
                border: '1px solid rgba(255, 255, 255, 0.08)',
                fontSize: '0.75rem',
              }}
            >
              {(['all', 'ledger-1', 'ledger-2'] as const).map((lid) => (
                <button
                  key={lid}
                  onClick={() => setLedgerFilter(lid)}
                  style={{
                    padding: '0.3rem 0.65rem',
                    borderRadius: '6px',
                    border: 'none',
                    background: ledgerFilter === lid ? '#1e242d' : 'transparent',
                    color: ledgerFilter === lid ? '#0df2a6' : '#94a3b8',
                    fontWeight: ledgerFilter === lid ? 600 : 500,
                    cursor: 'pointer',
                    transition: 'all 0.15s ease',
                  }}
                >
                  {lid === 'all' ? 'All Ledgers' : lid.toUpperCase()}
                </button>
              ))}
            </div>

            {/* Status Filter */}
            <div
              style={{
                display: 'inline-flex',
                background: 'rgba(255, 255, 255, 0.04)',
                borderRadius: '8px',
                padding: '0.2rem',
                border: '1px solid rgba(255, 255, 255, 0.08)',
                fontSize: '0.75rem',
              }}
            >
              {(['all', 'ACTIVE', 'FROZEN', 'CLOSED'] as const).map((st) => (
                <button
                  key={st}
                  onClick={() => setStatusFilter(st)}
                  style={{
                    padding: '0.3rem 0.65rem',
                    borderRadius: '6px',
                    border: 'none',
                    background: statusFilter === st ? '#1e242d' : 'transparent',
                    color: statusFilter === st ? '#0df2a6' : '#94a3b8',
                    fontWeight: statusFilter === st ? 600 : 500,
                    cursor: 'pointer',
                    transition: 'all 0.15s ease',
                  }}
                >
                  {st === 'all' ? 'All States' : st}
                </button>
              ))}
            </div>

            <Button
              variant="secondary"
              size="sm"
              onClick={onRefresh}
              isLoading={isRefreshing}
            >
              Refresh
            </Button>
          </div>
        </div>

        {/* Quick metrics sub-strip */}
        <div
          style={{
            marginTop: '1rem',
            paddingTop: '0.85rem',
            borderTop: '1px solid rgba(255, 255, 255, 0.05)',
            display: 'flex',
            flexWrap: 'wrap',
            alignItems: 'center',
            justifyContent: 'space-between',
            fontSize: '0.75rem',
            color: '#64748b',
          }}
        >
          <span>
            Showing <strong style={{ color: '#f8fafc' }}>{filteredAccounts.length}</strong> of{' '}
            {accounts.length} provisioned accounts
          </span>
          <span>
            Filtered Available Liquidity:{' '}
            <strong style={{ color: '#0df2a6' }}>{formatINR(totalAvailable)}</strong>
          </span>
        </div>
      </Card>

      {/* Main Accounts Table Card */}
      <Card style={{ padding: 0, overflow: 'hidden' }}>
        <AccountsTable
          accounts={filteredAccounts}
          onOpenStatement={(acct) => onSelectAccount(acct)}
        />
      </Card>

      {/* Account Detail & Statement Sheet */}
      <AccountDetailSheet
        account={selectedAccount}
        onClose={() => onSelectAccount(null)}
        statementEntries={statementEntries}
        isLoadingStatement={isLoadingStatement}
      />
    </div>
  );
}
