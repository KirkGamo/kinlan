import { StyleSheet, View } from 'react-native';
import Svg, { Path } from 'react-native-svg';

import { colors, radius, space, tints } from '@/theme';

import { Text } from './text';

/**
 * Status is never colour alone (PRODUCT.md): every chip has a drawn icon and a word.
 * Icons: check (healthy), dot (new or waiting), triangle (down), dash (offline or unknown).
 */
const ICONS = {
  check: 'M9 16.17 4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z',
  dot: 'M12 7a5 5 0 1 0 0 10 5 5 0 0 0 0-10z',
  triangle: 'M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z',
  dash: 'M19 13H5v-2h14v2z',
} as const;

export type ChipTone = 'ok' | 'new' | 'down' | 'neutral';

const TONE = {
  ok: { fg: colors.green, bg: tints.green, icon: ICONS.check },
  new: { fg: colors.orange, bg: tints.orange, icon: ICONS.dot },
  down: { fg: colors.red, bg: tints.red, icon: ICONS.triangle },
  neutral: { fg: colors.text2, bg: colors.raised, icon: ICONS.dash },
} as const;

export function StatusChip({ tone, label }: { tone: ChipTone; label: string }) {
  const t = TONE[tone];
  return (
    <View style={[styles.chip, { backgroundColor: t.bg }]} accessible accessibilityLabel={label}>
      <Svg width={14} height={14} viewBox="0 0 24 24">
        <Path d={t.icon} fill={t.fg} />
      </Svg>
      <Text role="labelSmall" color={tone === 'ok' ? 'green' : tone === 'new' ? 'orange' : tone === 'down' ? 'red' : 'text2'}>
        {label}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  chip: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    gap: space.s1,
    minHeight: 26,
    paddingLeft: space.s2,
    paddingRight: 10,
    borderRadius: radius.pill,
  },
});
