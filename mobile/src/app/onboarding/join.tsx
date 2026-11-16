import { router } from 'expo-router';
import { useEffect, useState } from 'react';

import { useCircles, useJoinCircle } from '@/api/circles';
import { selectCircle } from '@/api/selection';
import { Button, FormScreen, Text, TextField } from '@/components/ui';

export default function JoinScreen() {
  const join = useJoinCircle();
  const circles = useCircles();
  const [code, setCode] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [joined, setJoined] = useState<string | null>(null);

  // Leave only once the app's own Circles list has the new one: the tabs are guarded by that
  // list, so navigating any earlier lands back on onboarding (seen on a phone, Nov 17).
  const arrived = joined != null && (circles.data?.some((c) => c.id === joined) ?? false);
  useEffect(() => {
    if (!arrived || joined == null) return;
    selectCircle(joined); // open the Circle you just joined, not whichever came first
    router.replace('/');
  }, [arrived, joined]);

  function submit() {
    if (code.replace(/[^a-z0-9]/gi, '').length !== 8) {
      setError('An invite code has 8 letters and numbers, like K7QM-2RXP.');
      return;
    }
    setError(null);
    join.mutate(code, {
      onSuccess: (circle) => setJoined(circle.id), // then straight to that Circle's Overview
      onError: (e) => setError(e.message),
    });
  }

  return (
    <FormScreen>
      <Text role="body" color="text2">
        Ask someone in the Circle to share an invite code from Settings. Codes work once and
        expire after 7 days.
      </Text>
      <TextField
        label="Invite code"
        value={code}
        onChangeText={setCode}
        error={error}
        placeholder="K7QM-2RXP"
        autoCapitalize="characters"
        returnKeyType="go"
        onSubmitEditing={submit}
      />
      <Button label="Join" onPress={submit} loading={join.isPending || (joined != null && !arrived)} />
    </FormScreen>
  );
}
