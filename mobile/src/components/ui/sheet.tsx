import { useEffect, useState, type ReactNode } from 'react';
import { Keyboard, Modal, Pressable, ScrollView, StyleSheet, useWindowDimensions, View } from 'react-native';
import { GestureDetector, GestureHandlerRootView, usePanGesture } from 'react-native-gesture-handler';
import Animated, {
  FadeIn,
  FadeOut,
  SlideInDown,
  SlideOutDown,
  useAnimatedStyle,
  useReducedMotion,
  useSharedValue,
  withSpring,
  withTiming,
} from 'react-native-reanimated';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import Svg, { Path } from 'react-native-svg';
import { scheduleOnRN } from 'react-native-worklets';

import { haptics } from '@/haptics';
import { colors, motion, radius, scrim, space } from '@/theme';

import { Text } from './text';

/**
 * A bottom sheet over a fading scrim (direction.md motion: 350 ms decelerate). Closes with the
 * close button, a tap on the scrim, Esc on web, the Android back gesture, or a drag down on the
 * handle and title: past 30% of its height, or a quick flick, it closes (with a tick as it crosses
 * that point); otherwise it springs back. The body keeps its own scrolling.
 */
export function Sheet({
  open,
  onClose,
  title,
  icon,
  meta,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  /** A 24-unit icon path, drawn in a raised tile beside the title (prototype). */
  icon?: string;
  /** A line under the title: usually a status chip and a short fact. */
  meta?: ReactNode;
  children: ReactNode;
}) {
  const insets = useSafeAreaInsets();
  const { height } = useWindowDimensions();
  const drag = useSheetDrag(open, onClose);
  // The sheet rides on top of the keyboard, and its body shrinks so the head stays on screen.
  // (Keyboard events, not Reanimated's keyboard hook: that one can't see a Modal's keyboard.)
  const keyboard = useKeyboardHeight(open);
  const lift = { paddingBottom: keyboard };
  const bodyHeight = { maxHeight: Math.max(160, height * 0.72 - keyboard) };
  return (
    <Modal visible={open} transparent animationType="none" onRequestClose={onClose} statusBarTranslucent>
      {open ? (
        <GestureHandlerRootView style={styles.root}>
          <View style={[styles.root, lift]}>
          <Animated.View entering={FadeIn.duration(motion.screen)} exiting={FadeOut.duration(motion.small)} style={StyleSheet.absoluteFill}>
            <Animated.View style={[StyleSheet.absoluteFill, drag.scrimStyle]}>
              <Pressable style={styles.scrim} onPress={onClose} accessibilityLabel="Close" accessibilityRole="button" />
            </Animated.View>
          </Animated.View>
          <Animated.View
            entering={SlideInDown.duration(motion.screen).easing(motion.easing.decelerate)}
            exiting={SlideOutDown.duration(motion.small)}
            accessibilityViewIsModal
            onLayout={drag.onLayout}
            style={[styles.sheet, { paddingBottom: space.card + insets.bottom }, drag.sheetStyle]}>
            <GestureDetector gesture={drag.pan}>
              <View style={styles.grab}>
                <View style={styles.handle} />
                <View style={styles.head}>
                  {icon ? (
                    <View style={styles.iconTile}>
                      <Svg width={26} height={26} viewBox="0 0 24 24">
                        <Path d={icon} fill={colors.text} />
                      </Svg>
                    </View>
                  ) : null}
                  <View style={styles.title}>
                    <Text role="titleLarge" accessibilityRole="header">
                      {title}
                    </Text>
                    {meta ? <View style={styles.meta}>{meta}</View> : null}
                  </View>
                  <Pressable onPress={onClose} accessibilityRole="button" accessibilityLabel="Close" hitSlop={8} style={({ pressed }) => [styles.close, pressed && styles.pressed]}>
                    <Svg width={20} height={20} viewBox="0 0 24 24">
                      <Path d="M19 6.41 17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z" fill={colors.text} />
                    </Svg>
                  </Pressable>
                </View>
              </View>
            </GestureDetector>
            <ScrollView style={bodyHeight} contentContainerStyle={styles.body} keyboardShouldPersistTaps="handled">
              {children}
            </ScrollView>
          </Animated.View>
          </View>
        </GestureHandlerRootView>
      ) : null}
    </Modal>
  );
}

