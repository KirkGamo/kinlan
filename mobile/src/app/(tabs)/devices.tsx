import { router, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { Pressable, RefreshControl, StyleSheet, View } from 'react-native';

import { useSiteSummary, type Circle, type Site } from '@/api/circles';
import { useDevices, useMembers, type Device, type Member } from '@/api/overview';
import { selectSite, useTabData } from '@/api/selection';
import { Button, Card, Chips, ErrorCard, Loader, Screen, SectionLabel, Segmented, StatusChip, Text } from '@/components/ui';
import { DeviceMap } from '@/features/devices/device-map';
import { DeviceActions } from '@/features/devices/device-actions';
import { DeviceSheet } from '@/features/devices/device-sheet';
import { DeviceIcon } from '@/features/devices/icons';
import { chip, facts, FILTERS, matches, type Filter } from '@/features/devices/model';
import { isStale } from '@/features/overview/model';
import { Avatar } from '@/features/account/avatar';
import { useMe } from '@/api/session';
import { SiteHeader } from '@/features/overview/site-header';
import { useNow } from '@/hooks/use-now';
import { haptics } from '@/haptics';
import { colors, radius, space } from '@/theme';

type View_ = 'people' | 'status' | 'map';
const VIEWS: { key: View_; label: string }[] = [
  { key: 'people', label: 'People' },
  { key: 'status', label: 'Status' },
  { key: 'map', label: 'Map' },
];

/**
 * Devices (briefs.md section 2): "Who's on my network?" People, Status and Map views over the
 * same devices, filter chips, and the device sheet. Every action on the map is also in the lists.
 */
export default function DevicesScreen() {
  const tab = useTabData();
  if (tab.state === 'loading') {
    return (
      <Screen>
        <Card style={styles.center}>
          <Loader label="Loading" />
        </Card>
      </Screen>
    );
  }
  if (tab.state === 'error') {
    return (
      <Screen>
        <ErrorCard message={tab.message} onRetry={tab.retry} />
      </Screen>
    );
  }
  const { circle, sites, site, canManage } = tab;
  if (!site) {
    return (
      <Screen>
        <Text role="titleLarge" accessibilityRole="header">
          Devices
        </Text>
        <Card>
          <Text role="body" color="text2">
            No sites yet. Add a site on Overview, then pair a PC on it to see its devices.
          </Text>
        </Card>
      </Screen>
    );
  }
  if (site.status === 'pending') {
    return (
      <Screen>
        <SiteHeader title="Devices" site={site} sites={sites} sub="Not paired yet" onSwitch={selectSite} />
        <Card>
          <Text role="title">No devices yet</Text>
          <Text role="body" color="text2">
            {canManage
              ? 'Devices appear after the agent’s first scan. Pair a PC on this network first.'
              : 'Devices appear once an owner or admin pairs a PC on this network.'}
          </Text>
          {canManage ? (
            <Button label="Pair the agent" onPress={() => router.push({ pathname: '/onboarding/pair', params: { site: site.id } })} />
          ) : null}
        </Card>
      </Screen>
    );
  }
  return <Live key={site.id} circle={circle} site={site} sites={sites} canManage={canManage} />;
}

function Live({ circle, site, sites, canManage }: { circle: Circle; site: Site; sites: Site[]; canManage: boolean }) {
  const devices = useDevices(site.id);
  const members = useMembers(circle.id);
  const summary = useSiteSummary(site.id, true, 15_000);
  const now = useNow(10_000);
  const meId = useMe().data?.id;
  const [view, setView] = useState<View_>('people');
  const [filter, setFilter] = useState<Filter>('all');
  const [selected, setSelected] = useState<string | null>(null);
  const [pingOnOpen, setPingOnOpen] = useState(false);
  // Long-press (or a row's TalkBack action) opens quick actions; `rename` jumps to the form.
  const [actions, setActions] = useState<{ device: Device; rename: boolean } | null>(null);
  const open = (id: string, ping = false) => {
    setActions(null);
    setPingOnOpen(ping);
    setSelected(id);
  };
  // Links into Devices: ?device=… opens that device's sheet (an alert's Review, a push), and
  // ?filter=…&at=… sets the filter (Overview's "new devices to review"). `at` makes a repeat
  // tap of the same link apply again.
  const { device: asked, filter: askedFilter, at } = useLocalSearchParams<{ device?: string; filter?: Filter; at?: string }>();
  const [handled, setHandled] = useState<string | undefined>(undefined);
  if (asked && asked !== handled) {
    setHandled(asked);
    setSelected(asked);
  }
  const filterRequest = askedFilter && FILTERS.some((f) => f.key === askedFilter) ? `${askedFilter}-${at ?? ''}` : undefined;
  const [handledFilter, setHandledFilter] = useState<string | undefined>(undefined);
  if (filterRequest && filterRequest !== handledFilter) {
    setHandledFilter(filterRequest);
    setFilter(askedFilter as Filter);
  }
  const [refreshing, setRefreshing] = useState(false);

  const stale = summary.data ? isStale(summary.data, now) : false;
  const list = devices.data ?? [];
  const online = list.filter((d) => d.online).length;
  const fresh = list.filter((d) => d.needs_review).length;
  const sub = devices.data
    ? `${list.length} ${list.length === 1 ? 'device' : 'devices'}${stale ? '' : ` · ${online} online`}${fresh ? ` · ${fresh} new` : ''}`
    : 'Loading…';

  async function refresh() {
    haptics.tick(); // released past the pull threshold
    setRefreshing(true);
    await Promise.all([devices.refetch(), members.refetch(), summary.refetch()]);
    setRefreshing(false);
  }

  let body;
  if (devices.isPending || members.isPending) {
    body = (
      <Card style={styles.center}>
        <Loader label="Loading devices" />
      </Card>
    );
  } else if (devices.isError || members.isError) {
    body = <ErrorCard message={(devices.error ?? members.error)?.message ?? ''} onRetry={() => void refresh()} />;
  } else if (list.length === 0) {
    body = (
      <Card>
        <Text role="title">No devices found yet</Text>
        <Text role="body" color="text2">
          The agent scans the network every few minutes. Devices show up here after its first scan.
        </Text>
      </Card>
    );
  } else if (view === 'map') {
    body = (
      <DeviceMap
        devices={list}
        filter={filter}
        summary={summary.data}
        gatewayIp={site.gateway_ip}
        selectedId={selected}
        onSelect={setSelected}
        onMore={() => setView('status')}
        stale={stale}
      />
    );
  } else {
    const groups = view === 'people' ? byPerson(list, members.data ?? []) : byStatus(list);
    const shown = groups
      .map((g) => ({ ...g, items: g.items.filter((d) => matches(d, filter)) }))
      .filter((g) => g.items.length > 0 || (g.person && filter === 'all'));
    body = shown.length ? (
      shown.map((g) => (
        <View key={g.key} style={styles.group}>
          {g.person ? (
            <PersonHeader name={g.title} items={g.items} stale={stale} me={g.key === meId} />
          ) : (
            <SectionLabel end={String(g.items.length)}>{g.title}</SectionLabel>
          )}
          {g.items.length ? (
            g.items.map((d) => (
              <DeviceRow
                key={d.id}
                d={d}
                stale={stale}
                onPress={() => open(d.id)}
                onActions={canManage ? (rename) => setActions({ device: d, rename }) : undefined}
                onPing={canManage ? () => open(d.id, true) : undefined}
              />
            ))
          ) : (
            <Text role="bodySmall" color="text2">
              No devices yet. Open one and choose them under “Whose is this?”.
            </Text>
          )}
        </View>
      ))
    ) : (
      <Card>
        <Text role="body" color="text2">
          No devices match this filter.
        </Text>
      </Card>
    );
  }

  return (
    <Screen
      onReselectAtTop={() => {
        // Tapping Devices again at the top clears the filter.
        if (filter === 'all') return;
        haptics.tick();
        setFilter('all');
      }}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} tintColor={colors.yellow} colors={[colors.onYellow]} progressBackgroundColor={colors.yellow} />}>
      <SiteHeader title="Devices" site={site} sites={sites} sub={sub} onSwitch={selectSite} />
      {stale ? (
        <Card style={styles.stale}>
          <StatusChip tone="neutral" label="Offline" />
          {/* flex: 1 lets the sentence wrap beside the chip instead of running off the card (Android). */}
          <View style={styles.staleText}>
            <Text role="bodySmall" color="text2">
              The agent isn’t reporting, so who’s online may be out of date.
            </Text>
          </View>
        </Card>
      ) : null}
      <Segmented label="Group devices by" options={VIEWS} value={view} onChange={setView} />
      <Chips label="Filter devices" variant="filter" options={FILTERS} value={filter} onChange={setFilter} />
      {body}
      <DeviceSheet
        deviceId={selected}
        siteId={site.id}
        members={members.data ?? []}
        canManage={canManage}
        stale={stale}
        startPing={pingOnOpen}
        onClose={() => {
          setSelected(null);
          setPingOnOpen(false);
        }}
      />
      <DeviceActions
        device={actions?.device ?? null}
        rename={actions?.rename ?? false}
        siteId={site.id}
        members={members.data ?? []}
        stale={stale}
        onClose={() => setActions(null)}
        onPing={(id) => open(id, true)}
        onOpen={(id) => open(id)}
      />
    </Screen>
  );
}

