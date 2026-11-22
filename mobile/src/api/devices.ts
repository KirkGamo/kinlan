/** One device: detail, edits and ping tests (plan, Section 4.3, Devices and Commands). */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api } from './client';
import type { Device, DeviceType, Member } from './overview';
import { keys } from './keys';

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
/** An open port; `info` marks a web admin page (80, 8080), shown but not counted as a risk. */
type PortFinding = { port: number; service: string; first_seen_at: string; last_seen_at: string; info: boolean };
export type DeviceDetail = Device & { risky_ports: PortFinding[]; last_ping_test: PingTest | null };

type CommandStatus = 'pending' | 'running' | 'done' | 'failed' | 'expired';
export type Command = {
  id: string;
  type: string;
  status: CommandStatus;
  result: Record<string, unknown> | null;
  created_at: string;
  finished_at: string | null;
};

type DevicePatch = {
  custom_name?: string | null;
  device_type?: DeviceType;
  owner_user_id?: string | null;
  trusted?: boolean;
};

/**
 * One device's detail. While it loads, the row the sheet was opened from stands in (the list
 * already has its name, type, addresses and status), so the sheet opens complete; only the ports
 * and the last ping test wait for the detail.
 */
export function useDevice(deviceId: string | null, siteId?: string) {
  const client = useQueryClient();
  return useQuery({
    queryKey: keys.device(deviceId),
    queryFn: () => api<DeviceDetail>(`/devices/${deviceId}`),
    enabled: !!deviceId,
    placeholderData: () => {
      const row = client.getQueryData<Device[]>(keys.devices(siteId))?.find((d) => d.id === deviceId);
      return row ? { ...row, risky_ports: [], last_ping_test: null } : undefined;
    },
  });
}

/**
 * Edit a device. The change shows at once in the sheet and the list (optimistic) and rolls back
 * if the server refuses; then the list and the Overview counts refresh from the server.
 * `members` names the new owner in the meantime.
 */
export function useUpdateDevice(deviceId: string, siteId: string, members: Member[] = []) {
  const client = useQueryClient();
  const detailKey = keys.device(deviceId);
  const listKey = keys.devices(siteId);
  return useMutation({
    mutationFn: (patch: DevicePatch) =>
      api<DeviceDetail>(`/devices/${deviceId}`, { method: 'PATCH', body: patch }),
    onMutate: async (patch) => {
      await Promise.all([client.cancelQueries({ queryKey: detailKey }), client.cancelQueries({ queryKey: listKey })]);
      const detail = client.getQueryData<DeviceDetail>(detailKey);
      const list = client.getQueryData<Device[]>(listKey);
      const apply = <T extends Device>(d: T): T => applyPatch(d, patch, members);
      if (detail) client.setQueryData<DeviceDetail>(detailKey, apply(detail));
      if (list) client.setQueryData<Device[]>(listKey, list.map((d) => (d.id === deviceId ? apply(d) : d)));
      return { detail, list };
    },
    onError: (_error, _patch, before) => {
      if (before?.detail) client.setQueryData(detailKey, before.detail);
      if (before?.list) client.setQueryData(listKey, before.list);
    },
    onSuccess: (detail) => {
      client.setQueryData(detailKey, detail);
    },
    onSettled: () => {
      void client.invalidateQueries({ queryKey: keys.site(siteId) });
    },
  });
}

/** What the server will return, as far as the app can tell before it answers. */
function applyPatch<T extends Device>(d: T, patch: DevicePatch, members: Member[]): T {
  const next: T = { ...d };
  if ('custom_name' in patch) {
    next.custom_name = patch.custom_name ?? null;
    if (patch.custom_name) next.display_name = patch.custom_name; // a cleared name waits for the server
  }
  if (patch.device_type) next.device_type = patch.device_type;
  if ('owner_user_id' in patch) {
    const m = members.find((x) => x.user_id === patch.owner_user_id);
    next.owner = m ? { user_id: m.user_id, display_name: m.display_name } : null;
  }
  if (patch.trusted != null) {
    next.trusted = patch.trusted;
    if (patch.trusted) next.needs_review = false;
  }
  return next;
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
    queryKey: keys.command(commandId),
    queryFn: () => api<Command>(`/commands/${commandId}`),
    enabled: !!commandId,
    refetchInterval: (q) => {
      const s = q.state.data?.status;
      return s === 'done' || s === 'failed' || s === 'expired' ? false : 1_000;
    },
  });
}

/** What the agent's port check returns (agent portcheck.py, PortCheck.to_dict). */
export type PortCheckResult = {
  ports: number[];
  macs: string[];
  open: { mac: string; port: number; service: string }[];
  duration_ms: number;
};
const INFO_PORTS = new Set([80, 8080]);
export const isRiskyPort = (port: number) => !INFO_PORTS.has(port);

/**
 * Run the agent's risky-port check on one device, or on every device (no `deviceId`), and wait
 * for the result; when it's in, the devices, the device and the site summary refresh.
 */
export function usePortCheck(siteId: string, deviceId?: string) {
  const client = useQueryClient();
  const start = useMutation({
    mutationFn: () =>
      api<Command>(`/sites/${siteId}/commands`, {
        method: 'POST',
        body: { type: 'port_check', params: deviceId ? { device_id: deviceId } : {} },
      }),
  });
  const command = useCommand(start.data?.id ?? null);
  const status = command.data?.status ?? start.data?.status;
  const finished = status === 'done' || status === 'failed' || status === 'expired';
  return {
    run: () => start.mutate(undefined),
    running: start.isPending || (start.isSuccess && !finished),
    status,
    result: status === 'done' ? (command.data?.result as PortCheckResult | null) : null,
    error: start.error?.message ?? (finished && status !== 'done' ? String(command.data?.result?.error ?? 'The agent didn’t finish the check.') : null),
    refresh: () => {
      void client.invalidateQueries({ queryKey: keys.devices(siteId) });
      void client.invalidateQueries({ queryKey: keys.summary(siteId) });
      if (deviceId) void client.invalidateQueries({ queryKey: keys.device(deviceId) });
    },
  };
}
