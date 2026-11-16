/**
 * The API client: JSON over HTTPS to the KinLAN API (docs/KinLAN_Technical_Plan.md, 4.2-4.3).
 *
 * - Errors arrive as {"error": {"code", "message"}} and become an ApiError whose message is
 *   already written for people.
 * - Access tokens last 15 minutes. On a 401 the client swaps the refresh token for a new pair
 *   once (shared by every request waiting at that moment) and retries; if that fails the
 *   session ends and listeners are told, so the app can return to sign-in.
 */
import { readSession, writeSession } from './session-storage';

export const API_URL = (process.env.EXPO_PUBLIC_API_URL ?? 'https://kinlan-api.onrender.com').replace(/\/$/, '');
const BASE = `${API_URL}/api/v1`;
/** Long enough for the free server to wake up (about 50 s), short enough never to hang. */
const TIMEOUT_MS = 60_000;

export type Session = { accessToken: string; refreshToken: string };

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

// ---------------------------------------------------------------- session

let session: Session | null = null;
let loaded = false;
const listeners = new Set<(signedIn: boolean) => void>();

export async function loadSession(): Promise<Session | null> {
  if (!loaded) {
    const raw = await readSession();
    session = raw ? (JSON.parse(raw) as Session) : null;
    loaded = true;
  }
  return session;
}

export async function setSession(next: Session | null): Promise<void> {
  session = next;
  loaded = true;
  await writeSession(next ? JSON.stringify(next) : null);
  listeners.forEach((listener) => listener(next !== null));
}

export function onSessionChange(listener: (signedIn: boolean) => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

type TokenPair = { access_token: string; refresh_token: string };
export const toSession = (pair: TokenPair): Session => ({
  accessToken: pair.access_token,
  refreshToken: pair.refresh_token,
});

// ---------------------------------------------------------------- requests

type Options = { method?: 'GET' | 'POST' | 'PATCH' | 'DELETE'; body?: unknown; auth?: boolean };

async function send(path: string, { method = 'GET', body, auth = true }: Options): Promise<Response> {
  const headers: Record<string, string> = { Accept: 'application/json' };
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  if (auth && session) headers.Authorization = `Bearer ${session.accessToken}`;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    return await fetch(`${BASE}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: controller.signal,
    });
  } catch {
    if (controller.signal.aborted) {
      throw new ApiError(0, 'timeout', 'KinLAN took too long to answer. Try again in a moment.');
    }
    throw new ApiError(0, 'offline', "Can't reach KinLAN. Check your internet connection.");
  } finally {
    clearTimeout(timer);
  }
}

async function toError(response: Response): Promise<ApiError> {
  try {
    const { error } = (await response.json()) as { error: { code: string; message: string } };
    return new ApiError(response.status, error.code, error.message);
  } catch {
    return new ApiError(response.status, `http_${response.status}`, 'Something went wrong. Try again.');
  }
}

let refreshing: Promise<boolean> | null = null;

/** Swap the refresh token for a new pair; one refresh at a time for all waiting requests. */
function refresh(): Promise<boolean> {
  refreshing ??= (async () => {
    const current = session;
    if (!current) return false;
    const response = await send('/auth/refresh', {
      method: 'POST',
      body: { refresh_token: current.refreshToken },
      auth: false,
    }).catch(() => null);
    if (response?.ok) {
      await setSession(toSession((await response.json()) as TokenPair));
      return true;
    }
    if (response && response.status === 401) await setSession(null); // expired or reused: sign out
    return false;
  })().finally(() => {
    refreshing = null;
  });
  return refreshing;
}

export async function api<T>(path: string, options: Options = {}): Promise<T> {
  await loadSession();
  let response = await send(path, options);
  if (response.status === 401 && options.auth !== false && session && (await refresh())) {
    response = await send(path, options);
  }
  if (!response.ok) throw await toError(response);
  return (response.status === 204 ? undefined : await response.json()) as T;
}
