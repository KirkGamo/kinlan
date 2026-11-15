/** One device: detail, edits and ping tests (plan, Section 4.3, Devices and Commands). */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api } from './client';
import type { Device, DeviceType } from './overview';

export type PingTest = {
  id: string;
  ts: string;
  sent: number;
  received: number;
  loss_pct: number;
  min_ms: number | null;
  avg_ms: number | null;
  max_ms: number | null;
  jitter_ms: number | null;
};
export type PortFinding = { port: number; service: string; first_seen_at: string; last_seen_at: string };
export type DeviceDetail = Device & { risky_ports: PortFinding[]; last_ping_test: PingTest | null };

export type CommandStatus = 'pending' | 'running' | 'done' | 'failed' | 'expired';
export type Command = {
  id: string;
  type: string;
  status: CommandStatus;
  result: Record<string, unknown> | null;
  created_at: string;
  finished_at: string | null;
};

export type DevicePatch = {
  custom_name?: string | null;
  device_type?: DeviceType;
  owner_user_id?: string | null;
  trusted?: boolean;
};

export function useDevice(deviceId: string | null) {
  return useQuery({
    queryKey: ['devices', deviceId],
    queryFn: () => api<DeviceDetail>(`/devices/${deviceId}`),
    enabled: !!deviceId,
  });
}

/** Edit a device; the list and the Overview counts refresh with it. */
export function useUpdateDevice(deviceId: string, siteId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (patch: DevicePatch) =>
      api<DeviceDetail>(`/devices/${deviceId}`, { method: 'PATCH', body: patch }),
    onSuccess: (detail) => {
      client.setQueryData(['devices', deviceId], detail);
      void client.invalidateQueries({ queryKey: ['sites', siteId] });
    },
  });
}

export const PING_COUNT = 5;

export function useStartPing(siteId: string, deviceId: string) {
  return useMutation({
    mutationFn: () =>
      api<Command>(`/sites/${siteId}/commands`, {
        method: 'POST',
        body: { type: 'ping_test', params: { device_id: deviceId, count: PING_COUNT } },
      }),
  });
}

/** Polls a command each second until it finishes, fails or expires. */
export function useCommand(commandId: string | null) {
  return useQuery({
    queryKey: ['commands', commandId],
    queryFn: () => api<Command>(`/commands/${commandId}`),
    enabled: !!commandId,
    refetchInterval: (q) => {
      const s = q.state.data?.status;
      return s === 'done' || s === 'failed' || s === 'expired' ? false : 1_000;
    },
  });
}
