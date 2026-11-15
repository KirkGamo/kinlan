import { useState } from 'react';
import { StyleSheet, View, type LayoutChangeEvent } from 'react-native';
import Svg, { Circle, G, Line, Path, Text as SvgText } from 'react-native-svg';

import type { SiteSummary } from '@/api/circles';
import type { Device, DeviceType } from '@/api/overview';
import { Card, Text } from '@/components/ui';
import { ms } from '@/features/overview/model';
import { colors, FONT_FAMILY } from '@/theme';

import { ICON_PATHS } from './icons';
import { matches, type Filter } from './model';

const NODE = 20; // node radius
const MAX_RING = 30; // beyond this, offline devices collapse into one node

type Node = {
  key: string;
  x: number;
  y: number;
  label: string;
  type: DeviceType | 'internet';
  ring: string;
  badge?: string;
  device?: Device;
  dim: boolean;
};

/**
 * The logical network map (briefs.md section 2): the router in the middle, the internet above,
 * every device around it. Links carry live numbers; a provider outage breaks the internet link
 * and a router failure breaks the agent PC's link. It shows who shares the network, not wiring.
 */
export function DeviceMap({
  devices,
  filter,
  summary,
  gatewayIp,
  selectedId,
  onSelect,
  stale,
}: {
  devices: Device[];
  filter: Filter;
  summary: SiteSummary | undefined;
  gatewayIp: string | null;
  selectedId: string | null;
  onSelect: (id: string) => void;
  stale: boolean;
}) {
  const [width, setWidth] = useState(0);
  const onLayout = (e: LayoutChangeEvent) => setWidth(Math.round(e.nativeEvent.layout.width));

  const router = devices.find((d) => gatewayIp && d.ip === gatewayIp);
  const agentPc = devices.find((d) => d.is_agent && d !== router);
  const others = devices.filter((d) => d !== router && d !== agentPc);
  const collapse = others.length > MAX_RING;
  const ringDevices = collapse ? others.filter((d) => d.online || d.needs_review) : others;
  const hidden = others.length - ringDevices.length;

  const H = Math.max(340, Math.round(width * 1.05));
  const cx = width / 2;
  const cy = H * 0.55;
  const R = Math.min(width * 0.38, H * 0.36);
  const internetY = 36;

  const ringColor = (d: Device) =>
    d.needs_review ? colors.orange : stale ? colors.unlitRing : d.online ? colors.green : colors.unlitRing;

  // Slots from 35° to 325° clockwise from the top, so the internet link stays clear; the
  // agent's PC takes the bottom slot.
  const slots = ringDevices.length + 1 + (hidden ? 1 : 0);
  const pcSlot = Math.floor(slots / 2);
  const at = (i: number) => {
    const deg = 35 + (290 * (i + 0.5)) / slots;
    const rad = (deg * Math.PI) / 180;
    return { x: cx + R * Math.sin(rad), y: cy - R * Math.cos(rad) };
  };
  const nodes: Node[] = [];
  let slot = 0;
  const next = () => {
    if (slot === pcSlot) slot += 1;
    return at(slot++);
  };
  for (const d of ringDevices) {
    nodes.push({
      key: d.id,
      ...next(),
      label: d.display_name,
      type: d.device_type,
      ring: ringColor(d),
      badge: d.needs_review ? 'New' : undefined,
      device: d,
      dim: !matches(d, filter),
    });
  }
  if (hidden) {
    nodes.push({ key: 'offline', ...next(), label: `+${hidden} offline`, type: 'unknown', ring: colors.unlitRing, dim: filter === 'online' || filter === 'review' });
  }
  // The agent's PC is a scanned device when its hostname matches; otherwise draw it anyway,
  // since the router link's latency is measured from it.
  const pc: Node = {
    key: agentPc?.id ?? 'pc',
    ...at(pcSlot),
    label: 'This PC',
    type: agentPc?.device_type ?? 'computer',
    ring: stale ? colors.unlitRing : colors.green,
    device: agentPc,
    dim: false,
  };

  const routerDown = !stale && summary?.gateway != null && !summary.gateway.ok;
  const providerDown = !stale && !routerDown && (!!summary?.open_outage_since || (summary?.internet != null && !summary.internet.ok));
  const sel = selectedId;

  const online = devices.filter((d) => d.online).length;
  const fresh = devices.filter((d) => d.needs_review).length;
  const summaryLabel =
    `Network map. Router, ${online} ${online === 1 ? 'device' : 'devices'} online` +
    (fresh ? `, ${fresh} new` : '') +
    (providerDown ? ', internet down' : summary?.internet?.ok ? `, internet ${ms(summary.internet.rtt_ms)}` : '') +
    '. Every device is also in the People and Status lists.';

  const internetLabel = providerDown ? 'no reply' : summary?.internet?.ok ? ms(summary.internet.rtt_ms) : '—';
  const pcLabel = routerDown ? 'no reply' : summary?.gateway?.ok ? ms(summary.gateway.rtt_ms) : '—';

  return (
    <Card style={styles.card}>
      <View onLayout={onLayout}>
        {width ? (
          <Svg width={width} height={H} accessible accessibilityLabel={summaryLabel}>
            {/* Links first, so nodes sit on top. */}
            <Link x1={cx} y1={cy} x2={cx} y2={internetY} broken={providerDown} label={internetLabel} />
            <Link x1={cx} y1={cy} x2={pc.x} y2={pc.y} broken={routerDown} label={pcLabel} />
            {nodes.map((n) => (
              <Line
                key={`l-${n.key}`}
                x1={cx}
                y1={cy}
                x2={n.x}
                y2={n.y}
                stroke={n.device && n.device.id === sel ? colors.yellow : colors.border}
                strokeWidth={n.device && n.device.id === sel ? 2.5 : 1.5}
                opacity={n.dim || (sel && n.device?.id !== sel) ? 0.35 : 1}
              />
            ))}

            <MapNode n={{ key: 'internet', x: cx, y: internetY, label: 'Internet', type: 'internet', ring: providerDown ? colors.red : colors.unlitRing, dim: !!sel }} side />
            <MapNode
              n={{
                key: 'router',
                x: cx,
                y: cy,
                label: router?.display_name ?? 'Router',
                type: 'router',
                ring: routerDown ? colors.red : stale ? colors.unlitRing : colors.green,
                device: router,
                dim: !!sel && router?.id !== sel,
              }}
              big
              side
              selected={!!router && router.id === sel}
              onPress={router ? () => onSelect(router.id) : undefined}
            />
            <MapNode
              n={{ ...pc, dim: !!sel && agentPc?.id !== sel }}
              selected={!!agentPc && agentPc.id === sel}
              onPress={agentPc ? () => onSelect(agentPc.id) : undefined}
            />
            {nodes.map((n) => (
              <MapNode
                key={n.key}
                n={{ ...n, dim: n.dim || (!!sel && n.device?.id !== sel) }}
                selected={!!n.device && n.device.id === sel}
                onPress={n.device ? () => onSelect(n.device!.id) : undefined}
              />
            ))}
          </Svg>
        ) : (
          <View style={{ height: 340 }} />
        )}
      </View>
      <Text role="bodySmall" color="text2">
        Shows which devices share this network, not how they’re wired: KinLAN can’t tell Wi-Fi from cable or see extenders.
      </Text>
    </Card>
  );
}

