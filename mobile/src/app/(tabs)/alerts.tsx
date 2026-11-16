import { router } from 'expo-router';
import { useState } from 'react';
import { Pressable, RefreshControl, StyleSheet, View } from 'react-native';
import Animated, { FadeIn, LinearTransition, SlideOutRight, useReducedMotion } from 'react-native-reanimated';

import { useAcknowledge, useAlerts, type Alert } from '@/api/alerts';
import { useSites, type Circle, type Site } from '@/api/circles';
import { selectSite, useCurrentCircle, useSelectedSite } from '@/api/selection';
import { Button, Card, Loader, Screen, Segmented, StatusChip, Text, type ChipTone } from '@/components/ui';
import { ago, clock } from '@/features/overview/model';
import { SiteHeader } from '@/features/overview/site-header';
import { useNow } from '@/hooks/use-now';
import { haptics } from '@/haptics';
import { colors, motion, radius, space } from '@/theme';

/** Severity as icon + word (never colour alone); "back online" reads as good news. */
function severity(a: Alert): { tone: ChipTone; label: string } {
  if (a.type === 'back_online') return { tone: 'ok', label: 'Back online' };
  if (a.severity === 'critical') return { tone: 'down', label: 'Critical' };
  if (a.severity === 'warning') return { tone: 'new', label: 'Warning' };
  return { tone: 'neutral', label: 'Info' };
}

/** Where tapping an alert goes: the device it's about, or Diagnose for connection problems. */
function deviceOf(a: Alert): string | null {
  if (a.type !== 'new_device' && a.type !== 'risky_port') return null;
  return a.subject_ref?.split(':')[0] ?? null;
}

/**
 * Alerts (briefs.md section 5): what needs attention, newest first, Open then Resolved. Owners and
 * admins acknowledge; a new device or open port has Review. The server already suppresses
 * repeats within 30 minutes, so the list shows exactly what it sends.
 */
export default function AlertsScreen() {
  const { circles, circle } = useCurrentCircle();
  const sites = useSites(circle?.id);
  const site = useSelectedSite(sites.data);

  if (circles.isPending || sites.isPending) {
    return (
      <Screen>
        <Card style={styles.center}>
          <Loader label="Loading" />
        </Card>
      </Screen>
    );
  }
  if (circles.isError || sites.isError || !circle) {
    return (
      <Screen>
        <ErrorCard message={(circles.error ?? sites.error)?.message ?? 'Something went wrong.'} onRetry={() => void sites.refetch()} />
      </Screen>
    );
  }
  if (!site) {
    return (
      <Screen>
        <Text role="titleLarge" accessibilityRole="header">
          Alerts
        </Text>
        <Card>
          <Text role="body" color="text2">
            No alerts. Add a site and pair its agent, and KinLAN will tell you when something needs attention.
          </Text>
        </Card>
      </Screen>
    );
  }
  return <Feed key={site.id} circle={circle} site={site} sites={sites.data} />;
}

