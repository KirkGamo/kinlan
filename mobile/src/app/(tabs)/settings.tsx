import { ComingNext } from '@/components/placeholder';
import { Screen, Text } from '@/components/ui';

export default function SettingsScreen() {
  return (
    <Screen>
      <Text role="headline" accessibilityRole="header">
        Settings
      </Text>
      <ComingNext issue={62} what="Members, invites, alert thresholds and the account sheet" />
    </Screen>
  );
}
