import type { ReactNode } from 'react';
import { Modal, Pressable, ScrollView, StyleSheet, useWindowDimensions, View } from 'react-native';
import Animated, { FadeIn, FadeOut, SlideInDown, SlideOutDown } from 'react-native-reanimated';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import Svg, { Path } from 'react-native-svg';

import { colors, motion, radius, space } from '@/theme';

import { Text } from './text';

/**
 * A bottom sheet over a fading scrim (direction.md motion: 350 ms decelerate). Closes with the
 * close button, a tap on the scrim, Esc on web, or the Android back gesture.
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
  return (
    <Modal visible={open} transparent animationType="none" onRequestClose={onClose} statusBarTranslucent>
      {open ? (
        <View style={styles.root}>
          <Animated.View entering={FadeIn.duration(motion.screen)} exiting={FadeOut.duration(motion.small)} style={StyleSheet.absoluteFill}>
            <Pressable style={styles.scrim} onPress={onClose} accessibilityLabel="Close" accessibilityRole="button" />
          </Animated.View>
          <Animated.View
            entering={SlideInDown.duration(motion.screen).easing(motion.easing.decelerate)}
            exiting={SlideOutDown.duration(motion.small)}
            accessibilityViewIsModal
            style={[styles.sheet, { paddingBottom: space.card + insets.bottom }]}>
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
            <ScrollView style={{ maxHeight: height * 0.72 }} contentContainerStyle={styles.body} keyboardShouldPersistTaps="handled">
              {children}
            </ScrollView>
          </Animated.View>
        </View>
      ) : null}
    </Modal>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, justifyContent: 'flex-end' },
  scrim: { flex: 1, backgroundColor: 'rgba(0, 0, 0, 0.6)' },
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
