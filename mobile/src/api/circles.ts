/** Circles, sites and pairing (server Sections 4.2-4.3; app flow in docs/design/briefs.md, 4). */
import { useMutation, useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query';

import { api } from './client';
import { keys } from './keys';

export type Role = 'owner' | 'admin' | 'viewer';
export type Circle = {
  id: string;
  name: string;
  role: Role;
  member_count: number;
  site_count: number;
  created_at: string;
};
export type SiteStatus = 'online' | 'degraded' | 'unreachable' | 'pending';
export type Site = {
  id: string;
  circle_id: string;
  name: string;
  timezone: string;
  status: SiteStatus;
  last_seen_at: string | null;
  cidr: string | null;
  gateway_ip: string | null;
  created_at: string;
};
type PairingCode = { code: string; expires_at: string };

/** The summary is polled every few seconds; carry its status into the cached sites lists, so
 * the switcher and Settings never show a site as online after the Overview says it's down. */
function syncSiteStatus(client: QueryClient, summary: { site_id: string; status: SiteStatus }) {
  client.setQueriesData<Site[]>({ queryKey: ['circles'] }, (sites) => {
    if (!Array.isArray(sites)) return sites;
    const stale = sites.find((s) => s.id === summary.site_id && s.status !== summary.status);
    return stale ? sites.map((s) => (s === stale ? { ...s, status: summary.status } : s)) : sites;
  });
  client.setQueryData<Site>(keys.site(summary.site_id), (site) =>
    site && site.status !== summary.status ? { ...site, status: summary.status } : site,
  );
}
type List<T> = { items: T[]; next_cursor: string | null };

export function useCircles(enabled = true) {
  return useQuery({
    queryKey: keys.circles,
    queryFn: async () => (await api<List<Circle>>('/circles')).items,
    enabled,
  });
}

export const fetchSites = async (circleId: string) => (await api<List<Site>>(`/circles/${circleId}/sites`)).items;
export const fetchSummary = (siteId: string) => api<SiteSummary>(`/sites/${siteId}/summary`);

/** The Circle's sites. Polled, because their status (online, unreachable) feeds the site
 * switcher and Settings; the site on screen is also kept current by its summary (below). */
export function useSites(circleId: string | undefined) {
  return useQuery({
    queryKey: keys.sites(circleId ?? 'none'),
    queryFn: () => fetchSites(circleId!),
    enabled: !!circleId,
    refetchInterval: 30_000,
  });
}

/** One site; `poll` refetches every few seconds (the pairing screen waits for the agent). */
export function useSite(siteId: string, poll = false) {
  return useQuery({
    queryKey: keys.site(siteId),
    queryFn: () => api<Site>(`/sites/${siteId}`),
    refetchInterval: poll ? 3_000 : false,
  });
}

type LatestSample = { ts: string; rtt_ms: number | null; ok: boolean };
export type Deduction = { factor: string; points: number; reason: string; detail: string };
type DiagnoseStepState = { n: number; status: 'pass' | 'fail' | 'skipped'; ms: number | null };
type LastDiagnose = {
  command_id: string;
  finished_at: string;
  root_cause_step: number | null;
  steps: DiagnoseStepState[];
};
/** Everything the Overview needs for one site (GET /sites/{id}/summary). */
export type SiteSummary = {
  site_id: string;
  status: SiteStatus;
  last_seen_at: string | null;
  score: number;
  grade: string;
  grade_summary: string;
  deductions: Deduction[];
  internet: LatestSample | null;
  gateway: LatestSample | null;
  /** The newest name lookup and HTTPS check (agent 1.2.0 checks every 5 minutes; older: absent). */
  dns?: LatestSample | null;
  web?: LatestSample | null;
  devices_total: number;
  devices_online: number;
  needs_review: number;
  open_alerts: number;
  open_outage_since: string | null;
  last_diagnose: LastDiagnose | null;
};

/** The site's summary, refetched every `everyMs` (the agent reports about every 10 s). */
export function useSiteSummary(siteId: string | undefined, enabled = true, everyMs = 5_000) {
  const client = useQueryClient();
  return useQuery({
    queryKey: keys.summary(siteId ?? 'none'),
    queryFn: async () => {
      const summary = await fetchSummary(siteId!);
      syncSiteStatus(client, summary);
      return summary;
    },
    enabled: enabled && !!siteId,
    refetchInterval: enabled ? everyMs : false,
  });
}

export function useCreateCircle() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (name: string) =>
      api<Circle>('/circles', { method: 'POST', body: { name: name.trim() } }),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.circles }),
  });
}

export function useJoinCircle() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (code: string) =>
      api<Circle>('/invites/accept', { method: 'POST', body: { code: code.trim() } }),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.circles }),
  });
}

export function useCreateSite(circleId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (name: string) =>
      api<Site>(`/circles/${circleId}/sites`, { method: 'POST', body: { name: name.trim() } }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: keys.sites(circleId) });
      void client.invalidateQueries({ queryKey: keys.circles });
    },
  });
}

export function usePairingCode(siteId: string) {
  return useMutation({
    mutationFn: () => api<PairingCode>(`/sites/${siteId}/pairing-code`, { method: 'POST' }),
  });
}
