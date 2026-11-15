import { router } from 'expo-router';
import { useState } from 'react';
import { Pressable, RefreshControl, StyleSheet, View } from 'react-native';
import Svg, { Path } from 'react-native-svg';

import { useSiteSummary, useSites, type Circle, type Site, type SiteSummary } from '@/api/circles';
import { useDevices, useLatency, useMembers } from '@/api/overview';
import { selectSite, useCurrentCircle, useSelectedSite } from '@/api/selection';
import { Button, Card, Loader, Screen, SectionLabel, StatusChip, Text } from '@/components/ui';
import { HealthCard } from '@/features/overview/health-card';
import { LatencyChart } from '@/features/overview/latency-chart';
import { LightStrip } from '@/features/overview/light-strip';
import { ago, isStale, lights, problems, verdict, type Light } from '@/features/overview/model';
import { People } from '@/features/overview/people';
import { SiteHeader } from '@/features/overview/site-header';
import { useNow } from '@/hooks/use-now';
import { colors, radius, space } from '@/theme';

const UNLIT: Light[] = Array.from({ length: 5 }, () => ({ state: 'unlit', value: '—' }));

/**
 * Overview (briefs.md section 1): answers "is anything wrong now?" first. The five lights and the
 * verdict lead; open problems, your people, the health grade, the 24-hour chart and devices
 * follow. A site with no agent yet becomes the pairing call to action.
 */
export default function OverviewScreen() {
  const { circles, circle } = useCurrentCircle();
  const sites = useSites(circle?.id);
  const site = useSelectedSite(sites.data);

  if (circles.isPending || sites.isPending) return <Skeleton />;
  if (circles.isError || sites.isError) {
    const error = circles.error ?? sites.error;
    return (
      <Screen>
        <ErrorCard message={error?.message ?? 'Something went wrong.'} onRetry={() => void sites.refetch()} />
      </Screen>
    );
  }
  if (!circle) return <Skeleton />;
  const canManage = circle.role === 'owner' || circle.role === 'admin';
  if (!site) return <NoSites circle={circle} canManage={canManage} />;
  if (site.status === 'pending') return <Unpaired site={site} sites={sites.data} canManage={canManage} />;
  return <Live key={site.id} circle={circle} site={site} sites={sites.data} />;
}