/** The keyboard's height while it's up and this sheet is open; 0 otherwise. */
function useKeyboardHeight(open: boolean): number {
  const [h, setH] = useState(0);
  useEffect(() => {
    if (!open) return;
    const show = Keyboard.addListener('keyboardDidShow', (e) => setH(e.endCoordinates.height));
    const hide = Keyboard.addListener('keyboardDidHide', () => setH(0));
    return () => {
      show.remove();
      hide.remove();
      setH(0);
    };
  }, [open]);
  return h;
}

/** Past this share of the sheet's height, or faster than FLING, a drag closes the sheet. */
const CLOSE_AT = 0.3;
const FLING = 1000;
const OUT_MS = motion.small;
const BACK_MS = motion.reducedFade;

function useSheetDrag(open: boolean, onClose: () => void) {
  const reduce = useReducedMotion();
  const y = useSharedValue(0);
  const sheetHeight = useSharedValue(400);
  const past = useSharedValue(false);

  useEffect(() => {
    if (open) {
      y.set(0);
      past.set(false);
    }
  }, [open, y, past]);

  const pan = usePanGesture({
    activeOffsetY: [-8, 8],
    failOffsetX: [-24, 24],
    onUpdate: (e) => {
      'worklet';
      y.set(Math.max(0, e.translationY));
      const now = y.get() > sheetHeight.get() * CLOSE_AT;
      if (now !== past.get()) {
        past.set(now);
        if (now) scheduleOnRN(haptics.tick);
      }
    },
    onDeactivate: (e) => {
      'worklet';
      if (y.get() > sheetHeight.get() * CLOSE_AT || e.velocityY > FLING) {
        y.set(
          withTiming(sheetHeight.get(), { duration: OUT_MS }, (done) => {
            if (done) scheduleOnRN(onClose);
          }),
        );
      } else {
        y.set(reduce ? withTiming(0, { duration: BACK_MS }) : withSpring(0, { damping: 22, stiffness: 260 }));
      }
      past.set(false);
    },
  });

  const sheetStyle = useAnimatedStyle(() => ({ transform: [{ translateY: y.get() }] }));
  const scrimStyle = useAnimatedStyle(() => ({ opacity: 1 - Math.min(1, y.get() / Math.max(1, sheetHeight.get())) }));
  const onLayout = (e: { nativeEvent: { layout: { height: number } } }) => {
    sheetHeight.set(e.nativeEvent.layout.height);
  };
  return { pan, sheetStyle, scrimStyle, onLayout };
}

const styles = StyleSheet.create({
  root: { flex: 1, justifyContent: 'flex-end' },
  grab: { gap: space.s3 },
  scrim: { flex: 1, backgroundColor: scrim },
  sheet: {
    backgroundColor: colors.card,
    borderTopLeftRadius: radius.sheet,
    borderTopRightRadius: radius.sheet,
    borderCurve: 'continuous',
    padding: space.card,
    gap: space.s3,
    width: '100%',
    maxWidth: 560,
    alignSelf: 'center',
  },
  handle: { alignSelf: 'center', width: 36, height: 4, borderRadius: 2, backgroundColor: colors.raised, marginTop: -8 },
  head: { flexDirection: 'row', alignItems: 'center', gap: space.s4 },
  iconTile: {
    width: 52,
    height: 52,
    borderRadius: 18,
    borderCurve: 'continuous',
    backgroundColor: colors.raised,
    alignItems: 'center',
    justifyContent: 'center',
  },
  meta: { flexDirection: 'row', alignItems: 'center', gap: space.s2, flexWrap: 'wrap', marginTop: 6 },
  body: { gap: space.s3 },
  title: { flex: 1, gap: 0 },
  close: {
    width: 44,
    height: 44,
    borderRadius: radius.pill,
    backgroundColor: colors.raised,
    alignItems: 'center',
    justifyContent: 'center',
  },
  pressed: { opacity: 0.7 },
});
