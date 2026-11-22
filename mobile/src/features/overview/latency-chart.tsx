import { useCallback, useMemo, useState } from 'react';
import { PanResponder, StyleSheet, View, type GestureResponderEvent, type LayoutChangeEvent } from 'react-native';
import Animated, { FadeIn } from 'react-native-reanimated';
import Svg, { Circle, Defs, Line, LinearGradient, Path, Rect, Stop } from 'react-native-svg';

import type { Latency, LatencyPoint } from '@/api/overview';
import { Card, Loader, Text } from '@/components/ui';
import { colors, space } from '@/theme';

import { clock, day, ms } from './model';

const H = 132; // plot height
const PAD_TOP = 8;

type Pt = { x: number; t: number; v: number | null };

export type ChartRange = '1h' | '24h' | '7d' | '30d';
const RANGE_WORDS: Record<ChartRange, string> = { '1h': 'hour', '24h': '24 hours', '7d': '7 days', '30d': '30 days' };
/** Longer ranges cross days, so their times carry the date ("Nov 16, 9:41"). */
const when = (iso: string, range: ChartRange) => (range === '1h' || range === '24h' ? clock(iso) : day(iso, ''));
/** The left end of the axis: a clock time within a day, a date beyond. */
const start = (iso: string, range: ChartRange) => {
  if (range === '1h' || range === '24h') return clock(iso);
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
};

/**
 * Connection over time (briefs.md section 1): internet (yellow, solid, with a fade) and router
 * (grey, dashed) told apart by line style and labels, outages shaded red. Drag across it (or
 * hover on web) for a crosshair and that time's readout. Overview shows 24 hours; Site detail
 * any range.
 */
export function LatencyChart({
  data,
  loading,
  error,
  range = '24h',
}: {
  data?: Latency;
  loading: boolean;
  error?: string;
  range?: ChartRange;
}) {
  const [width, setWidth] = useState(0);
  const [at, setAt] = useState<number | null>(null);

  const model = useMemo(() => (data && width ? build(data, width, range) : null), [data, width, range]);

  const pick = useCallback(
    (x: number) => {
      if (!model || model.empty) return;
      setAt(Math.max(0, Math.min(width, x)));
    },
    [model, width],
  );
  const responder = useMemo(
    () =>
      PanResponder.create({
        onStartShouldSetPanResponder: () => true,
        onMoveShouldSetPanResponder: (_, g) => Math.abs(g.dx) > Math.abs(g.dy),
        onPanResponderTerminationRequest: () => false,
        onPanResponderGrant: (e: GestureResponderEvent) => pick(e.nativeEvent.locationX),
        onPanResponderMove: (e: GestureResponderEvent) => pick(e.nativeEvent.locationX),
        onPanResponderRelease: () => setAt(null),
        onPanResponderTerminate: () => setAt(null),
      }),
    [pick],
  );

  const onLayout = (e: LayoutChangeEvent) => setWidth(Math.round(e.nativeEvent.layout.width));

  let body;
  if (loading) body = <View style={styles.center}><Loader label="Loading the chart" /></View>;
  else if (error) body = <View style={styles.center}><Text role="bodySmall" color="red">{error}</Text></View>;
  else if (model && model.empty)
    body = (
      <View style={styles.center}>
        <Text role="bodySmall" color="text2" align="center">
          {`No measurements in the last ${RANGE_WORDS[range]} yet. The chart fills in as the agent reports.`}
        </Text>
      </View>
    );
  else if (model) {
    const cursor = at == null ? null : nearest(model, at);
    body = (
      <Animated.View entering={FadeIn.duration(600)} {...responder.panHandlers} style={styles.plot}
        // Hover reads the chart on web; touch uses the drag above.
        {...({ onPointerMove: (e: { nativeEvent: { offsetX?: number } }) => e.nativeEvent.offsetX != null && pick(e.nativeEvent.offsetX), onPointerLeave: () => setAt(null) } as object)}>
        <Svg width={width} height={H + PAD_TOP} accessible accessibilityLabel={model.label}>
          <Defs>
            <LinearGradient id="fade" x1="0" y1="0" x2="0" y2="1">
              <Stop offset="0" stopColor={colors.yellow} stopOpacity={0.3} />
              <Stop offset="1" stopColor={colors.yellow} stopOpacity={0} />
            </LinearGradient>
          </Defs>
          {model.outages.map((o) => (
            <Rect key={o.key} x={o.x} y={PAD_TOP} width={Math.max(2, o.w)} height={H} rx={6} fill={o.measured ? colors.red : colors.unlitRing} fillOpacity={o.measured ? 0.14 : 0.16} />
          ))}
          {model.grid.map((y) => (
            <Line key={y} x1={0} x2={width} y1={y} y2={y} stroke={colors.border} strokeWidth={1} />
          ))}
          <Path d={model.area} fill="url(#fade)" />
          <Path d={model.routerPath} fill="none" stroke={colors.text2} strokeWidth={2} strokeDasharray="5 5" strokeLinecap="round" />
          <Path d={model.internetPath} fill="none" stroke={colors.yellow} strokeWidth={3} strokeLinecap="round" strokeLinejoin="round" />
          {cursor ? (
            <>
              <Line x1={cursor.x} x2={cursor.x} y1={PAD_TOP} y2={H + PAD_TOP} stroke={colors.text} strokeWidth={1} />
              <Circle cx={cursor.x} cy={cursor.internet?.v != null ? model.y(cursor.internet.v) : H + PAD_TOP - 6} r={5} fill={cursor.internet?.v != null ? colors.yellow : colors.red} stroke={colors.bg} strokeWidth={2} />
            </>
          ) : null}
        </Svg>
        <View style={styles.axis}>
          <Text role="labelSmall" color="text2" tabular>{start(data!.since, range)}</Text>
          <Text role="labelSmall" color="text2" tabular>{`max ${Math.round(model.max)} ms`}</Text>
          <Text role="labelSmall" color="text2">now</Text>
        </View>
      </Animated.View>
    );
  }

  const cursor = model && at != null ? nearest(model, at) : null;
  return (
    <Card>
      <View style={styles.legend}>
        <Legend dashed={false} label="Internet" />
        <Legend dashed label="Router" />
        {model?.measured ? <Swatch color={colors.red} opacity={0.35} label="Outage" /> : null}
        {model?.silent ? <Swatch color={colors.unlitRing} opacity={0.45} label="Agent off" /> : null}
      </View>
      <View onLayout={onLayout}>{body}</View>
      {data && model && !model.empty ? (
        <Text role="bodySmall" color="text2" tabular accessibilityLiveRegion="polite">
          {cursor ? readoutAt(cursor, range) : readoutAll(data)}
        </Text>
      ) : null}
    </Card>
  );
}

