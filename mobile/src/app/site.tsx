import { useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { useSiteSummary, useSites } from '@/api/circles';
import { useLatency, useOutages, type LatencyRange, type OutageEntry } from '@/api/overview';
import { useCurrentCircle } from '@/api/selection';
import { useAlertSettings } from '@/api/settings';
import { Button, Card, ErrorCard, FormScreen, Loader, SectionLabel, Segmented, StatusChip, Text } from '@/components/ui';
import { LatencyChart } from '@/features/overview/latency-chart';
import { LossBars } from '@/features/overview/loss-bars';
import { ago, day, isStale } from '@/features/overview/model';
import { useNow } from '@/hooks/use-now';
import { colors, radius, size, space } from '@/theme';

const RANGES: { key: LatencyRange; label: string }[] = [
  { key: '1h', label: '1 h' },
  { key: '24h', label: '24 h' },
  { key: '7d', label: '7 d' },
  { key: '30d', label: '30 d' },
];
const RANGE_WORDS: Record<LatencyRange, string> = { '1h': '1 hour', '24h': '24 hours', '7d': '7 days', '30d': '30 days' };
const CAUSE: Record<OutageEntry['cause'], string> = {
  isp: 'Internet provider',
  lan: 'Inside the network',
  unknown: 'Cause unknown',
};
const DEFAULT_ALERT_PCT = 5;

/**
 * Site detail (plan, Section 6.2; Network Statistics): "how has the connection been, and when
 * did it break?" Latency over 1 hour to 30 days, lost pings against the site's alert line, and
 * every outage. Opened from the Overview's connection chart; any member can read it.
 */
export default function SiteDetailScreen() {
  const { site: siteId } = useLocalSearchParams<{ site: string }>();
  const { circle } = useCurrentCircle();
  const site = useSites(circle?.id).data?.find((s) => s.id === siteId);
  const summary = useSiteSummary(siteId, true, 30_000);
  const [range, setRange] = useState<LatencyRange>('24h');
  const latency = useLatency(siteId, true, range);
  const settings = useAlertSettings(siteId);
  const now = useNow(30_000);
  const s = summary.data;
  const stale = s ? isStale(s, now) : false;
  const alertPct = settings.data?.loss_pct ?? DEFAULT_ALERT_PCT;
  // While a new range loads, the previous one stays on screen (placeholder data), dimmed a little.
  const switching = latency.isPlaceholderData;
  const measured = !!latency.data && ((latency.data.series.internet?.length ?? 0) + (latency.data.series.gateway?.length ?? 0)) > 0;

  return (
    <FormScreen>
      <View style={styles.head}>
        <Text role="headline">{site?.name ?? 'Connection'}</Text>
        <Text role="bodySmall" color="text2">
          {stale && s?.last_seen_at
            ? `Agent offline · last data ${ago(s.last_seen_at, now)}`
            : `Internet and router, measured every 10 seconds`}
        </Text>
      </View>

      <Segmented label="Time range" options={RANGES} value={range} onChange={(k) => setRange(k)} />

      <SectionLabel end={switching ? 'loading…' : measured ? 'drag to read' : undefined}>{`Latency · ${RANGE_WORDS[range]}`}</SectionLabel>
      <View style={switching ? styles.switching : undefined}>
        {latency.isError && !latency.data ? (
          <ErrorCard message={latency.error.message} onRetry={() => void latency.refetch()} />
        ) : (
          <LatencyChart data={latency.data} loading={latency.isPending} range={range} />
        )}
      </View>

      <SectionLabel>Lost pings</SectionLabel>
      <View style={switching ? styles.switching : undefined}>
        <LossBars data={latency.data} loading={latency.isPending} alertPct={alertPct} />
      </View>

      <OutageLog siteId={siteId} />
    </FormScreen>
  );
}

/** Every outage, newest first, 20 at a time: when, how long, and why in plain words. */
function OutageLog({ siteId }: { siteId: string }) {
  const outages = useOutages(siteId);
  const items = outages.data?.pages.flatMap((p) => p.items) ?? [];

  return (
    <>
      <SectionLabel end={items.length ? `${items.length}${outages.hasNextPage ? '+' : ''}` : undefined}>Outages</SectionLabel>
      {outages.isPending ? (
        <Card style={styles.center}>
          <Loader label="Loading outages" />
        </Card>
      ) : outages.isError ? (
        <ErrorCard message={outages.error.message} onRetry={() => void outages.refetch()} />
      ) : items.length === 0 ? (
        <Card>
          <StatusChip tone="ok" label="None" />
          <Text role="body" color="text2">
            No outages recorded. When the internet drops, each one appears here with when it started,
            how long it lasted and why.
          </Text>
        </Card>
      ) : (
        <View style={styles.list}>
          {items.map((o) => (
            <OutageRow key={o.id} o={o} />
          ))}
          {outages.hasNextPage ? (
            <Button label="Show older" variant="ghost" loading={outages.isFetchingNextPage} onPress={() => void outages.fetchNextPage()} />
          ) : null}
        </View>
      )}
    </>
  );
}

function OutageRow({ o }: { o: OutageEntry }) {
  // The agent measures real outages (exact times and cause); the server can only say the agent
  // went quiet, which may be the PC switched off rather than the internet.
  const measured = o.detected_by === 'agent';
  const lasted = o.ongoing ? 'Still down' : o.duration_s != null ? `Lasted ${duration(o.duration_s)}` : '';
  const why = measured ? CAUSE[o.cause] : 'The agent stopped reporting';
  return (
    <View style={styles.row} accessible accessibilityLabel={`${measured ? 'Outage' : 'Agent off'}, ${day(o.started_at)}. ${lasted}. ${why}.`}>
      <View style={styles.rowText}>
        <Text role="title" tabular>
          {day(o.started_at)}
        </Text>
        <Text role="bodySmall" color="text2" tabular>
          {[lasted, why].filter(Boolean).join(' · ')}
        </Text>
      </View>
      <StatusChip tone={measured ? 'down' : 'neutral'} label={o.ongoing ? 'Down now' : measured ? 'Down' : 'Agent off'} />
    </View>
  );
}

/** "45 s", "14 min", "2 h 5 min", "3 days 4 h" (briefs.md shared rules: plain numbers). */
function duration(seconds: number): string {
  const s = Math.round(seconds);
  if (s < 60) return `${s} s`;
  const m = Math.round(s / 60);
  if (m < 60) return `${m} min`;
  const h = Math.floor(m / 60);
  if (h < 48) return m % 60 ? `${h} h ${m % 60} min` : `${h} h`;
  const d = Math.floor(h / 24);
  return h % 24 ? `${d} days ${h % 24} h` : `${d} days`;
}

const styles = StyleSheet.create({
  head: { gap: space.s1 },
  switching: { opacity: 0.6 },
  center: { minHeight: size.loading, alignItems: 'center', justifyContent: 'center' },
  list: { gap: space.item },
  row: {
    minHeight: size.row,
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.s3,
    backgroundColor: colors.card,
    borderRadius: radius.row,
    paddingHorizontal: space.s4,
    paddingVertical: space.s3,
  },
  rowText: { flex: 1, gap: 2 },
});
