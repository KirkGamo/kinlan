import { router } from 'expo-router';
import { StyleSheet, View } from 'react-native';

import { useMe, useSession } from '@/api/session';
import { Button, FormScreen, Mark, Text } from '@/components/ui';
import { space } from '@/theme';

/** Signed in but not in any Circle yet: create one, or join one with an invite code. */
export default function OnboardingStart() {
  const me = useMe();
  const { signOut } = useSession();
  const first = me.data?.display_name.split(' ')[0];

  return (
    <FormScreen>
      <View style={styles.top}>
        <Mark width={96} />
        <Text role="headline" align="center" accessibilityRole="header">
          {first ? `Welcome, ${first}` : 'Welcome'}
        </Text>
        <Text role="body" color="text2" align="center">
          A Circle is the people who look after one or more networks together: a household,
          roommates, an office or a school lab.
        </Text>
      </View>
      <View style={styles.actions}>
        <Button label="Create a Circle" onPress={() => router.push('/onboarding/new-circle')} />
        <Text role="bodySmall" color="text2" align="center">
          You’ll be its owner, add your network and invite others.
        </Text>
        <Button label="Join with an invite code" variant="ghost" onPress={() => router.push('/onboarding/join')} />
        <Text role="bodySmall" color="text2" align="center">
          Someone in the Circle gives you an 8-character code.
        </Text>
      </View>
      <Button label="Sign out" variant="ghost" onPress={() => void signOut()} />
    </FormScreen>
  );
}

const styles = StyleSheet.create({
  top: { flex: 1, minHeight: 260, justifyContent: 'center', alignItems: 'center', gap: space.s4 },
  actions: { gap: space.s2 },
});
