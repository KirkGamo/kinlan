/**
 * Every TanStack Query key in one place. Keys nest by owner (a site's devices sit under
 * ['sites', id]), so invalidating a parent refreshes everything under it.
 */
/** Hooks that wait for an id (the query is disabled until then) pass it through as is. */
type Id = string | null | undefined;

export const keys = {
  me: ['me'] as const,
  circles: ['circles'] as const,
  sites: (circleId: Id) => ['circles', circleId, 'sites'] as const,
  members: (circleId: Id) => ['circles', circleId, 'members'] as const,
  notifications: (circleId: Id) => ['circles', circleId, 'notifications'] as const,
  site: (siteId: Id) => ['sites', siteId] as const,
  summary: (siteId: Id) => ['sites', siteId, 'summary'] as const,
  devices: (siteId: Id) => ['sites', siteId, 'devices'] as const,
  latency: (siteId: Id, range: string) => ['sites', siteId, 'latency', range] as const,
  outages: (siteId: Id) => ['sites', siteId, 'outages'] as const,
  pingTests: (deviceId: Id) => ['devices', deviceId, 'ping-tests'] as const,
  alerts: (siteId: Id) => ['sites', siteId, 'alerts'] as const,
  alertList: (siteId: Id, status: 'open' | 'resolved') => ['sites', siteId, 'alerts', status] as const,
  alertSettings: (siteId: Id) => ['sites', siteId, 'alert-settings'] as const,
  diagnoses: (siteId: Id) => ['sites', siteId, 'diagnoses'] as const,
  device: (deviceId: Id) => ['devices', deviceId] as const,
  command: (commandId: Id) => ['commands', commandId] as const,
};
