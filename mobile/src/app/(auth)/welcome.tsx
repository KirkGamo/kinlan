import { router } from 'expo-router';
import { StyleSheet, View } from 'react-native';

import { Button, FormScreen, Mark, Text, Wordmark } from '@/components/ui';
import { space } from '@/theme';

export default function WelcomeScreen() {
  return (
    <FormScreen>
      <View style={styles.brand}>
        <Mark width={132} />
        <Wordmark />
        <Text role="body" color="text2" align="center">
          Your people, your network.
        </Text>
      </View>
      <View style={styles.pitch}>
        <Text role="title" align="center">
          Know when the internet breaks, and where.
        </Text>
        <Text role="bodySmall" color="text2" align="center">
          KinLAN watches the networks your Circle shares, from home to the lab, and tells everyone
          when something needs attention.
        </Text>
      </View>
      <View style={styles.actions}>
        <Button label="Create an account" onPress={() => router.push('/sign-up')} />
        <Button label="I already have an account" variant="ghost" onPress={() => router.push('/sign-in')} />
      </View>
    </FormScreen>
  );
}

const styles = StyleSheet.create({
  brand: { flex: 1, minHeight: 280, alignItems: 'center', justifyContent: 'center', gap: space.s4 },
  pitch: { gap: space.s2, paddingHorizontal: space.s2 },
  actions: { gap: space.s3, paddingTop: space.s4 },
});
