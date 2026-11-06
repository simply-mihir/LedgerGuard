import React from 'react';
import { Card } from '../ui/card';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';

interface ExperimentCardProps {
  title: string;
  scenario: string;
  description: string;
  failurePoint: string;
  expectedInvariant: string;
  recoveryExpectation: string;
  onSelect: () => void;
  isRunning?: boolean;
  isDisabled?: boolean;
  disabledReason?: string;
}

export function ExperimentCard({
  title,
  scenario,
  description,
  failurePoint,
  expectedInvariant,
  recoveryExpectation,
  onSelect,
  isRunning = false,
  isDisabled = false,
  disabledReason,
}: ExperimentCardProps) {
  return (
    <Card accent="blue" style={{ padding: '1.5rem' }}>
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'flex-start',
          justifyContent: 'space-between',
          gap: '1rem',
          marginBottom: '1rem',
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.4rem' }}>
            <span style={{ fontSize: '1.125rem', fontWeight: 700, color: '#f8fafc' }}>
              {title}
            </span>
            <Badge variant="blue" size="sm">
              {scenario}
            </Badge>
          </div>
          <p style={{ fontSize: '0.8125rem', color: '#94a3b8', maxWidth: '640px', lineHeight: 1.5 }}>
            {description}
          </p>
        </div>

        <Button
          variant="primary"
          size="md"
          onClick={onSelect}
          disabled={isDisabled || isRunning}
          isLoading={isRunning}
          icon={
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <polygon points="5 3 19 12 5 21 5 3" />
            </svg>
          }
        >
          Review & Execute
        </Button>
      </div>

      {isDisabled && disabledReason && (
        <div
          style={{
            padding: '0.6rem 0.85rem',
            borderRadius: '8px',
            background: 'rgba(244, 63, 94, 0.1)',
            border: '1px solid rgba(244, 63, 94, 0.3)',
            color: '#fb7185',
            fontSize: '0.75rem',
            marginBottom: '1rem',
          }}
        >
          🔒 {disabledReason}
        </div>
      )}

      {/* Structured Scenario Grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
          gap: '0.85rem',
          fontSize: '0.75rem',
          marginTop: '1rem',
          paddingTop: '1rem',
          borderTop: '1px solid rgba(255, 255, 255, 0.06)',
        }}
      >
        <div style={{ background: 'rgba(0, 0, 0, 0.25)', padding: '0.75rem', borderRadius: '8px' }}>
          <span style={{ color: '#f43f5e', fontWeight: 600, display: 'block', marginBottom: '0.2rem' }}>
            Failure Injection Point
          </span>
          <span style={{ color: '#cbd5e1' }}>{failurePoint}</span>
        </div>

        <div style={{ background: 'rgba(0, 0, 0, 0.25)', padding: '0.75rem', borderRadius: '8px' }}>
          <span style={{ color: '#0df2a6', fontWeight: 600, display: 'block', marginBottom: '0.2rem' }}>
            Expected Invariant
          </span>
          <span style={{ color: '#cbd5e1' }}>{expectedInvariant}</span>
        </div>

        <div style={{ background: 'rgba(0, 0, 0, 0.25)', padding: '0.75rem', borderRadius: '8px' }}>
          <span style={{ color: '#38bdf8', fontWeight: 600, display: 'block', marginBottom: '0.2rem' }}>
            Recovery Expectation
          </span>
          <span style={{ color: '#cbd5e1' }}>{recoveryExpectation}</span>
        </div>
      </div>
    </Card>
  );
}
