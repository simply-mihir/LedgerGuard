'use client';

import React, { useState, useEffect, Suspense } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useAuth } from '../../lib/auth-context';

function getSafeReturnUrl(param: string | null): string {
  if (!param) return '/console';
  // Reject unsafe protocol-relative or backslash-prefixed targets
  if (param.startsWith('/') && !param.startsWith('//') && !param.startsWith('/\\')) {
    // Also ensure no embedded colon-slashes before query
    const pathOnly = param.split('?')[0];
    if (!pathOnly.includes(':')) {
      return param;
    }
  }
  return '/console';
}

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { isAuthenticated, isLoading: authLoading, login, verifyMfa } = useAuth();

  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [mfaCode, setMfaCode] = useState('');
  const [tempToken, setTempToken] = useState<string | null>(null);

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const returnUrl = getSafeReturnUrl(searchParams.get('returnUrl'));

  useEffect(() => {
    if (!authLoading && isAuthenticated) {
      router.replace(returnUrl);
    }
  }, [isAuthenticated, authLoading, router, returnUrl]);

  const handleCredentialSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!identifier.trim() || !password) {
      setErrorMessage('Please enter both operator ID and password.');
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      const resp = await login(identifier, password);
      if (resp.status === 'MFA_REQUIRED' && resp.temp_token) {
        setTempToken(resp.temp_token);
      } else {
        router.push(returnUrl);
      }
    } catch (err: any) {
      setErrorMessage(err.message || 'Authentication failed. Please verify credentials.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleMfaSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!tempToken || mfaCode.trim().length !== 6) {
      setErrorMessage('Please enter the 6-digit verification code.');
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      await verifyMfa(tempToken, mfaCode.trim());
      router.push(returnUrl);
    } catch (err: any) {
      setErrorMessage(err.message || 'Invalid verification code.');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (authLoading) {
    return (
      <div className="min-h-screen bg-[#F9F8F6] flex items-center justify-center p-6 text-sm text-[#737373]">
        Verifying security session...
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#F9F8F6] flex flex-col justify-between selection:bg-[#1D4ED8] selection:text-white">
      {/* Top micro-bar */}
      <header className="border-b border-[#E5E2DA] bg-[#F9F8F6]/80 px-6 py-4 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-2 group text-inherit no-underline">
          <span className="w-2.5 h-2.5 bg-[#171717] rounded-none group-hover:bg-[#1D4ED8] transition-colors" />
          <span className="font-mono text-xs uppercase tracking-widest text-[#171717] font-semibold">
            LedgerGuard
          </span>
          <span className="text-[#A3A3A3] text-xs">/</span>
          <span className="text-xs text-[#737373] tracking-wide">Operator Authentication</span>
        </Link>
        <Link
          href="/"
          className="text-xs text-[#737373] hover:text-[#171717] transition-colors no-underline"
        >
          &larr; Return to Overview
        </Link>
      </header>

      {/* Main asymmetric editorial container */}
      <main className="flex-1 flex items-center justify-center p-6 md:p-12">
        <div className="w-full max-w-4xl grid grid-cols-1 lg:grid-cols-12 gap-10 items-center">
          {/* Left Context Narrative */}
          <div className="lg:col-span-6 flex flex-col gap-6">
            <div className="inline-flex items-center gap-2 text-xs font-mono tracking-wider text-[#1D4ED8] uppercase font-semibold">
              <span className="w-1.5 h-1.5 bg-[#1D4ED8]" />
              Controlled Financial Zone
            </div>

            <h1 className="font-serif text-3xl md:text-4xl text-[#171717] font-normal tracking-tight leading-tight">
              Operator Console Authentication
            </h1>

            <p className="text-sm text-[#525252] leading-relaxed">
              LedgerGuard operator routes access live distributed transaction coordinators, participant ledger journals, and recovery orchestrators. Access is restricted to authorized operations personnel.
            </p>

            <div className="border-t border-[#E5E2DA] pt-6 flex flex-col gap-3">
              <div className="flex items-start gap-3">
                <span className="font-mono text-xs text-[#1D4ED8] font-bold mt-0.5">01</span>
                <div>
                  <div className="text-xs font-medium text-[#171717]">Argon2id Hash Verification</div>
                  <div className="text-xs text-[#737373]">RFC 9106 memory-hard password verification with constant-time dummy side-channel defense.</div>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <span className="font-mono text-xs text-[#1D4ED8] font-bold mt-0.5">02</span>
                <div>
                  <div className="text-xs font-medium text-[#171717]">Server-Managed Sessions</div>
                  <div className="text-xs text-[#737373]">PostgreSQL-persisted session tokens in HttpOnly, SameSite cookies with strict CSRF protection.</div>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <span className="font-mono text-xs text-[#1D4ED8] font-bold mt-0.5">03</span>
                <div>
                  <div className="text-xs font-medium text-[#171717]">RFC 6238 TOTP Multi-Factor</div>
                  <div className="text-xs text-[#737373]">Time-based 6-digit authenticator codes with drift tolerance and brute-force lockout.</div>
                </div>
              </div>
            </div>
          </div>

          {/* Right Form Container */}
          <div className="lg:col-span-6">
            <div className="bg-white border border-[#E5E2DA] p-8 md:p-10 shadow-[0_4px_24px_rgba(0,0,0,0.02)]">
              {errorMessage && (
                <div
                  role="alert"
                  aria-live="polite"
                  className="mb-6 p-4 bg-[#FEF2F2] border-l-2 border-[#DC2626] text-xs text-[#991B1B] flex items-start gap-2"
                >
                  <span className="font-bold text-[#DC2626]">&bull;</span>
                  <span>{errorMessage}</span>
                </div>
              )}

              {!tempToken ? (
                /* Step 1: Credentials Form */
                <form onSubmit={handleCredentialSubmit} className="flex flex-col gap-5">
                  <div>
                    <h2 className="text-lg font-medium text-[#171717] tracking-tight">Operator Sign-In</h2>
                    <p className="text-xs text-[#737373] mt-1">Enter your operator ID or authorized email address.</p>
                  </div>

                  <div className="flex flex-col gap-1.5">
                    <label htmlFor="operator-identifier" className="text-xs font-mono tracking-wider uppercase text-[#525252]">
                      Operator Identifier
                    </label>
                    <input
                      id="operator-identifier"
                      name="identifier"
                      type="text"
                      autoComplete="username"
                      required
                      value={identifier}
                      onChange={(e) => setIdentifier(e.target.value)}
                      placeholder="operator or user@ledgerguard.internal"
                      className="w-full bg-[#FAF9F5] border border-[#E5E2DA] px-3.5 py-2.5 text-sm text-[#171717] placeholder:text-[#A3A3A3] focus:outline-none focus:border-[#1D4ED8] focus:ring-1 focus:ring-[#1D4ED8] transition-colors"
                      disabled={isSubmitting}
                    />
                  </div>

                  <div className="flex flex-col gap-1.5">
                    <div className="flex items-center justify-between">
                      <label htmlFor="operator-password" className="text-xs font-mono tracking-wider uppercase text-[#525252]">
                        Password
                      </label>
                      <button
                        type="button"
                        onClick={() => setShowPassword(!showPassword)}
                        className="text-xs text-[#737373] hover:text-[#171717] bg-transparent border-0 cursor-pointer"
                        aria-label={showPassword ? 'Hide password' : 'Show password'}
                      >
                        {showPassword ? 'Hide' : 'Show'}
                      </button>
                    </div>
                    <input
                      id="operator-password"
                      name="password"
                      type={showPassword ? 'text' : 'password'}
                      autoComplete="current-password"
                      required
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="••••••••••••"
                      className="w-full bg-[#FAF9F5] border border-[#E5E2DA] px-3.5 py-2.5 text-sm text-[#171717] placeholder:text-[#A3A3A3] focus:outline-none focus:border-[#1D4ED8] focus:ring-1 focus:ring-[#1D4ED8] transition-colors"
                      disabled={isSubmitting}
                    />
                  </div>

                  <button
                    type="submit"
                    disabled={isSubmitting}
                    className="w-full mt-2 bg-[#171717] hover:bg-[#1D4ED8] text-white text-xs font-mono uppercase tracking-widest py-3 px-4 transition-colors disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer border-0"
                  >
                    {isSubmitting ? 'Authenticating...' : 'Authenticate Operator'}
                  </button>

                  <div className="text-[11px] text-[#A3A3A3] text-center pt-2 border-t border-[#F5F4F0]">
                    Protected by rate-limited lockout and origin validation.
                  </div>
                </form>
              ) : (
                /* Step 2: MFA Verification Form */
                <form onSubmit={handleMfaSubmit} className="flex flex-col gap-5">
                  <div>
                    <div className="inline-block text-[10px] font-mono uppercase tracking-wider text-[#1D4ED8] bg-[#EFF6FF] px-2 py-0.5 mb-2">
                      Step 2 of 2
                    </div>
                    <h2 className="text-lg font-medium text-[#171717] tracking-tight">Two-Factor Verification</h2>
                    <p className="text-xs text-[#737373] mt-1">
                      Enter the 6-digit authentication code from your mobile authenticator app.
                    </p>
                  </div>

                  <div className="flex flex-col gap-1.5">
                    <label htmlFor="mfa-code" className="text-xs font-mono tracking-wider uppercase text-[#525252]">
                      Verification Code (TOTP)
                    </label>
                    <input
                      id="mfa-code"
                      name="code"
                      type="text"
                      inputMode="numeric"
                      pattern="[0-9]*"
                      maxLength={6}
                      autoComplete="one-time-code"
                      required
                      autoFocus
                      value={mfaCode}
                      onChange={(e) => setMfaCode(e.target.value.replace(/[^0-9]/g, ''))}
                      placeholder="123456"
                      className="w-full bg-[#FAF9F5] border border-[#E5E2DA] px-3.5 py-3 text-center font-mono text-xl tracking-[0.3em] text-[#171717] placeholder:text-[#A3A3A3] focus:outline-none focus:border-[#1D4ED8] focus:ring-1 focus:ring-[#1D4ED8] transition-colors"
                      disabled={isSubmitting}
                    />
                  </div>

                  <button
                    type="submit"
                    disabled={isSubmitting || mfaCode.length !== 6}
                    className="w-full bg-[#1D4ED8] hover:bg-[#1E40AF] text-white text-xs font-mono uppercase tracking-widest py-3 px-4 transition-colors disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer border-0"
                  >
                    {isSubmitting ? 'Verifying Code...' : 'Verify & Enter Console'}
                  </button>

                  <button
                    type="button"
                    onClick={() => {
                      setTempToken(null);
                      setMfaCode('');
                      setErrorMessage(null);
                    }}
                    className="text-xs text-[#737373] hover:text-[#171717] text-center bg-transparent border-0 cursor-pointer py-1"
                  >
                    &larr; Re-enter credentials
                  </button>
                </form>
              )}
            </div>
          </div>
        </div>
      </main>

      {/* Minimal Footer */}
      <footer className="border-t border-[#E5E2DA] px-6 py-4 text-center text-xs text-[#A3A3A3] font-mono">
        LedgerGuard Distributed Accounting Engine · Coordinator &amp; Dual Ledger Partitioning
      </footer>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-[#F9F8F6] flex items-center justify-center p-6 text-xs text-[#737373]">
          Loading operator authentication portal...
        </div>
      }
    >
      <LoginForm />
    </Suspense>
  );
}
