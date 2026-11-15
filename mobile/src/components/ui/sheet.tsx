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
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
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
            <View style={styles.head}>
              <View style={styles.title}>
                <Text role="titleLarge" accessibilityRole="header">
                  {title}
                </Text>
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
  head: { flexDirection: 'row', alignItems: 'center', gap: space.s3 },
  body: { gap: space.s3 },
  title: { flex: 1 },
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
