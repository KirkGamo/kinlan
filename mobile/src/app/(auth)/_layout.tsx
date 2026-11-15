import { Stack } from 'expo-router';

import { colors, FONT_FAMILY } from '@/theme';

export const unstable_settings = { initialRouteName: 'welcome' };

/** Signed-out screens. Sign in and Sign up get a back arrow to Welcome. */
export default function AuthLayout() {
  return (
    <Stack
      screenOptions={{
        contentStyle: { backgroundColor: colors.bg },
        headerStyle: { backgroundColor: colors.bg },
        headerTintColor: colors.text,
        headerTitleStyle: { fontFamily: FONT_FAMILY, fontWeight: '800' },
        headerShadowVisible: false,
      }}>
      <Stack.Screen name="welcome" options={{ headerShown: false }} />
      <Stack.Screen name="sign-in" options={{ title: 'Sign in' }} />
      <Stack.Screen name="sign-up" options={{ title: 'Create your account' }} />
    </Stack>
  );
}
