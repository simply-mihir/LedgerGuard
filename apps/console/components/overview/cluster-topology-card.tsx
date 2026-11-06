import React from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '../ui/card';
import { Badge } from '../ui/badge';
import { StatusDot } from '../ui/status-dot';
import { CLUSTER_NODES } from '../../lib/constants';

interface ClusterTopologyCardProps {
  reachability: Record<string, boolean> | undefined;
}

export function ClusterTopologyCard({ reachability }: ClusterTopologyCardProps) {
  const nodes = CLUSTER_NODES.map((n) => ({
    ...n,
    isReachable: reachability ? Boolean(reachability[n.id]) : true,
  }));

  const totalHealthy = nodes.filter((n) => n.isReachable).length;

  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>Cluster Topology & Isolation</CardTitle>
          <div style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '0.15rem' }}>
            Independent PostgreSQL 17 failure domains
          </div>
        </div>
        <Badge variant={totalHealthy === 3 ? 'mint' : 'rose'} size="sm">
          {totalHealthy}/3 Reachable
        </Badge>
      </CardHeader>

      <CardContent style={{ padding: '1.25rem 1.5rem' }}>
        {/* Connected Node Layout */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
            gap: '1rem',
            position: 'relative',
          }}
        >
          {nodes.map((node) => {
            const isCoord = node.role === 'coordinator';
            return (
              <div
                key={node.id}
                style={{
                  background: 'rgba(255, 255, 255, 0.02)',
                  border: `1px solid ${
                    node.isReachable ? 'rgba(255, 255, 255, 0.08)' : 'rgba(244, 63, 94, 0.35)'
                  }`,
                  borderRadius: '12px',
                  padding: '1rem',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '0.75rem',
                  position: 'relative',
                }}
              >
                {/* Node Header */}
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <StatusDot status={node.isReachable ? 'active' : 'danger'} size={5} pulse={node.isReachable} />
                    <span style={{ fontSize: '0.875rem', fontWeight: 600, color: '#f8fafc' }}>
                      {node.name}
                    </span>
                  </div>
                  <Badge variant={isCoord ? 'blue' : 'neutral'} size="sm">
                    {isCoord ? 'COORDINATOR' : 'PARTICIPANT'}
                  </Badge>
                </div>

                {/* Port & Routing */}
                <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.25rem' }}>
                    <span style={{ color: '#64748b' }}>PostgreSQL Port</span>
                    <span className="font-mono" style={{ color: '#0df2a6', fontWeight: 600 }}>
                      :{node.port}
                    </span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: '#64748b' }}>Network State</span>
                    <span style={{ color: node.isReachable ? '#34d399' : '#fb7185', fontWeight: 500 }}>
                      {node.isReachable ? 'Online & Isolated' : 'Unreachable'}
                    </span>
                  </div>
                </div>

                {/* Role Description */}
                <div
                  style={{
                    fontSize: '0.6875rem',
                    color: '#64748b',
                    paddingTop: '0.5rem',
                    borderTop: '1px solid rgba(255, 255, 255, 0.04)',
                    lineHeight: 1.4,
                  }}
                >
                  {node.description}
                </div>
              </div>
            );
          })}
        </div>

        {/* Protocol Routing Caption */}
        <div
          style={{
            marginTop: '1rem',
            padding: '0.6rem 0.85rem',
            borderRadius: '8px',
            background: 'rgba(255, 255, 255, 0.02)',
            border: '1px solid rgba(255, 255, 255, 0.05)',
            fontSize: '0.6875rem',
            color: '#64748b',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <span>TCC Protocol Transport: Local PostgreSQL Row Locks & Durable Outbox/Inbox</span>
          <span className="font-mono" style={{ color: '#38bdf8' }}>No Distributed XA / Database 2PC Locks</span>
        </div>
      </CardContent>
    </Card>
  );
}
