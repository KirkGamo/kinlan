import { useEffect, useRef, useState } from 'react';
import { StyleSheet, View } from 'react-native';

import {
  PING_COUNT,
  useCommand,
  useDevice,
  useStartPing,
  useUpdateDevice,
  type DeviceDetail,
  type PingTest,
} from '@/api/devices';
import type { DeviceType, Member } from '@/api/overview';
import { Button, Chips, Facts, Loader, Sheet, StatusChip, Text, TextField } from '@/components/ui';
import { day, ms } from '@/features/overview/model';
import { haptics } from '@/haptics';
import { colors, radius, size, space } from '@/theme';

import { ICON_PATHS, TYPE_LABEL } from './icons';
import { chip, isPrivateAddress } from './model';

const TYPES = (Object.keys(TYPE_LABEL) as DeviceType[]).map((key) => ({ key, label: TYPE_LABEL[key] }));
const SHARED = '__shared';

/** Plain advice for the ports the agent flags (PRODUCT.md: plain first, details on tap). */
const PORT_ADVICE: Record<number, string> = {
  21: 'FTP sends passwords unencrypted. Turn it off on this device, or use SFTP instead.',
  23: 'Telnet sends passwords unencrypted. Turn it off on this device.',
  445: 'File sharing (SMB) is open. Keep it off unless you share folders on purpose.',
  3389: 'Remote Desktop is open. Turn it off if nobody connects to this PC remotely.',
  5900: 'Screen sharing (VNC) is open. Turn it off if you don’t use it.',
};

/**
 * Device detail as a bottom sheet (briefs.md section 2): identity, whose it is, and for owners
 * and admins rename, type, trust and a ping test. KinLAN can't block devices, so it never offers to.
 */
export function DeviceSheet({
  deviceId,
  siteId,
  members,
  canManage,
  stale,
  startPing = false,
  onClose,
}: {
  deviceId: string | null;
  siteId: string;
  members: Member[];
  canManage: boolean;
  stale: boolean;
  /** Start a ping test as the sheet opens (a row's quick Ping action). */
  startPing?: boolean;
  onClose: () => void;
}) {
  const device = useDevice(deviceId, siteId);
  const d = device.data;
  const st = d ? chip(d, stale) : null;
  return (
    <Sheet
      open={deviceId != null}
      onClose={onClose}
      title={d?.display_name ?? 'Device'}
      icon={d ? ICON_PATHS[d.device_type] : undefined}
      meta={
        d && st ? (
          <>
            <StatusChip tone={st.tone} label={st.label} />
            {d.trusted ? <StatusChip tone="ok" label="Trusted" /> : null}
            <Text role="bodySmall" color="text2">
              {TYPE_LABEL[d.device_type]}
            </Text>
          </>
        ) : null
      }>
      {deviceId != null && device.isPending ? (
        <View style={styles.center}>
          <Loader label="Loading the device" />
        </View>
      ) : device.isError ? (
        <Text role="body" color="red">
          {device.error.message}
        </Text>
      ) : !d ? null : (
        // Keyed by device, so switching devices resets the rename field and ping state.
        <Body key={d.id} d={d} siteId={siteId} members={members} canManage={canManage} stale={stale} startPing={startPing} partial={device.isPlaceholderData} />
      )}
    </Sheet>
  );
}

