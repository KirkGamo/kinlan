import * as SecureStore from 'expo-secure-store';

/** Android and iOS: the session lives in the OS keystore (expo-secure-store). */
const KEY = 'kinlan.session';

export async function readSession(): Promise<string | null> {
  return SecureStore.getItemAsync(KEY);
}

export async function writeSession(value: string | null): Promise<void> {
  if (value === null) await SecureStore.deleteItemAsync(KEY);
  else await SecureStore.setItemAsync(KEY, value);
}
