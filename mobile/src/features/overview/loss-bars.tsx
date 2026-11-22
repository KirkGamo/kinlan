import { useMemo, useState } from 'react';
import { StyleSheet, View, type LayoutChangeEvent } from 'react-native';
import Svg, { Line, Rect } from 'react-native-svg';

import type { Latency } from '@/api/overview';
import { Card, Loader, Text } from '@/components/ui';
import { colors, radius, space } from '@/theme';

const H = 72; // bar height at the top of the scale

/**
 * Lost pings over time (plan, Section 8.2: bar charts for loss): one bar per time slot of the
 * latency chart above, neutral grey, orange above the site's own alert line. The dashed line and
 * the legend name that threshold, so colour is never the only cue.
 */
export function LossBars({
  data,
  loading,
  alertPct,
}: {
  data?: Latency;
  loading: boolean;
  /** The site's packet-loss alert threshold (Settings → Alerts), in percent. */
  alertPct: number;
}) {
  const [width, setWidth] = useState(0);
  const onLayout = (e: LayoutChangeEvent) => setWidth(Math.round(e.nativeEvent.layout.width));
  const model = useMemo(() => (data && width ? build(data, width, alertPct) : null), [data, width, alertPct]);

  let body;
  if (loading && !data) body = <View style={styles.center}><Loader label="Loading lost pings" /></View>;
  else if (!model || model.bars.length === 0)
    body = (
      <View style={styles.center}>
        <Text role="bodySmall" color="text2" align="center">
          No pings in this range yet.
        </Text>
      </View>
    );
  else
    body = (
      <Svg width={width} height={H + 2} accessible accessibilityLabel={model.label}>
        {model.bars.map((b) => (
          <Rect key={b.key} x={b.x} y={H - b.h} width={b.w} height={Math.max(b.h, 1)} rx={Math.min(2, b.w / 2)}
            fill={b.over ? colors.orange : colors.text2} fillOpacity={b.over ? 1 : b.h ? 0.55 : 0.18} />
        ))}
        <Line x1={0} x2={width} y1={model.lineY} y2={model.lineY} stroke={colors.orange} strokeWidth={1} strokeDasharray="4 4" />
      </Svg>
    );

  return (
    <Card>
      <View style={styles.legend}>
        <Key color={colors.text2} opacity={0.55} label="Lost pings" />
        <Key color={colors.orange} opacity={1} label={`Above your ${alertPct}% alert line`} />
      </View>
      <View onLayout={onLayout}>{body}</View>
      {model && model.bars.length ? (
        <Text role="bodySmall" color="text2" tabular>
          {model.summary}
        </Text>
      ) : null}
    </Card>
  );
}

function Key({ color, opacity, label }: { color: string; opacity: number; label: string }) {
  return (
    <View style={styles.key}>
      <View style={[styles.swatch, { backgroundColor: color, opacity }]} />
      <Text role="labelSmall" color="text2">
        {label}
      </Text>
    </View>
  );
}

function build(data: Latency, width: number, alertPct: number) {
  const points = (data.series.internet ?? []).filter((p) => p.samples > 0);
  const t0 = Date.parse(data.since);
  const span = Math.max(1, Date.parse(data.until) - t0);
  const slot = ((data.bucket_seconds * 1000) / span) * width;
  const w = Math.max(1, slot - Math.min(2, slot * 0.25)); // a hairline gap between bars
  // The scale always shows the alert line with room above it; a bad hour can push it higher.
  const top = Math.max(alertPct * 2, 10, ...points.map((p) => Math.ceil(p.loss_pct / 10) * 10));
  const y = (pct: number) => (Math.min(pct, top) / top) * (H - 2);
  const bars = points.map((p) => ({
    key: p.t,
    x: ((Date.parse(p.t) - t0) / span) * width,
    w,
    h: y(p.loss_pct),
    over: p.loss_pct > alertPct,
  }));
  const over = bars.filter((b) => b.over).length;
  const worst = Math.max(0, ...points.map((p) => p.loss_pct));
  const summary = over
    ? `${over} of ${bars.length} time slots lost more than ${alertPct}% of pings; the worst lost ${Math.round(worst)}%.`
    : worst > 0
      ? `Never above your ${alertPct}% line; the worst slot lost ${worst < 1 ? 'under 1' : Math.round(worst)}%.`
      : 'No pings were lost in this range.';
  return { bars, lineY: H - y(alertPct), summary, label: `Lost pings: ${summary}` };
}

const styles = StyleSheet.create({
  legend: { flexDirection: 'row', flexWrap: 'wrap', columnGap: space.s4, rowGap: space.s1 },
  key: { flexDirection: 'row', alignItems: 'center', gap: space.s2 },
  swatch: { width: 12, height: 12, borderRadius: radius.small / 2 },
  center: { height: H + 2, alignItems: 'center', justifyContent: 'center', paddingHorizontal: space.s4 },
});
