import { QueryClientProvider } from '@tanstack/react-query';
import { useFonts, type FontFamilyDefinition } from 'expo-font';
import { DarkTheme, Stack, ThemeProvider } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { StatusBar } from 'expo-status-bar';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Platform, StyleSheet, View } from 'react-native';
import { GestureHandlerRootView } from 'react-native-gesture-handler';

import { queryClient } from '@/api/query-client';
import { useCircles } from '@/api/circles';
import { prefetchFirstScreen } from '@/api/selection';
import { pushSupported } from '@/api/push';
import { SessionProvider, useSession } from '@/api/session';
import { Button, FormScreen, Loader, Mark, Text } from '@/components/ui';
import { BootSplash } from '@/features/boot/boot-splash';
import { PushBridge } from '@/features/push/push-bridge';
import { loadHapticsPref } from '@/haptics';
import { colors, FONT_FAMILY, space } from '@/theme';

SplashScreen.preventAutoHideAsync();
void loadHapticsPref();

// Web: paint the page dark before React renders, so a dark app never flashes white.
if (Platform.OS === 'web' && typeof document !== 'undefined') {
  document.documentElement.style.backgroundColor = colors.bg;
  document.documentElement.style.colorScheme = 'dark'; // the browser's scrollbars and controls too
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
  // Cold start, with no blank frame anywhere: the native splash stays until the animated one has
  // drawn (they match), the lamps light with nothing else competing for the thread, the first
  // screen's data loads meanwhile, then the app mounts under the lit mark and the splash fades
  // only once that screen has been drawn.
  const [booted, setBooted] = useState(false);
  const [played, setPlayed] = useState(false);
  const [warm, setWarm] = useState(false);
  const [drawn, setDrawn] = useState(false);
  const warming = useRef(false);
  const hideNative = useCallback(() => void SplashScreen.hideAsync(), []);
  const onPlayed = useCallback(() => setPlayed(true), []);
  const done = useCallback(() => setBooted(true), []);
  const circleList = circles.data;
  const needsWarm = signedIn && !!circleList?.length; // signed out or no Circle: nothing to load

  useEffect(() => {
    if (deciding || !needsWarm || warming.current) return;
    warming.current = true;
    // Runs once. The cap isn't cleared on a re-render, so a slow API can never hold the splash.
    setTimeout(() => setWarm(true), WARM_CAP_MS);
    prefetchFirstScreen(queryClient, circleList)
      .catch(() => undefined) // the screen shows its own loading or error state
      .finally(() => setWarm(true));
  }, [deciding, needsWarm, circleList]);

  const mountApp = booted || (!deciding && played && (warm || !needsWarm));
  const onAppLayout = useCallback(() => {
    // Wait for the frame that draws the app before fading the splash off it.
    requestAnimationFrame(() => requestAnimationFrame(() => setDrawn(true)));
  }, []);

  // The screens decide where you belong from the Circles list, so they never render while it's
  // loading: after signing in they'd send someone with a Circle to onboarding (seen Nov 22).
  // After the cold start that wait shows the loader on Night Ground, never a blank screen.
  return (
    <View style={styles.root}>
      {mountApp && !deciding ? (
        <View style={styles.root} onLayout={onAppLayout}>
          <Routes signedIn={signedIn} status={status} circles={circles} />
        </View>
      ) : booted ? (
        <View style={styles.waiting}>
          <Loader label="Loading your Circles" />
        </View>
      ) : null}
      {booted ? null : (
        <BootSplash ready={mountApp && drawn} onShown={hideNative} onPlayed={onPlayed} onDone={done} />
      )}
    </View>
  );
}

function Routes({
  signedIn,
  status,
  circles,
}: {
  signedIn: boolean;
  status: ReturnType<typeof useSession>['status'];
  circles: ReturnType<typeof useCircles>;
}) {
  if (signedIn && circles.isError && !circles.data) { // a failed refresh keeps the app
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
        <Stack.Screen
          name="report"
          options={{
            headerShown: true,
            title: 'Report',
            headerStyle: { backgroundColor: colors.bg },
            headerTintColor: colors.text,
            headerTitleStyle: { fontFamily: FONT_FAMILY, fontWeight: '800' },
            headerShadowVisible: false,
            animation: 'slide_from_right',
          }}
        />
        <Stack.Screen
          name="site"
          options={{
            headerShown: true,
            title: 'Connection',
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

/** The longest the splash waits for the first screen's data before showing it loading. */
const WARM_CAP_MS = 4_000;

const styles = StyleSheet.create({
  root: { flex: 1 },
  waiting: { flex: 1, backgroundColor: colors.bg, alignItems: 'center', justifyContent: 'center' },
});
