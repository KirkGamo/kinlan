import { useEffect, type ReactNode } from 'react';
import { StyleSheet, View } from 'react-native';
import { GestureDetector, usePanGesture } from 'react-native-gesture-handler';
import Animated, { useAnimatedStyle, useReducedMotion, useSharedValue, withSpring, withTiming } from 'react-native-reanimated';
import Svg, { Path } from 'react-native-svg';
import { scheduleOnRN } from 'react-native-worklets';

import { Text } from '@/components/ui';
import { haptics } from '@/haptics';
import { colors, motion, radius, space } from '@/theme';

/** Past this share of the card's width, letting go acknowledges. */
const ACK_AT = 0.4;
const OUT_MS = motion.small;
const BACK_MS = motion.reducedFade;

/**
 * Swipe an open alert to the right to acknowledge it: a check and "Acknowledge" show underneath,
 * a tick marks the point past which letting go counts, and the card slides out. A shortcut only:
 * the card's Acknowledge button and its TalkBack action do the same. `failed` brings it back.
 */
export function SwipeToAck({ onAck, failed, children }: { onAck: () => void; failed: boolean; children: ReactNode }) {
  const reduce = useReducedMotion();
  const x = useSharedValue(0);
  const width = useSharedValue(360);
  const past = useSharedValue(false);

  useEffect(() => {
    if (failed) x.set(withTiming(0, { duration: BACK_MS }));
  }, [failed, x]);

  const pan = usePanGesture({
    activeOffsetX: [-12, 12],
    failOffsetY: [-10, 10], // vertical movement belongs to the list's scroll
    onUpdate: (e) => {
      'worklet';
      x.set(Math.max(0, e.translationX));
      const now = x.get() > width.get() * ACK_AT;
      if (now !== past.get()) {
        past.set(now);
        if (now) scheduleOnRN(haptics.tick);
      }
    },
    onDeactivate: () => {
      'worklet';
      if (x.get() > width.get() * ACK_AT) {
        x.set(withTiming(width.get(), { duration: OUT_MS }));
        scheduleOnRN(onAck);
      } else {
        x.set(reduce ? withTiming(0, { duration: BACK_MS }) : withSpring(0, { damping: 22, stiffness: 260 }));
      }
      past.set(false);
    },
  });

  const card = useAnimatedStyle(() => ({ transform: [{ translateX: x.get() }] }));
  const under = useAnimatedStyle(() => ({ opacity: Math.min(1, x.get() / Math.max(1, width.get() * ACK_AT)) }));

  return (
    <View
      onLayout={(e) => {
        width.set(e.nativeEvent.layout.width);
      }}>
      <Animated.View style={[styles.under, under]} importantForAccessibility="no-hide-descendants">
        <Svg width={20} height={20} viewBox="0 0 24 24">
          <Path d="M9 16.17 4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z" fill={colors.text} />
        </Svg>
        <Text role="labelSmall">Acknowledge</Text>
      </Animated.View>
      <GestureDetector gesture={pan}>
        <Animated.View style={card}>{children}</Animated.View>
      </GestureDetector>
    </View>
  );
}

const styles = StyleSheet.create({
  under: {
    position: 'absolute',
    top: 0,
    right: 0,
    bottom: 0,
    left: 0,
    backgroundColor: colors.raised,
    borderRadius: radius.row, // the alert card's corners
    borderCurve: 'continuous',
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.s2,
    paddingHorizontal: space.card,
  },
});