/** A band's legend: a small filled block plus its word, so colour is never the only cue. */
function Swatch({ color, opacity, label }: { color: string; opacity: number; label: string }) {
  return (
    <View style={styles.legendItem}>
      <View style={[styles.swatch, { backgroundColor: color, opacity }]} />
      <Text role="labelSmall" color="text2">
        {label}
      </Text>
    </View>
  );
}

function Legend({ dashed, label }: { dashed: boolean; label: string }) {
  return (
    <View style={styles.legendItem}>
      <Svg width={18} height={6}>
        <Line x1={0} x2={18} y1={3} y2={3} stroke={dashed ? colors.text2 : colors.yellow} strokeWidth={dashed ? 2 : 3} strokeDasharray={dashed ? '4 3' : undefined} />
      </Svg>
      <Text role="labelSmall" color="text2">{label}</Text>
    </View>
  );
}

function readoutAll(data: Latency): string {
  const i = data.summary.internet;
  const g = data.summary.gateway;
  const loss = i?.loss_pct != null ? ` · loss ${i.loss_pct < 1 && i.loss_pct > 0 ? '<1' : Math.round(i.loss_pct)}%` : '';
  return `Average internet ${ms(i?.avg_ms)} · router ${ms(g?.avg_ms)}${loss}`;
}

function readoutAt(c: Cursor, range: ChartRange): string {
  const time = when(new Date(c.t).toISOString(), range);
  const inet = c.internet == null ? 'no data' : c.internet.v == null ? 'no reply' : ms(c.internet.v);
  const router = c.router == null ? 'no data' : c.router.v == null ? 'no reply' : ms(c.router.v);
  return `${time} · internet ${inet} · router ${router}`;
}

type Cursor = { x: number; t: number; internet: Pt | null; router: Pt | null };

function nearest(model: Model, x: number): Cursor {
  const near = (pts: Pt[]) => {
    let best: Pt | null = null;
    for (const p of pts) if (!best || Math.abs(p.x - x) < Math.abs(best.x - x)) best = p;
    // Only a bucket within ~1.5 buckets of the finger counts; otherwise that time had no data.
    return best && Math.abs(best.x - x) <= model.bucketW * 1.5 ? best : null;
  };
  const internet = near(model.internet);
  const router = near(model.router);
  const snap = internet ?? router;
  return { x: snap?.x ?? x, t: snap?.t ?? model.tAt(x), internet, router };
}

