'use client';

import React, { useState } from 'react';
import { useAuth } from '../../../lib/auth-context';

export default function SecurityPage() {
  const { operator, csrfToken, fetchWithAuth } = useAuth();

  const [enrollSecret, setEnrollSecret] = useState<string | null>(null);
  const [provisioningUri, setProvisioningUri] = useState<string | null>(null);
  const [manualKey, setManualKey] = useState<string | null>(null);
  const [confirmCode, setConfirmCode] = useState('');
  const [isEnrolling, setIsEnrolling] = useState(false);
  const [isConfirming, setIsConfirming] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleStartEnrollment = async () => {
    setIsEnrolling(true);
    setErrorMessage(null);
    setStatusMessage(null);
    try {
      const res = await fetchWithAuth('/api/auth/mfa/enroll', { method: 'POST' });
      if (!res.ok) {
        throw new Error('Failed to initiate TOTP enrollment.');
      }
      const data = await res.json();
      setEnrollSecret(data.totp_secret);
      setProvisioningUri(data.provisioning_uri);
      setManualKey(data.manual_entry_key);
    } catch (err: any) {
      setErrorMessage(err.message || 'Error staging TOTP secret.');
    } finally {
      setIsEnrolling(false);
    }
  };

  const handleConfirmMfa = async (e: React.FormEvent) => {
    e.preventDefault();
    if (confirmCode.trim().length !== 6) {
      setErrorMessage('Please enter a 6-digit confirmation code.');
      return;
    }

    setIsConfirming(true);
    setErrorMessage(null);
    try {
      const res = await fetchWithAuth('/api/auth/mfa/confirm', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code: confirmCode.trim() }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.detail || 'Verification code does not match authenticator secret.');
      }
      setStatusMessage('Two-factor authentication is now active on your operator account.');
      setEnrollSecret(null);
      setProvisioningUri(null);
      setManualKey(null);
      setConfirmCode('');
      if (operator) {
        operator.totp_enabled = true;
      }
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to verify confirmation code.');
    } finally {
      setIsConfirming(false);
    }
  };

  return (
    <div className="flex flex-col gap-6">
      {/* Editorial Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 pb-6 border-b border-white/[0.08]">
        <div>
          <div className="inline-flex items-center gap-2 font-mono text-[11px] text-[#38BDF8] uppercase tracking-wider mb-2">
            <span className="w-1.5 h-1.5 rounded-full bg-[#38BDF8] shadow-[0_0_8px_rgba(56,189,248,0.6)]" />
            Operator Access Control
          </div>
          <h1 className="text-3xl md:text-4xl font-serif text-[#F8FAFC] font-normal tracking-tight">
            Identity &amp; Session Security
          </h1>
          <p className="text-xs text-[#94A3B8] max-w-2xl mt-1 leading-relaxed">
            Server-managed sessions, cryptographic password hashing, and RFC 6238 Time-based One-Time Password (TOTP) two-factor authentication.
          </p>
        </div>
      </div>

      {statusMessage && (
        <div
          style={{
            padding: '1rem 1.25rem',
            borderRadius: 'var(--radius-control, 14px)',
            background: 'rgba(6, 78, 59, 0.3)',
            border: '1px solid rgba(16, 185, 129, 0.4)',
            color: '#A7F3D0',
            fontSize: '0.75rem',
            fontFamily: 'var(--font-mono)',
          }}
        >
          ✔ {statusMessage}
        </div>
      )}

      {errorMessage && (
        <div
          style={{
            padding: '1rem 1.25rem',
            borderRadius: 'var(--radius-control, 14px)',
            background: 'rgba(127, 29, 29, 0.3)',
            border: '1px solid rgba(239, 68, 68, 0.4)',
            color: '#FCA5A5',
            fontSize: '0.75rem',
            fontFamily: 'var(--font-mono)',
          }}
        >
          ⚠ {errorMessage}
        </div>
      )}

      {/* Operator Credentials Surface */}
      <div
        style={{
          borderRadius: 'var(--radius-primary, 28px)',
          background: 'rgba(15, 23, 42, 0.75)',
          backdropFilter: 'blur(24px)',
          WebkitBackdropFilter: 'blur(24px)',
          border: '1px solid rgba(255, 255, 255, 0.08)',
          boxShadow: '0 20px 40px -15px rgba(0, 0, 0, 0.5)',
          padding: '1.75rem',
          fontFamily: 'var(--font-mono)',
          fontSize: '0.75rem',
        }}
      >
        <h2 className="text-base font-serif text-white tracking-tight mb-4 pb-2 border-b border-white/[0.08]">
          Current Operator Credentials
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div
            style={{
              padding: '1rem',
              borderRadius: 'var(--radius-control, 14px)',
              background: 'rgba(11, 15, 23, 0.7)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
            }}
          >
            <span className="text-[#94A3B8] text-[10px] uppercase block font-medium">Username / ID</span>
            <span className="text-white font-bold text-sm mt-1 block">{operator?.username}</span>
          </div>

          <div
            style={{
              padding: '1rem',
              borderRadius: 'var(--radius-control, 14px)',
              background: 'rgba(11, 15, 23, 0.7)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
            }}
          >
            <span className="text-[#94A3B8] text-[10px] uppercase block font-medium">Email Address</span>
            <span className="text-white text-sm mt-1 block">{operator?.email}</span>
          </div>

          <div
            style={{
              padding: '1rem',
              borderRadius: 'var(--radius-control, 14px)',
              background: 'rgba(11, 15, 23, 0.7)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
            }}
          >
            <span className="text-[#94A3B8] text-[10px] uppercase block font-medium">Role Permission</span>
            <span className="text-[#38BDF8] font-bold text-sm mt-1 block">{operator?.role}</span>
          </div>

          <div
            style={{
              padding: '1rem',
              borderRadius: 'var(--radius-control, 14px)',
              background: 'rgba(11, 15, 23, 0.7)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
            }}
          >
            <span className="text-[#94A3B8] text-[10px] uppercase block font-medium">CSRF Token Protection</span>
            <span className="text-[#34D399] font-bold text-sm mt-1 block">
              {csrfToken ? 'Active (Synchronizer Token)' : 'Disabled'}
            </span>
          </div>
        </div>
      </div>

      {/* Two-Factor Authentication Setup Card */}
      <div
        style={{
          borderRadius: 'var(--radius-primary, 28px)',
          background: 'rgba(15, 23, 42, 0.75)',
          backdropFilter: 'blur(24px)',
          WebkitBackdropFilter: 'blur(24px)',
          border: '1px solid rgba(255, 255, 255, 0.08)',
          boxShadow: '0 20px 40px -15px rgba(0, 0, 0, 0.5)',
          padding: '1.75rem',
        }}
      >
        <div className="flex items-center justify-between pb-4 mb-4 border-b border-white/[0.08]">
          <div>
            <h2 className="text-base font-serif text-white tracking-tight">
              Two-Factor Authentication (TOTP)
            </h2>
            <p className="text-xs text-[#94A3B8] mt-0.5">
              RFC 6238 time-based authenticator (Google Authenticator, 1Password, Aegis)
            </p>
          </div>
          <span
            style={{
              padding: '0.25rem 0.65rem',
              borderRadius: 'var(--radius-pill, 9999px)',
              fontSize: '0.75rem',
              fontFamily: 'var(--font-mono)',
              fontWeight: 700,
              backgroundColor: operator?.totp_enabled ? 'rgba(5, 150, 105, 0.2)' : 'rgba(245, 158, 11, 0.2)',
              color: operator?.totp_enabled ? '#34D399' : '#F59E0B',
              border: operator?.totp_enabled ? '1px solid rgba(52, 211, 153, 0.3)' : '1px solid rgba(245, 158, 11, 0.3)',
            }}
          >
            {operator?.totp_enabled ? 'MFA ACTIVE' : 'MFA NOT CONFIGURED'}
          </span>
        </div>

        {!operator?.totp_enabled && !enrollSecret && (
          <div>
            <p className="text-xs text-[#CBD5E1] mb-4 leading-relaxed">
              Two-factor authentication adds a critical layer of security to this operator console. When enabled, signing in requires both your password and a 6-digit code from your authenticator app.
            </p>
            <button
              onClick={handleStartEnrollment}
              disabled={isEnrolling}
              style={{
                padding: '0.75rem 1.5rem',
                borderRadius: 'var(--radius-control, 14px)',
                background: 'linear-gradient(135deg, #1D4ED8 0%, #0284C7 100%)',
                border: '1px solid rgba(56, 189, 248, 0.4)',
                color: '#FFFFFF',
                fontFamily: 'var(--font-mono)',
                fontSize: '0.75rem',
                fontWeight: 700,
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
                cursor: isEnrolling ? 'not-allowed' : 'pointer',
                opacity: isEnrolling ? 0.6 : 1,
                boxShadow: '0 8px 24px -4px rgba(29, 78, 216, 0.5)',
                transition: 'all 0.2s ease',
              }}
            >
              {isEnrolling ? 'Staging Secret...' : 'Enroll Authenticator App'}
            </button>
          </div>
        )}

        {enrollSecret && (
          <div
            style={{
              padding: '1.25rem',
              borderRadius: 'var(--radius-secondary, 20px)',
              background: 'rgba(11, 15, 23, 0.8)',
              border: '1px solid rgba(56, 189, 248, 0.3)',
              display: 'flex',
              flexDirection: 'column',
              gap: '1rem',
            }}
          >
            <div>
              <span className="text-[10px] font-mono uppercase text-[#38BDF8] font-bold block">
                Step 1: Add Key to Authenticator
              </span>
              <p className="text-xs text-[#CBD5E1] mt-1">
                Enter the following base32 secret into your authenticator application:
              </p>
              <div
                style={{
                  padding: '0.875rem 1rem',
                  borderRadius: 'var(--radius-control, 14px)',
                  background: 'rgba(15, 23, 42, 0.85)',
                  border: '1px solid rgba(255, 255, 255, 0.1)',
                  fontFamily: 'var(--font-mono)',
                  fontSize: '0.875rem',
                  letterSpacing: '0.1em',
                  color: '#FCD34D',
                  marginTop: '0.5rem',
                  userSelect: 'all',
                }}
              >
                {manualKey}
              </div>
              <div className="text-[10px] font-mono text-[#94A3B8] mt-1 break-all">
                Provisioning URI: {provisioningUri}
              </div>
            </div>

            <form onSubmit={handleConfirmMfa} className="pt-3 border-t border-white/[0.08] space-y-3">
              <span className="text-[10px] font-mono uppercase text-[#38BDF8] font-bold block">
                Step 2: Confirm 6-Digit Code
              </span>
              <div className="flex items-center gap-3">
                <input
                  type="text"
                  maxLength={6}
                  placeholder="123456"
                  value={confirmCode}
                  onChange={(e) => setConfirmCode(e.target.value.replace(/[^0-9]/g, ''))}
                  style={{
                    width: '140px',
                    padding: '0.625rem 1rem',
                    borderRadius: 'var(--radius-control, 14px)',
                    background: 'rgba(15, 23, 42, 0.85)',
                    border: '1px solid rgba(255, 255, 255, 0.15)',
                    fontFamily: 'var(--font-mono)',
                    fontSize: '1.125rem',
                    textAlign: 'center',
                    letterSpacing: '0.2em',
                    color: '#FFFFFF',
                    outline: 'none',
                  }}
                />
                <button
                  type="submit"
                  disabled={isConfirming || confirmCode.length !== 6}
                  style={{
                    padding: '0.625rem 1.25rem',
                    borderRadius: 'var(--radius-control, 14px)',
                    background: 'linear-gradient(135deg, #059669 0%, #10B981 100%)',
                    border: '1px solid rgba(52, 211, 153, 0.4)',
                    color: '#FFFFFF',
                    fontFamily: 'var(--font-mono)',
                    fontSize: '0.75rem',
                    fontWeight: 700,
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em',
                    cursor: (isConfirming || confirmCode.length !== 6) ? 'not-allowed' : 'pointer',
                    opacity: (isConfirming || confirmCode.length !== 6) ? 0.5 : 1,
                    transition: 'all 0.2s ease',
                  }}
                >
                  {isConfirming ? 'Verifying...' : 'Activate MFA'}
                </button>
              </div>
            </form>
          </div>
        )}

        {operator?.totp_enabled && (
          <p className="text-xs text-[#94A3B8] font-mono">
            ✔ Your account is protected by hardware/software TOTP authentication. Sign-in requests require secondary confirmation.
          </p>
        )}
      </div>
    </div>
  );
}
