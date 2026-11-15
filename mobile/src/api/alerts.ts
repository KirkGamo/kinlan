/** Alerts: open and resolved feeds, acknowledgement, and the tab badge count (Section 4.3). */
import { useInfiniteQuery, useMutation, useQueryClient } from '@tanstack/react-query';

import { api } from './client';
import { useCircles, useSiteSummary, useSites } from './circles';
import { useSelectedSite } from './selection';

export type AlertType = 'new_device' | 'risky_port' | 'unreachable' | 'back_online' | 'high_latency' | 'packet_loss' | string;
export type Alert = {
  id: string;
  site_id: string;
  type: AlertType;
  severity: 'info' | 'warning' | 'critical';
  title: string;
  body: string;
  subject_ref: string | null;
  created_at: string;
  acked_at: string | null;
  acked_by: string | null;
  resolved_at: string | null;
};
type Page = { items: Alert[]; next_cursor: string | null };

export const alertKeys = {
  site: (siteId: string) => ['sites', siteId, 'alerts'] as const,
  list: (siteId: string, status: 'open' | 'resolved') => ['sites', siteId, 'alerts', status] as const,
};

/** One feed, newest first, 20 at a time; open alerts refresh every 15 s. */
export function useAlerts(siteId: string, status: 'open' | 'resolved') {
  return useInfiniteQuery({
    queryKey: alertKeys.list(siteId, status),
    queryFn: ({ pageParam }) =>
      api<Page>(`/sites/${siteId}/alerts?status=${status}&limit=20${pageParam ? `&cursor=${encodeURIComponent(pageParam)}` : ''}`),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor,
    refetchInterval: status === 'open' ? 15_000 : false,
  });
}

export function useAcknowledge(siteId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (alertId: string) => api<Alert>(`/alerts/${alertId}/ack`, { method: 'POST' }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: alertKeys.site(siteId) });
      void client.invalidateQueries({ queryKey: ['sites', siteId, 'summary'] });
    },
  });
}

/** Open alerts on the site the tabs show, for the Alerts tab badge. */
export function useOpenAlertCount(): number {
  const circles = useCircles();
  const sites = useSites(circles.data?.[0]?.id);
  const site = useSelectedSite(sites.data);
  const summary = useSiteSummary(site?.id, !!site && site.status !== 'pending', 30_000);
  return summary.data?.open_alerts ?? 0;
}