function Body({
  d,
  siteId,
  members,
  canManage,
  stale,
  startPing,
  partial,
}: {
  d: DeviceDetail;
  siteId: string;
  members: Member[];
  canManage: boolean;
  stale: boolean;
  startPing: boolean;
  /** Drawn from the list row while the detail loads: ports and the last ping test come later. */
  partial: boolean;
}) {
  const update = useUpdateDevice(d.id, siteId, members);
  const ping = usePing(d, siteId);
  const { run: runPing } = ping;
  const autoPinged = useRef(false);
  useEffect(() => {
    if (!startPing || autoPinged.current || !canManage || !d.ip || stale) return;
    autoPinged.current = true;
    runPing();
  }, [startPing, canManage, d.ip, stale, runPing]);
  const [name, setName] = useState(d.custom_name ?? '');
  const owners = [
    ...members.map((m) => ({ key: m.user_id, label: m.display_name })),
    { key: SHARED, label: 'Shared' },
  ];
  const whose = d.owner?.user_id ?? SHARED;
  const renamed = name.trim() !== (d.custom_name ?? '');

  return (
    <>
      {d.is_agent ? (
        <Text role="bodySmall" color="text2">
          This PC runs the KinLAN agent: every check and ping test starts here.
        </Text>
      ) : null}
      {isPrivateAddress(d.mac) ? (
        <Text role="bodySmall" color="text2">
          Private address: this phone or laptop hides its real hardware address, so its maker can’t be named.
        </Text>
      ) : null}

      <Facts
        rows={[
          ['Manufacturer', d.vendor ?? 'Unknown'],
          ['IP address', d.ip ?? 'Unknown'],
          ['Hardware address', d.mac],
          ['First seen', day(d.first_seen_at)],
          ['Last seen', day(d.last_seen_at)],
        ]}
      />

      <Text role="silk" color="text2">
        Whose is this?
      </Text>
      {canManage ? (
        <Chips
          label="Whose is this?"
          variant="outline"
          options={owners}
          value={whose}
          disabled={update.isPending}
          onChange={(key) => update.mutate({ owner_user_id: key === SHARED ? null : key })}
        />
      ) : (
        <Text role="body">{d.owner?.display_name ?? 'Shared'}</Text>
      )}

      {/* The two actions side by side, high enough to reach without scrolling. */}
      {canManage ? (
        <View style={styles.actions}>
          <View style={styles.action}>
            <Button
              label={ping.running ? 'Pinging…' : ping.shown ? 'Ping again' : 'Ping test'}
              variant={d.trusted ? 'primary' : 'ghost'}
              onPress={ping.run}
              loading={ping.running}
              disabled={!d.ip || stale}
            />
          </View>
          {!d.trusted ? (
            <View style={styles.action}>
              <Button
                label="Mark as trusted"
                loading={update.isPending && update.variables?.trusted === true}
                onPress={() => update.mutate({ trusted: true }, { onSuccess: haptics.confirm })}
                accessibilityHint="It stops counting as a new device to review"
              />
            </View>
          ) : null}
        </View>
      ) : null}
      {canManage && stale ? (
        <Text role="bodySmall" color="text2">
          Ping tests run from the agent, which is offline right now.
        </Text>
      ) : null}
      {update.isError ? (
        <Text role="bodySmall" color="red" accessibilityRole="alert">
          {update.error.message}
        </Text>
      ) : null}

      <PingResult d={d} ping={ping} />

      {partial && d.open_risky_ports > 0 ? (
        <Loader label="Loading open ports" />
      ) : d.risky_ports.length ? (
        <>
          <Text role="silk" color="text2">
            Open ports to check
          </Text>
          {d.risky_ports.map((p) => (
            <View key={p.port} style={styles.port}>
              <StatusChip tone="new" label={`${p.service} · port ${p.port}`} />
              <Text role="body" color="text2">
                {PORT_ADVICE[p.port] ?? `${p.service} is open on this device. Turn it off if you don’t use it.`}
              </Text>
            </View>
          ))}
        </>
      ) : null}

      {canManage ? (
        <>
          <Text role="silk" color="text2">
            Name and type
          </Text>
          <TextField
            label="Name"
            value={name}
            onChangeText={setName}
            placeholder={d.hostname ?? d.vendor ?? 'Living room TV'}
            autoCapitalize="words"
            returnKeyType="done"
            onSubmitEditing={() => renamed && update.mutate({ custom_name: name.trim() || null })}
            hint="Leave empty to use the name the device reports."
          />
          {renamed ? (
            <Button label="Save name" variant="ghost" loading={update.isPending} onPress={() => update.mutate({ custom_name: name.trim() || null })} />
          ) : null}
          <Chips
            label="Device type"
            options={TYPES}
            value={d.device_type}
            disabled={update.isPending}
            onChange={(key) => update.mutate({ device_type: key })}
          />
        </>
      ) : null}
    </>
  );
}

