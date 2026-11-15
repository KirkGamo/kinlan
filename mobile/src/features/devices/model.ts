/** How a device's state reads in the list, the map and the sheet (briefs.md section 2). */
import type { Device } from '@/api/overview';
import type { ChipTone } from '@/components/ui';

export type Filter = 'all' | 'review' | 'online' | 'offline';
export const FILTERS: { key: Filter; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'review', label: 'Needs review' },
  { key: 'online', label: 'Online' },
  { key: 'offline', label: 'Offline' },
];

export function matches(d: Device, f: Filter): boolean {
  if (f === 'review') return d.needs_review;
  if (f === 'online') return d.online;
  if (f === 'offline') return !d.online;
  return true;
}

export function chip(d: Device, stale = false): { tone: ChipTone; label: string } {
  if (d.needs_review) return { tone: 'new', label: 'New' };
  if (stale) return { tone: 'neutral', label: 'Unknown' }; // agent offline: online flags are old
  return d.online ? { tone: 'ok', label: 'Online' } : { tone: 'neutral', label: 'Offline' };
}

/** "Apple · 192.168.1.23", leaving out what isn't known. */
export function facts(d: Device): string {
  return [d.is_agent ? 'This PC, runs the agent' : null, d.vendor, d.ip].filter(Boolean).join(' · ') || d.mac;
}

/** Randomized (locally administered) hardware addresses: the second hex digit is 2, 6, A or E. */
export function isPrivateAddress(mac: string): boolean {
  return /^.[26ae]/i.test(mac);
}
