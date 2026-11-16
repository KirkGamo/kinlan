/**
 * Haptics with names that say what happened (DESIGN.md, Haptics). Rules: only what the user does
 * or the result of it, never polling or background updates; one vibration per action. Android
 * uses the system's own patterns, so the phone's touch-feedback setting is respected. The in-app
 * Vibration switch (Settings) silences all of them; web does nothing.
 */
import * as Haptics from 'expo-haptics';
import { useSyncExternalStore } from 'react';
import { Platform } from 'react-native';

import { readPref, writePref } from './pref-storage';

let enabled = true;
const listeners = new Set<() => void>();

/** Reads the saved switch once at start-up; until then haptics are on (the default). */
export async function loadHapticsPref(): Promise<void> {
  const saved = await readPref();
  if (saved != null) setState(saved !== 'off');
}

export function setHapticsEnabled(on: boolean): void {
  setState(on);
  void writePref(on ? 'on' : 'off');
}

export function useHapticsEnabled(): boolean {
  return useSyncExternalStore(subscribe, () => enabled);
}

function setState(on: boolean) {
  enabled = on;
  listeners.forEach((l) => l());
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function play(android: Haptics.AndroidHaptics, ios: () => Promise<void>) {
  if (!enabled || Platform.OS === 'web') return;
  const run = Platform.OS === 'android' ? Haptics.performAndroidHapticsAsync(android) : ios();
  run.catch(() => {}); // no vibrator, or the system declined: stay silent
}

export const haptics = {
  /** A choice changed: tab, segment, chip, or a gesture crossing its threshold. */
  tick: () => play(Haptics.AndroidHaptics.Segment_Tick, Haptics.selectionAsync),
  /** A switch turned on or off. */
  toggle: (on: boolean) =>
    play(on ? Haptics.AndroidHaptics.Toggle_On : Haptics.AndroidHaptics.Toggle_Off, () =>
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light),
    ),
  /** Something the user started finished well: a check passed, pairing worked, a device trusted. */
  confirm: () =>
    play(Haptics.AndroidHaptics.Confirm, () => Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success)),
  /** Something the user started failed, or a destructive step is about to happen. */
  reject: () => play(Haptics.AndroidHaptics.Reject, () => Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error)),
  /** A long press that opens actions. */
  longPress: () =>
    play(Haptics.AndroidHaptics.Long_Press, () => Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium)),
};