/** A ping test from the agent: start it, then poll the command until it finishes. */
function usePing(d: DeviceDetail, siteId: string) {
  const start = useStartPing(siteId, d.id);
  const [commandId, setCommandId] = useState<string | null>(null);
  const cmd = useCommand(commandId);
  const status = cmd.data?.status;
  const running = start.isPending || (commandId != null && (status == null || status === 'pending' || status === 'running'));
  const result = status === 'done' ? (cmd.data?.result as Partial<PingTest> | null) : null;
  const shown: Partial<PingTest> | null = result ?? (commandId ? null : d.last_ping_test);
  const run = () => start.mutate(undefined, { onSuccess: (c) => setCommandId(c.id), onError: haptics.reject });
  // The result of a ping the user started: confirm on replies, reject on none or no result.
  const finished = status === 'done' || status === 'expired' || status === 'failed';
  const received = result?.received;
  useEffect(() => {
    if (!commandId || !finished) return;
    if (status === 'done' && received) haptics.confirm();
    else haptics.reject();
  }, [commandId, finished, status, received]);
  return { run, running, status, result, shown, error: start.isError ? start.error.message : null };
}

/** The result card: five reply cells, a plain verdict and the numbers; hidden until there is one. */
function PingResult({ d, ping }: { d: DeviceDetail; ping: ReturnType<typeof usePing> }) {
  const { running, status, shown, result, error } = ping;
  if (!running && !shown && status !== 'expired' && status !== 'failed' && !error) return null;
  return (
    <View style={styles.ping}>
      <Cells sent={shown?.sent ?? PING_COUNT} received={running ? undefined : shown?.received} running={running} />
      {running ? (
        <Text role="body" color="text2">{`Sending ${PING_COUNT} pings from the agent…`}</Text>
      ) : status === 'expired' || status === 'failed' ? (
        <Text role="body" color="orange">
          {status === 'expired'
            ? 'The agent didn’t pick this up. Is the PC with the agent on?'
            : 'The ping test didn’t finish. Try again in a moment.'}
        </Text>
      ) : shown ? (
        <>
          <Text role="title">{verdict(d.display_name, shown)}</Text>
          <Text role="bodySmall" color="text2" tabular>
            {`${shown.received} of ${shown.sent} replies · average ${ms(shown.avg_ms)} · max ${ms(shown.max_ms)} · loss ${Math.round(shown.loss_pct ?? 0)}%`}
            {!result && d.last_ping_test ? ` · ${day(d.last_ping_test.ts)}` : ''}
          </Text>
        </>
      ) : null}
      {error ? (
        <Text role="bodySmall" color="red" accessibilityRole="alert">
          {error}
        </Text>
      ) : null}
    </View>
  );
}

/** Five reply cells: green for a reply, red for a lost echo, unlit while waiting. */
function Cells({ sent, received, running }: { sent: number; received: number | undefined; running: boolean }) {
  return (
    <View style={styles.cells} accessible accessibilityLabel={running ? 'Ping running' : received != null ? `${received} of ${sent} replies` : 'No result yet'}>
      {Array.from({ length: sent }, (_, i) => {
        const state = running || received == null ? 'wait' : i < received ? 'ok' : 'lost';
        return <View key={i} style={[styles.cell, state === 'ok' && styles.cellOk, state === 'lost' && styles.cellLost]} />;
      })}
      {running ? <Loader label="Pinging" /> : null}
    </View>
  );
}

function verdict(name: string, t: Partial<PingTest>): string {
  if (!t.received) return `${name} isn’t answering`;
  if ((t.loss_pct ?? 0) > 0 || (t.jitter_ms ?? 0) > 30) return 'Responds, but unevenly';
  return 'Responds well';
}

const styles = StyleSheet.create({
  center: { minHeight: size.loading, alignItems: 'center', justifyContent: 'center' },
  actions: { flexDirection: 'row', gap: space.s2 },
  action: { flex: 1 },
  ping: { gap: space.s2, backgroundColor: colors.raised, borderRadius: radius.row, padding: space.s4 },
  cells: { flexDirection: 'row', alignItems: 'center', gap: space.s2 },
  cell: { width: 28, height: 28, borderRadius: radius.small, backgroundColor: colors.unlit, borderWidth: 1.5, borderColor: colors.unlitRing },
  cellOk: { backgroundColor: colors.green, borderColor: colors.green },
  cellLost: { backgroundColor: colors.red, borderColor: colors.red },
  port: { gap: space.s2 },
});
