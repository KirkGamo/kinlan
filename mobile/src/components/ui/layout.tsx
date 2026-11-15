import type { ReactNode } from 'react';
import { ScrollView, StyleSheet, View, type ViewStyle } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { colors, radius, space } from '@/theme';

import { Text } from './text';

/** A tab screen: black ground, safe areas, the 16-dp gutter, and room under the tab bar. */
export function Screen({ children, scroll = true }: { children: ReactNode; scroll?: boolean }) {
  return (
    <SafeAreaView edges={['top']} style={styles.screen}>
      {scroll ? (
        <ScrollView contentContainerStyle={styles.content} contentInsetAdjustmentBehavior="automatic">
          {children}
        </ScrollView>
      ) : (
        <View style={styles.content}>{children}</View>
      )}
    </SafeAreaView>
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
