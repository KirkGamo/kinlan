import { Link } from 'expo-router';
import { useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { ApiError } from '@/api/client';
import { useSession } from '@/api/session';
import { Button, FormScreen, Text, TextField } from '@/components/ui';
import { space } from '@/theme';

type Errors = { name?: string; email?: string; password?: string; form?: string };

export default function SignUpScreen() {
  const { signUp } = useSession();
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<Errors>({});

  async function submit() {
    const found: Errors = {};
    if (!name.trim()) found.name = 'Enter the name your Circle will see.';
    if (!/^\S+@\S+\.\S+$/.test(email.trim())) found.email = 'Enter an email address like ana@example.com.';
    if (password.length < 8) found.password = 'Use at least 8 characters.';
    setErrors(found);
    if (Object.keys(found).length) return;

    setBusy(true);
    try {
      await signUp(name, email, password); // on success the navigator switches to the app
    } catch (e) {
      if (e instanceof ApiError && e.code === 'email_taken') {
        setErrors({ email: 'That email already has an account. Sign in instead.' });
      } else if (e instanceof ApiError && e.code === 'validation_error' && e.message.startsWith('email')) {
        // The server's validator is stricter than ours (for example reserved domains).
        setErrors({ email: 'That email address doesn’t look right. Check it and try again.' });
      } else {
        setErrors({ form: e instanceof ApiError ? e.message : 'Something went wrong. Try again.' });
      }
      setBusy(false);
    }
  }

  return (
    <FormScreen>
      <Text role="body" color="text2">
        You’ll create or join a Circle next: the people who look after a network together.
      </Text>
      <View style={styles.fields}>
        <TextField
          label="Your name"
          value={name}
          onChangeText={setName}
          error={errors.name}
          autoCapitalize="words"
          autoComplete="name"
          textContentType="name"
          returnKeyType="next"
        />
        <TextField
          label="Email"
          value={email}
          onChangeText={setEmail}
          error={errors.email}
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
          error={errors.password}
          hint="At least 8 characters."
          secret
          autoCapitalize="none"
          autoComplete="new-password"
          textContentType="newPassword"
          returnKeyType="go"
          onSubmitEditing={submit}
        />
      </View>
      {errors.form ? (
        <Text role="bodySmall" color="red" accessibilityRole="alert">
          {errors.form}
        </Text>
      ) : null}
      <Button label="Create account" onPress={submit} loading={busy} />
      <Text role="bodySmall" color="text2" align="center">
        Already have an account?{' '}
        <Link href="/sign-in" replace>
          <Text role="bodySmall" color="yellow">
            Sign in
          </Text>
        </Link>
      </Text>
    </FormScreen>
  );
}

const styles = StyleSheet.create({ fields: { gap: space.s4 } });
