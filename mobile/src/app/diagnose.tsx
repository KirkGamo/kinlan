import { useQueryClient } from '@tanstack/react-query';
import { Stack, useLocalSearchParams } from 'expo-router';
import { useEffect, useRef, useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import Animated, { FadeIn, useReducedMotion } from 'react-native-reanimated';

import { useSiteSummary } from '@/api/circles';
import { canManage as manages, useCurrentCircle } from '@/api/selection';
import type { Command } from '@/api/devices';
import { isActive, useDiagnoses, useStartDiagnose, type DiagnoseResult } from '@/api/diagnose';
import { Button, Card, FormScreen, Loader, SectionLabel, StatusChip, Text, type ChipTone } from '@/components/ui';
import { LightStrip } from '@/features/overview/light-strip';
import { clock, day, isStale, ms, type Light } from '@/features/overview/model';
import { useNow } from '@/hooks/use-now';
import { haptics } from '@/haptics';
import { colors, motion, radius, size, space, strokes, tints } from '@/theme';
import { keys } from '@/api/keys';

/** Plain names for the six checks, from this PC up to secure websites (briefs.md section 3). */
const RUNGS = [
  'This PC’s connection',
  'Router on the network',
  'Router answers',
  'Internet provider',
  'Website names (DNS)',
  'Secure websites',
];

/** One next step for each place the network can break. */
const NEXT: Record<number, string> = {
  1: 'Check this PC’s cable or Wi-Fi, then run the diagnose again.',
  2: 'Make sure the router is on and this PC is on the router’s Wi-Fi.',
  3: 'Move the PC closer to the router, or restart the router.',
  4: 'Wait a few minutes, or call your internet provider. Your router is fine.',
  5: 'Restart the router, or set its DNS servers to 8.8.8.8 and 9.9.9.9.',
  6: 'If the Wi-Fi has a sign-in page, sign in. Otherwise check a firewall or web filter.',
};

const UNLIT: Light[] = Array.from({ length: 5 }, () => ({ state: 'unlit', value: '—' }));

/**
 * Diagnose (briefs.md section 3): "Where exactly is the problem?" Runs the agent's six checks,
 * then shows the root cause with one next step above a ladder of the checks. Tap a rung for
 * its technical detail.
 */
export default function DiagnoseScreen() {
  const { site: siteId, run } = useLocalSearchParams<{ site: string; run?: string }>();
  const { circle } = useCurrentCircle();
  const canManage = manages(circle);
  const summary = useSiteSummary(siteId, true, 15_000);
  const now = useNow(10_000);
  const stale = summary.data ? isStale(summary.data, now) : false;
  const runs = useDiagnoses(siteId);
  const start = useStartDiagnose(siteId);
  const client = useQueryClient();

  const latest = runs.data?.[0];
  const running = start.isPending || isActive(latest);
  const lastDone = runs.data?.find((c) => c.status === 'done');

  // Opening Diagnose from the FAB starts a run once (briefs.md section 1).
  const autoStarted = useRef(false);
  const { mutate: startRun } = start;
  useEffect(() => {
    if (run !== '1' || autoStarted.current || !runs.isSuccess || !canManage || stale) return;
    autoStarted.current = true;
    if (!isActive(runs.data?.[0])) startRun();
  }, [run, runs.isSuccess, runs.data, canManage, stale, startRun]);

  // The end of a run watched here: confirm when all six pass, reject on a root cause or no result.
  const wasRunning = useRef(false);
  useEffect(() => {
    if (running) {
      wasRunning.current = true;
      return;
    }
    if (!wasRunning.current || !latest) return;
    wasRunning.current = false;
    const cause = (latest.result as DiagnoseResult | undefined)?.root_cause_step;
    if (latest.status === 'done' && !cause) haptics.confirm();
    else haptics.reject();
  }, [running, latest]);

  // A finished run changes the Overview's DNS and Web lights: refresh the site summary.
  const doneId = lastDone?.id;
  useEffect(() => {
    if (doneId) void client.invalidateQueries({ queryKey: keys.summary(siteId) });
  }, [doneId, siteId, client]);

  if (runs.isPending) {
    return (
      <FormScreen>
        <Loader label="Loading diagnoses" />
      </FormScreen>
    );
  }
  if (runs.isError) {
    return (
      <FormScreen>
        <Text role="body" color="red" accessibilityRole="alert">
          {runs.error.message}
        </Text>
        <Button label="Try again" variant="ghost" onPress={() => void runs.refetch()} />
      </FormScreen>
    );
  }

  const shown = running ? undefined : lastDone;
  const result = shown?.result as DiagnoseResult | undefined;

  const headerSub = running
    ? 'Running the checks…'
    : latest?.status === 'expired'
      ? 'The agent didn’t respond'
      : result && shown?.finished_at
        ? `Finished ${clock(shown.finished_at)} · ${result.root_cause_step ? `root cause: step ${result.root_cause_step}` : 'all six passed'}`
        : 'Not run yet';

  return (
    <FormScreen>
      <Stack.Screen options={{ headerTitle: () => <HeaderTitle sub={headerSub} /> }} />
      <LightStrip lights={result ? toLights(result) : UNLIT} igniteKey={shown?.id ?? 'none'} />
      <Verdict latest={latest} running={running} shown={shown} result={result} stale={stale} />

      {canManage ? (
        stale ? (
          <Text role="bodySmall" color="text2">
            The agent is offline, so a new diagnose can’t run. This is the last result.
          </Text>
        ) : (
          <Button label={lastDone ? 'Run again' : 'Run diagnose'} onPress={() => start.mutate()} loading={running} />
        )
      ) : null}
      {start.isError ? (
        <Text role="bodySmall" color="red" accessibilityRole="alert">
          {start.error.message}
        </Text>
      ) : null}

      <SectionLabel end="tap for details">The six checks</SectionLabel>
      <Ladder key={shown?.id ?? 'none'} result={result} running={running} />

      <History runs={(runs.data ?? []).filter((c) => c.id !== shown?.id && c.status === 'done')} />
    </FormScreen>
  );
}

function Verdict({
  latest,
  running,
  shown,
  result,
  stale,
}: {
  latest: Command | undefined;
  running: boolean;
  shown: Command | undefined;
  result: DiagnoseResult | undefined;
  stale: boolean;
}) {
  let tone: ChipTone = 'neutral';
  let chip = 'Not run yet';
  let title = 'Find where the network breaks';
  let text = 'The agent checks six things in order, from this PC up to secure websites, and stops at the first one that fails.';
  if (running) {
    const waiting = latest?.status === 'pending';
    return (
      <Card style={styles.verdict}>
        <View style={styles.meta}>
          <Loader label={waiting ? 'Waiting for the agent' : 'Running the checks'} />
          <Text role="bodySmall" color="text2">
            {waiting ? 'Waiting for the agent' : 'Running'}
          </Text>
        </View>
        <Text role="headline" accessibilityRole="header">
          {waiting ? 'Sending it to the agent…' : 'Checking your network…'}
        </Text>
        <Text role="body" color="text2">
          {waiting
            ? 'The PC with the agent picks this up within a few seconds when it’s on.'
            : 'This takes 2 to 15 seconds.'}
        </Text>
      </Card>
    );
  }
  if (latest?.status === 'expired' || latest?.status === 'failed') {
    tone = 'neutral';
    chip = latest.status === 'expired' ? 'No answer' : 'Didn’t finish';
    title = latest.status === 'expired' ? 'The agent didn’t respond' : 'The diagnose didn’t finish';
    text =
      latest.status === 'expired'
        ? 'Is the PC with the agent on and connected? Turn it on, then run the diagnose again.'
        : 'Something interrupted the checks. Run the diagnose again.';
  } else if (result) {
    const failed = result.steps.find((s) => s.n === result.root_cause_step);
    if (failed) {
      tone = 'down';
      chip = `Step ${failed.n} failed`;
      title = failed.summary || result.summary;
      text = NEXT[failed.n] ?? '';
    } else {
      tone = 'ok';
      chip = 'Healthy';
      title = 'Everything checks out';
      text = 'All six checks passed, from this PC to secure websites.';
    }
  }
  return (
    <Card style={styles.verdict}>
      <View style={styles.meta}>
        <StatusChip tone={tone} label={chip} />
        {shown?.finished_at ? (
          <Text role="bodySmall" color={stale ? 'orange' : 'text2'} tabular>
            {`Checked ${clock(shown.finished_at)}`}
          </Text>
        ) : null}
      </View>
      <Text role="headline" accessibilityRole="header">
        {title}
      </Text>
      {text ? (
        <Text role="body" color="text2">
          {text}
        </Text>
      ) : null}
    </Card>
  );
}

function Ladder({ result, running }: { result: DiagnoseResult | undefined; running: boolean }) {
  const reduce = useReducedMotion();
  const [open, setOpen] = useState<number | null>(null);
  return (
    <View style={styles.ladder}>
      {RUNGS.map((name, i) => {
        const n = i + 1;
        const step = result?.steps.find((s) => s.n === n);
        const state = running ? 'waiting' : (step?.status ?? 'none');
        const isRoot = result?.root_cause_step === n;
        const expanded = open === n && !!step;
        const lastRung = n === RUNGS.length;
        return (
          <Animated.View key={n} entering={reduce || !result ? undefined : FadeIn.delay(i * motion.lightStagger).duration(motion.small)} style={styles.rungRow}>
            {/* The rail: each step's number, joined to the next by a line (prototype). */}
            <View style={styles.rail}>
              <Badge n={n} state={state} />
              {lastRung ? null : <View style={[styles.railLine, state === 'pass' && styles.railLinePass]} />}
            </View>
            <Pressable
              disabled={!step}
              onPress={() => setOpen(expanded ? null : n)}
              accessibilityRole="button"
              accessibilityState={{ expanded, disabled: !step }}
              accessibilityLabel={`Step ${n}, ${name}: ${WORD[state]}. ${step?.summary ?? ''}`}
              style={({ pressed }) => [styles.rung, isRoot && styles.root, pressed && styles.pressed]}>
              <View style={styles.rungText}>
                <Text role="title">{name}</Text>
                <Text role="bodySmall" color={state === 'fail' ? 'red' : 'text2'}>
                  {step?.summary || WORD[state]}
                </Text>
              </View>
              {expanded ? (
                <View style={styles.detail}>
                  <Text role="silk" color="text2">
                    {`${step.name} · ${step.layer}`}
                  </Text>
                  <Text role="bodySmall" selectable>
                    {step.detail || 'No details recorded.'}
                  </Text>
                  {step.ms != null ? (
                    <Text role="bodySmall" color="text2" tabular>
                      {`The check took ${ms(step.ms)}.`}
                    </Text>
                  ) : null}
                </View>
              ) : null}
            </Pressable>
          </Animated.View>
        );
      })}
    </View>
  );
}

const WORD: Record<string, string> = {
  pass: 'Passed',
  fail: 'Failed',
  skipped: 'Skipped: an earlier check failed',
  waiting: 'Waiting',
  none: 'Not checked yet',
};


/** The step's number on the rail, tinted by its state; the rung's text says the state in words. */
function Badge({ n, state }: { n: number; state: string }) {
  const look =
    state === 'pass'
      ? { bg: tints.green, fg: 'green' as const }
      : state === 'fail'
        ? { bg: colors.red, fg: 'onRed' as const }
        : { bg: colors.raised, fg: 'text2' as const };
  return (
    <View style={[styles.badge, { backgroundColor: look.bg }]}>
      <Text role="labelSmall" color={look.fg} tabular>
        {String(n)}
      </Text>
    </View>
  );
}

function History({ runs }: { runs: Command[] }) {
  if (!runs.length) return null;
  return (
    <>
      <SectionLabel>Earlier</SectionLabel>
      {runs.map((c) => {
        const r = c.result as DiagnoseResult | null;
        const root = r?.root_cause_step;
        return (
          <View key={c.id} style={styles.history}>
            <Text role="body" tabular>
              {c.finished_at ? `${day(c.finished_at)}` : '—'}
            </Text>
            <StatusChip tone={root ? 'down' : 'ok'} label={root ? `Failed at ${RUNGS[root - 1]}` : 'All good'} />
          </View>
        );
      })}
    </>
  );
}

/** The pushed screen's title with the run's outcome below it (prototype). */
function HeaderTitle({ sub }: { sub: string }) {
  return (
    <View>
      <Text role="titleLarge" accessibilityRole="header">
        Diagnose
      </Text>
      <Text role="bodySmall" color="text2" numberOfLines={1}>
        {sub}
      </Text>
    </View>
  );
}

/** Six steps onto five lights (direction.md): PC = 1, Router = 2 and 3, Provider = 4, DNS = 5, Web = 6. */
function toLights(r: DiagnoseResult): Light[] {
  const st = (n: number) => r.steps.find((s) => s.n === n);
  const light = (...ns: number[]): Light => {
    const steps = ns.map(st);
    if (steps.some((s) => s?.status === 'fail')) return { state: 'fail', value: 'Failing' };
    // A step's ms is how long the check took (several pings, a full HTTPS request), not
    // latency, so the lights say OK and the rung details carry the measurements.
    if (steps.every((s) => s?.status === 'pass')) return { state: 'pass', value: 'OK' };
    return { state: 'unlit', value: 'Not checked' };
  };
  return [light(1), light(2, 3), light(4), light(5), light(6)];
}

const styles = StyleSheet.create({
  verdict: { paddingTop: space.s6, gap: space.s2 },
  meta: { flexDirection: 'row', alignItems: 'center', gap: space.s3, flexWrap: 'wrap' },
  ladder: { gap: 0 },
  rungRow: { flexDirection: 'row', gap: space.s3 },
  rail: { width: 32, alignItems: 'center' },
  railLine: { flex: 1, width: 2, marginVertical: 4, backgroundColor: colors.unlit },
  railLinePass: { backgroundColor: strokes.green },
  rung: {
    flex: 1,
    marginBottom: space.item,
    backgroundColor: colors.card,
    borderRadius: radius.row,
    borderCurve: 'continuous',
    paddingHorizontal: space.s4,
    paddingVertical: space.s3,
    minHeight: size.row,
    justifyContent: 'center',
    gap: space.s3,
    borderWidth: 2,
    borderColor: 'transparent',
  },
  root: { borderColor: colors.red },
  pressed: { backgroundColor: colors.raised },
  rungText: { flex: 1, gap: 2 },
  badge: { width: 32, height: 32, borderRadius: radius.pill, alignItems: 'center', justifyContent: 'center' },
  detail: { gap: space.s1, backgroundColor: colors.raised, borderRadius: radius.inner, padding: space.s3 },
  history: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: space.s3,
    backgroundColor: colors.card,
    borderRadius: radius.row,
    paddingHorizontal: space.s4,
    minHeight: 56,
  },
});
