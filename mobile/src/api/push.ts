/**
 * Push notifications (plan, Section 6.4): ask permission after sign-in, register the phone's
 * Expo push token with the API, remove it on sign-out, and keep each member's push switches.
 * Android only: the web build has no push, so alerts stay in the Alerts tab there.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import Constants from 'expo-constants';
import * as Device from 'expo-device';
import * as Notifications from 'expo-notifications';
import { AndroidImportance } from 'expo-notifications';
import { Platform } from 'react-native';

import { colors } from '@/theme';

import { api } from './client';
import { keys } from './keys';

export const pushSupported = Platform.OS === 'android';

/** The token this phone registered, so sign-out can remove exactly it. */
let registered: string | null = null;

if (pushSupported) {
  // While the app is open, still show the banner: an outage shouldn't wait for the user to look.
  Notifications.setNotificationHandler({
    handleNotification: async () => ({
      shouldShowBanner: true,
      shouldShowList: true,
      shouldPlaySound: true,
      shouldSetBadge: false,
    }),
  });
}

/** One channel per severity, so Android's settings can quiet info without silencing outages. */
async function createChannels() {
  await Notifications.setNotificationChannelAsync('critical', {
    name: 'Outages and security',
    importance: AndroidImportance.HIGH,
    lightColor: colors.red,
    vibrationPattern: [0, 250, 150, 250],
  });
  await Notifications.setNotificationChannelAsync('warning', {
    name: 'New devices and warnings',
    importance: AndroidImportance.DEFAULT,
    lightColor: colors.orange,
  });
  await Notifications.setNotificationChannelAsync('info', {
    name: 'Back online and other news',
    importance: AndroidImportance.LOW,
  });
}

type PushState = 'unsupported' | 'denied' | 'registered' | 'error';

/** Ask once, register the token. Safe to call on every launch; it only prompts the first time. */
export async function registerForPush(): Promise<PushState> {
  if (!pushSupported || !Device.isDevice) return 'unsupported';
  try {
    await createChannels();
    const current = await Notifications.getPermissionsAsync();
    const granted = current.granted || (await Notifications.requestPermissionsAsync()).granted;
    if (!granted) return 'denied';
    const projectId = Constants.expoConfig?.extra?.eas?.projectId as string | undefined;
    const { data: token } = await Notifications.getExpoPushTokenAsync({ projectId });
    await api('/push-tokens', { method: 'POST', body: { token, platform: 'android' } });
    registered = token;
    return 'registered';
  } catch (e) {
    console.warn('push registration failed', e);
    return 'error';
  }
}

/** Sign-out: this phone stops getting this account's alerts. Best effort. */
export async function unregisterPush(): Promise<void> {
  if (!registered) return;
  const token = registered;
  registered = null;
  await api(`/push-tokens/${encodeURIComponent(token)}`, { method: 'DELETE' }).catch(() => undefined);
}

export type NotificationSwitches = {
  outages: boolean;
  new_devices: boolean;
  security: boolean;
  performance: boolean;
};

export function useNotificationSwitches(circleId: string | undefined) {
  return useQuery({
    queryKey: keys.notifications(circleId),
    queryFn: () => api<NotificationSwitches>(`/circles/${circleId}/notifications`),
    enabled: !!circleId,
  });
}

export function useUpdateNotificationSwitches(circleId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (patch: Partial<NotificationSwitches>) =>
      api<NotificationSwitches>(`/circles/${circleId}/notifications`, { method: 'PATCH', body: patch }),
    onSuccess: (data) => client.setQueryData(keys.notifications(circleId), data),
  });
}
