/** Diagnose runs: start one, and the site's latest few (plan, Section 4.3, Commands). */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api } from './client';
import type { Command } from './devices';

export type DiagnoseStep = {
  n: number;
  name: string;
  layer: string;
  status: 'pass' | 'fail' | 'skipped';
  ms: number | null;
  summary: string;
  detail: string;
};
export type DiagnoseResult = { steps: DiagnoseStep[]; root_cause_step: number | null; summary: string };

const key = (siteId: string) => ['sites', siteId, 'diagnoses'] as const;

export function isActive(c: Command | undefined): boolean {
  return c?.status === 'pending' || c?.status === 'running';
}

/** The last five runs, newest first; polls each second while one is still running. */
export function useDiagnoses(siteId: string) {
  return useQuery({
    queryKey: key(siteId),
    queryFn: async () => (await api<{ items: Command[] }>(`/sites/${siteId}/diagnoses?limit=5`)).items,
    refetchInterval: (q) => (isActive(q.state.data?.[0]) ? 1_000 : false),
  });
}

export function useStartDiagnose(siteId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => api<Command>(`/sites/${siteId}/commands`, { method: 'POST', body: { type: 'diagnose' } }),
    onSuccess: (cmd) => {
      client.setQueryData<Command[]>(key(siteId), (old) => [cmd, ...(old ?? [])].slice(0, 5));
      void client.invalidateQueries({ queryKey: key(siteId) });
    },
  });
}
