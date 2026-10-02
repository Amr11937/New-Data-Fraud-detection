/**
 * Front-end-only sign-in. This is a UI gate, NOT security: any non-empty
 * username/password is accepted and the "session" is just a flag in
 * localStorage. The API behind it is not authenticated.
 */
import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { fmsWs } from '@/services/websocket';

const STORAGE_KEY = 'fraudvision:user';

interface AuthState {
  user: string | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

function readStoredUser(): string | null {
  try {
    return localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<string | null>(readStoredUser);

  const login = useCallback(async (username: string, password: string) => {
    // Brief delay so the sign-in feels like a real round trip.
    await new Promise((resolve) => setTimeout(resolve, 900));
    if (!username.trim() || !password) throw new Error('Enter your username and password.');
    try {
      localStorage.setItem(STORAGE_KEY, username.trim());
    } catch {
      // storage unavailable -- session simply won't survive a reload
    }
    setUser(username.trim());
  }, []);

  const logout = useCallback(() => {
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch {
      // ignore
    }
    fmsWs.disconnect();
    setUser(null);
  }, []);

  const value = useMemo(() => ({ user, login, logout }), [user, login, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}

export function RequireAuth({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const location = useLocation();
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  return <>{children}</>;
}
