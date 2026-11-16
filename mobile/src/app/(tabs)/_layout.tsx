import { NativeTabs } from 'expo-router/native-tabs';

import { useOpenAlertCount } from '@/api/alerts';
import { haptics } from '@/haptics';
import { colors } from '@/theme';

/**
 * The four tabs on Android: a native Material 3 navigation bar, whose active indicator is the
 * yellow pill from the design (direction.md). Icons are Material Symbols via expo-symbols.
 */
export default function TabsLayout() {
  const open = useOpenAlertCount();
  return (
    <NativeTabs
      backgroundColor={colors.card}
      indicatorColor={colors.yellow}
      rippleColor={colors.raised}
      iconColor={{ default: colors.text2, selected: colors.onYellow }}
      labelStyle={{ default: { color: colors.text2 }, selected: { color: colors.text } }}
      badgeBackgroundColor={colors.red}
      badgeTextColor={colors.onRed}
      labelVisibilityMode="labeled"
      // A tick when the tab changes; pressing the tab you're on stays quiet.
      screenListeners={({ navigation }) => ({
        tabPress: () => {
          if (!navigation.isFocused()) haptics.tick();
        },
      })}>
      <NativeTabs.Trigger name="index">
        <NativeTabs.Trigger.Label>Overview</NativeTabs.Trigger.Label>
        <NativeTabs.Trigger.Icon md="home" />
      </NativeTabs.Trigger>
      <NativeTabs.Trigger name="devices">
        <NativeTabs.Trigger.Label>Devices</NativeTabs.Trigger.Label>
        <NativeTabs.Trigger.Icon md="devices" />
      </NativeTabs.Trigger>
      <NativeTabs.Trigger name="alerts">
        <NativeTabs.Trigger.Label>Alerts</NativeTabs.Trigger.Label>
        <NativeTabs.Trigger.Icon md="notifications" />
        <NativeTabs.Trigger.Badge hidden={open === 0}>{open > 99 ? '99+' : String(open)}</NativeTabs.Trigger.Badge>
      </NativeTabs.Trigger>
      <NativeTabs.Trigger name="settings">
        <NativeTabs.Trigger.Label>Settings</NativeTabs.Trigger.Label>
        <NativeTabs.Trigger.Icon md="settings" />
      </NativeTabs.Trigger>
    </NativeTabs>
  );
}
