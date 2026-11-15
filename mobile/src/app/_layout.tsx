import { QueryClientProvider } from '@tanstack/react-query';
import { useFonts, type FontFamilyDefinition } from 'expo-font';
import { DarkTheme, Stack, ThemeProvider } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { StatusBar } from 'expo-status-bar';
import { useEffect } from 'react';
import { Platform } from 'react-native';

import { queryClient } from '@/api/query-client';
import { SessionProvider, useSession } from '@/api/session';
import { colors, FONT_FAMILY } from '@/theme';

SplashScreen.preventAutoHideAsync();

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
    <QueryClientProvider client={queryClient}>
      <SessionProvider>
        <ThemeProvider value={navigationTheme}>
          <StatusBar style="light" />
          <RootNavigator />
        </ThemeProvider>
      </SessionProvider>
    </QueryClientProvider>
  );
}

/** Signed out: only the welcome and sign-in screens exist. Signed in: only the app. */
function RootNavigator() {
  const { status } = useSession();

  useEffect(() => {
    if (status !== 'loading') SplashScreen.hideAsync(); // keep the splash until we know
  }, [status]);

  if (status === 'loading') return null;

  return (
    <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: colors.bg } }}>
      <Stack.Protected guard={status === 'signedIn'} redirectTo="/welcome">
        <Stack.Screen name="(tabs)" />
      </Stack.Protected>
      <Stack.Protected guard={status === 'signedOut'} redirectTo="/">
        <Stack.Screen name="(auth)" />
      </Stack.Protected>
    </Stack>
  );
}
