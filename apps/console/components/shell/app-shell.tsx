import React, { useState } from 'react';
import { NavigationTab, OverviewData } from '../../lib/types';
import { NavigationRail } from './navigation-rail';
import { TopBar } from './top-bar';
import { MobileNav } from './mobile-nav';

interface AppShellProps {
  activeTab: NavigationTab;
  onSelectTab: (tab: NavigationTab) => void;
  accountsCount: number;
  transfersCount: number;
  overview: OverviewData | null;
  lastRefreshedAt: Date | null;
  isRefreshing: boolean;
  onRefresh: () => void;
  errorMsg: string | null;
  onClearError: () => void;
  screenActions?: React.ReactNode;
  children: React.ReactNode;
}

export function AppShell({
  activeTab,
  onSelectTab,
  accountsCount,
  transfersCount,
  overview,
  lastRefreshedAt,
  isRefreshing,
  onRefresh,
  errorMsg,
  onClearError,
  screenActions,
  children,
}: AppShellProps) {
  const [isRailCollapsed, setIsRailCollapsed] = useState(false);

  return (
    <div
      style={{
        display: 'flex',
        minHeight: '100vh',
        backgroundColor: '#090a0c',
        color: '#f8fafc',
      }}
    >
      {/* Desktop Navigation Rail */}
      <NavigationRail
        activeTab={activeTab}
        onSelectTab={onSelectTab}
        accountsCount={accountsCount}
        transfersCount={transfersCount}
        overview={overview}
        isCollapsed={isRailCollapsed}
        onToggleCollapse={() => setIsRailCollapsed(!isRailCollapsed)}
      />

      {/* Main Right Content Area */}
      <div
        style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          minWidth: 0,
        }}
      >
        {/* Mobile Sticky Navigation Header */}
        <MobileNav
          activeTab={activeTab}
          onSelectTab={onSelectTab}
          accountsCount={accountsCount}
          transfersCount={transfersCount}
          overview={overview}
        />

        {/* Desktop Contextual Top Bar */}
        <TopBar
          activeTab={activeTab}
          lastRefreshedAt={lastRefreshedAt}
          isRefreshing={isRefreshing}
          onRefresh={onRefresh}
          screenActions={screenActions}
        />

        {/* Workspace Canvas */}
        <main
          style={{
            flex: 1,
            padding: '1.75rem 2rem',
            width: '100%',
            maxWidth: '1520px',
            margin: '0 auto',
          }}
        >
          {/* Dismissible Error Banner */}
          {errorMsg && (
            <div
              role="alert"
              style={{
                marginBottom: '1.5rem',
                padding: '0.875rem 1.25rem',
                borderRadius: '12px',
                background: 'rgba(244, 63, 94, 0.12)',
                border: '1px solid rgba(244, 63, 94, 0.3)',
                color: '#fb7185',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                fontSize: '0.875rem',
                animation: 'fade-in 0.2s ease',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                <span style={{ fontSize: '1rem' }}>⚠</span>
                <span>{errorMsg}</span>
              </div>
              <button
                onClick={onClearError}
                aria-label="Dismiss error"
                style={{
                  background: 'none',
                  border: 'none',
                  color: '#fb7185',
                  cursor: 'pointer',
                  fontSize: '1rem',
                  padding: '0.2rem',
                }}
              >
                ✕
              </button>
            </div>
          )}

          {/* Active Screen View */}
          {children}
        </main>
      </div>
    </div>
  );
}
