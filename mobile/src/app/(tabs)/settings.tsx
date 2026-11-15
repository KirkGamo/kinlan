import { useState } from 'react';

import { useMe, useSession } from '@/api/session';
import { ComingNext } from '@/components/placeholder';
import { Button, Card, Loader, Screen, SectionLabel, Text } from '@/components/ui';

export default function SettingsScreen() {
  const { signOut } = useSession();
  const me = useMe();
  const [leaving, setLeaving] = useState(false);

  return (
    <Screen>
      <Text role="headline" accessibilityRole="header">
        Settings
      </Text>
      <SectionLabel>Account</SectionLabel>
      <Card>
        {me.isPending ? (
          <Loader label="Loading your account" />
        ) : me.isError ? (
          <Text role="bodySmall" color="red">
            {me.error.message}
          </Text>
        ) : (
          <>
            <Text role="title">{me.data.display_name}</Text>
            <Text role="bodySmall" color="text2">
              {me.data.email}
            </Text>
          </>
        )}
      </Card>
      <Button
        label="Sign out"
        variant="ghost"
        loading={leaving}
        onPress={() => {
          setLeaving(true);
          void signOut();
        }}
      />
      <ComingNext issue={62} what="Members, invites, alert thresholds and the account sheet" />
    </Screen>
  );
}
