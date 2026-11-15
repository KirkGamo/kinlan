import { router } from 'expo-router';
import { useState } from 'react';

import { useJoinCircle } from '@/api/circles';
import { Button, FormScreen, Text, TextField } from '@/components/ui';

export default function JoinScreen() {
  const join = useJoinCircle();
  const [code, setCode] = useState('');
  const [error, setError] = useState<string | null>(null);

  function submit() {
    if (code.replace(/[^a-z0-9]/gi, '').length !== 8) {
      setError('An invite code has 8 letters and numbers, like K7QM-2RXP.');
      return;
    }
    setError(null);
    join.mutate(code, {
      onSuccess: () => router.replace('/'), // straight to that Circle's Overview
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
      <Button label="Join" onPress={submit} loading={join.isPending} />
    </FormScreen>
  );
}
