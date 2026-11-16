import * as SecureStore from 'expo-secure-store';

/** Android and iOS: the Vibration switch is kept with the session in the OS store. */
const KEY = 'kinlan.haptics';

export async function readPref(): Promise<string | null> {
  try {
    return await SecureStore.getItemAsync(KEY);
  } catch {
    return null;
  }
}

export async function writePref(value: string): Promise<void> {
  try {
    await SecureStore.setItemAsync(KEY, value);
  } catch {
    // not saved: the switch lasts until the app restarts
  }
}