type Group = { key: string; title: string; items: Device[]; person?: boolean };

/** Needs review first, then one group per member, then shared and unassigned. */
function byPerson(list: Device[], members: Member[]): Group[] {
  const review = list.filter((d) => d.needs_review);
  const rest = list.filter((d) => !d.needs_review);
  return [
    { key: 'review', title: 'Needs review', items: review },
    ...members.map((m) => ({ key: m.user_id, title: m.display_name, items: rest.filter((d) => d.owner?.user_id === m.user_id), person: true })),
    { key: 'shared', title: 'Shared and unassigned', items: rest.filter((d) => !d.owner) },
  ];
}

function byStatus(list: Device[]): Group[] {
  return [
    { key: 'review', title: 'Needs review', items: list.filter((d) => d.needs_review) },
    { key: 'online', title: 'Online', items: list.filter((d) => !d.needs_review && d.online) },
    { key: 'offline', title: 'Offline', items: list.filter((d) => !d.needs_review && !d.online) },
  ];
}

function PersonHeader({ name, items, stale, me }: { name: string; items: Device[]; stale: boolean; me: boolean }) {
  const on = items.filter((d) => d.online).length;
  return (
    <View style={styles.person}>
      <Avatar name={name} me={me} size={32} />
      <Text role="title">{name}</Text>
      <Text role="bodySmall" color="text2" tabular>
        {stale || !items.length ? `${items.length} ${items.length === 1 ? 'device' : 'devices'}` : `${on} of ${items.length} online`}
      </Text>
    </View>
  );
}

