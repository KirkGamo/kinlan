import { useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { useSites } from '@/api/circles';
import { openReport, useCreateReport, type Report, type ReportRange } from '@/api/reports';
import { useCurrentCircle } from '@/api/selection';
import { Button, Card, FormScreen, Segmented, StatusChip, Text } from '@/components/ui';
import { day } from '@/features/overview/model';
import { haptics } from '@/haptics';
import { space } from '@/theme';

const RANGES: { key: ReportRange; label: string }[] = [
  { key: '24h', label: '24 hours' },
  { key: '7d', label: '7 days' },
  { key: '30d', label: '30 days' },
];

/** What's inside, in the report's own order (server app/reports.py). */
const CONTENTS = [
  'The connection chart, with outages marked',
  'Ping results for the router, the internet and tested devices',
  'Every outage, how long it lasted and why',
  'The health grade and what lowered it',
  'Security advice: what to fix first, then router settings',
  'Every device: address, maker, trusted or not',
];

/**
 * Network report (plan, Section 4.7; required Features 4 and 5): pick a range, make the PDF,
 * open it to save, share or print. Any member can make one.
 */
export default function ReportScreen() {
  const { site: siteId } = useLocalSearchParams<{ site: string }>();
  const { circle } = useCurrentCircle();
  const site = useSites(circle?.id).data?.find((s) => s.id === siteId);
  const create = useCreateReport(siteId);
  const [range, setRange] = useState<ReportRange>('7d');
  const [made, setMade] = useState<Report | null>(null);
  const [opening, setOpening] = useState(false);
  const [openError, setOpenError] = useState<string | null>(null);

  function make() {
    setMade(null);
    setOpenError(null);
    create.mutate(range, {
      onSuccess: (report) => {
        haptics.confirm();
        setMade(report);
      },
      onError: haptics.reject,
    });
  }

  async function open(report: Report) {
    setOpening(true);
    setOpenError(null);
    try {
      await openReport(report.id);
    } catch (e) {
      setOpenError(e instanceof Error ? e.message : 'The PDF didn’t open. Try again.');
    } finally {
      setOpening(false);
    }
  }

  return (
    <FormScreen>
      <View style={styles.intro}>
        <Text role="headline">{site ? `${site.name} report` : 'Network report'}</Text>
        <Text role="body" color="text2">
          A PDF to keep, share with your internet provider or print. It covers:
        </Text>
        <View style={styles.list}>
          {CONTENTS.map((line) => (
            <Text key={line} role="bodySmall" color="text2">
              {`·  ${line}`}
            </Text>
          ))}
        </View>
      </View>

      <Segmented label="Report range" options={RANGES} value={range} onChange={(k) => setRange(k)} />
      <Button label={made ? 'Make it again' : 'Make the report'} variant={made ? 'ghost' : 'primary'} onPress={make} loading={create.isPending} />

      {create.isError ? (
        <Text role="body" color="red" accessibilityRole="alert">
          {create.error.message}
        </Text>
      ) : null}

      {made ? (
        <Card>
          <StatusChip tone="ok" label="Ready" />
          <Text role="title">{made.filename}</Text>
          <Text role="bodySmall" color="text2">
            {`${day(made.range_start)} to ${day(made.range_end)}`}
          </Text>
          <Button label="Open the PDF" onPress={() => void open(made)} loading={opening} accessibilityHint="Opens the report in your browser, where you can save, share or print it" />
          {openError ? (
            <Text role="bodySmall" color="red" accessibilityRole="alert">
              {openError}
            </Text>
          ) : null}
        </Card>
      ) : null}
    </FormScreen>
  );
}

const styles = StyleSheet.create({
  intro: { gap: space.s2 },
  list: { gap: space.s1, paddingLeft: space.s1 },
});
