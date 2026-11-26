import { Link, router, type Href } from 'expo-router';
import { Platform, Pressable, StyleSheet, View } from 'react-native';

import { Button, FormScreen, Mark, Text, Wordmark } from '@/components/ui';
import { APK_URL, WEB_URL } from '@/links';
import { space } from '@/theme';

/** The other way to use KinLAN: the Android app from the web, the web app from the phone. */
const ELSEWHERE =
  Platform.OS === 'web'
    ? { label: 'Get the Android app', url: APK_URL, hint: 'Downloads KinLAN.apk' }
    : { label: 'Use KinLAN in a browser', url: WEB_URL, hint: 'Opens the web app' };

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
        {/* A real link on the web (<a href>); on the phone it opens the browser. */}
        <Link href={ELSEWHERE.url as Href} asChild>
          <Pressable
            style={({ pressed }) => [styles.elsewhere, pressed && styles.pressed]}
            accessibilityRole="link"
            accessibilityHint={ELSEWHERE.hint}>
            <Text role="bodySmall" color="text2" align="center">
              {ELSEWHERE.label}
            </Text>
          </Pressable>
        </Link>
      </View>
    </FormScreen>
  );
}

const styles = StyleSheet.create({
  brand: { flex: 1, minHeight: 280, alignItems: 'center', justifyContent: 'center', gap: space.s4 },
  pitch: { gap: space.s2, paddingHorizontal: space.s2 },
  actions: { gap: space.s3, paddingTop: space.s4 },
  elsewhere: { minHeight: 44, alignItems: 'center', justifyContent: 'center' },
  pressed: { opacity: 0.6 },
});
