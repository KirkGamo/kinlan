import { router, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';

import { useCreateSite } from '@/api/circles';
import { Button, FormScreen, Text, TextField } from '@/components/ui';

/** A site is one network: one agent watches it. */
export default function NewSiteScreen() {
  const { circle } = useLocalSearchParams<{ circle: string }>();
  const create = useCreateSite(circle);
  const [name, setName] = useState('');
  const [error, setError] = useState<string | null>(null);

  function submit() {
    if (!name.trim()) {
      setError('Name the network, for example “Home” or “Lab 3”.');
      return;
    }
    setError(null);
    create.mutate(name, {
      onSuccess: (site) => router.replace({ pathname: '/onboarding/pair', params: { site: site.id } }),
      onError: (e) => setError(e.message),
    });
  }

  return (
    <FormScreen>
      <Text role="body" color="text2">
        A site is one network, like your home Wi-Fi or a lab. You’ll pair a PC on it next.
      </Text>
      <TextField
        label="Site name"
        value={name}
        onChangeText={setName}
        error={error}
        placeholder="Home"
        autoCapitalize="words"
        returnKeyType="go"
        onSubmitEditing={submit}
      />
      <Button label="Continue" onPress={submit} loading={create.isPending} />
    </FormScreen>
  );
}
