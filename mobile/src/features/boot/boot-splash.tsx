import { useEffect, useState } from 'react';
import { StyleSheet, View } from 'react-native';
import Animated, {
  useAnimatedProps,
  useAnimatedStyle,
  useReducedMotion,
  useSharedValue,
  withDelay,
  withSequence,
  withTiming,
  type SharedValue,
} from 'react-native-reanimated';
import { scheduleOnRN } from 'react-native-worklets';
import Svg, { Circle } from 'react-native-svg';

import { Loader, Perforation, Text, Wordmark } from '@/components/ui';
import { colors, motion, space } from '@/theme';

const AnimatedCircle = Animated.createAnimatedComponent(Circle);

/** The mark's five lights (same arc as `Mark`), drawn 132 dp wide like the native splash. */
const ARC: [number, number][] = [
  [14, 51.4],
  [34.6, 35.6],
  [60, 30],
  [85.4, 35.6],
  [106, 51.4],
];
const MARK_W = 132;
const MARK_H = (MARK_W * 50) / 120;
const R = 9;

// brand.md section 6 and the prototype's splash(): a beat, the lights one by one, then the words.
const START_MS = 250;
const LIGHT_MS = 220;
const POP_MS = 130; // up to 1.18 and back, 260 ms in all
const WORDS_AT = START_MS + 5 * motion.lightStagger + 140;
const WORDS_MS = 420;
const TAG_DELAY = 120;
const PLAYED_AT = WORDS_AT + WORDS_MS; // the earliest the splash may leave
const SLOW_AT = PLAYED_AT + 1000; // still loading by now: show the loader under the words

/**
 * The cold-start splash (brand.md section 6). It takes over from the native splash, which shows
 * the same five lights unlit in the same place, lights them left to right, raises the wordmark
 * and tagline, and fades out once the app underneath has been drawn (`ready`). A fast start doesn't wait
 * for more than the ignition; a slow one keeps the lit mark and adds the loader. Reduce Motion:
 * the lights are already on and the words fade in. No haptics: nothing was tapped (DESIGN.md).
 */
