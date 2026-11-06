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
      <div className="min-h-screen bg-[#F8F9FA] flex items-center justify-center p-6 text-sm text-[#64748B] font-mono">
        Verifying security session...
      </div>
    );
  }

  return (
    <div
      className="min-h-screen flex flex-col justify-between selection:bg-[#1D4ED8] selection:text-white"
      style={{
        background: 'linear-gradient(180deg, #F8F9FA 0%, #EDF2F7 45%, #E2E8F0 100%)',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      {/* Ambient background glow shapes */}
      <div
        style={{
          position: 'absolute',
          top: '-150px',
          right: '-100px',
          width: '600px',
          height: '600px',
          borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(56, 189, 248, 0.15) 0%, rgba(29, 78, 216, 0.05) 50%, transparent 70%)',
          filter: 'blur(70px)',
          pointerEvents: 'none',
        }}
      />
      <div
        style={{
          position: 'absolute',
          bottom: '-150px',
          left: '-100px',
          width: '550px',
          height: '550px',
          borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(16, 185, 129, 0.12) 0%, rgba(56, 189, 248, 0.04) 50%, transparent 70%)',
          filter: 'blur(70px)',
          pointerEvents: 'none',
        }}
      />

      {/* Floating Rounded Header */}
      <header
        style={{
          padding: '1.25rem 2rem',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          position: 'relative',
          zIndex: 10,
        }}
      >
        <Link
          href="/"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.625rem',
            padding: '0.5rem 1rem',
            borderRadius: 'var(--radius-pill, 9999px)',
            background: 'rgba(255, 255, 255, 0.8)',
            backdropFilter: 'blur(16px)',
            WebkitBackdropFilter: 'blur(16px)',
            border: '1px solid rgba(255, 255, 255, 0.8)',
            boxShadow: '0 4px 16px rgba(0, 0, 0, 0.04)',
            textDecoration: 'none',
            color: 'inherit',
          }}
        >
          <span className="w-2.5 h-2.5 rounded-full bg-[#1D4ED8] shadow-[0_0_8px_rgba(29,78,216,0.5)]" />
          <span className="font-mono text-xs uppercase tracking-widest text-[#0F172A] font-bold">
            LedgerGuard
          </span>
          <span className="text-[#94A3B8] text-xs">/</span>
          <span className="text-xs text-[#64748B] font-medium">Operator Authentication</span>
        </Link>

        <Link
          href="/"
          style={{
            fontSize: '0.75rem',
            fontFamily: 'var(--font-mono)',
            color: '#475569',
            textDecoration: 'none',
            padding: '0.5rem 1rem',
            borderRadius: 'var(--radius-pill, 9999px)',
            background: 'rgba(255, 255, 255, 0.6)',
            backdropFilter: 'blur(12px)',
            border: '1px solid rgba(255, 255, 255, 0.7)',
            transition: 'all 0.2s ease',
          }}
        >
          ← Return to Overview
        </Link>
      </header>

      {/* Main asymmetric editorial container */}
      <main className="flex-1 flex items-center justify-center p-6 md:p-12 relative z-10">
        <div className="w-full max-w-4xl grid grid-cols-1 lg:grid-cols-12 gap-10 items-center">
          {/* Left Context Narrative */}
          <div className="lg:col-span-6 flex flex-col gap-6">
            <div className="inline-flex items-center gap-2 text-xs font-mono tracking-wider text-[#1D4ED8] uppercase font-semibold">
              <span className="w-1.5 h-1.5 rounded-full bg-[#1D4ED8] shadow-[0_0_6px_rgba(29,78,216,0.5)]" />
              Controlled Financial Zone
            </div>

            <h1 className="font-serif text-3xl md:text-4xl text-[#0F172A] font-normal tracking-tight leading-tight">
              Operator Console Authentication
            </h1>

            <p className="text-sm text-[#475569] leading-relaxed">
              LedgerGuard operator routes access live distributed transaction coordinators, participant ledger journals, and recovery orchestrators. Access is restricted to authorized operations personnel.
            </p>

            <div className="border-t border-slate-200/80 pt-6 flex flex-col gap-3">
              <div
                style={{
                  padding: '0.875rem 1rem',
                  borderRadius: 'var(--radius-secondary, 20px)',
                  background: 'rgba(255, 255, 255, 0.65)',
                  backdropFilter: 'blur(12px)',
                  border: '1px solid rgba(255, 255, 255, 0.8)',
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: '0.75rem',
                }}
              >
                <span className="font-mono text-xs text-[#1D4ED8] font-bold mt-0.5">01</span>
                <div>
                  <div className="text-xs font-semibold text-[#0F172A]">Argon2id Hash Verification</div>
                  <div className="text-xs text-[#64748B] mt-0.5">RFC 9106 memory-hard password verification with constant-time dummy side-channel defense.</div>
                </div>
              </div>
              <div
                style={{
                  padding: '0.875rem 1rem',
                  borderRadius: 'var(--radius-secondary, 20px)',
                  background: 'rgba(255, 255, 255, 0.65)',
                  backdropFilter: 'blur(12px)',
                  border: '1px solid rgba(255, 255, 255, 0.8)',
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: '0.75rem',
                }}
              >
                <span className="font-mono text-xs text-[#1D4ED8] font-bold mt-0.5">02</span>
                <div>
                  <div className="text-xs font-semibold text-[#0F172A]">Server-Managed Sessions</div>
                  <div className="text-xs text-[#64748B] mt-0.5">PostgreSQL-persisted session tokens in HttpOnly, SameSite cookies with strict CSRF protection.</div>
                </div>
              </div>
              <div
                style={{
                  padding: '0.875rem 1rem',
                  borderRadius: 'var(--radius-secondary, 20px)',
                  background: 'rgba(255, 255, 255, 0.65)',
                  backdropFilter: 'blur(12px)',
                  border: '1px solid rgba(255, 255, 255, 0.8)',
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: '0.75rem',
                }}
              >
                <span className="font-mono text-xs text-[#1D4ED8] font-bold mt-0.5">03</span>
                <div>
                  <div className="text-xs font-semibold text-[#0F172A]">RFC 6238 TOTP Multi-Factor</div>
                  <div className="text-xs text-[#64748B] mt-0.5">Time-based 6-digit authenticator codes with drift tolerance and brute-force lockout.</div>
                </div>
              </div>
            </div>
          </div>

          {/* Right Rounded Glass Form Container */}
          <div className="lg:col-span-6">
            <div
              style={{
                borderRadius: 'var(--radius-primary, 32px)',
                background: 'rgba(255, 255, 255, 0.85)',
                backdropFilter: 'blur(28px)',
                WebkitBackdropFilter: 'blur(28px)',
                border: '1px solid rgba(255, 255, 255, 0.95)',
                boxShadow: '0 25px 50px -12px rgba(15, 23, 42, 0.12), 0 0 0 1px rgba(255, 255, 255, 0.8)',
                padding: '2.5rem',
              }}
            >
              {errorMessage && (
                <div
                  role="alert"
                  aria-live="polite"
                  style={{
                    marginBottom: '1.5rem',
                    padding: '0.875rem 1rem',
                    borderRadius: 'var(--radius-control, 14px)',
                    background: 'rgba(254, 242, 242, 0.9)',
                    border: '1px solid rgba(239, 68, 68, 0.3)',
                    fontSize: '0.75rem',
                    color: '#991B1B',
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: '0.5rem',
                  }}
                >
                  <span className="font-bold text-[#DC2626]">•</span>
                  <span>{errorMessage}</span>
                </div>
              )}

              {!tempToken ? (
                /* Step 1: Credentials Form */
                <form onSubmit={handleCredentialSubmit} className="flex flex-col gap-5">
                  <div>
                    <h2 className="text-lg font-serif text-[#0F172A] tracking-tight font-medium">Operator Sign-In</h2>
                    <p className="text-xs text-[#64748B] mt-1">Enter your operator ID or authorized email address.</p>
                  </div>

                  <div className="flex flex-col gap-1.5">
                    <label htmlFor="operator-identifier" className="text-xs font-mono tracking-wider uppercase text-[#475569] font-medium">
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
                      style={{
                        minHeight: '44px',
                        padding: '8px 14px',
                        borderRadius: 'var(--radius-control, 14px)',
                        background: 'rgba(248, 250, 252, 0.9)',
                        border: '1px solid rgba(203, 213, 225, 0.8)',
                        fontSize: '0.875rem',
                        color: '#0F172A',
                        outline: 'none',
                        transition: 'border-color 0.2s ease, box-shadow 0.2s ease',
                      }}
                      disabled={isSubmitting}
                    />
                  </div>

                  <div className="flex flex-col gap-1.5">
                    <div className="flex items-center justify-between">
                      <label htmlFor="operator-password" className="text-xs font-mono tracking-wider uppercase text-[#475569] font-medium">
                        Password
                      </label>
                      <button
                        type="button"
                        onClick={() => setShowPassword(!showPassword)}
                        style={{
                          fontSize: '0.75rem',
                          color: '#64748B',
                          background: 'transparent',
                          border: 'none',
                          cursor: 'pointer',
                          minHeight: '24px',
                          minWidth: '40px',
                          padding: '4px',
                          fontFamily: 'var(--font-mono)',
                        }}
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
                      style={{
                        minHeight: '44px',
                        padding: '8px 14px',
                        borderRadius: 'var(--radius-control, 14px)',
                        background: 'rgba(248, 250, 252, 0.9)',
                        border: '1px solid rgba(203, 213, 225, 0.8)',
                        fontSize: '0.875rem',
                        color: '#0F172A',
                        outline: 'none',
                        transition: 'border-color 0.2s ease, box-shadow 0.2s ease',
                      }}
                      disabled={isSubmitting}
                    />
                  </div>

                  <button
                    type="submit"
                    disabled={isSubmitting}
                    style={{
                      minHeight: '44px',
                      marginTop: '1rem',
                      padding: '0.75rem 1.25rem',
                      borderRadius: 'var(--radius-control, 14px)',
                      background: 'linear-gradient(135deg, #1D4ED8 0%, #0284C7 100%)',
                      border: '1px solid rgba(56, 189, 248, 0.4)',
                      color: '#FFFFFF',
                      fontSize: '0.75rem',
                      fontFamily: 'var(--font-mono)',
                      fontWeight: 700,
                      textTransform: 'uppercase',
                      letterSpacing: '0.08em',
                      cursor: isSubmitting ? 'not-allowed' : 'pointer',
                      opacity: isSubmitting ? 0.6 : 1,
                      boxShadow: '0 8px 20px -4px rgba(29, 78, 216, 0.4)',
                      transition: 'all 0.2s ease',
                    }}
                  >
                    {isSubmitting ? 'Authenticating...' : 'Authenticate Operator'}
                  </button>

                  <div className="text-[11px] text-[#94A3B8] text-center pt-2 border-t border-slate-100 font-mono">
                    Protected by rate-limited lockout and origin validation.
                  </div>
                </form>
              ) : (
                /* Step 2: MFA Verification Form */
                <form onSubmit={handleMfaSubmit} className="flex flex-col gap-5">
                  <div>
                    <div
                      style={{
                        display: 'inline-block',
                        padding: '0.2rem 0.6rem',
                        borderRadius: 'var(--radius-pill, 9999px)',
                        background: 'rgba(29, 78, 216, 0.1)',
                        border: '1px solid rgba(29, 78, 216, 0.2)',
                        color: '#1D4ED8',
                        fontFamily: 'var(--font-mono)',
                        fontSize: '0.625rem',
                        fontWeight: 700,
                        textTransform: 'uppercase',
                        letterSpacing: '0.05em',
                        marginBottom: '0.5rem',
                      }}
                    >
                      Step 2 of 2
                    </div>
                    <h2 className="text-lg font-serif text-[#0F172A] tracking-tight font-medium">Two-Factor Verification</h2>
                    <p className="text-xs text-[#64748B] mt-1">
                      Enter the 6-digit authentication code from your mobile authenticator app.
                    </p>
                  </div>

                  <div className="flex flex-col gap-1.5">
                    <label htmlFor="mfa-code" className="text-xs font-mono tracking-wider uppercase text-[#475569] font-medium">
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
                      style={{
                        minHeight: '48px',
                        padding: '8px 14px',
                        borderRadius: 'var(--radius-control, 14px)',
                        background: 'rgba(248, 250, 252, 0.9)',
                        border: '1px solid rgba(203, 213, 225, 0.8)',
                        fontFamily: 'var(--font-mono)',
                        fontSize: '1.25rem',
                        textAlign: 'center',
                        letterSpacing: '0.3em',
                        color: '#0F172A',
                        outline: 'none',
                      }}
                      disabled={isSubmitting}
                    />
                  </div>

                  <button
                    type="submit"
                    disabled={isSubmitting || mfaCode.length !== 6}
                    style={{
                      minHeight: '44px',
                      marginTop: '1rem',
                      padding: '0.75rem 1.25rem',
                      borderRadius: 'var(--radius-control, 14px)',
                      background: 'linear-gradient(135deg, #059669 0%, #10B981 100%)',
                      border: '1px solid rgba(52, 211, 153, 0.4)',
                      color: '#FFFFFF',
                      fontSize: '0.75rem',
                      fontFamily: 'var(--font-mono)',
                      fontWeight: 700,
                      textTransform: 'uppercase',
                      letterSpacing: '0.08em',
                      cursor: (isSubmitting || mfaCode.length !== 6) ? 'not-allowed' : 'pointer',
                      opacity: (isSubmitting || mfaCode.length !== 6) ? 0.5 : 1,
                      boxShadow: '0 8px 20px -4px rgba(16, 185, 129, 0.4)',
                      transition: 'all 0.2s ease',
                    }}
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
                    style={{
                      fontSize: '0.75rem',
                      color: '#64748B',
                      textAlign: 'center',
                      background: 'transparent',
                      border: 'none',
                      cursor: 'pointer',
                      minHeight: '24px',
                      padding: '6px 8px',
                      fontFamily: 'var(--font-mono)',
                    }}
                  >
                    ← Re-enter credentials
                  </button>
                </form>
              )}
            </div>
          </div>
        </div>
      </main>

      {/* Minimal Footer */}
      <footer className="border-t border-slate-200/80 px-6 py-4 text-center text-xs text-[#94A3B8] font-mono relative z-10">
        LedgerGuard Distributed Accounting Engine · Coordinator &amp; Dual Ledger Partitioning
      </footer>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-[#F8F9FA] flex items-center justify-center p-6 text-xs text-[#64748B] font-mono">
          Loading operator authentication portal...
        </div>
      }
    >
      <LoginForm />
    </Suspense>
  );
}
