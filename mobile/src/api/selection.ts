/**
 * Which Circle and site the tabs show. One small store shared by every tab: switching sites on
 * Overview carries over to Devices and Alerts, and switching Circles (the account sheet) changes
 * them all. In memory only; the first Circle and its first site are the defaults.
 */
import { useSyncExternalStore } from 'react';

import type { QueryClient } from '@tanstack/react-query';

import { fetchSites, fetchSummary, useCircles, useSites, type Circle, type Site } from './circles';
import { keys } from './keys';

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

/**
 * What every tab needs before it can draw: the chosen Circle and its sites. A failed refresh
 * keeps showing the data already loaded; only a first load that fails is an error, and its retry
 * re-runs the request that failed (the Circles list, or that Circle's sites).
 */
export type TabData =
  | { state: 'loading' }
  | { state: 'error'; message: string; retry: () => void }
  | { state: 'ready'; circle: Circle; sites: Site[]; site: Site | undefined; canManage: boolean };

export function useTabData(): TabData {
  const { circles, circle } = useCurrentCircle();
  const sites = useSites(circle?.id);
  const site = useSelectedSite(sites.data);
  if (!circles.data) {
    return circles.isError
      ? { state: 'error', message: circles.error.message, retry: () => void circles.refetch() }
      : { state: 'loading' };
  }
  if (!circle) return { state: 'loading' }; // no Circle yet: the root layout opens onboarding
  if (!sites.data) {
    return sites.isError
      ? { state: 'error', message: sites.error.message, retry: () => void sites.refetch() }
      : { state: 'loading' };
  }
  return { state: 'ready', circle, sites: sites.data, site, canManage: canManage(circle) };
}

/**
 * Load what the first screen draws (the chosen Circle's sites, then its site's summary) while the
 * cold-start splash plays, so the splash fades into a finished Overview instead of a loader.
 */
export async function prefetchFirstScreen(client: QueryClient, circles: Circle[]): Promise<void> {
  const circle = circles.find((c) => c.id === selectedCircle) ?? circles[0];
  if (!circle) return;
  const sites = await client.fetchQuery({ queryKey: keys.sites(circle.id), queryFn: () => fetchSites(circle.id) });
  const site = sites.find((s) => s.id === selectedSite) ?? sites[0];
  if (!site || site.status === 'pending') return;
  await client.fetchQuery({ queryKey: keys.summary(site.id), queryFn: () => fetchSummary(site.id) });
}
