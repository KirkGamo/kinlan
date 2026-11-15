import { router } from 'expo-router';
import { useState } from 'react';

import { useCreateCircle } from '@/api/circles';
import { Button, FormScreen, Text, TextField } from '@/components/ui';

export default function NewCircleScreen() {
  const create = useCreateCircle();
  const [name, setName] = useState('');
  const [error, setError] = useState<string | null>(null);

  function submit() {
    if (!name.trim()) {
      setError('Give your Circle a name, for example “Dela Cruz Home” or “Lab 3”.');
      return;
    }
    setError(null);
    create.mutate(name, {
      onSuccess: (circle) => router.replace({ pathname: '/onboarding/new-site', params: { circle: circle.id } }),
      onError: (e) => setError(e.message),
    });
  }

  return (
    <FormScreen>
      <Text role="body" color="text2">
        Name it after the people or the place, so everyone recognises it.
      </Text>
      <TextField
        label="Circle name"
        value={name}
        onChangeText={setName}
        error={error}
        placeholder="Dela Cruz Home"
        autoCapitalize="words"
        returnKeyType="go"
        onSubmitEditing={submit}
      />
      <Button label="Continue" onPress={submit} loading={create.isPending} />
    </FormScreen>
  );
}
