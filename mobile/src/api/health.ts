import { useQuery } from '@tanstack/react-query';

import { API_URL } from './client';

export type Health = { status: string; version: string };

/** GET /healthz: is the KinLAN API reachable? A free Render instance may take a minute to wake. */
export function useApiHealth() {
  return useQuery({
    queryKey: ['healthz'],
    queryFn: async (): Promise<Health> => {
      const response = await fetch(`${API_URL}/healthz`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return (await response.json()) as Health;
    },
    refetchInterval: 30_000,
  });
}
