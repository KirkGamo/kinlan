import { ComingNext } from '@/components/placeholder';
import { Screen, Text } from '@/components/ui';

export default function DevicesScreen() {
  return (
    <Screen>
      <Text role="headline" accessibilityRole="header">
        Devices
      </Text>
      <ComingNext issue={59} what="People, Status and Map views with the device sheet" />
    </Screen>
  );
}
