import { router } from 'expo-router';
import { Pressable, StyleSheet, View } from 'react-native';

import type { Device, Member } from '@/api/overview';
import { Card, Text } from '@/components/ui';
import { colors, radius, space } from '@/theme';

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  const letters =
    parts.length > 1
      ? parts[0][0] + parts[parts.length - 1][0]
      : (parts[0] ?? '?').slice(0, 2);
  return letters.toUpperCase();
}

/**
 * Your people (brand.md, people-first devices): each member with how many of their devices are
 * online. Tapping one opens Devices. Avatars never use the status colours.
 */
export function People({
  members,
  devices,
  stale = false,
}: {
  members: Member[];
  devices: Device[];
  stale?: boolean;
}) {
  // While the agent is offline, online flags are old: show only how many devices each has.
  const count = (list: Device[]) =>
    stale
      ? `${list.length} ${list.length === 1 ? 'device' : 'devices'}`
      : `${list.filter((d) => d.online).length} of ${list.length} online`;
  const owned = devices.filter((d) => d.owner);
  if (owned.length === 0) {
    return (
      <Card>
        <Text role='body' color='text2'>
          No devices belong to anyone here yet. Open a device in Devices and say
          whose it is.
        </Text>
      </Card>
    );
  }
  const shared = devices.filter((d) => !d.owner);
  return (
    <View style={styles.list}>
      {members.map((m) => {
        const mine = owned.filter((d) => d.owner?.user_id === m.user_id);
        const sub = mine.length ? count(mine) : 'No devices yet';
        return <Person key={m.user_id} name={m.display_name} sub={sub} />;
      })}
      {shared.length ? (
        <Person name='Shared' sub={count(shared)} shared />
      ) : null}
    </View>
  );
}

function Person({
  name,
  sub,
  shared,
}: {
  name: string;
  sub: string;
  shared?: boolean;
}) {
  return (
    <Pressable
      onPress={() => router.navigate('/devices')}
      accessibilityRole='button'
      accessibilityLabel={`${name}: ${sub}`}
      accessibilityHint='Opens Devices'
      style={({ pressed }) => [styles.person, pressed && styles.pressed]}
    >
      <View style={[styles.avatar, shared && styles.sharedAvatar]}>
        <Text role='labelSmall' color={shared ? 'text2' : 'onYellow'}>
          {shared ? 'ALL' : initials(name)}
        </Text>
      </View>
      <View style={styles.text}>
        <Text role='title' numberOfLines={1}>
          {name}
        </Text>
        <Text role='bodySmall' color='text2' tabular>
          {sub}
        </Text>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  list: { gap: space.item },
  person: {
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
  avatar: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: colors.yellow,
    alignItems: 'center',
    justifyContent: 'center',
  },
  sharedAvatar: { backgroundColor: colors.raised },
  text: { flex: 1, gap: 2 },
});
