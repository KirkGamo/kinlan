import { useNavigation } from 'expo-router';
import { useEffect, useRef, type ReactElement, type ReactNode } from 'react';
import { ScrollView, StyleSheet, View, type RefreshControlProps, type ScrollViewInstance, type ViewStyle } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { colors, radius, space } from '@/theme';

import { Text } from './text';

/**
 * A tab screen: black ground, safe areas, the 16-dp gutter, and room under the tab bar.
 * Tapping its tab again scrolls back to the top; tapping it once more at the top calls
 * `onReselectAtTop` (Devices clears its filter).
 */
export function Screen({
  children,
  scroll = true,
  refreshControl,
  fab,
  onReselectAtTop,
}: {
  children: ReactNode;
  scroll?: boolean;
  refreshControl?: ReactElement<RefreshControlProps>;
  /** A floating action button, bottom-right above the tab bar (Overview's Diagnose). */
  fab?: ReactNode;
  onReselectAtTop?: () => void;
}) {
  const ref = useRef<ScrollViewInstance>(null);
  const y = useRef(0);
  const atTop = useRef(onReselectAtTop);
  useEffect(() => {
    atTop.current = onReselectAtTop;
  }, [onReselectAtTop]);
  const navigation = useNavigation();
  useEffect(() => {
    // Native tabs emit tabPress for a repeat tap too; only the focused tab's repeat counts.
    return navigation.addListener('tabPress' as never, () => {
      if (!navigation.isFocused()) return;
      if (y.current > 4) ref.current?.scrollTo({ y: 0, animated: true });
      else atTop.current?.();
    });
  }, [navigation]);

  // Insets from the provider, not a native SafeAreaView: those pad a frame late on mount, which
  // showed as the header jumping under the status bar when a loading screen gave way to content.
  const insets = useSafeAreaInsets();
  return (
    <View style={[styles.screen, { paddingTop: insets.top }]}>
      {scroll ? (
        <ScrollView
          ref={ref}
          onScroll={(e) => {
            y.current = e.nativeEvent.contentOffset.y;
          }}
          scrollEventThrottle={64}
          contentContainerStyle={styles.content}
          contentInsetAdjustmentBehavior="automatic"
          refreshControl={refreshControl}>
          {children}
        </ScrollView>
      ) : (
        <View style={styles.content}>{children}</View>
      )}
      {fab ? <View style={styles.fab}>{fab}</View> : null}
    </View>
  );
}

export function Card({ children, style }: { children: ReactNode; style?: ViewStyle }) {
  return <View style={[styles.card, style]}>{children}</View>;
}

/** Silkscreen section label: more space above a heading than below it. */
export function SectionLabel({ children, end }: { children: string; end?: string }) {
  return (
    <View style={styles.label}>
      <Text role="silk" color="text2">
        {children}
      </Text>
      {end ? (
        <Text role="silk" color="text2">
          {end}
        </Text>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.bg },
  fab: { position: 'absolute', right: space.gutter, bottom: space.gutter },
  content: {
    paddingHorizontal: space.gutter,
    paddingTop: space.s4,
    paddingBottom: space.section * 3,
    gap: space.s3,
  },
  card: {
    backgroundColor: colors.card,
    borderRadius: radius.card,
    borderCurve: 'continuous',
    padding: space.card,
    gap: space.s2,
  },
  label: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: space.section - space.s3,
    paddingHorizontal: space.s1,
  },
});
