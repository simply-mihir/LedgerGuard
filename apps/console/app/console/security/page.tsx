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
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 pb-6 border-b border-[#1E293B]">
        <div>
          <div className="inline-flex items-center gap-2 font-mono text-[11px] text-[#38BDF8] uppercase tracking-wider mb-2">
            <span className="w-1.5 h-1.5 bg-[#38BDF8]" />
            Operator Access Control
          </div>
          <h1 className="text-3xl md:text-4xl font-serif text-[#F8FAFC] font-normal tracking-tight">
            Identity &amp; Session Security
          </h1>
          <p className="text-xs text-[#94A3B8] max-w-2xl mt-1">
            Server-managed sessions, cryptographic password hashing, and RFC 6238 Time-based One-Time Password (TOTP) two-factor authentication.
          </p>
        </div>
      </div>

      {statusMessage && (
        <div className="p-4 bg-[#064E3B]/30 border-l-2 border-[#10B981] text-xs text-[#A7F3D0] font-mono">
          ✔ {statusMessage}
        </div>
      )}

      {errorMessage && (
        <div className="p-4 bg-[#7F1D1D]/30 border-l-2 border-[#DC2626] text-xs text-[#FCA5A5] font-mono">
          ⚠ {errorMessage}
        </div>
      )}

      {/* Operator Identity Card */}
      <div className="p-6 bg-[#0F172A] border border-[#1E293B] font-mono text-xs">
        <h2 className="text-base font-serif text-white tracking-tight mb-4 pb-2 border-b border-[#1E293B]">
          Current Operator Credentials
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="p-3 bg-[#0B0F17] border border-[#1E293B]">
            <span className="text-[#64748B] text-[10px] uppercase block">Username / ID</span>
            <span className="text-white font-bold text-sm mt-1 block">{operator?.username}</span>
          </div>

          <div className="p-3 bg-[#0B0F17] border border-[#1E293B]">
            <span className="text-[#64748B] text-[10px] uppercase block">Email Address</span>
            <span className="text-white text-sm mt-1 block">{operator?.email}</span>
          </div>

          <div className="p-3 bg-[#0B0F17] border border-[#1E293B]">
            <span className="text-[#64748B] text-[10px] uppercase block">Role Permission</span>
            <span className="text-[#38BDF8] font-bold text-sm mt-1 block">{operator?.role}</span>
          </div>

          <div className="p-3 bg-[#0B0F17] border border-[#1E293B]">
            <span className="text-[#64748B] text-[10px] uppercase block">CSRF Token Protection</span>
            <span className="text-[#10B981] font-bold text-sm mt-1 block">
              {csrfToken ? 'Active (Synchronizer Token)' : 'Disabled'}
            </span>
          </div>
        </div>
      </div>

      {/* Two-Factor Authentication Setup Card */}
      <div className="p-6 bg-[#0F172A] border border-[#1E293B]">
        <div className="flex items-center justify-between pb-4 mb-4 border-b border-[#1E293B]">
          <div>
            <h2 className="text-base font-serif text-white tracking-tight">
              Two-Factor Authentication (TOTP)
            </h2>
            <p className="text-xs text-[#94A3B8]">
              RFC 6238 time-based authenticator (Google Authenticator, 1Password, Aegis)
            </p>
          </div>
          <span
            className={`px-2.5 py-1 text-xs font-mono font-bold ${
              operator?.totp_enabled
                ? 'bg-[#064E3B] text-[#10B981]'
                : 'bg-[#78350F] text-[#F59E0B]'
            }`}
          >
            {operator?.totp_enabled ? 'MFA ACTIVE' : 'MFA NOT CONFIGURED'}
          </span>
        </div>

        {!operator?.totp_enabled && !enrollSecret && (
          <div>
            <p className="text-xs text-[#CBD5E1] mb-4">
              Two-factor authentication adds a critical layer of security to this operator console. When enabled, signing in requires both your password and a 6-digit code from your authenticator app.
            </p>
            <button
              onClick={handleStartEnrollment}
              disabled={isEnrolling}
              className="px-5 py-2.5 bg-[#1D4ED8] hover:bg-[#2563EB] text-white text-xs font-mono uppercase tracking-widest transition-colors cursor-pointer border-0"
            >
              {isEnrolling ? 'Staging Secret...' : 'Enroll Authenticator App'}
            </button>
          </div>
        )}

        {enrollSecret && (
          <div className="p-5 bg-[#0B0F17] border border-[#38BDF8]/40 space-y-4">
            <div>
              <span className="text-[10px] font-mono uppercase text-[#38BDF8] font-bold">
                Step 1: Add Key to Authenticator
              </span>
              <p className="text-xs text-[#CBD5E1] mt-1">
                Enter the following base32 secret into your authenticator application:
              </p>
              <div className="p-3 bg-[#0F172A] border border-[#1E293B] font-mono text-sm tracking-wider text-[#FCD34D] mt-2 select-all">
                {manualKey}
              </div>
              <div className="text-[10px] font-mono text-[#64748B] mt-1 break-all">
                Provisioning URI: {provisioningUri}
              </div>
            </div>

            <form onSubmit={handleConfirmMfa} className="pt-3 border-t border-[#1E293B] space-y-3">
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
                  className="w-36 bg-[#0F172A] border border-[#1E293B] px-3 py-2 text-center font-mono text-lg tracking-widest text-white focus:outline-none focus:border-[#1D4ED8]"
                />
                <button
                  type="submit"
                  disabled={isConfirming || confirmCode.length !== 6}
                  className="px-4 py-2 bg-[#10B981] hover:bg-[#059669] text-white text-xs font-mono uppercase tracking-wider transition-colors disabled:opacity-50 cursor-pointer border-0"
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