function DeviceRow({
  d,
  stale,
  onPress,
  onActions,
  onPing,
}: {
  d: Device;
  stale: boolean;
  onPress: () => void;
  /** Owners and admins: long-press opens quick actions (`true` opens on Rename). */
  onActions?: (rename: boolean) => void;
  onPing?: () => void;
}) {
  const st = chip(d, stale);
  const canPing = !!d.ip && !stale;
  return (
    <Pressable
      onPress={onPress}
      onLongPress={
        onActions
          ? () => {
              haptics.longPress();
              onActions(false);
            }
          : undefined
      }
      accessibilityRole="button"
      accessibilityLabel={`${d.display_name}, ${st.label}${d.trusted ? ', trusted' : ''}. ${facts(d)}`}
      accessibilityHint="Opens the device"
      // The same quick actions for TalkBack, where long-press isn't practical.
      accessibilityActions={
        onActions
          ? [
              { name: 'activate' },
              ...(onPing && canPing ? [{ name: 'ping', label: 'Ping test' }] : []),
              { name: 'actions', label: 'Quick actions' },
              { name: 'rename', label: 'Rename' },
            ]
          : undefined
      }
      onAccessibilityAction={(e) => {
        const name = e.nativeEvent.actionName;
        if (name === 'ping') onPing?.();
        else if (name === 'actions') onActions?.(false);
        else if (name === 'rename') onActions?.(true);
        else onPress();
      }}
      style={({ pressed }) => [styles.row, pressed && styles.pressed]}>
      <View style={styles.icon}>
        <DeviceIcon type={d.device_type} size={20} color={d.online && !stale ? colors.text : colors.text2} />
      </View>
      <View style={styles.rowText}>
        <Text role="title" numberOfLines={1}>
          {d.display_name}
        </Text>
        <Text role="bodySmall" color="text2" numberOfLines={1} tabular>
          {d.trusted ? `${facts(d)} · Trusted` : facts(d)}
        </Text>
      </View>
      <StatusChip tone={st.tone} label={st.label} />
    </Pressable>
  );
}


const styles = StyleSheet.create({
  center: { minHeight: 120, alignItems: 'center', justifyContent: 'center' },
  stale: { flexDirection: 'row', alignItems: 'center', gap: space.s3, paddingVertical: space.s3 },
  staleText: { flex: 1 },
  group: { gap: space.item },
  person: { flexDirection: 'row', alignItems: 'center', gap: space.s3, marginTop: space.s5, paddingHorizontal: space.s1 },
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
  icon: { width: 40, height: 40, borderRadius: 20, backgroundColor: colors.raised, alignItems: 'center', justifyContent: 'center' },
  rowText: { flex: 1, gap: 2 },
});