function Live({ circle, site, sites }: { circle: Circle; site: Site; sites: Site[] }) {
  const summary = useSiteSummary(site.id, true, 10_000);
  const latency = useLatency(site.id);
  const devices = useDevices(site.id);
  const members = useMembers(circle.id);
  const now = useNow(5_000);
  const [ignite, setIgnite] = useState(0);
  const [refreshing, setRefreshing] = useState(false);

  async function refresh() {
    setRefreshing(true);
    await Promise.all([summary.refetch(), latency.refetch(), devices.refetch(), members.refetch()]);
    setRefreshing(false);
    setIgnite((n) => n + 1); // the lights re-ignite after a pull, like switching sites
  }

  const s = summary.data;
  const staleNow = s ? isStale(s, now) : false;
  // While the agent is offline the online counts are old, so only the total is shown.
  const sub = !s
    ? circle.name
    : staleNow
      ? `${circle.name} · ${s.devices_total} devices`
      : `${circle.name} · ${s.devices_online} of ${s.devices_total} devices online`;
  const header = <SiteHeader site={site} sites={sites} sub={sub} onSwitch={selectSite} />;

  if (!s) {
    return (
      <Screen>
        {header}
        <LightStrip lights={UNLIT} igniteKey="loading" />
        {summary.isError ? (
          <ErrorCard message={summary.error.message} onRetry={() => void summary.refetch()} />
        ) : (
          <Card style={styles.loading}>
            <Loader label="Loading the site" />
          </Card>
        )}
      </Screen>
    );
  }

  const lit = lights(s, now);
  const v = verdict(s, now, lit);
  const open = problems(s, now, v);
  const stale = staleNow;
  const canManage = circle.role === 'owner' || circle.role === 'admin';
  const diagnose = () => router.push({ pathname: '/diagnose', params: { site: site.id, run: stale ? '0' : '1' } });

  return (
    <Screen
      fab={canManage ? <DiagnoseFab onPress={diagnose} /> : null}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={refresh} tintColor={colors.yellow} colors={[colors.onYellow]} progressBackgroundColor={colors.yellow} />
      }>
      {header}
      <LightStrip lights={lit} igniteKey={`${site.id}-${ignite}`} onDiagnose={canManage && !stale ? diagnose : undefined} />

      <Card style={styles.verdict}>
        <View style={styles.meta}>
          <StatusChip tone={v.tone} label={v.chip} />
          <Text role="bodySmall" color={stale ? 'orange' : 'text2'} tabular>
            {s.last_seen_at ? `Updated ${ago(s.last_seen_at, now)}` : 'No data yet'}
          </Text>
        </View>
        <Text role="headline" accessibilityRole="header">
          {v.title}
        </Text>
        <Text role="body" color="text2">
          {v.text}
        </Text>
        {summary.isRefetchError ? (
          <Text role="bodySmall" color="orange">
            {`Couldn’t refresh: ${summary.error?.message ?? 'no connection'}. Showing the last data.`}
          </Text>
        ) : null}
      </Card>

      {open.length ? (
        <>
          <SectionLabel end={String(open.length)}>Open problems</SectionLabel>
          {open.map((p) => (
            <Pressable
              key={p.key}
              onPress={() => (p.key === 'outage' && canManage ? diagnose() : router.navigate(p.to))}
              accessibilityRole="button"
              accessibilityLabel={`${p.title}. ${p.key === 'outage' && canManage ? 'Run a diagnose to find where it breaks.' : p.next}`}
              style={({ pressed }) => [styles.row, pressed && styles.pressed]}>
              <View style={styles.rowText}>
                <Text role="title">{p.title}</Text>
                <Text role="bodySmall" color="text2">
                  {p.key === 'outage' && canManage ? 'Run a diagnose to find where it breaks.' : p.next}
                </Text>
              </View>
              <StatusChip tone={p.tone} label={p.chip} />
            </Pressable>
          ))}
        </>
      ) : null}

      <SectionLabel end={stale ? 'devices' : 'devices online'}>Your people</SectionLabel>
      {devices.data && members.data ? (
        <People members={members.data} devices={devices.data} stale={stale} />
      ) : devices.isError || members.isError ? (
        <ErrorCard message={(devices.error ?? members.error)?.message ?? ''} onRetry={() => void Promise.all([devices.refetch(), members.refetch()])} />
      ) : (
        <Card style={styles.loading}>
          <Loader label="Loading people" />
        </Card>
      )}

      <SectionLabel>Health</SectionLabel>
      <HealthCard score={s.score} grade={s.grade} summary={s.grade_summary} deductions={s.deductions} sweepKey={`${site.id}-${ignite}`} />

      <SectionLabel end="drag to read">Connection · 24 h</SectionLabel>
      <LatencyChart data={latency.data} loading={latency.isPending} error={latency.isError ? latency.error.message : undefined} />

      <SectionLabel>Devices</SectionLabel>
      <DevicesRow summary={s} stale={stale} />
    </Screen>
  );
}

/** The Diagnose pill (owners and admins): opens Diagnose and starts a run. */
function DiagnoseFab({ onPress }: { onPress: () => void }) {
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel="Diagnose"
      accessibilityHint="Runs the six checks to find where the network breaks"
      style={({ pressed }) => [styles.fab, pressed && styles.fabPressed]}>
      <Svg width={20} height={20} viewBox="0 0 24 24">
        <Path
          d="M15.5 14h-.79l-.28-.27A6.47 6.47 0 0 0 16 9.5 6.5 6.5 0 1 0 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"
          fill={colors.onYellow}
        />
      </Svg>
      <Text role="label" color="onYellow">
        Diagnose
      </Text>
    </Pressable>
  );
}