export function BootSplash({
  ready,
  onShown,
  onPlayed,
  onDone,
}: {
  /** The app underneath has been drawn: fade out (once the ignition has played). */
  ready: boolean;
  /** The splash has drawn: hide the native one. */
  onShown: () => void;
  /** The lamps are lit and the words are in: the app may start mounting underneath. */
  onPlayed: () => void;
  onDone: () => void;
}) {
  const reduce = useReducedMotion();
  const lights = [useSharedValue(0), useSharedValue(0), useSharedValue(0), useSharedValue(0), useSharedValue(0)];
  const pops = [useSharedValue(1), useSharedValue(1), useSharedValue(1), useSharedValue(1), useSharedValue(1)];
  const words = useSharedValue(0);
  const tag = useSharedValue(0);
  const shown = useSharedValue(1);
  const texture = useSharedValue(0); // the native splash has no texture: fade it in, don't pop it
  const [played, setPlayed] = useState(false);
  const [slow, setSlow] = useState(false);

  useEffect(() => {
    texture.set(withTiming(1, { duration: reduce ? motion.reducedFade : START_MS }));
    if (reduce) {
      lights.forEach((l) => l.set(1));
      words.set(withTiming(1, { duration: motion.reducedFade }));
      tag.set(withTiming(1, { duration: motion.reducedFade }));
    } else {
      lights.forEach((l, i) => {
        const at = START_MS + (i + 1) * motion.lightStagger;
        l.set(withDelay(at, withTiming(1, { duration: LIGHT_MS, easing: motion.easing.standard })));
        pops[i].set(
          withDelay(
            at,
            withSequence(
              withTiming(1.18, { duration: POP_MS, easing: motion.easing.decelerate }),
              withTiming(1, { duration: POP_MS, easing: motion.easing.standard }),
            ),
          ),
        );
      });
      words.set(withDelay(WORDS_AT, withTiming(1, { duration: WORDS_MS, easing: motion.easing.decelerate })));
      tag.set(withDelay(WORDS_AT + TAG_DELAY, withTiming(1, { duration: WORDS_MS, easing: motion.easing.decelerate })));
    }
    const played = setTimeout(
      () => {
        setPlayed(true);
        onPlayed();
      },
      reduce ? motion.reducedFade : PLAYED_AT,
    );
    const slowTimer = setTimeout(() => setSlow(true), reduce ? motion.reducedFade + 1000 : SLOW_AT);
    return () => {
      clearTimeout(played);
      clearTimeout(slowTimer);
    };
    // Runs once, on the cold start this splash belongs to.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!ready || !played) return;
    const out = reduce ? motion.reducedFade : motion.screen;
    shown.set(
      withTiming(0, { duration: out, easing: motion.easing.accelerate }, (finished) => {
        if (finished) scheduleOnRN(onDone);
      }),
    );
  }, [ready, played, reduce, shown, onDone]);

  const fade = useAnimatedStyle(() => ({ opacity: shown.get() }));
  const textureStyle = useAnimatedStyle(() => ({ opacity: texture.get() }));
  const wordsStyle = useAnimatedStyle(() => ({ opacity: words.get(), transform: [{ translateY: (1 - words.get()) * 8 }] }));
  const tagStyle = useAnimatedStyle(() => ({ opacity: tag.get(), transform: [{ translateY: (1 - tag.get()) * 8 }] }));

  return (
    <Animated.View
      style={[styles.root, fade]}
      pointerEvents={ready && played ? 'none' : 'auto'}
      accessible
      accessibilityLabel="KinLAN. Your people, your network."
      accessibilityRole="progressbar"
      onLayout={onShown}>
      <Animated.View style={[StyleSheet.absoluteFill, textureStyle]} pointerEvents="none">
        <Perforation from="center" />
      </Animated.View>
      <View style={styles.mark}>
        <Svg width={MARK_W} height={MARK_H} viewBox="0 16 120 50">
          {ARC.map(([cx, cy], i) => (
            <Light key={cx} cx={cx} cy={cy} lit={lights[i]} pop={pops[i]} />
          ))}
        </Svg>
        <View style={styles.below}>
          <Animated.View style={wordsStyle}>
            <Wordmark />
          </Animated.View>
          <Animated.View style={tagStyle}>
            <Text role="body" color="text2" align="center">
              Your people, your network.
            </Text>
          </Animated.View>
          {slow && !ready ? (
            <View style={styles.loader}>
              <Loader label="Loading" />
            </View>
          ) : null}
        </View>
      </View>
    </Animated.View>
  );
}

/** One light: an unlit lamp with its ring, and the yellow light fading in over it with a pop. */
function Light({ cx, cy, lit, pop }: { cx: number; cy: number; lit: SharedValue<number>; pop: SharedValue<number> }) {
  const on = useAnimatedProps(() => ({ r: R * pop.get(), fillOpacity: lit.get() }));
  return (
    <>
      <Circle cx={cx} cy={cy} r={R - 1} fill={colors.unlit} stroke={colors.unlitRing} strokeWidth={2} />
      <AnimatedCircle cx={cx} cy={cy} fill={colors.yellow} animatedProps={on} />
    </>
  );
}

const styles = StyleSheet.create({
  root: { ...StyleSheet.absoluteFill, backgroundColor: colors.bg, alignItems: 'center', justifyContent: 'center', zIndex: 10 },
  // The mark sits at the exact centre, like the native splash image; the words hang below it.
  mark: { width: MARK_W, height: MARK_H },
  below: { position: 'absolute', top: MARK_H + space.s4, left: -120, right: -120, alignItems: 'center', gap: space.s4 },
  loader: { paddingTop: space.s4 },
});
