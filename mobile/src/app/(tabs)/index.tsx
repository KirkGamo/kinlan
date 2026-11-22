import { router, useLocalSearchParams } from 'expo-router';
import { useRef, useState } from 'react';
import { Pressable, RefreshControl, StyleSheet, View } from 'react-native';
import Svg, { Path } from 'react-native-svg';

import { useSiteSummary, type Circle, type Site, type SiteSummary } from '@/api/circles';
import { useDevices, useLatency, useMembers } from '@/api/overview';
import { canManage as manages, selectSite, useTabData } from '@/api/selection';
import { Button, Card, ErrorCard, Loader, Perforation, Screen, SectionLabel, StatusChip, Text } from '@/components/ui';
import { HealthCard } from '@/features/overview/health-card';
import { LatencyChart } from '@/features/overview/latency-chart';
import { LightStrip } from '@/features/overview/light-strip';
import { ago, isStale, lights, problems, verdict, type Light, type Problem } from '@/features/overview/model';
import { People } from '@/features/overview/people';
import { SiteHeader, SiteHeaderSkeleton } from '@/features/overview/site-header';
import { useNow } from '@/hooks/use-now';
import { haptics } from '@/haptics';
import { colors, radius, size, space } from '@/theme';

const UNLIT: Light[] = Array.from({ length: 5 }, () => ({ state: 'unlit', value: '—' }));

/**
 * Overview (briefs.md section 1): answers "is anything wrong now?" first. The five lights and the
 * verdict lead; open problems, your people, the health grade, the 24-hour chart and devices
 * follow. A site with no agent yet becomes the pairing call to action.
 */
export default function OverviewScreen() {
  const tab = useTabData();
  if (tab.state === 'loading') return <Skeleton />;
  if (tab.state === 'error') {
    return (
      <Screen>
        <ErrorCard message={tab.message} onRetry={tab.retry} />
      </Screen>
    );
  }
  const { circle, sites, site, canManage } = tab;
  if (!site) return <NoSites circle={circle} canManage={canManage} />;
  if (site.status === 'pending') return <Unpaired site={site} sites={sites} canManage={canManage} />;
  return <Live key={site.id} circle={circle} site={site} sites={sites} />;
}

function Live({ circle, site, sites }: { circle: Circle; site: Site; sites: Site[] }) {
  const summary = useSiteSummary(site.id, true, 10_000);
  const latency = useLatency(site.id);
  const devices = useDevices(site.id);
  const members = useMembers(circle.id);
  const now = useNow(5_000);
  const [ignite, setIgnite] = useState(0);
  const [refreshing, setRefreshing] = useState(false);
  const taps = useRef(0);
  // An outage push opens Overview with ?light=failing&at=…: open the failing light's sheet.
  const { light: askedLight, at } = useLocalSearchParams<{ light?: string; at?: string }>();

  async function refresh() {
    haptics.tick(); // released past the pull threshold
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
  // The first failing light; with the agent offline every light is unlit, so This PC explains it.
  // If everything is green again by the time the push is tapped, nothing opens.
  const failing = lit.findIndex((l) => l.state === 'fail');
  const lightIndex = failing >= 0 ? failing : isStale(s, now) ? 0 : -1;
  const lightRequest = askedLight === 'failing' && lightIndex >= 0 ? { id: at ?? 'failing', index: lightIndex } : undefined;
  const v = verdict(s, now, lit);
  const open = problems(s, now, v);
  const stale = staleNow;
  const canManage = manages(circle);
  const diagnose = () => router.push({ pathname: '/diagnose', params: { site: site.id, run: stale ? '0' : '1' } });
  // Each problem opens exactly where it's dealt with: an outage runs Diagnose (owners and admins),
  // new devices open Devices filtered to Needs review, anything else opens Alerts.
  const openProblem = (p: Problem) => {
    // `taps` makes each tap a new link, so Devices applies the filter again.
    if (p.key === 'outage' && canManage) diagnose();
    else if (p.key === 'review') router.navigate({ pathname: '/devices', params: { filter: 'review', at: String(++taps.current) } });
    else router.navigate(p.to);
  };

  return (
    <Screen
      fab={canManage ? <DiagnoseFab onPress={diagnose} /> : null}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={refresh} tintColor={colors.yellow} colors={[colors.onYellow]} progressBackgroundColor={colors.yellow} />
      }>
      {header}
      <LightStrip lights={lit} igniteKey={`${site.id}-${ignite}`} request={lightRequest} onDiagnose={canManage && !stale ? diagnose : undefined} />

      <Card style={styles.verdict}>
        <Perforation />
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
              onPress={() => openProblem(p)}
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

      <SectionLabel>Report</SectionLabel>
      <Pressable
        onPress={() => router.push({ pathname: '/report', params: { site: site.id } })}
        accessibilityRole="button"
        accessibilityLabel="Network report. A PDF with the chart, devices, outages and security advice."
        style={({ pressed }) => [styles.row, pressed && styles.pressed]}>
        <View style={styles.rowText}>
          <Text role="title">Network report</Text>
          <Text role="bodySmall" color="text2">
            A PDF with the chart, devices, outages and security advice.
          </Text>
        </View>
        <Text role="label" color="yellow">
          PDF
        </Text>
      </Pressable>
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
          d="M15.9 5c-.17 0-.32.09-.41.23l-.07.15-5.18 11.65c-.16.29-.26.61-.26.96 0 1.11.9 2.01 2.01 2.01.96 0 1.77-.68 1.96-1.59l.01-.03L16.4 5.5c0-.28-.22-.5-.5-.5zM1 9l2 2c2.88-2.88 6.79-4.08 10.53-3.62l1.19-2.68C9.89 3.84 4.74 5.27 1 9zm20 2l2-2c-1.64-1.64-3.55-2.82-5.59-3.57l-.53 2.82c1.5.62 2.9 1.53 4.12 2.75zm-4 4l2-2c-.8-.8-1.7-1.42-2.66-1.89l-.55 2.92c.42.27.83.59 1.21.97zM5 13l2 2c1.13-1.13 2.56-1.79 4.03-2l1.28-2.88c-2.63-.08-5.3.87-7.31 2.88z"
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
        <Perforation />
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
        <Perforation />
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
      <SiteHeaderSkeleton />
      <LightStrip lights={UNLIT} igniteKey="skeleton" />
      <Card style={styles.loading}>
        <Loader label="Loading" />
      </Card>
    </Screen>
  );
}

const styles = StyleSheet.create({
  verdict: { paddingTop: space.s6, gap: space.s2, overflow: 'hidden' }, // clips the perforation
  meta: { flexDirection: 'row', alignItems: 'center', gap: space.s3, flexWrap: 'wrap' },
  loading: { alignItems: 'center', justifyContent: 'center', minHeight: size.loading },
  row: {
    minHeight: size.row,
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
});
