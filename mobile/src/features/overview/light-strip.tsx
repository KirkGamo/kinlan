import { useEffect, useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import Animated, {
  cancelAnimation,
  useAnimatedStyle,
  useReducedMotion,
  useSharedValue,
  withDelay,
  withRepeat,
  withSequence,
  withTiming,
} from 'react-native-reanimated';

import { Button, Card, Facts, Sheet, StatusChip, Text, type ChipTone } from '@/components/ui';
import { colors, glows, motion, radius, space } from '@/theme';

import { LAYERS, type Light, type LightState } from './model';

const FILL: Record<LightState, string> = {
  pass: colors.green,
  warn: colors.orange,
  fail: colors.red,
  unlit: colors.unlit,
};
/** The glow ring around a lit light: its colour at about a fifth strength (prototype: 18-22%). */
const GLOW: Record<LightState, string> = {
  pass: glows.green,
  warn: glows.orange,
  fail: glows.red,
  unlit: 'transparent',
};
/** Material "layers": the network layer a light stands for (prototype sheet icon). */
const LAYERS_ICON =
  'M11.99 18.54l-7.37-5.73L3 14.07l9 7 9-7-1.63-1.27-7.38 5.74zM12 16l7.36-5.73L21 9l-9-7-9 7 1.63 1.27L12 16z';

const WORD: Record<LightState, string> = {
  pass: 'working',
  warn: 'slow',
  fail: 'failing',
  unlit: 'not checked',
};
const CHIP: Record<LightState, { tone: ChipTone; label: string }> = {
  pass: { tone: 'ok', label: 'Working' },
  warn: { tone: 'new', label: 'Slow' },
  fail: { tone: 'down', label: 'Failing' },
  unlit: { tone: 'neutral', label: 'Not checked' },
};

/**
 * The five status lights (direction.md thesis): This PC, Router, Provider, DNS, Web. They ignite
 * left to right whenever `igniteKey` changes (opening the screen, switching sites); the failing
 * light breathes. Tap a light for what that layer checks and what its state means.
 */
export function LightStrip({
  lights,
  igniteKey,
  request,
  onDiagnose,
}: {
  lights: Light[];
  igniteKey: string;
  /** Open a light's sheet from a link (an outage push); a new `id` opens it again. */
  request?: { id: string; index: number };
  /** Owners and admins get "Run diagnose" in the layer sheet. */
  onDiagnose?: () => void;
}) {
  const [open, setOpen] = useState<number | null>(null);
  const [handled, setHandled] = useState<string | undefined>(undefined);
  if (request && request.id !== handled) {
    setHandled(request.id);
    setOpen(request.index);
  }
  const layer = open == null ? null : LAYERS[open];
  const light = open == null ? null : lights[open];
  return (
    <Card style={styles.strip}>
      <View style={styles.row} accessibilityRole="list" accessibilityLabel="Network path, tap a light for details">
        {lights.map((l, i) => (
          <Lamp key={`${igniteKey}-${i}`} index={i} light={l} onPress={() => setOpen(i)} />
        ))}
      </View>
      <Sheet
        open={open != null}
        onClose={() => setOpen(null)}
        title={layer?.title ?? ''}
        icon={LAYERS_ICON}
        meta={
          layer && light ? (
            <>
              <StatusChip {...CHIP[light.state]} />
              <Text role="bodySmall" color="text2">
                {layer.layer}
              </Text>
            </>
          ) : null
        }>
        {layer && light ? (
          <>
            <Text role="body" color="text2">
              {layer.what}
            </Text>
            <Facts
              rows={[
                ['Now', light.value],
                ['What it means', meaning(light.state, open ?? 0)],
              ]}
            />
            {onDiagnose ? (
              <Button
                label="Run diagnose"
                onPress={() => {
                  setOpen(null);
                  onDiagnose();
                }}
              />
            ) : null}
          </>
        ) : null}
      </Sheet>
    </Card>
  );
}

function meaning(state: LightState, index: number): string {
  switch (state) {
    case 'pass':
      return 'Working normally.';
    case 'warn':
      return 'Working, but slower than usual.';
    case 'fail':
      return 'This is where your network breaks right now. The checks after it can’t run until it works.';
    default:
      return index >= 3
        ? 'Not checked recently. DNS and secure web are checked each time a diagnose runs.'
        : 'Not checked: the agent isn’t reporting, or an earlier layer failed.';
  }
}

function Lamp({ index, light, onPress }: { index: number; light: Light; onPress: () => void }) {
  const reduce = useReducedMotion();
  const lit = useSharedValue(reduce ? 1 : 0);
  const scale = useSharedValue(1);
  const ring = useSharedValue(0);
  const failing = light.state === 'fail';

  // Ignite once on mount (the parent remounts the lamps to re-run it).
  useEffect(() => {
    if (reduce) return;
    const delay = index * motion.lightStagger;
    lit.value = withDelay(delay, withTiming(1, { duration: 160 }));
    scale.value = withDelay(delay, withSequence(withTiming(1.18, { duration: 110 }), withTiming(1, { duration: 150 })));
  }, [index, lit, scale, reduce]);

  useEffect(() => {
    if (!failing || reduce) {
      cancelAnimation(ring);
      ring.value = failing ? 0.5 : 0;
      return;
    }
    ring.value = withRepeat(withSequence(withTiming(0.7, { duration: 1200 }), withTiming(0.15, { duration: 1200 })), -1);
    return () => cancelAnimation(ring);
  }, [failing, reduce, ring]);

  const dot = useAnimatedStyle(() => ({ opacity: lit.value, transform: [{ scale: scale.value }] }));
  const halo = useAnimatedStyle(() => ({ opacity: ring.value }));
  const unlit = light.state === 'unlit';
  const layer = LAYERS[index];

  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={`${layer.name}: ${light.value}, ${WORD[light.state]}`}
      accessibilityHint="Opens what this layer checks"
      style={({ pressed }) => [styles.lamp, pressed && styles.pressed]}>
      <View style={styles.socket}>
        {failing ? <Animated.View style={[styles.halo, halo]} /> : null}
        <View style={styles.unlit} />
        {unlit ? null : (
          // A real 4-dp ring in the light's colour (the prototype's glow); Android draws no shadow here.
          <Animated.View style={[styles.glow, { backgroundColor: GLOW[light.state] }, dot]}>
            <View style={[styles.dot, { backgroundColor: FILL[light.state] }]} />
          </Animated.View>
        )}
      </View>
      <Text role="silk" color="text2" align="center" numberOfLines={1}>
        {layer.name}
      </Text>
      <Text role="labelSmall" color={unlit ? 'text2' : 'text'} align="center" numberOfLines={2} tabular>
        {light.value}
      </Text>
    </Pressable>
  );
}

