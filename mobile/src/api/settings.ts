/** Members, invites, alert thresholds and the account (plan, Sections 4.2 and 4.4). */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api } from './client';
import type { Role } from './circles';

export type Invite = { code: string; role: Role; expires_at: string };
export type AlertSettings = {
  latency_ms: number;
  loss_pct: number;
  offline_seconds: number;
  notify_new_device: boolean;
};

function useCircleRefresh(circleId: string) {
  const client = useQueryClient();
  return () => {
    void client.invalidateQueries({ queryKey: ['circles', circleId, 'members'] });
    void client.invalidateQueries({ queryKey: ['circles'] });
  };
}

export function useChangeRole(circleId: string) {
  const refresh = useCircleRefresh(circleId);
  return useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: Role }) =>
      api(`/circles/${circleId}/members/${userId}`, { method: 'PATCH', body: { role } }),
    onSuccess: refresh,
  });
}

/** Remove someone (owners), or yourself (leave the Circle). */
export function useRemoveMember(circleId: string) {
  const refresh = useCircleRefresh(circleId);
  return useMutation({
    mutationFn: (userId: string) => api(`/circles/${circleId}/members/${userId}`, { method: 'DELETE' }),
    onSuccess: refresh,
  });
}

export function useCreateInvite(circleId: string) {
  return useMutation({
    mutationFn: (role: Role) => api<Invite>(`/circles/${circleId}/invites`, { method: 'POST', body: { role } }),
  });
}

export function useAlertSettings(siteId: string | undefined) {
  return useQuery({
    queryKey: ['sites', siteId, 'alert-settings'],
    queryFn: () => api<AlertSettings>(`/sites/${siteId}/alert-settings`),
    enabled: !!siteId,
  });
}

export function useUpdateAlertSettings(siteId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (patch: Partial<AlertSettings>) =>
      api<AlertSettings>(`/sites/${siteId}/alert-settings`, { method: 'PATCH', body: patch }),
    onSuccess: (data) => client.setQueryData(['sites', siteId, 'alert-settings'], data),
  });
}

export function useDeleteAccount() {
  return useMutation({ mutationFn: () => api('/me', { method: 'DELETE' }) });
}
