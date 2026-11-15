import { router } from 'expo-router';
import { Pressable, StyleSheet, View } from 'react-native';

import { useCircles, useSites, type Site } from '@/api/circles';
import { ComingNext } from '@/components/placeholder';
import { Button, Card, Loader, Screen, SectionLabel, StatusChip, Text, type ChipTone } from '@/components/ui';
import { colors, radius, space } from '@/theme';

const STATUS: Record<Site['status'], { tone: ChipTone; label: string }> = {
  online: { tone: 'ok', label: 'Online' },
  degraded: { tone: 'new', label: 'Degraded' },
  unreachable: { tone: 'down', label: 'Unreachable' },
  pending: { tone: 'neutral', label: 'Not paired' },
};

/** Until the full Overview (#58): your Circle and its sites, with a way to pair or add one. */
export default function OverviewScreen() {
  const circles = useCircles();
  const circle = circles.data?.[0]; // the account sheet's Circle switcher arrives with #62
  const sites = useSites(circle?.id);
  const canManage = circle?.role === 'owner' || circle?.role === 'admin';

  return (
    <Screen>
      <View>
        <Text role="titleLarge" accessibilityRole="header">
          {circle?.name ?? 'Overview'}
        </Text>
        {circle ? (
          <Text role="bodySmall" color="text2">
            {`${circle.member_count} ${circle.member_count === 1 ? 'member' : 'members'} · you’re ${circle.role === 'admin' ? 'an' : 'the'} ${circle.role}`}
          </Text>
        ) : null}
      </View>

      <SectionLabel>Sites</SectionLabel>
      {sites.isPending ? (
        <Loader label="Loading sites" />
      ) : sites.isError ? (
        <Text role="bodySmall" color="red">
          {sites.error.message}
        </Text>
      ) : sites.data.length === 0 ? (
        <Card>
          <Text role="title">No sites yet</Text>
          <Text role="bodySmall" color="text2">
            A site is one network. Add one, then pair a PC on it.
          </Text>
        </Card>
      ) : (
        sites.data.map((site) => (
          <SiteRow key={site.id} site={site} canManage={canManage} />
        ))
      )}
      {canManage && circle ? (
        <Button
          label="Add a site"
          variant="ghost"
          onPress={() => router.push({ pathname: '/onboarding/new-site', params: { circle: circle.id } })}
        />
      ) : null}
      <ComingNext issue={58} what="Status lights, verdict, your people, health grade and the 24-hour chart" />
    </Screen>
  );
}

function SiteRow({ site, canManage }: { site: Site; canManage: boolean }) {
  const status = STATUS[site.status];
  const pair = site.status === 'pending' && canManage;
  return (
    <Pressable
      disabled={!pair}
      onPress={() => router.push({ pathname: '/onboarding/pair', params: { site: site.id } })}
      accessibilityRole={pair ? 'button' : undefined}
      accessibilityLabel={`${site.name}, ${status.label}${pair ? '. Pair the agent' : ''}`}
      style={({ pressed }) => [styles.row, pressed && styles.pressed]}>
      <View style={styles.rowText}>
        <Text role="title">{site.name}</Text>
        <Text role="bodySmall" color="text2">
          {site.cidr ? `${site.cidr} · router ${site.gateway_ip ?? 'unknown'}` : 'Waiting for its agent'}
        </Text>
      </View>
      {pair ? (
        <Text role="labelSmall" color="yellow">
          Pair the agent
        </Text>
      ) : (
        <StatusChip tone={status.tone} label={status.label} />
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
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
  rowText: { flex: 1, gap: 2 },
});