function DevicesRow({ summary, stale }: { summary: SiteSummary; stale: boolean }) {
  const n = summary.needs_review;
  return (
    <Pressable
      onPress={() => router.navigate('/devices')}
      accessibilityRole="button"
      accessibilityHint="Opens Devices"
      style={({ pressed }) => [styles.row, pressed && styles.pressed]}>
      <View style={styles.rowText}>
        <Text role="title" tabular>
          {stale ? `${summary.devices_total} devices` : `${summary.devices_online} of ${summary.devices_total} online`}
        </Text>
        <Text role="bodySmall" color="text2">
          {stale
            ? 'Who’s online shows again when the agent reports.'
            : n
              ? 'Review the new ones: say whose they are.'
              : 'Everything here has been seen before.'}
        </Text>
      </View>
      {n ? <StatusChip tone="new" label={`${n} new to review`} /> : null}
    </Pressable>
  );
}


function Unpaired({ site, sites, canManage }: { site: Site; sites: Site[]; canManage: boolean }) {
  return (
    <Screen>
      <SiteHeader site={site} sites={sites} sub="Not paired yet" onSwitch={selectSite} />
      <LightStrip lights={UNLIT} igniteKey="pending" />
      <Card style={styles.verdict}>
        <StatusChip tone="neutral" label="Not paired" />
        <Text role="headline" accessibilityRole="header">
          Pair the agent to start
        </Text>
        <Text role="body" color="text2">
          {canManage
            ? 'The lights come on once a PC on this network runs the KinLAN agent. It takes about two minutes.'
            : 'An owner or admin of this Circle needs to pair a PC on this network. The lights come on once they do.'}
        </Text>
        {canManage ? (
          <Button label="Pair the agent" onPress={() => router.push({ pathname: '/onboarding/pair', params: { site: site.id } })} />
        ) : null}
      </Card>
    </Screen>
  );
}

function NoSites({ circle, canManage }: { circle: Circle; canManage: boolean }) {
  return (
    <Screen>
      <Text role="titleLarge" accessibilityRole="header">
        {circle.name}
      </Text>
      <Card style={styles.verdict}>
        <Text role="headline">No sites yet</Text>
        <Text role="body" color="text2">
          {canManage
            ? 'A site is one network, like your home Wi-Fi or a lab. Add one, then pair a PC on it.'
            : 'An owner or admin of this Circle needs to add a site first.'}
        </Text>
        {canManage ? (
          <Button label="Add a site" onPress={() => router.push({ pathname: '/onboarding/new-site', params: { circle: circle.id } })} />
        ) : null}
      </Card>
    </Screen>
  );
}

function Skeleton() {
  return (
    <Screen>
      <View style={styles.skelTitle} />
      <LightStrip lights={UNLIT} igniteKey="skeleton" />
      <Card style={styles.loading}>
        <Loader label="Loading" />
      </Card>
    </Screen>
  );
}

function ErrorCard({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <Card>
      <StatusChip tone="down" label="Couldn’t load" />
      <Text role="body" color="text2">
        {message}
      </Text>
      <Button label="Try again" variant="ghost" onPress={onRetry} />
    </Card>
  );
}

const styles = StyleSheet.create({
  verdict: { paddingTop: space.s6, gap: space.s2 },
  meta: { flexDirection: 'row', alignItems: 'center', gap: space.s3, flexWrap: 'wrap' },
  loading: { alignItems: 'center', justifyContent: 'center', minHeight: 120 },
  row: {
    minHeight: 68,
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.s3,
    backgroundColor: colors.card,
    borderRadius: radius.row,
    borderCurve: 'continuous',
    paddingHorizontal: space.s4,
    paddingVertical: space.s3,
  },
  pressed: { backgroundColor: colors.raised },
  fab: {
    minHeight: 56,
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.s2,
    paddingHorizontal: space.s5,
    borderRadius: radius.pill,
    backgroundColor: colors.yellow,
    shadowColor: '#000',
    shadowOpacity: 0.4,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 4 },
    elevation: 6,
  },
  fabPressed: { transform: [{ scale: 0.96 }] },
  rowText: { flex: 1, gap: 2 },
  skelTitle: { width: 160, height: 28, borderRadius: 8, backgroundColor: colors.card, marginVertical: space.s2 },
});
