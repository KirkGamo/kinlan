import { API_URL } from '@/api/client';
import { useApiHealth } from '@/api/health';
import { ComingNext } from '@/components/placeholder';
import { Card, Screen, SectionLabel, Text } from '@/components/ui';

export default function OverviewScreen() {
  const health = useApiHealth();
  const status = health.isPending
    ? 'Checking the KinLAN API…'
    : health.isError
      ? "Can't reach the KinLAN API right now."
      : `Connected · API ${health.data.version}`;

  return (
    <Screen>
      <Text role="headline" accessibilityRole="header">
        Overview
      </Text>
      <SectionLabel>Connection</SectionLabel>
      <Card>
        <Text role="title" color={health.isError ? 'red' : 'text'}>
          {status}
        </Text>
        <Text role="bodySmall" color="text2">
          {API_URL}
        </Text>
      </Card>
      <ComingNext issue={58} what="Status lights, verdict, your people, health grade and the 24-hour chart" />
    </Screen>
  );
}
