import * as Notifications from 'expo-notifications';
import { router } from 'expo-router';
import { useEffect, useRef } from 'react';

import { registerForPush } from '@/api/push';

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
    const url = response.notification.request.content.data?.url;
    if (typeof url === 'string' && url.startsWith('/')) router.push(url as never);
  }, [response]);

  return null;
}
