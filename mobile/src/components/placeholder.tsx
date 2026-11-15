import { Card, SectionLabel, Text } from '@/components/ui';

/** Stand-in for a screen that arrives with a later Sprint 3 issue. */
export function ComingNext({ issue, what }: { issue: number; what: string }) {
  return (
    <>
      <SectionLabel>Coming next</SectionLabel>
      <Card>
        <Text role="title">{what}</Text>
        <Text role="bodySmall" color="text2">
          {`Built in issue #${issue}. The interactive prototype in docs/design/prototype shows the design.`}
        </Text>
      </Card>
    </>
  );
}
