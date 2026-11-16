import * as Clipboard from 'expo-clipboard';
import { router, useLocalSearchParams } from 'expo-router';
import { useEffect, useRef, useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { usePairingCode, useSite, useSiteSummary } from '@/api/circles';
import { Button, Card, FormScreen, Loader, SectionLabel, StatusChip, Text } from '@/components/ui';
import { haptics } from '@/haptics';
import { colors, radius, space } from '@/theme';

/**
 * Pair the agent (briefs.md section 4): a 6-digit code with a 10-minute countdown and a copy
 * button, the PC steps with the consent wording, and a live wait that turns into "Connected".
 */
export default function PairScreen() {
  const { site: siteId } = useLocalSearchParams<{ site: string }>();
  const site = useSite(siteId, true); // polls every 3 s until the agent connects
  const connected = !!site.data && site.data.status !== 'pending';
  const summary = useSiteSummary(siteId, connected);

  // Confirm once when the agent connects while the user waits here (not on a revisit).
  const waited = useRef(false);
  useEffect(() => {
    if (!site.data) return;
    if (!connected) waited.current = true;
    else if (waited.current) {
      waited.current = false;
      haptics.confirm();
    }
  }, [connected, site.data]);

  if (site.isPending) {
    return (
      <FormScreen>
        <Loader label="Loading the site" />
      </FormScreen>
    );
  }
  if (site.isError) {
    return (
      <FormScreen>
        <Text role="body" color="red" accessibilityRole="alert">
          {site.error.message}
        </Text>
      </FormScreen>
    );
  }
  if (connected) return <Connected siteName={site.data.name} devices={summary.data?.devices_total} />;
  return <Waiting siteId={siteId} siteName={site.data.name} />;
}

/** Shown while the site waits for its agent; mounting it asks the server for a fresh code. */
function Waiting({ siteId, siteName }: { siteId: string; siteName: string }) {
  const pairing = usePairingCode(siteId);
  const { mutate: newCode } = pairing;
  const [now, setNow] = useState(() => Date.now());
  const [copied, setCopied] = useState(false);

  useEffect(() => newCode(), [newCode]);
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1_000);
    return () => clearInterval(timer);
  }, []);

  const code = pairing.data?.code;
  const secondsLeft = pairing.data
    ? Math.max(0, Math.round((Date.parse(pairing.data.expires_at) - now) / 1000))
    : 0;
  const expired = !!pairing.data && secondsLeft === 0;

  async function copy() {
    if (!code) return;
    await Clipboard.setStringAsync(code);
    haptics.confirm();
    setCopied(true);
    setTimeout(() => setCopied(false), 2_000);
  }

  return (
    <FormScreen>
      <Card style={styles.codeCard}>
        <Text role="bodySmall" color="text2" align="center">
          {`Pairing code for ${siteName}`}
        </Text>
        {pairing.isError ? (
          <Text role="bodySmall" color="red" align="center" accessibilityRole="alert">
            {pairing.error.message}
          </Text>
        ) : !code ? (
          <Loader label="Making a pairing code" />
        ) : (
          <View
            style={styles.digits}
            accessible
            accessibilityLabel={`Pairing code ${code.split('').join(' ')}${expired ? ', expired' : ''}`}>
            {code.split('').map((digit, i) => (
              <View key={i} style={[styles.digit, i === 3 && styles.gap, expired && styles.expired]}>
                <Text role="display">{digit}</Text>
              </View>
            ))}
          </View>
        )}
        {code && !expired ? (
          <Text role="bodySmall" color="text2" align="center">
            Expires in{' '}
            <Text role="bodySmall" color="yellow">
              {`${Math.floor(secondsLeft / 60)}:${String(secondsLeft % 60).padStart(2, '0')}`}
            </Text>
          </Text>
        ) : null}
        {expired ? (
          <Button label="This code expired. Get a new one" onPress={() => newCode()} loading={pairing.isPending} />
        ) : (
          <Button label={copied ? 'Copied' : 'Copy code'} variant="ghost" onPress={copy} disabled={!code} />
        )}
      </Card>

      <Card style={styles.waiting}>
        <Loader label="Waiting for the agent" />
        <View style={styles.waitingText}>
          <Text role="title">Waiting for the agent…</Text>
          <Text role="bodySmall" color="text2">
            Keep this screen open. It changes as soon as the PC connects.
          </Text>
        </View>
      </Card>

      <SectionLabel>On a PC on that network</SectionLabel>
      <Card>
        <Step n={1}>Open PowerShell as Administrator in the KinLAN agent folder.</Step>
        <Step n={2}>{'Run  kinlan-agent pair  and type the code above.'}</Step>
        <Step n={3}>
          Agree to the prompt: “Only monitor networks you own or are authorized to monitor.”
        </Step>
        <Step n={4}>{'Start monitoring with  kinlan-agent run  and keep it open.'}</Step>
      </Card>
    </FormScreen>
  );
}

function Step({ n, children }: { n: number; children: string }) {
  return (
    <View style={styles.step}>
      <View style={styles.stepNumber}>
        <Text role="labelSmall">{String(n)}</Text>
      </View>
      <View style={styles.stepText}>
        <Text role="body" color="text2">
          {children}
        </Text>
      </View>
    </View>
  );
}

function Connected({ siteName, devices }: { siteName: string; devices: number | undefined }) {
  return (
    <FormScreen>
      <Card style={styles.connected}>
        <StatusChip tone="ok" label="Connected" />
        <Text role="headline">{`${siteName} is connected`}</Text>
        <Text role="body" color="text2">
          The agent is measuring the network now. Every device it finds in this first scan is
          your baseline, so none of them raise a “new device” alert.
        </Text>
      </Card>
      <Card>
        {devices ? (
          <>
            <Text role="title">{`We found ${devices} ${devices === 1 ? 'device' : 'devices'}`}</Text>
            <Text role="bodySmall" color="text2">
              Review them in the Devices tab: name them and say whose they are. You can do it
              later.
            </Text>
          </>
        ) : (
          <View style={styles.scanning}>
            <Loader label="Scanning the network" />
            <Text role="bodySmall" color="text2">
              Scanning the network for devices. This takes about 15 seconds.
            </Text>
          </View>
        )}
      </Card>
      <Button label="Go to Overview" onPress={() => router.replace('/')} />
    </FormScreen>
  );
}

const styles = StyleSheet.create({
  codeCard: { alignItems: 'stretch', gap: space.s4, paddingVertical: space.s6 },
  digits: { flexDirection: 'row', justifyContent: 'center', gap: space.s2 },
  digit: {
    width: 44,
    height: 60,
    borderRadius: radius.inner,
    borderCurve: 'continuous',
    backgroundColor: colors.raised,
    alignItems: 'center',
    justifyContent: 'center',
  },
  gap: { marginLeft: space.s3 },
  expired: { opacity: 0.35 },
  waiting: { flexDirection: 'row', alignItems: 'center', gap: space.s4 },
  waitingText: { flex: 1, gap: 2 },
  step: { flexDirection: 'row', gap: space.s3, paddingVertical: space.s1 },
  stepNumber: {
    width: 24,
    height: 24,
    borderRadius: radius.pill,
    backgroundColor: colors.raised,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 1,
  },
  stepText: { flex: 1 },
  connected: { gap: space.s3 },
  scanning: { flexDirection: 'row', alignItems: 'center', gap: space.s3 },
});
