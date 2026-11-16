import { StyleSheet, View } from 'react-native';

import { colors, space } from '@/theme';

import { Text } from './text';

/** Label-value facts in a sheet (prototype): one top hairline, label left, bold value right. */
export function Facts({ rows }: { rows: [label: string, value: string][] }) {
  return (
    <View style={styles.facts}>
      {rows.map(([label, value]) => (
        <View key={label} style={styles.row}>
          <Text role="bodySmall" color="text2">
            {label}
          </Text>
          <View style={styles.value}>
            <Text role="bodySmall" align="right" strong tabular selectable>
              {value}
            </Text>
          </View>
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  facts: { gap: space.s2, paddingTop: space.s4, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.border },
  row: { flexDirection: 'row', alignItems: 'flex-start', gap: space.s4 },
  value: { flex: 1 },
});
