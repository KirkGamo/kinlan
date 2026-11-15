import { Link } from 'expo-router';
import { useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { ApiError } from '@/api/client';
import { useSession } from '@/api/session';
import { Button, FormScreen, Text, TextField } from '@/components/ui';
import { space } from '@/theme';

export default function SignInScreen() {
  const { signIn } = useSession();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    if (!email.includes('@') || !password) {
      setError('Enter your email and password.');
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await signIn(email, password); // on success the navigator switches to the app
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Something went wrong. Try again.');
      setBusy(false);
    }
  }

  return (
    <FormScreen>
      <Text role="body" color="text2">
        Welcome back. Sign in to see your Circle’s networks.
      </Text>
      <View style={styles.fields}>
        <TextField
          label="Email"
          value={email}
          onChangeText={setEmail}
          keyboardType="email-address"
          autoCapitalize="none"
          autoComplete="email"
          textContentType="emailAddress"
          returnKeyType="next"
        />
        <TextField
          label="Password"
          value={password}
          onChangeText={setPassword}
          secret
          autoCapitalize="none"
          autoComplete="current-password"
          textContentType="password"
          returnKeyType="go"
          onSubmitEditing={submit}
        />
      </View>
      {error ? (
        <Text role="bodySmall" color="red" accessibilityRole="alert">
          {error}
        </Text>
      ) : null}
      <Button label="Sign in" onPress={submit} loading={busy} />
      <Text role="bodySmall" color="text2" align="center">
        New to KinLAN?{' '}
        <Link href="/sign-up" replace>
          <Text role="bodySmall" color="yellow">
            Create an account
          </Text>
        </Link>
      </Text>
    </FormScreen>
  );
}

const styles = StyleSheet.create({ fields: { gap: space.s4 } });
