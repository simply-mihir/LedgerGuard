'use client';

import React, { useState, useEffect, useCallback } from 'react';
import {
  AccountItem,
  ExperimentResult,
  NavigationTab,
  OverviewData,
  ReconciliationReport,
  StatementEntry,
  TransferItem,
  WorkflowEvent,
} from '../lib/types';
import {
  executeExperiment,
  executeReconciliation,
  getAccounts,
  getAccountStatement,
  getOverview,
  getTransfers,
  getTransferTimeline,
} from '../lib/api';
import { AppShell } from '../components/shell/app-shell';
import { OverviewScreen } from '../components/overview/overview-screen';
import { AccountsScreen } from '../components/accounts/accounts-screen';
import { TransfersScreen } from '../components/transfers/transfers-screen';
import { ReconciliationScreen } from '../components/reconciliation/reconciliation-screen';
import { FailureLabScreen } from '../components/failure-lab/failure-lab-screen';
import { REFRESH_INTERVAL_MS } from '../lib/constants';

export default function OperatorConsole() {
  const [activeTab, setActiveTab] = useState<NavigationTab>('overview');
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [lastRefreshedAt, setLastRefreshedAt] = useState<Date | null>(null);

  // Core Data
  const [overview, setOverview] = useState<OverviewData | null>(null);
  const [accounts, setAccounts] = useState<AccountItem[]>([]);
  const [transfers, setTransfers] = useState<TransferItem[]>([]);

  // Selection & Detail Workspaces
  const [selectedAccount, setSelectedAccount] = useState<AccountItem | null>(null);
  const [statementEntries, setStatementEntries] = useState<StatementEntry[]>([]);
  const [statementNextCursor, setStatementNextCursor] = useState<number | null>(null);
  const [isLoadingStatement, setIsLoadingStatement] = useState<boolean>(false);
  const [isLoadingMoreStatement, setIsLoadingMoreStatement] = useState<boolean>(false);

  const [selectedTransfer, setSelectedTransfer] = useState<TransferItem | null>(null);
  const [transferTimeline, setTransferTimeline] = useState<WorkflowEvent[]>([]);
  const [isLoadingTimeline, setIsLoadingTimeline] = useState<boolean>(false);

  // Audit & Experiment States
  const [reconciliationReport, setReconciliationReport] = useState<ReconciliationReport | null>(null);
  const [isReconciling, setIsReconciling] = useState<boolean>(false);

  const [experimentResult, setExperimentResult] = useState<ExperimentResult | null>(null);
  const [isRunningExperiment, setIsRunningExperiment] = useState<boolean>(false);

  // Errors
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Fetch overview quietly (background poll)
  const pollOverview = useCallback(async () => {
    try {
      const data = await getOverview();
      setOverview(data);
      setLastRefreshedAt(new Date());
    } catch (err: any) {
      console.warn('Background overview poll warning:', err.message);
    }
  }, []);

  // Full Refresh (invoked manually or on initial load)
  const refreshAll = useCallback(async () => {
    setIsRefreshing(true);
    setErrorMsg(null);
    try {
      const [overviewData, accountsData, transfersData] = await Promise.all([
        getOverview().catch(() => null),
        getAccounts().catch(() => []),
        getTransfers(50).catch(() => []),
      ]);

      if (overviewData) setOverview(overviewData);
      setAccounts(accountsData);
      setTransfers(transfersData);
      setLastRefreshedAt(new Date());
    } catch (err: any) {
      setErrorMsg(err.message || 'Error synchronizing platform state.');
    } finally {
      setIsRefreshing(false);
    }
  }, []);

  // Initial mount and 10-second polling interval
  useEffect(() => {
    refreshAll();
    const interval = setInterval(pollOverview, REFRESH_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [refreshAll, pollOverview]);

  // Handle statement inspection with cursor pagination
  const handleOpenStatement = async (account: AccountItem) => {
    setSelectedAccount(account);
    setIsLoadingStatement(true);
    setStatementNextCursor(null);
    try {
      const data = await getAccountStatement(account.account_id, 20);
      setStatementEntries(data.entries);
      setStatementNextCursor(data.next_cursor);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to retrieve account statement.');
      setStatementEntries([]);
      setStatementNextCursor(null);
    } finally {
      setIsLoadingStatement(false);
    }
  };

  const handleLoadMoreStatement = async () => {
    if (!selectedAccount || statementNextCursor === null) return;
    setIsLoadingMoreStatement(true);
    try {
      const data = await getAccountStatement(
        selectedAccount.account_id,
        20,
        statementNextCursor
      );
      setStatementEntries((prev) => [...prev, ...data.entries]);
      setStatementNextCursor(data.next_cursor);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to load additional statement entries.');
    } finally {
      setIsLoadingMoreStatement(false);
    }
  };

  // Handle transfer timeline inspection
  const handleOpenTimeline = async (transfer: TransferItem) => {
    setSelectedTransfer(transfer);
    setIsLoadingTimeline(true);
    try {
      const events = await getTransferTimeline(transfer.transfer_id);
      setTransferTimeline(events);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to retrieve transfer timeline.');
      setTransferTimeline([]);
    } finally {
      setIsLoadingTimeline(false);
    }
  };

  // Trigger live reconciliation audit
  const handleRunReconciliation = async () => {
    setIsReconciling(true);
    setErrorMsg(null);
    try {
      const report = await executeReconciliation();
      setReconciliationReport(report);
      // Refresh overview to update reconciliation badge
      await pollOverview();
    } catch (err: any) {
      setErrorMsg(err.message || 'Reconciliation audit failed.');
    } finally {
      setIsReconciling(false);
    }
  };

  // Run failure injection experiment
  const handleRunExperiment = async (scenario: string) => {
    setIsRunningExperiment(true);
    setErrorMsg(null);
    setExperimentResult(null);
    try {
      const res = await executeExperiment(scenario);
      setExperimentResult(res);
      // Refresh transfers and overview after experiment settlement
      await refreshAll();
    } catch (err: any) {
      setErrorMsg(err.message || 'Experiment execution failed.');
    } finally {
      setIsRunningExperiment(false);
    }
  };

  return (
    <AppShell
      activeTab={activeTab}
      onSelectTab={setActiveTab}
      accountsCount={accounts.length}
      transfersCount={transfers.length}
      overview={overview}
      lastRefreshedAt={lastRefreshedAt}
      isRefreshing={isRefreshing}
      onRefresh={refreshAll}
      errorMsg={errorMsg}
      onClearError={() => setErrorMsg(null)}
    >
      {/* 1. Overview Screen */}
      {activeTab === 'overview' && (
        <OverviewScreen
          overview={overview}
          accounts={accounts}
          transfers={transfers}
          onNavigateTab={setActiveTab}
          onOpenTransferTimeline={handleOpenTimeline}
          onRunReconciliation={handleRunReconciliation}
          isReconciling={isReconciling}
          lastRefreshedAt={lastRefreshedAt}
        />
      )}

      {/* 2. Accounts Screen */}
      {activeTab === 'accounts' && (
        <AccountsScreen
          accounts={accounts}
          onRefresh={refreshAll}
          isRefreshing={isRefreshing}
          selectedAccount={selectedAccount}
          onSelectAccount={(acct) => {
            if (acct) {
              handleOpenStatement(acct);
            } else {
              setSelectedAccount(null);
              setStatementEntries([]);
              setStatementNextCursor(null);
            }
          }}
          statementEntries={statementEntries}
          isLoadingStatement={isLoadingStatement}
          nextCursor={statementNextCursor}
          onLoadMore={handleLoadMoreStatement}
          isLoadingMore={isLoadingMoreStatement}
        />
      )}

      {/* 3. Transfers Screen */}
      {activeTab === 'transfers' && (
        <TransfersScreen
          transfers={transfers}
          onRefresh={refreshAll}
          isRefreshing={isRefreshing}
          selectedTransfer={selectedTransfer}
          onSelectTransfer={(tr) => {
            if (tr) {
              handleOpenTimeline(tr);
            } else {
              setSelectedTransfer(null);
            }
          }}
          timelineEvents={transferTimeline}
          isLoadingTimeline={isLoadingTimeline}
        />
      )}

      {/* 4. Reconciliation Screen */}
      {activeTab === 'reconciliation' && (
        <ReconciliationScreen
          report={reconciliationReport}
          overview={overview}
          onRunAudit={handleRunReconciliation}
          isReconciling={isReconciling}
        />
      )}

      {/* 5. Failure Lab Screen */}
      {activeTab === 'experiments' && (
        <FailureLabScreen
          onRunExperiment={handleRunExperiment}
          isRunning={isRunningExperiment}
          result={experimentResult}
          faultInjectionEnabled={overview?.fault_injection_enabled ?? true}
        />
      )}
    </AppShell>
  );
}
