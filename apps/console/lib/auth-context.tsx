'use client';

import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { OperatorPublicInfo, LoginResponse, SessionResponse } from './types';

interface AuthContextValue {
  isAuthenticated: boolean;
  isLoading: boolean;
  operator: OperatorPublicInfo | null;
  csrfToken: string | null;
  login: (identifier: string, password: string) => Promise<LoginResponse>;
  verifyMfa: (tempToken: string, code: string) => Promise<LoginResponse>;
  logout: () => Promise<void>;
  checkSession: () => Promise<void>;
  fetchWithAuth: (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [operator, setOperator] = useState<OperatorPublicInfo | null>(null);
  const [csrfToken, setCsrfToken] = useState<string | null>(null);
  const router = useRouter();

  const checkSession = useCallback(async () => {
    try {
      const res = await fetch('/api/auth/session', { cache: 'no-store' });
      if (res.ok) {
        const data: SessionResponse = await res.json();
        if (data.authenticated && data.operator) {
          setIsAuthenticated(true);
          setOperator(data.operator);
          setCsrfToken(data.csrf_token || null);
          return;
        }
      }
      setIsAuthenticated(false);
      setOperator(null);
      setCsrfToken(null);
    } catch {
      setIsAuthenticated(false);
      setOperator(null);
      setCsrfToken(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    checkSession();
  }, [checkSession]);

  const login = async (identifier: string, password: string): Promise<LoginResponse> => {
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ identifier, password }),
    });

    const data: LoginResponse = await res.json();
    if (!res.ok) {
      const err = (data as any)?.detail || data.message || 'Authentication failed';
      throw new Error(err);
    }

    if (data.status === 'SUCCESS' && data.operator) {
      setIsAuthenticated(true);
      setOperator(data.operator);
      setCsrfToken(data.csrf_token || null);
    }

    return data;
  };

  const verifyMfa = async (tempToken: string, code: string): Promise<LoginResponse> => {
    const res = await fetch('/api/auth/mfa/verify', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ temp_token: tempToken, code }),
    });

    const data: LoginResponse = await res.json();
    if (!res.ok) {
      const err = (data as any)?.detail || data.message || 'Verification failed';
      throw new Error(err);
    }

    if (data.status === 'SUCCESS' && data.operator) {
      setIsAuthenticated(true);
      setOperator(data.operator);
      setCsrfToken(data.csrf_token || null);
    }

    return data;
  };

  const logout = async (): Promise<void> => {
    try {
      const headers: Record<string, string> = {};
      if (csrfToken) {
        headers['X-CSRF-Token'] = csrfToken;
      }
      await fetch('/api/auth/logout', { method: 'POST', headers });
    } catch {
      // Ignore network errors on logout
    }
    setIsAuthenticated(false);
    setOperator(null);
    setCsrfToken(null);
    router.push('/login');
  };

  const fetchWithAuth = async (input: RequestInfo | URL, init: RequestInit = {}): Promise<Response> => {
    const headers = new Headers(init.headers || {});
    if (csrfToken && ['POST', 'PUT', 'PATCH', 'DELETE'].includes(init.method?.toUpperCase() || '')) {
      headers.set('X-CSRF-Token', csrfToken);
    }
    return fetch(input, { ...init, headers });
  };

  return (
    <AuthContext.Provider
      value={{
        isAuthenticated,
        isLoading,
        operator,
        csrfToken,
        login,
        verifyMfa,
        logout,
        checkSession,
        fetchWithAuth,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return ctx;
}
