import { useEffect, useRef } from 'react';
import { StyleSheet, View } from 'react-native';

import { isRiskyPort, usePortCheck } from '@/api/devices';
import { Button, StatusChip, Text } from '@/components/ui';
import { haptics } from '@/haptics';
import { space } from '@/theme';

/** Plain advice for each port the agent checks (PRODUCT.md: plain first, details on tap). */
export const PORT_ADVICE: Record<number, string> = {
  21: 'FTP sends passwords unencrypted. Turn it off on this device, or use SFTP instead.',
  23: 'Telnet sends passwords unencrypted. Turn it off on this device.',
  80: 'Its web admin page answers on your network. That’s normal for a router or printer; make sure it has its own strong password.',
  445: 'File sharing (SMB) is open. Keep it off unless you share folders on purpose.',
  3389: 'Remote Desktop is open. Turn it off if nobody connects to this PC remotely.',
  5900: 'Screen sharing (VNC) is open. Turn it off if you don’t use it.',
  8080: 'A web admin page answers on your network. Make sure it has its own strong password.',
};

export function portAdvice(port: number, service: string): string {
  return PORT_ADVICE[port] ?? `${service} is open on this device. Turn it off if you don’t use it.`;
}

/**
 * Check ports (plan, Section 3.2; Feature 5): asks the agent to try the risky ports on one device
 * or the whole site, then says what it found in one line. The findings themselves show on each
 * device (and in Alerts when risky); this only reports the check.
 */
export function PortCheck({
  siteId,
  deviceId,
  disabled,
  why,
}: {
  siteId: string;
  /** One device; omit to check every device on the site. */
  deviceId?: string;
  disabled?: boolean;
  /** Why it's disabled, shown under the button. */
  why?: string;
}) {
  const check = usePortCheck(siteId, deviceId);
  const { status, result, refresh } = check;
  const reported = useRef<string | undefined>(undefined);

  // Once per check: refresh what the findings changed, and say how it went.
  useEffect(() => {
    if (!status || status === reported.current || (status !== 'done' && status !== 'failed' && status !== 'expired')) return;
    reported.current = status;
    if (status !== 'done') {
      haptics.reject();
      return;
    }
    refresh();
    if (result?.open.some((f) => isRiskyPort(f.port))) haptics.reject();
    else haptics.confirm();
  }, [status, result, refresh]);

  const risky = result?.open.filter((f) => isRiskyPort(f.port)) ?? [];
  const info = (result?.open.length ?? 0) - risky.length;
  const devices = result?.macs.length ?? 0;
  const seconds = result ? Math.max(1, Math.round(result.duration_ms / 1000)) : 0;

  return (
    <View style={styles.root}>
      <Button
        label={check.running ? 'Checking ports…' : result ? 'Check again' : deviceId ? 'Check ports' : 'Check every device'}
        variant="ghost"
        onPress={check.run}
        loading={check.running}
        disabled={disabled}
        accessibilityHint="Tries file sharing, remote access and unencrypted logins, without changing anything"
      />
      {disabled && why ? (
        <Text role="bodySmall" color="text2">
          {why}
        </Text>
      ) : null}
      {result ? (
        <View style={styles.result} accessibilityLiveRegion="polite">
          <StatusChip tone={risky.length ? 'down' : 'ok'} label={risky.length ? `${risky.length} risky` : 'No risky ports'} />
          {/* flex: 1 lets the sentence wrap beside the chip instead of running off (Android). */}
          <View style={styles.resultText}>
            <Text role="bodySmall" color="text2">
              {`${deviceId ? 'Checked this device' : `Checked ${devices} ${devices === 1 ? 'device' : 'devices'}`} in ${seconds} s.${info ? ` ${info} web admin ${info === 1 ? 'page' : 'pages'} answered.` : ''}`}
            </Text>
          </View>
        </View>
      ) : null}
      {check.error ? (
        <Text role="bodySmall" color="red" accessibilityRole="alert">
          {check.error}
        </Text>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  root: { gap: space.s2 },
  result: { flexDirection: 'row', alignItems: 'center', gap: space.s3 },
  resultText: { flex: 1 },
});
