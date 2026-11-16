/** Web: haptics do nothing, but the switch still remembers its position. */
const KEY = 'kinlan.haptics';

export async function readPref(): Promise<string | null> {
  try {
    return globalThis.localStorage?.getItem(KEY) ?? null;
  } catch {
    return null;
  }
}

export async function writePref(value: string): Promise<void> {
  try {
    globalThis.localStorage?.setItem(KEY, value);
  } catch {
    // storage blocked
  }
}