function Link({ x1, y1, x2, y2, broken, label }: { x1: number; y1: number; x2: number; y2: number; broken: boolean; label: string }) {
  const mx = (x1 + x2) / 2;
  const my = (y1 + y2) / 2;
  return (
    <>
      <Line x1={x1} y1={y1} x2={x2} y2={y2} stroke={broken ? colors.red : colors.text2} strokeWidth={2} strokeDasharray={broken ? '6 6' : undefined} />
      <SvgText x={mx + 8} y={my + 4} fill={broken ? colors.red : colors.text} fontSize={11} fontWeight="700" fontFamily={FONT_FAMILY}>
        {label}
      </SvgText>
    </>
  );
}

/** `side` puts the label beside the node, off the vertical links of the internet and router. */
function MapNode({ n, big, side, selected, onPress }: { n: Node; big?: boolean; side?: boolean; selected?: boolean; onPress?: () => void }) {
  const r = big ? NODE + 6 : NODE;
  const icon = big ? 26 : 20;
  const label = n.label.length > 14 ? `${n.label.slice(0, 13)}…` : n.label;
  return (
    <G opacity={n.dim ? 0.35 : 1} onPress={onPress}>
      {selected ? <Circle cx={n.x} cy={n.y} r={r + 6} fill="none" stroke={colors.yellow} strokeWidth={3} /> : null}
      <Circle cx={n.x} cy={n.y} r={r} fill={colors.raised} stroke={n.ring} strokeWidth={2.5} />
      <G transform={`translate(${n.x - icon / 2} ${n.y - icon / 2}) scale(${icon / 24})`}>
        <Path d={ICON_PATHS[n.type]} fill={colors.text} />
      </G>
      {n.badge ? (
        <>
          <Circle cx={n.x + r * 0.75} cy={n.y - r * 0.75} r={6} fill={colors.orange} stroke={colors.card} strokeWidth={2} />
        </>
      ) : null}
      <SvgText
        x={side ? n.x - r - 8 : n.x}
        y={side ? n.y + 4 : n.y + r + 14}
        fill={n.badge ? colors.orange : colors.text2}
        fontSize={11}
        fontWeight="600"
        fontFamily={FONT_FAMILY}
        textAnchor={side ? 'end' : 'middle'}>
        {n.badge ? `${label} · New` : label}
      </SvgText>
    </G>
  );
}

const styles = StyleSheet.create({
  card: { paddingHorizontal: 12 },
});