function Feed({ circle, site, sites }: { circle: Circle; site: Site; sites: Site[] }) {
  const open = useAlerts(site.id, 'open');
  const resolved = useAlerts(site.id, 'resolved');
  const ack = useAcknowledge(site.id);
  const now = useNow(30_000);
  const reduce = useReducedMotion();
  const [refreshing, setRefreshing] = useState(false);
  const [tab, setTab] = useState<'open' | 'resolved'>('open');
  const canManage = circle.role === 'owner' || circle.role === 'admin';

  const openItems = open.data?.pages.flatMap((p) => p.items) ?? [];
  const resolvedItems = resolved.data?.pages.flatMap((p) => p.items) ?? [];
  const sub = open.data ? (openItems.length ? `${openItems.length}${open.hasNextPage ? '+' : ''} open` : 'Nothing open') : 'Loading…';

  async function refresh() {
    haptics.tick(); // released past the pull threshold
    setRefreshing(true);
    await Promise.all([open.refetch(), resolved.refetch()]);
    setRefreshing(false);
  }

  const go = (a: Alert) => {
    const device = deviceOf(a);
    if (device) router.navigate({ pathname: '/devices', params: { device } });
    else if (canManage && a.type !== 'back_online') router.push({ pathname: '/diagnose', params: { site: a.site_id } });
    else router.navigate('/');
  };

  let body;
  if (open.isPending || resolved.isPending) {
    body = (
      <Card style={styles.center}>
        <Loader label="Loading alerts" />
      </Card>
    );
  } else if (open.isError || resolved.isError) {
    body = <ErrorCard message={(open.error ?? resolved.error)?.message ?? ''} onRetry={() => void refresh()} />;
  } else if (!openItems.length && !resolvedItems.length) {
    body = (
      <Card>
        <StatusChip tone="ok" label="All clear" />
        <Text role="body" color="text2">
          No alerts. KinLAN will tell you when something needs attention.
        </Text>
      </Card>
    );
  } else if (tab === 'open') {
    body = (
      <>
        {openItems.length ? (
          openItems.map((a) => (
            <Animated.View key={a.id} exiting={reduce ? undefined : SlideOutRight.duration(motion.screen)} layout={reduce ? undefined : LinearTransition.duration(motion.small)}>
              <AlertCard a={a} now={now} onOpen={() => go(a)}>
                {/* One action per card (prototype): a device alert is reviewed (trusting the
                    device resolves it); anything else is acknowledged. */}
                {!canManage ? null : deviceOf(a) ? (
                  <Button label="Review" variant="ghost" onPress={() => go(a)} accessibilityHint="Opens the device to say whose it is or trust it" />
                ) : (
                  <Button
                    label="Acknowledge"
                    variant="ghost"
                    loading={ack.isPending && ack.variables === a.id}
                    onPress={() => ack.mutate(a.id)}
                    accessibilityHint="Marks it as seen and moves it to Resolved"
                  />
                )}
              </AlertCard>
            </Animated.View>
          ))
        ) : (
          <Card>
            <StatusChip tone="ok" label="All clear" />
            <Text role="body" color="text2">
              Nothing needs attention right now.
            </Text>
          </Card>
        )}
        {open.hasNextPage ? <Button label="Show older open alerts" variant="ghost" loading={open.isFetchingNextPage} onPress={() => void open.fetchNextPage()} /> : null}
        {ack.isError ? (
          <Text role="bodySmall" color="red" accessibilityRole="alert">
            {ack.error.message}
          </Text>
        ) : null}
      </>
    );
  } else {
    body = resolvedItems.length ? (
      <>
        {resolvedItems.map((a) => (
          <Animated.View key={a.id} entering={reduce ? undefined : FadeIn.duration(motion.small)}>
            <AlertCard a={a} now={now} onOpen={() => go(a)} ended={ending(a)} />
          </Animated.View>
        ))}
        {resolved.hasNextPage ? (
          <Button label="Show older" variant="ghost" loading={resolved.isFetchingNextPage} onPress={() => void resolved.fetchNextPage()} />
        ) : null}
      </>
    ) : (
      <Card>
        <Text role="body" color="text2">
          Nothing resolved yet. Acknowledged and cleared alerts move here.
        </Text>
      </Card>
    );
  }

  return (
    <Screen refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} tintColor={colors.yellow} colors={[colors.onYellow]} progressBackgroundColor={colors.yellow} />}>
      <SiteHeader title="Alerts" site={site} sites={sites} sub={sub} onSwitch={selectSite} />
      {open.data && resolved.data && (openItems.length || resolvedItems.length) ? (
        <Segmented
          label="Show alerts"
          options={[
            { key: 'open', label: `Open (${openItems.length}${open.hasNextPage ? '+' : ''})` },
            { key: 'resolved', label: 'Resolved' },
          ]}
          value={tab}
          onChange={setTab}
        />
      ) : null}
      {body}
    </Screen>
  );
}

/** How a resolved alert ended: the server resolved it, or someone acknowledged it. */
function ending(a: Alert): string {
  if (a.resolved_at) return `Resolved ${day(a.resolved_at)}`;
  if (a.acked_at) return `Acknowledged ${day(a.acked_at)}`;
  return '';
}

function day(iso: string): string {
  const d = new Date(iso);
  return d.toDateString() === new Date().toDateString()
    ? clock(iso)
    : `${d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}, ${clock(iso)}`;
}

/** Text above a footer with the chip (left) and actions (right), so actions never squeeze it. */
function AlertCard({
  a,
  now,
  onOpen,
  ended,
  children,
}: {
  a: Alert;
  now: number;
  onOpen: () => void;
  ended?: string;
  children?: React.ReactNode;
}) {
  const sev = severity(a);
  return (
    <View style={[styles.card, ended ? styles.resolved : null]}>
      <Pressable
        onPress={onOpen}
        accessibilityRole="button"
        accessibilityLabel={`${sev.label}: ${a.title}. ${a.body} ${ended ?? ''}`}
        style={({ pressed }) => [styles.text, pressed && styles.pressed]}>
        <Text role="title">{a.title}</Text>
        <Text role="bodySmall" color="text2">
          {a.body}
        </Text>
        <Text role="bodySmall" color="text2" tabular>
          {ended ? `${ago(a.created_at, now)} · ${ended}` : ago(a.created_at, now)}
        </Text>
      </Pressable>
      <View style={styles.footer}>
        <StatusChip tone={sev.tone} label={sev.label} />
        {children ? <View style={styles.actions}>{children}</View> : null}
      </View>
    </View>
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
  center: { minHeight: 120, alignItems: 'center', justifyContent: 'center' },
  card: {
    backgroundColor: colors.card,
    borderRadius: radius.row,
    borderCurve: 'continuous',
    padding: space.s4,
    gap: space.s3,
  },
  resolved: { opacity: 0.8 },
  text: { gap: 2, borderRadius: 12 },
  pressed: { opacity: 0.7 },
  footer: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: space.s3, flexWrap: 'wrap' },
  actions: { flexDirection: 'row', gap: space.s2, flexShrink: 1 },
});
