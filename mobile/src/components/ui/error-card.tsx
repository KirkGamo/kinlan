import { Card } from './layout';
import { Button } from './controls';
import { StatusChip } from './status-chip';
import { Text } from './text';

/** A load that failed: what went wrong in plain words, and a way to try again. */
export function ErrorCard({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <Card>
      <StatusChip tone="down" label="Couldn’t load" />
      <Text role="body" color="text2">
        {message}
      </Text>
      <Button label="Try again" variant="ghost" onPress={onRetry} />
    </Card>
  );
}
