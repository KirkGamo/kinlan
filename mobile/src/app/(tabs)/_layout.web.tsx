import { TabList, TabSlot, TabTrigger, Tabs, type TabTriggerSlotProps } from 'expo-router/ui';
import { Pressable, StyleSheet, View } from 'react-native';

import { Text } from '@/components/ui';
import { colors, radius, space, touch } from '@/theme';

/**
 * Web build: native tabs only have a basic web fallback, so the web layout uses headless tabs
 * from expo-router/ui with the same four destinations and the same yellow selected pill.
 */
export default function WebTabsLayout() {
  return (
    <Tabs>
      <TabSlot style={styles.slot} />
      <TabList asChild>
        <View style={styles.bar} role="tablist">
          <TabTrigger name="index" href="/" asChild>
            <TabButton label="Overview" />
          </TabTrigger>
          <TabTrigger name="devices" href="/devices" asChild>
            <TabButton label="Devices" />
          </TabTrigger>
          <TabTrigger name="alerts" href="/alerts" asChild>
            <TabButton label="Alerts" />
          </TabTrigger>
          <TabTrigger name="settings" href="/settings" asChild>
            <TabButton label="Settings" />
          </TabTrigger>
        </View>
      </TabList>
    </Tabs>
  );
}

// The trigger's ref is typed for a View, not a Pressable; tab switching doesn't need it.
type TabButtonProps = Omit<TabTriggerSlotProps, 'ref'> & { label: string };

function TabButton({ label, isFocused, ...props }: TabButtonProps) {
  return (
    <Pressable
      {...props}
      role="tab"
      aria-selected={isFocused}
      style={({ pressed }) => [styles.tab, pressed && styles.pressed]}>
      <View style={[styles.pill, isFocused && styles.pillOn]}>
        <Text role="labelSmall" color={isFocused ? 'onYellow' : 'text2'}>
          {label}
        </Text>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  slot: { flex: 1 },
  bar: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    backgroundColor: colors.card,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    paddingVertical: space.s2,
  },
  tab: { minHeight: touch.min, minWidth: 76, alignItems: 'center', justifyContent: 'center' },
  pressed: { opacity: 0.7 },
  pill: { paddingHorizontal: space.s4, paddingVertical: space.s2, borderRadius: radius.pill },
  pillOn: { backgroundColor: colors.yellow },
});
