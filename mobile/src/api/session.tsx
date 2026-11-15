/**
 * Who is signed in, for the whole app. Sign-in and sign-up store the token pair (keystore on
 * Android, localStorage on web); sign-out revokes the refresh token on the server, forgets the
 * pair and clears every cached query so the next person sees nothing of the last one.
 */
import { useQuery } from '@tanstack/react-query';
import { createContext, use, useEffect, useState, type ReactNode } from 'react';

import { api, loadSession, onSessionChange, setSession, toSession } from './client';
import { unregisterPush } from './push';
import { queryClient } from './query-client';

type Status = 'loading' | 'signedIn' | 'signedOut';
type TokenPair = { access_token: string; refresh_token: string };

type SessionApi = {
  status: Status;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (displayName: string, email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
};

const SessionContext = createContext<SessionApi | null>(null);

async function signIn(email: string, password: string) {
  const pair = await api<TokenPair>('/auth/login', {
    method: 'POST',
    body: { email: email.trim(), password },
    auth: false,
  });
  await setSession(toSession(pair));
}

async function signUp(displayName: string, email: string, password: string) {
  const pair = await api<TokenPair>('/auth/register', {
    method: 'POST',
    body: { display_name: displayName.trim(), email: email.trim(), password },
    auth: false,
  });
  await setSession(toSession(pair));
}

async function signOut() {
  const current = await loadSession();
  if (current) {
    await unregisterPush(); // while still signed in, so the API knows whose token it is
    // Best effort: even offline, the device forgets the session.
    await api('/auth/logout', {
      method: 'POST',
      body: { refresh_token: current.refreshToken },
      auth: false,
    }).catch(() => undefined);
  }
  await setSession(null);
  queryClient.clear();
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<Status>('loading');

  useEffect(() => {
    let alive = true;
    loadSession()
      .then((session) => alive && setStatus(session ? 'signedIn' : 'signedOut'))
      .catch(() => alive && setStatus('signedOut'));
    const stop = onSessionChange((signedIn) => {
      setStatus(signedIn ? 'signedIn' : 'signedOut');
      if (!signedIn) queryClient.clear(); // also when a refresh fails and ends the session
    });
    return () => {
      alive = false;
      stop();
    };
  }, []);

  return (
    <SessionContext value={{ status, signIn, signUp, signOut }}>{children}</SessionContext>
  );
}

export function useSession(): SessionApi {
  const value = use(SessionContext);
  if (!value) throw new Error('useSession must be used inside <SessionProvider>');
  return value;
}

export type Me = { id: string; email: string; display_name: string; created_at: string };

/** The signed-in account (GET /me). */
export function useMe() {
  return useQuery({ queryKey: ['me'], queryFn: () => api<Me>('/me') });
}
