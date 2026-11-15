import { QueryClient } from '@tanstack/react-query';

import { ApiError } from './client';

/**
 * Server state lives in TanStack Query. Live views refetch on an interval set per screen
 * (5-10 s, plan Section 1.1); here only the shared defaults.
 */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5_000,
      // Retry network blips, not answers: a 4xx means the request itself won't succeed.
      retry: (failures, error) =>
        failures < 2 && !(error instanceof ApiError && error.status >= 400 && error.status < 500),
    },
  },
});
