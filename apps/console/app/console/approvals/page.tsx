'use client';

import React, { useEffect, useState } from 'react';
import { useAuth } from '../../../lib/auth-context';

interface ApprovalItem {
  request_id: string;
  action_type: string;
  state: string;
  initiator_id: string;
  initiator_role: string;
  approver_id?: string | null;
  expires_at: string;
  payload_hash: string;
}

export default function ApprovalsPage() {
  const { operator, csrfToken } = useAuth();
  const [items, setItems] = useState<ApprovalItem[]>([]);
  const [error, setError] = useState<string | null>(null);

  const loadApprovals = async () => {
    const res = await fetch('/api/operator/approvals', { cache: 'no-store' });
    if (res.ok) {
      setItems(await res.json());
    }
  };

  useEffect(() => {
    loadApprovals();
  }, []);

  const pendingCount = items.filter((i) => i.state === 'PENDING_APPROVAL').length;

  const handleAction = async (id: string, action: 'approve' | 'reject') => {
    setError(null);
    const res = await fetch(`/api/operator/approvals/${id}/${action}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(csrfToken ? { 'X-CSRF-Token': csrfToken } : {}),
      },
      body: JSON.stringify(
        action === 'approve'
          ? {
              approver_id: operator?.username || 'approver',
              approver_role: operator?.role ?? 'VIEWER',
              mfa_verified: operator?.totp_enabled ?? false,
              auth_age_seconds: 0,
            }
          : {
              actor_id: operator?.username || 'approver',
              actor_role: operator?.role ?? 'VIEWER',
            }
      ),
    });
    if (!res.ok) {
      const b = await res.json().catch(() => null);
      setError(b?.detail || `Action ${action} failed`);
      return;
    }
    loadApprovals();
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h1 style={{ fontSize: '1.5rem', fontWeight: 700, color: '#F8FAFC', letterSpacing: '-0.02em' }}>
            Four-Eyes Approval Inbox ({pendingCount} pending)
          </h1>
          <p style={{ fontSize: '0.875rem', color: '#94A3B8', marginTop: '0.25rem' }}>
            Dual-control authorization with immutable SHA-256 payload hashing, self-approval rejection, and MFA enforcement.
          </p>
        </div>
        <a
          href="/api/operator/approvals/export"
          target="_blank"
          rel="noreferrer"
          style={{ padding: '0.55rem 1rem', borderRadius: '12px', background: 'rgba(59,130,246,0.16)', border: '1px solid rgba(59,130,246,0.4)', color: '#93C5FD', fontSize: '0.8rem', fontWeight: 600, textDecoration: 'none' }}
        >
          Export Audit Trail
        </a>
      </header>

      {error && <div role="alert" style={{ padding: '0.875rem', borderRadius: '14px', background: 'rgba(244,63,94,0.14)', color: '#FDA4AF' }}>{error}</div>}

      {items.length === 0 ? (
        <div style={{ padding: '1.5rem', borderRadius: '24px', background: 'rgba(15, 23, 42, 0.72)', border: '1px solid rgba(255,255,255,0.08)', color: '#94A3B8' }}>
          No dual-control approval requests in queue.
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {items.map((item) => (
            <section key={item.request_id} style={{ padding: '1.25rem', borderRadius: '24px', background: 'rgba(15, 23, 42, 0.72)', border: '1px solid rgba(255,255,255,0.08)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
              <div>
                <div style={{ fontWeight: 600, color: '#F8FAFC' }}>{item.action_type}</div>
                <div style={{ fontSize: '0.78rem', color: '#94A3B8', fontFamily: 'var(--font-mono)' }}>
                  Initiator: {item.initiator_id} ({item.initiator_role}) • Hash: {item.payload_hash.slice(0, 14)}...
                </div>
                <div style={{ fontSize: '0.72rem', color: '#64748B' }}>Expires: {item.expires_at}</div>
              </div>
              <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                <span style={{ padding: '0.25rem 0.65rem', borderRadius: '9999px', fontSize: '0.72rem', fontWeight: 700, background: 'rgba(59,130,246,0.2)', color: '#93C5FD' }}>
                  {item.state}
                </span>
                {item.state === 'PENDING_APPROVAL' && (
                  <>
                    <button type="button" onClick={() => handleAction(item.request_id, 'approve')} style={{ padding: '0.4rem 0.75rem', borderRadius: '10px', background: 'rgba(16,185,129,0.2)', color: '#34D399', border: 'none', cursor: 'pointer', fontSize: '0.75rem' }}>
                      Approve
                    </button>
                    <button type="button" onClick={() => handleAction(item.request_id, 'reject')} style={{ padding: '0.4rem 0.75rem', borderRadius: '10px', background: 'rgba(244,63,94,0.2)', color: '#FDA4AF', border: 'none', cursor: 'pointer', fontSize: '0.75rem' }}>
                      Reject
                    </button>
                  </>
                )}
              </div>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