type Model = ReturnType<typeof build>;

function build(data: Latency, width: number, range: ChartRange) {
  const t0 = Date.parse(data.since);
  const t1 = Date.parse(data.until);
  const span = Math.max(1, t1 - t0);
  const half = (data.bucket_seconds * 1000) / 2;
  const x = (t: number) => ((t - t0) / span) * width;
  const pts = (series: LatencyPoint[] = []): Pt[] =>
    series.map((p) => {
      const t = Date.parse(p.t) + half;
      return { x: x(t), t, v: p.avg_ms };
    });
  const internet = pts(data.series.internet);
  const router = pts(data.series.gateway);
  const values = [...internet, ...router].map((p) => p.v).filter((v): v is number => v != null);
  const max = Math.max(50, Math.ceil(Math.max(0, ...values) / 50) * 50);
  const y = (v: number) => PAD_TOP + H - (Math.min(v, max) / max) * (H - 4);
  const bucketW = ((data.bucket_seconds * 1000) / span) * width;

  // A gap (lost bucket or no samples) breaks the line, so outages and agent downtime show as
  // breaks. Each unbroken run is drawn on its own; a lone bucket gets a tiny stroke so its
  // round cap shows as a dot.
  const runs = (series: Pt[]) => {
    const out: Pt[][] = [];
    let run: Pt[] = [];
    let prev: Pt | null = null;
    for (const p of series) {
      if (p.v == null || (prev && p.x - prev.x > bucketW * 1.5)) {
        if (run.length) out.push(run);
        run = [];
      }
      if (p.v != null) run.push(p);
      prev = p;
    }
    if (run.length) out.push(run);
    return out;
  };
  const xy = (p: Pt) => `${p.x.toFixed(1)} ${y(p.v ?? 0).toFixed(1)}`;
  const line = (series: Pt[]) =>
    runs(series)
      .map((r) => `M${r.map(xy).join(' L')}${r.length === 1 ? ' h0.1' : ''}`)
      .join(' ');
  const internetPath = line(internet);
  const floor = PAD_TOP + H;
  const area = runs(internet)
    .filter((r) => r.length > 1)
    .map((r) => `M${r.map(xy).join(' L')} L${r[r.length - 1].x.toFixed(1)} ${floor} L${r[0].x.toFixed(1)} ${floor} Z`)
    .join(' ');

  // Red only where the agent measured the internet down. When the agent itself was silent (the
  // server inferred the outage), nothing was measured: that span is grey "no data", not an outage.
  const outages = data.outages.map((o) => {
    const a = x(Math.max(t0, Date.parse(o.started_at)));
    const b = x(o.ended_at ? Math.min(t1, Date.parse(o.ended_at)) : t1);
    return { key: o.id, x: a, w: b - a, measured: o.detected_by === 'agent' };
  });
  const measured = outages.filter((o) => o.measured).length;
  const silent = outages.length - measured;

  const avg = data.summary.internet?.avg_ms;
  const label =
    `Latency over the last ${RANGE_WORDS[range]}: internet ${avg != null ? `about ${ms(avg)}` : 'no data'}, ` +
    `router ${ms(data.summary.gateway?.avg_ms)}` +
    (measured ? `, ${measured} ${measured === 1 ? 'outage' : 'outages'}` : ', no outages') +
    (silent ? `, agent offline ${silent} ${silent === 1 ? 'time' : 'times'}` : '');

  return {
    internet,
    router,
    internetPath,
    routerPath: line(router),
    area,
    outages,
    measured,
    silent,
    max,
    y,
    bucketW,
    grid: [PAD_TOP + H / 2, PAD_TOP + H],
    empty: internet.length + router.length === 0,
    tAt: (px: number) => t0 + (px / width) * span,
    label,
  };
}

const styles = StyleSheet.create({
  legend: { flexDirection: 'row', flexWrap: 'wrap', columnGap: space.s4, rowGap: space.s1 },
  swatch: { width: 12, height: 12, borderRadius: 3 },
  legendItem: { flexDirection: 'row', alignItems: 'center', gap: space.s2 },
  plot: { gap: space.s1 },
  axis: { flexDirection: 'row', justifyContent: 'space-between' },
  center: { height: H + PAD_TOP, alignItems: 'center', justifyContent: 'center', paddingHorizontal: space.s4 },
});
