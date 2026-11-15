/**
 * Which Circle and site the tabs show. One small store shared by every tab: switching sites on
 * Overview carries over to Devices and Alerts, and switching Circles (the account sheet) changes
 * them all. In memory only; the first Circle and its first site are the defaults.
 */
import { useSyncExternalStore } from 'react';

import { useCircles, type Circle } from './circles';

let selectedSite: string | null = null;
let selectedCircle: string | null = null;
const listeners = new Set<() => void>();

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}
const emit = () => listeners.forEach((l) => l());

export function selectSite(id: string) {
  selectedSite = id;
  emit();
}

/** Switching Circles also forgets the site, so the new Circle opens on its first site. */
export function selectCircle(id: string) {
  selectedCircle = id;
  selectedSite = null;
  emit();
}

/** The chosen site from `sites`, falling back to the first when none is chosen or it's gone. */
export function useSelectedSite<T extends { id: string }>(sites: T[] | undefined): T | undefined {
  const id = useSyncExternalStore(subscribe, () => selectedSite, () => selectedSite);
  return sites?.find((s) => s.id === id) ?? sites?.[0];
}

/** The Circles query plus the chosen Circle (the first one until you switch). */
export function useCurrentCircle(): { circles: ReturnType<typeof useCircles>; circle: Circle | undefined } {
  const circles = useCircles();
  const id = useSyncExternalStore(subscribe, () => selectedCircle, () => selectedCircle);
  const circle = circles.data?.find((c) => c.id === id) ?? circles.data?.[0];
  return { circles, circle };
}

export function canManage(circle: Circle | undefined): boolean {
  return circle?.role === 'owner' || circle?.role === 'admin';
}
