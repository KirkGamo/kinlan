import { useEffect } from 'react';
import { Text as RNText, StyleSheet, View } from 'react-native';
import Animated, {
  useAnimatedStyle,
  useReducedMotion,
  useSharedValue,
  withDelay,
  withRepeat,
  withSequence,
  withTiming,
} from 'react-native-reanimated';
import Svg, { Circle } from 'react-native-svg';

import { colors, FONT_FAMILY, motion, space } from '@/theme';

/** The KinLAN mark: five status lights bent into an arc (docs/design/brand.md). */
const ARC: [number, number][] = [
  [14, 51.4],
  [34.6, 35.6],
  [60, 30],
  [85.4, 35.6],
  [106, 51.4],
];

export function Mark({ width = 120 }: { width?: number }) {
  return (
    <Svg width={width} height={(width * 50) / 120} viewBox="0 16 120 50" accessibilityElementsHidden>
      {ARC.map(([cx, cy]) => (
        <Circle key={cx} cx={cx} cy={cy} r={9} fill={colors.yellow} />
      ))}
    </Svg>
  );
}

/**
 * "kin" + "LAN" (brand.md section 2): the logo, so it keeps its own proportions instead of a
 * type role. "LAN" is about half the height of "kin", in yellow, widely tracked.
 */
export function Wordmark({ size = 44 }: { size?: number }) {
  return (
    <View style={styles.wordmark} accessible accessibilityRole="header" accessibilityLabel="KinLAN">
      <RNText style={[styles.kin, { fontSize: size, lineHeight: size * 1.1, letterSpacing: -size * 0.036 }]}>
        kin
      </RNText>
      <RNText style={[styles.lan, { fontSize: size * 0.52, letterSpacing: size * 0.11 }]}>LAN</RNText>
    </View>
  );
}

function Dot({ index, color }: { index: number; color: string }) {
  const reduce = useReducedMotion();
  const lit = useSharedValue(0);
  useEffect(() => {
    if (reduce) return;
    lit.value = withDelay(
      index * motion.lightStagger,
      withRepeat(withSequence(withTiming(1, { duration: 200 }), withTiming(0, { duration: 700 })), -1),
    );
  }, [index, lit, reduce]);
  const style = useAnimatedStyle(() => ({ opacity: 0.35 + lit.value * 0.65 }));
  return <Animated.View style={[styles.dot, { backgroundColor: color }, reduce ? styles.dotStill : style]} />;
}

/**
 * Loading: five lights blinking in sequence instead of a spinner (brand.md section 6). Yellow by
 * default; on a yellow button they take the button's black (`onYellow`) so they stay visible.
 */
export function Loader({ label = 'Loading', color = colors.yellow }: { label?: string; color?: string }) {
  return (
    <View style={styles.loader} accessibilityRole="progressbar" accessibilityLabel={label}>
      {[0, 1, 2, 3, 4].map((i) => (
        <Dot key={i} index={i} color={color} />
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  wordmark: { flexDirection: 'row', alignItems: 'baseline', justifyContent: 'center', gap: space.s1 },
  kin: { fontFamily: FONT_FAMILY, fontWeight: '800', color: colors.text },
  lan: { fontFamily: FONT_FAMILY, fontWeight: '800', color: colors.yellow },
  loader: { flexDirection: 'row', gap: 6, alignItems: 'center', justifyContent: 'center' },
  dot: { width: 8, height: 8, borderRadius: 4 },
  dotStill: { opacity: 0.8 },
});
