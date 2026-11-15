import { useEffect, useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import Animated, {
  Easing,
  useAnimatedProps,
  useReducedMotion,
  useSharedValue,
  withTiming,
} from 'react-native-reanimated';
import Svg, { Path } from 'react-native-svg';

import type { Deduction } from '@/api/circles';
import { Card, Text } from '@/components/ui';
import { colors, radius, space } from '@/theme';

const AnimatedPath = Animated.createAnimatedComponent(Path);
const ARC = 'M16 62 A40 40 0 0 1 96 62';
const ARC_LENGTH = 126; // half of a 40-unit circle, rounded up so the end cap is covered
const SWEEP_MS = 1_100;

/**
 * Health grade (briefs.md section 1): a yellow gauge whose arc sweeps while the score counts
 * up, the largest reason, and "Why this grade?" expanding every deduction in place.
 */
export function HealthCard({
  score,
  grade,
  summary,
  deductions,
  sweepKey,
}: {
  score: number;
  grade: string;
  summary: string;
  deductions: Deduction[];
  sweepKey: string;
}) {
  const reduce = useReducedMotion();
  const [open, setOpen] = useState(false);
  const progress = useSharedValue(reduce ? score / 100 : 0);
  const shown = useCountUp(score, reduce, sweepKey);

  useEffect(() => {
    const to = Math.max(0, Math.min(1, score / 100));
    progress.value = reduce ? to : withTiming(to, { duration: SWEEP_MS, easing: Easing.out(Easing.cubic) });
  }, [score, reduce, progress, sweepKey]);

  const arc = useAnimatedProps(() => ({ strokeDashoffset: ARC_LENGTH * (1 - progress.value) }));

  return (
    <Card>
      <View style={styles.top}>
        <Svg width={112} height={70} viewBox="0 0 112 70" accessible={false}>
          <Path d={ARC} fill="none" stroke={colors.unlit} strokeWidth={10} strokeLinecap="round" />
          <AnimatedPath
            d={ARC}
            fill="none"
            stroke={colors.yellow}
            strokeWidth={10}
            strokeLinecap="round"
            strokeDasharray={`${ARC_LENGTH} ${ARC_LENGTH}`}
            animatedProps={arc}
          />
        </Svg>
        <View style={styles.score} accessible accessibilityLabel={`Health ${score} out of 100, grade ${grade}. ${summary}`}>
          <View style={styles.number}>
            <Text role="display" tabular>
              {String(shown)}
            </Text>
            <Text role="bodySmall" color="text2" tabular>
              {` / 100 · ${grade}`}
            </Text>
          </View>
          <Text role="bodySmall" color="text2">
            {summary}
          </Text>
        </View>
      </View>
      <Pressable
        onPress={() => setOpen((o) => !o)}
        accessibilityRole="button"
        accessibilityState={{ expanded: open }}
        style={({ pressed }) => [styles.why, pressed && styles.pressed]}>
        <Text role="labelSmall" color="yellow">
          {open ? 'Hide the reasons' : 'Why this grade?'}
        </Text>
      </Pressable>
      {open ? (
        <View style={styles.deductions}>
          {deductions.length === 0 ? (
            <Row reason="No deductions: every factor is healthy." detail="" points={0} />
          ) : (
            deductions.map((d) => <Row key={d.factor} reason={d.reason} detail={d.detail} points={d.points} />)
          )}
        </View>
      ) : null}
    </Card>
  );
}

function Row({ reason, detail, points }: { reason: string; detail: string; points: number }) {
  return (
    <View style={styles.ded}>
      <View style={styles.dedText}>
        <Text role="body">{reason}</Text>
        {detail ? (
          <Text role="bodySmall" color="text2">
            {detail}
          </Text>
        ) : null}
      </View>
      <Text role="title" color={points ? 'orange' : 'green'} tabular>
        {points ? `−${points}` : '0'}
      </Text>
    </View>
  );
}

/** Counts from 0 to `to` with an ease-out cubic; instant under Reduce Motion. */
function useCountUp(to: number, reduce: boolean, key: string): number {
  const [value, setValue] = useState(0);
  useEffect(() => {
    if (reduce) return;
    const start = Date.now();
    let frame = 0;
    const step = () => {
      const p = Math.min(1, (Date.now() - start) / SWEEP_MS);
      setValue(Math.round(to * (1 - (1 - p) ** 3)));
      if (p < 1) frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [to, reduce, key]);
  return reduce ? to : value;
}

const styles = StyleSheet.create({
  top: { flexDirection: 'row', alignItems: 'center', gap: space.s4 },
  score: { flex: 1, gap: 2 },
  number: { flexDirection: 'row', alignItems: 'baseline' },
  why: { alignSelf: 'flex-start', minHeight: 44, justifyContent: 'center', paddingHorizontal: space.s1, borderRadius: radius.pill },
  pressed: { opacity: 0.7 },
  deductions: { gap: space.s2 },
  ded: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: space.s3,
    backgroundColor: colors.raised,
    borderRadius: radius.row,
    padding: space.s4,
  },
  dedText: { flex: 1, gap: 2 },
});
