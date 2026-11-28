import { focusManager, QueryClient } from '@tanstack/react-query';
import { AppState, Platform } from 'react-native';

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

// Coming back to the app refetches what's stale, as a browser tab does on focus. On the phone
// TanStack Query can't see that by itself: tell it from Android's app state (a member who
// joined, or a site that went down while the app was in the background, shows at once).
if (Platform.OS !== 'web') {
  focusManager.setEventListener((setFocused) => {
    const subscription = AppState.addEventListener('change', (state) => setFocused(state === 'active'));
    return () => subscription.remove();
  });
}