const DOT = 22;

const styles = StyleSheet.create({
  strip: { paddingHorizontal: space.s2, paddingVertical: space.s4 },
  row: { flexDirection: 'row' },
  lamp: { flex: 1, alignItems: 'center', gap: space.s1, minHeight: 72, paddingHorizontal: 2, borderRadius: radius.row },
  pressed: { backgroundColor: colors.raised },
  socket: { width: DOT + 16, height: DOT + 16, alignItems: 'center', justifyContent: 'center', marginBottom: 2 },
  unlit: {
    position: 'absolute',
    width: DOT,
    height: DOT,
    borderRadius: DOT / 2,
    backgroundColor: colors.unlit,
    borderWidth: 1.5,
    borderColor: colors.unlitRing,
  },
  // Only status lights glow (brand.md): a soft ring in the light's own colour around the dot.
  glow: {
    width: DOT + 8,
    height: DOT + 8,
    borderRadius: (DOT + 8) / 2,
    alignItems: 'center',
    justifyContent: 'center',
  },
  dot: { width: DOT, height: DOT, borderRadius: DOT / 2 },
  halo: {
    position: 'absolute',
    width: DOT + 14,
    height: DOT + 14,
    borderRadius: (DOT + 14) / 2,
    borderWidth: 3,
    borderColor: colors.red,
  },
});
