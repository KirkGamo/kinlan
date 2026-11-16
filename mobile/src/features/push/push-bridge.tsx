import * as Notifications from 'expo-notifications';
import { router } from 'expo-router';
import { useEffect, useRef } from 'react';

import { registerForPush } from '@/api/push';
import { selectSite } from '@/api/selection';

/**
 * Mounted while signed in with a Circle (Android only): registers this phone for push once per
 * sign-in, and opens the screen a tapped notification links to, including the tap that
 * launched the app from closed.
 */
export function PushBridge() {
  useEffect(() => {
    void registerForPush();
  }, []);

  const response = Notifications.useLastNotificationResponse();
  const handled = useRef<string | null>(null);
  useEffect(() => {
    if (!response) return;
    const id = response.notification.request.identifier;
    if (handled.current === id) return;
    handled.current = id;
    const data = response.notification.request.content.data;
    // Show the site the alert is about first, so the device or light it links to is there.
    if (typeof data?.siteId === 'string') selectSite(data.siteId);
    const url = data?.url;
    if (typeof url === 'string' && url.startsWith('/')) router.navigate(url as never);
  }, [response]);

  return null;
}
