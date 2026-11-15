import { ComingNext } from '@/components/placeholder';
import { Screen, Text } from '@/components/ui';

export default function AlertsScreen() {
  return (
    <Screen>
      <Text role="headline" accessibilityRole="header">
        Alerts
      </Text>
      <ComingNext issue={61} what="Open and resolved alerts with acknowledge" />
    </Screen>
  );
}
