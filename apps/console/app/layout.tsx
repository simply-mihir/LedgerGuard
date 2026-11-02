import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'LedgerGuard — Operator Console',
  description: 'Auditable dual-ledger financial engine with application-level TCC coordination and cross-database reconciliation.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
