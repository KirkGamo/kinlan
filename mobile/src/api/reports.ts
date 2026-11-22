/** PDF network reports (plan, Section 4.7; server app/routers/reports.py). */
import { useMutation } from '@tanstack/react-query';
import { Linking, Platform } from 'react-native';

import { api, API_URL } from './client';

export type ReportRange = '24h' | '7d' | '30d';
export type Report = {
  id: string;
  site_id: string;
  range: ReportRange;
  range_start: string;
  range_end: string;
  created_at: string;
  filename: string;
  /** Relative to the API; signed for this report and valid for 10 minutes. */
  download_url: string;
};

export function useCreateReport(siteId: string) {
  return useMutation({
    mutationFn: (range: ReportRange) => api<Report>(`/sites/${siteId}/reports`, { method: 'POST', body: { range } }),
  });
}

/**
 * Open a report's PDF. The link is fetched fresh each time (they expire after 10 minutes), then
 * handed to the browser: a phone downloads it and opens the PDF viewer; web opens a new tab.
 */
export async function openReport(reportId: string): Promise<void> {
  const fresh = await api<Report>(`/reports/${reportId}`);
  const url = `${API_URL}${fresh.download_url}`;
  if (Platform.OS === 'web') {
    globalThis.open?.(url, '_blank', 'noopener');
    return;
  }
  await Linking.openURL(url);
}
