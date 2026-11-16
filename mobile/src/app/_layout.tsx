import { QueryClientProvider } from '@tanstack/react-query';
import { useFonts, type FontFamilyDefinition } from 'expo-font';
import { DarkTheme, Stack, ThemeProvider } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { StatusBar } from 'expo-status-bar';
import { useEffect } from 'react';
import { Platform, StyleSheet, View } from 'react-native';
import { GestureHandlerRootView } from 'react-native-gesture-handler';

import { queryClient } from '@/api/query-client';
import { useCircles } from '@/api/circles';
import { pushSupported } from '@/api/push';
import { SessionProvider, useSession } from '@/api/session';
import { Button, FormScreen, Mark, Text } from '@/components/ui';
import { PushBridge } from '@/features/push/push-bridge';
import { loadHapticsPref } from '@/haptics';
import { colors, FONT_FAMILY, space } from '@/theme';

SplashScreen.preventAutoHideAsync();
void loadHapticsPref();

// Web: paint the page dark before React renders, so a dark app never flashes white.
if (Platform.OS === 'web' && typeof document !== 'undefined') {
  document.documentElement.style.backgroundColor = colors.bg;
  document.body.style.backgroundColor = colors.bg;
}

/** React Navigation's dark theme, re-coloured with KinLAN's tokens. */
const navigationTheme = {
  ...DarkTheme,
  colors: {
    ...DarkTheme.colors,
    primary: colors.yellow,
    background: colors.bg,
    card: colors.card,
    text: colors.text,
    border: colors.border,
    notification: colors.red,
  },
};

/**
 * Android and iOS embed Manrope at build time (expo-font config plugin in app.json). Config
 * plugins don't run for web, so the web build loads the same faces under the same family name.
 */
const WEB_FONTS: FontFamilyDefinition[] =
  Platform.OS === 'web'
    ? [
        {
          fontFamily: FONT_FAMILY,
          fontDefinitions: [
            { path: require('@expo-google-fonts/manrope/500Medium/Manrope_500Medium.ttf'), weight: 500 },
            { path: require('@expo-google-fonts/manrope/600SemiBold/Manrope_600SemiBold.ttf'), weight: 600 },
            { path: require('@expo-google-fonts/manrope/700Bold/Manrope_700Bold.ttf'), weight: 700 },
            { path: require('@expo-google-fonts/manrope/800ExtraBold/Manrope_800ExtraBold.ttf'), weight: 800 },
          ],
        },
      ]
    : [];

export default function RootLayout() {
  const [fontsLoaded, fontError] = useFonts(WEB_FONTS);
  const fontsReady = fontsLoaded || fontError !== null; // a font failure falls back to the system face
  if (!fontsReady) return null;

  return (
    <GestureHandlerRootView style={styles.root}>
      <QueryClientProvider client={queryClient}>
        <SessionProvider>
          <ThemeProvider value={navigationTheme}>
            <StatusBar style="light" />
            <RootNavigator />
          </ThemeProvider>
        </SessionProvider>
      </QueryClientProvider>
    </GestureHandlerRootView>
  );
}

/**
 * Signed out: only the welcome and sign-in screens exist. Signed in without a Circle: only
 * onboarding (create or join one). Signed in with a Circle: the app, with onboarding still
 * reachable for adding sites and pairing.
 */
function RootNavigator() {
  const { status } = useSession();
  const signedIn = status === 'signedIn';
  const circles = useCircles(signedIn);
  const deciding = status === 'loading' || (signedIn && circles.isPending);

  useEffect(() => {
    if (!deciding) SplashScreen.hideAsync(); // keep the splash until we know where to go
  }, [deciding]);

  if (deciding) return null;
  if (signedIn && circles.isError) {
    return <StartupError message={circles.error.message} onRetry={() => circles.refetch()} />;
  }
  const hasCircle = (circles.data?.length ?? 0) > 0;

  return (
    <>
      {signedIn && hasCircle && pushSupported ? <PushBridge /> : null}
    <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: colors.bg } }}>
      <Stack.Protected guard={signedIn && hasCircle} redirectTo={signedIn ? '/onboarding' : '/welcome'}>
        <Stack.Screen name="(tabs)" />
        <Stack.Screen
          name="diagnose"
          options={{
            headerShown: true,
            title: 'Diagnose',
            headerStyle: { backgroundColor: colors.bg },
            headerTintColor: colors.text,
            headerTitleStyle: { fontFamily: FONT_FAMILY, fontWeight: '800' },
            headerShadowVisible: false,
            animation: 'slide_from_right',
          }}
        />
      </Stack.Protected>
      <Stack.Protected guard={signedIn} redirectTo="/welcome">
        <Stack.Screen name="onboarding" />
      </Stack.Protected>
      <Stack.Protected guard={status === 'signedOut'} redirectTo="/">
        <Stack.Screen name="(auth)" />
      </Stack.Protected>
    </Stack>
    </>
  );
}

/** The app couldn't load your Circles (offline, or the API is waking up). */
function StartupError({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <FormScreen>
      <View style={{ flex: 1, justifyContent: 'center', gap: space.s4 }}>
        <Mark width={96} />
        <Text role="title" align="center">
          {message}
        </Text>
        <Button label="Try again" onPress={onRetry} />
      </View>
    </FormScreen>
  );
}

const styles = StyleSheet.create({ root: { flex: 1 } });
