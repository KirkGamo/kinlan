/** The Overview's other reads: the 24-hour latency chart, devices and members (plan, Section 4.3). */
import { useQuery } from '@tanstack/react-query';

import { api } from './client';
import type { Role } from './circles';

export type LatencyPoint = {
  t: string;
  avg_ms: number | null; // null when every ping in the bucket was lost
  max_ms: number | null;
  loss_pct: number;
  samples: number;
};
export type LatencySummary = {
  avg_ms: number | null;
  max_ms: number | null;
  loss_pct: number | null;
  samples: number;
};
export type OutageSpan = {
  id: string;
  started_at: string;
  ended_at: string | null;
  ongoing: boolean;
  cause: 'isp' | 'lan' | 'unknown';
};
export type Latency = {
  bucket_seconds: number;
  since: string;
  until: string;
  series: { internet?: LatencyPoint[]; gateway?: LatencyPoint[] };
  summary: { internet?: LatencySummary; gateway?: LatencySummary };
  outages: OutageSpan[];
};

export type DeviceType = 'router' | 'computer' | 'laptop' | 'phone' | 'tv' | 'printer' | 'unknown';
export type Device = {
  id: string;
  site_id: string;
  display_name: string;
  custom_name: string | null;
  hostname: string | null;
  vendor: string | null;
  mac: string;
  ip: string | null;
  device_type: DeviceType;
  owner: { user_id: string; display_name: string } | null;
  trusted: boolean;
  baseline: boolean;
  needs_review: boolean;
  online: boolean;
  first_seen_at: string;
  last_seen_at: string;
  open_risky_ports: number;
  is_agent: boolean; // the PC running this site's agent
};
export type Member = { user_id: string; display_name: string; email: string; role: Role };
type List<T> = { items: T[]; next_cursor: string | null };

export function useLatency(siteId: string | undefined, enabled = true) {
  return useQuery({
    queryKey: ['sites', siteId, 'latency', '24h'],
    queryFn: () => api<Latency>(`/sites/${siteId}/latency?range=24h`),
    enabled: enabled && !!siteId,
    refetchInterval: 60_000, // one 15-minute bucket fills slowly; a minute is plenty
  });
}

export function useDevices(siteId: string | undefined, enabled = true) {
  return useQuery({
    queryKey: ['sites', siteId, 'devices'],
    queryFn: async () => (await api<List<Device>>(`/sites/${siteId}/devices`)).items,
    enabled: enabled && !!siteId,
    refetchInterval: 30_000,
  });
}

export function useMembers(circleId: string | undefined) {
  return useQuery({
    queryKey: ['circles', circleId, 'members'],
    queryFn: async () => (await api<List<Member>>(`/circles/${circleId}/members`)).items,
    enabled: !!circleId,
  });
}
