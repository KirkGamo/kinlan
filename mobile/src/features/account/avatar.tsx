import { StyleSheet, View } from 'react-native';

import { Text } from '@/components/ui';
import { colors } from '@/theme';

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  const letters =
    parts.length > 1
      ? parts[0][0] + parts[parts.length - 1][0]
      : (parts[0] ?? '?').slice(0, 2);
  return letters.toUpperCase();
}

/** Initials on a circle (brand.md): you are yellow, everyone else is grey. Never a status colour. */
export function Avatar({ name, me, size = 40 }: { name: string; me?: boolean; size?: number }) {
  return (
    <View style={[styles.avatar, { width: size, height: size, borderRadius: size / 2 }, me ? styles.me : styles.other]}>
      <Text role="labelSmall" color={me ? 'onYellow' : 'text'}>
        {initials(name)}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  avatar: { alignItems: 'center', justifyContent: 'center' },
  me: { backgroundColor: colors.yellow },
  other: { backgroundColor: colors.raised },
});
