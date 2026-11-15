import { useEffect, useState } from 'react';

/** Re-renders every `everyMs`, so "Updated 10 s ago" and staleness keep up between fetches. */
export function useNow(everyMs: number): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), everyMs);
    return () => clearInterval(timer);
  }, [everyMs]);
  return now;
}
