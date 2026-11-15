import { Stack } from 'expo-router';

import { colors, FONT_FAMILY } from '@/theme';

/** Onboarding: create or join a Circle, add a site, pair the agent (briefs.md section 4). */
export default function OnboardingLayout() {
  return (
    <Stack
      screenOptions={{
        contentStyle: { backgroundColor: colors.bg },
        headerStyle: { backgroundColor: colors.bg },
        headerTintColor: colors.text,
        headerTitleStyle: { fontFamily: FONT_FAMILY, fontWeight: '800' },
        headerShadowVisible: false,
      }}>
      <Stack.Screen name="index" options={{ headerShown: false }} />
      <Stack.Screen name="new-circle" options={{ title: 'Create a Circle' }} />
      <Stack.Screen name="join" options={{ title: 'Join a Circle' }} />
      <Stack.Screen name="new-site" options={{ title: 'Add a site' }} />
      <Stack.Screen name="pair" options={{ title: 'Pair the agent' }} />
    </Stack>
  );
}
