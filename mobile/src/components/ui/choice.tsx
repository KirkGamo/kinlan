import { Pressable, ScrollView, StyleSheet, View } from 'react-native';

import { colors, radius, space } from '@/theme';

import { Text } from './text';

/** A segmented switch (People | Status | Map): the selected segment is the yellow pill. */
export function Segmented<K extends string>({
  options,
  value,
  onChange,
  label,
}: {
  options: { key: K; label: string }[];
  value: K;
  onChange: (key: K) => void;
  label: string;
}) {
  return (
    <View style={styles.segmented} accessibilityRole="tablist" accessibilityLabel={label}>
      {options.map((o) => {
        const on = o.key === value;
        return (
          <Pressable
            key={o.key}
            onPress={() => onChange(o.key)}
            accessibilityRole="tab"
            accessibilityLabel={o.label}
            accessibilityState={{ selected: on }}
            style={[styles.segment, on && styles.segmentOn]}>
            <Text role="labelSmall" color={on ? 'onYellow' : 'text2'}>
              {o.label}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}

/** A row of toggle chips (filters, "Whose is this?", device type); one is selected. */
export function Chips<K extends string>({
  options,
  value,
  onChange,
  label,
  disabled,
}: {
  options: { key: K; label: string }[];
  value: K | null;
  onChange: (key: K) => void;
  label: string;
  disabled?: boolean;
}) {
  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chips} accessibilityLabel={label}>
      {options.map((o) => {
        const on = o.key === value;
        return (
          <Pressable
            key={o.key}
            disabled={disabled}
            onPress={() => onChange(o.key)}
            accessibilityRole="button"
            accessibilityLabel={o.label}
            accessibilityState={{ selected: on, disabled }}
            style={({ pressed }) => [styles.chip, on && styles.chipOn, pressed && styles.pressed]}>
            <Text role="labelSmall" color={on ? 'onYellow' : 'text'}>
              {o.label}
            </Text>
          </Pressable>
        );
      })}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  segmented: {
    flexDirection: 'row',
    backgroundColor: colors.card,
    borderRadius: radius.pill,
    padding: space.s1,
    gap: space.s1,
  },
  segment: { flex: 1, minHeight: 40, alignItems: 'center', justifyContent: 'center', borderRadius: radius.pill },
  segmentOn: { backgroundColor: colors.yellow },
  chips: { gap: space.s2, paddingVertical: 2 },
  chip: {
    minHeight: 36,
    paddingHorizontal: space.s4,
    justifyContent: 'center',
    borderRadius: radius.pill,
    backgroundColor: colors.raised,
  },
  chipOn: { backgroundColor: colors.yellow },
  pressed: { opacity: 0.75 },
});
