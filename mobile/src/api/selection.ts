/**
 * Which site the tabs show. One small store shared by Overview, Devices and Alerts, so switching
 * sites on Overview carries over to the other tabs. In memory only: the first site is the default.
 */
import { useSyncExternalStore } from 'react';

let selected: string | null = null;
const listeners = new Set<() => void>();

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function selectSite(id: string) {
  selected = id;
  listeners.forEach((l) => l());
}

/** The chosen site from `sites`, falling back to the first when none is chosen or it's gone. */
export function useSelectedSite<T extends { id: string }>(sites: T[] | undefined): T | undefined {
  const id = useSyncExternalStore(subscribe, () => selected, () => selected);
  return sites?.find((s) => s.id === id) ?? sites?.[0];
}
