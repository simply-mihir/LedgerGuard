import React from 'react';
import { ExperimentResult } from '../../lib/types';
import { Badge } from '../ui/badge';
import { formatINR } from '../../lib/format';

interface ExperimentStepperProps {
  result: ExperimentResult;
}

export function ExperimentStepper({ result }: ExperimentStepperProps) {
  const isSettled = result.status === 'SETTLED';

  const phaseColors: Record<string, { border: string; bg: string; text: string }> = {
    PREPARE: { border: '#38bdf8', bg: 'rgba(56, 189, 248, 0.08)', text: '#38bdf8' },
    DECISION_POINT: { border: '#0df2a6', bg: 'rgba(13, 242, 166, 0.08)', text: '#0df2a6' },
    FAULT_INJECTION: { border: '#f43f5e', bg: 'rgba(244, 63, 94, 0.12)', text: '#fb7185' },
    FORWARD_RECOVERY: { border: '#f59e0b', bg: 'rgba(245, 158, 11, 0.10)', text: '#fbbf24' },
    AUDIT_VERIFICATION: { border: '#0df2a6', bg: 'rgba(13, 242, 166, 0.08)', text: '#0df2a6' },
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      {/* Header bar */}
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '1rem',
          paddingBottom: '0.85rem',
          borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
        }}
      >
        <div>
          <span style={{ fontSize: '0.6875rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>
            Execution Trace
          </span>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: '0.2rem' }}>
            <span style={{ fontSize: '1rem', fontWeight: 700, color: '#f8fafc' }}>
              Transfer:{' '}
            </span>
            <span className="font-mono" style={{ fontSize: '0.875rem', color: '#0df2a6' }}>
              {result.transfer_id}
            </span>
          </div>
        </div>

        <Badge variant={isSettled ? 'mint' : 'amber'} size="md" dot={true}>
          {result.status}
        </Badge>
      </div>

      {/* Structured Stepper Trace */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
        {result.steps.map((st) => {
          const p = phaseColors[st.phase] || phaseColors.PREPARE;
          const isFault = st.phase === 'FAULT_INJECTION';

          return (
            <div
              key={st.step_number}
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: '1rem',
                padding: '1rem 1.25rem',
                background: p.bg,
                border: `1px solid ${p.border}40`,
                borderLeft: `4px solid ${p.border}`,
                borderRadius: '10px',
              }}
            >
              {/* Step Number Circle */}
              <div
                className="font-mono"
                style={{
                  width: '28px',
                  height: '28px',
                  borderRadius: '50%',
                  background: 'rgba(0, 0, 0, 0.4)',
                  border: `1px solid ${p.border}`,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: p.text,
                  fontSize: '0.75rem',
                  fontWeight: 700,
                  flexShrink: 0,
                }}
              >
                {st.step_number}
              </div>

              {/* Step Body */}
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: '0.5rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <span
                      style={{
                        fontSize: '0.6875rem',
                        fontWeight: 700,
                        color: p.text,
                        background: 'rgba(0, 0, 0, 0.3)',
                        padding: '0.15rem 0.45rem',
                        borderRadius: '4px',
                        border: `1px solid ${p.border}50`,
                      }}
                    >
                      {st.phase}
                    </span>
                    <span style={{ fontSize: '0.875rem', fontWeight: 600, color: '#f8fafc' }}>
                      {st.action}
                    </span>
                  </div>

                  <Badge
                    variant={
                      st.outcome === 'VERIFIED' || st.outcome === 'SUCCESS'
                        ? 'mint'
                        : isFault
                        ? 'rose'
                        : 'amber'
                    }
                    size="sm"
                  >
                    {st.outcome}
                  </Badge>
                </div>

                <p style={{ fontSize: '0.8125rem', color: '#cbd5e1', marginTop: '0.35rem', lineHeight: 1.5 }}>
                  {st.details}
                </p>
              </div>
            </div>
          );
        })}
      </div>

      {/* Final Accounting State Card */}
      {result.final_accounting_state && (
        <div
          style={{
            background: 'linear-gradient(135deg, rgba(13, 242, 166, 0.08) 0%, rgba(19, 22, 28, 0.9) 100%)',
            border: '1px solid rgba(13, 242, 166, 0.35)',
            borderRadius: '12px',
            padding: '1.25rem 1.5rem',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span style={{ color: '#0df2a6', fontSize: '1.125rem' }}>✓</span>
              <span style={{ fontSize: '0.875rem', fontWeight: 700, color: '#f8fafc' }}>
                Final Invariant Verification Passed
              </span>
            </div>
            <Badge variant="mint" size="sm" dot={true}>
              Zero Residual Holds Verified
            </Badge>
          </div>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
              gap: '1rem',
              fontSize: '0.8125rem',
            }}
          >
            <div style={{ background: 'rgba(0, 0, 0, 0.3)', padding: '0.75rem 1rem', borderRadius: '8px' }}>
              <div style={{ color: '#64748b', fontSize: '0.6875rem' }}>Alice Final Posted (L1)</div>
              <div style={{ fontSize: '1.125rem', fontWeight: 700, color: '#f8fafc', marginTop: '0.2rem' }}>
                {formatINR(result.final_accounting_state.alice_posted ?? 0)}
              </div>
            </div>

            <div style={{ background: 'rgba(0, 0, 0, 0.3)', padding: '0.75rem 1rem', borderRadius: '8px' }}>
              <div style={{ color: '#0df2a6', fontSize: '0.6875rem' }}>Alice Residual Hold</div>
              <div style={{ fontSize: '1.125rem', fontWeight: 700, color: '#0df2a6', marginTop: '0.2rem' }}>
                {formatINR(result.final_accounting_state.alice_held ?? 0)}
              </div>
            </div>

            <div style={{ background: 'rgba(0, 0, 0, 0.3)', padding: '0.75rem 1rem', borderRadius: '8px' }}>
              <div style={{ color: '#64748b', fontSize: '0.6875rem' }}>Bob Received Credit (L2)</div>
              <div style={{ fontSize: '1.125rem', fontWeight: 700, color: '#38bdf8', marginTop: '0.2rem' }}>
                {formatINR(result.final_accounting_state.bob_posted ?? 0)}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
