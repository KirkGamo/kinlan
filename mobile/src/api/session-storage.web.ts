/**
 * Web build: expo-secure-store has no web support (SDK 58 docs), so the session uses the
 * browser's localStorage. Access tokens last 15 minutes and refresh tokens rotate on every use
 * (a stolen, reused one signs every session out), which limits what a leaked value is worth.
 */
const KEY = 'kinlan.session';

export async function readSession(): Promise<string | null> {
  try {
    return globalThis.localStorage?.getItem(KEY) ?? null;
  } catch {
    return null; // private mode or blocked storage: behave as signed out
  }
}

export async function writeSession(value: string | null): Promise<void> {
  try {
    if (value === null) globalThis.localStorage?.removeItem(KEY);
    else globalThis.localStorage?.setItem(KEY, value);
  } catch {
    // storage blocked: the session lasts only for this page
  }
}
