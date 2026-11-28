import { useFocusEffect } from 'expo-router';
import { useCallback, useRef } from 'react';

/**
 * Refetch when the screen comes back into view. Tabs stay mounted, so without this a list
 * loaded once (the Circle's members, its sites) keeps what it showed the first time.
 */
export function useRefreshOnFocus(refetch: () => unknown) {
  const first = useRef(true);
  useFocusEffect(
    useCallback(() => {
      if (first.current) {
        first.current = false; // the first visit already fetched
        return;
      }
      void refetch();
    }, [refetch]),
  );
}
