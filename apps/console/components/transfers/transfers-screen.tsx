import React, { useState, useMemo } from 'react';
import { TransferItem, WorkflowEvent } from '../../lib/types';
import { Card } from '../ui/card';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { TransfersTable } from './transfers-table';
import { TransferDetailSheet } from './transfer-detail-sheet';
import { formatINR } from '../../lib/format';

interface TransfersScreenProps {
  transfers: TransferItem[];
  onRefresh: () => void;
  isRefreshing?: boolean;
  selectedTransfer: TransferItem | null;
  onSelectTransfer: (transfer: TransferItem | null) => void;
  timelineEvents: WorkflowEvent[];
  isLoadingTimeline?: boolean;
}

export function TransfersScreen({
  transfers,
  onRefresh,
  isRefreshing = false,
  selectedTransfer,
  onSelectTransfer,
  timelineEvents,
  isLoadingTimeline = false,
}: TransfersScreenProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [stateFilter, setStateFilter] = useState<string>('all');
  const [routeFilter, setRouteFilter] = useState<'all' | 'L1_TO_L2' | 'L2_TO_L1' | 'INTERNAL'>('all');
  const [attentionOnly, setAttentionOnly] = useState(false);

  const filteredTransfers = useMemo(() => {
    return transfers.filter((t) => {
      const matchesSearch =
        searchQuery.trim() === '' ||
        t.transfer_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
        t.source_account_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
        t.destination_account_id.toLowerCase().includes(searchQuery.toLowerCase());

      const matchesState = stateFilter === 'all' || t.state === stateFilter;

      let matchesRoute = true;
      if (routeFilter === 'L1_TO_L2') {
        matchesRoute = t.source_ledger_id === 'ledger-1' && t.destination_ledger_id === 'ledger-2';
      } else if (routeFilter === 'L2_TO_L1') {
        matchesRoute = t.source_ledger_id === 'ledger-2' && t.destination_ledger_id === 'ledger-1';
      } else if (routeFilter === 'INTERNAL') {
        matchesRoute = t.source_ledger_id === t.destination_ledger_id;
      }

      const matchesAttention = !attentionOnly || t.attention_required;

      return matchesSearch && matchesState && matchesRoute && matchesAttention;
    });
  }, [transfers, searchQuery, stateFilter, routeFilter, attentionOnly]);

  const settledSum = useMemo(() => {
    return filteredTransfers
      .filter((t) => t.state === 'SETTLED')
      .reduce((acc, t) => acc + t.amount_minor, 0);
  }, [filteredTransfers]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Top Filter Bar */}
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
          <div style={{ position: 'relative', minWidth: '260px', flex: 1, maxWidth: '380px' }}>
            <input
              type="text"
              placeholder="Search by Transfer or Account ID..."
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

          {/* Filters: State, Route, Attention toggle */}
          <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.65rem' }}>
            {/* State Filter */}
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
              {(['all', 'SETTLED', 'COMMITTING', 'PREPARING', 'CANCELLED'] as const).map((st) => (
                <button
                  key={st}
                  onClick={() => setStateFilter(st)}
                  style={{
                    padding: '0.3rem 0.65rem',
                    borderRadius: '6px',
                    border: 'none',
                    background: stateFilter === st ? '#1e242d' : 'transparent',
                    color: stateFilter === st ? '#0df2a6' : '#94a3b8',
                    fontWeight: stateFilter === st ? 600 : 500,
                    cursor: 'pointer',
                    transition: 'all 0.15s ease',
                  }}
                >
                  {st === 'all' ? 'All States' : st}
                </button>
              ))}
            </div>

            {/* Route Filter */}
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
              {(
                [
                  { id: 'all', label: 'All Routes' },
                  { id: 'L1_TO_L2', label: 'L1 → L2' },
                  { id: 'L2_TO_L1', label: 'L2 → L1' },
                ] as const
              ).map((r) => (
                <button
                  key={r.id}
                  onClick={() => setRouteFilter(r.id)}
                  style={{
                    padding: '0.3rem 0.65rem',
                    borderRadius: '6px',
                    border: 'none',
                    background: routeFilter === r.id ? '#1e242d' : 'transparent',
                    color: routeFilter === r.id ? '#0df2a6' : '#94a3b8',
                    fontWeight: routeFilter === r.id ? 600 : 500,
                    cursor: 'pointer',
                    transition: 'all 0.15s ease',
                  }}
                >
                  {r.label}
                </button>
              ))}
            </div>

            {/* Attention Only Toggle */}
            <button
              onClick={() => setAttentionOnly(!attentionOnly)}
              className="btn-interactive"
              style={{
                padding: '0.35rem 0.75rem',
                borderRadius: '8px',
                background: attentionOnly ? 'rgba(245, 158, 11, 0.15)' : 'rgba(255, 255, 255, 0.04)',
                border: `1px solid ${attentionOnly ? 'rgba(245, 158, 11, 0.4)' : 'rgba(255, 255, 255, 0.08)'}`,
                color: attentionOnly ? '#fbbf24' : '#94a3b8',
                fontSize: '0.75rem',
                fontWeight: attentionOnly ? 600 : 500,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '0.35rem',
              }}
            >
              <span>⚠</span>
              <span>Attention Only</span>
            </button>

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
            Displaying <strong style={{ color: '#f8fafc' }}>{filteredTransfers.length}</strong> of{' '}
            {transfers.length} transfers
          </span>
          <span>
            Settled Volume:{' '}
            <strong style={{ color: '#0df2a6' }}>{formatINR(settledSum)}</strong>
          </span>
        </div>
      </Card>

      {/* Main Transfers Table Card */}
      <Card style={{ padding: 0, overflow: 'hidden' }}>
        <TransfersTable
          transfers={filteredTransfers}
          onOpenTimeline={(transfer) => onSelectTransfer(transfer)}
        />
      </Card>

      {/* Transfer Lifecycle Detail Sheet */}
      <TransferDetailSheet
        transfer={selectedTransfer}
        onClose={() => onSelectTransfer(null)}
        timelineEvents={timelineEvents}
        isLoadingTimeline={isLoadingTimeline}
      />
    </div>
  );
}
