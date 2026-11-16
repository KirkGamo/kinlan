import { useState } from 'react';
import { Pressable, StyleSheet, TextInput, View, type TextInputProps } from 'react-native';

import { colors, FONT_FAMILY, radius, space, strokes, touch, type } from '@/theme';

import { Loader } from './brand';
import { Text } from './text';

type ButtonProps = {
  label: string;
  onPress: () => void;
  /** primary: the yellow action; ghost: neutral; danger: destructive (red label, never filled). */
  variant?: 'primary' | 'ghost' | 'danger';
  loading?: boolean;
  disabled?: boolean;
  accessibilityHint?: string;
};

/** Pill button. Primary is the yellow brand button with black text; ghost is the raised grey. */
export function Button({ label, onPress, variant = 'primary', loading, disabled, accessibilityHint }: ButtonProps) {
  const inactive = disabled || loading;
  return (
    <Pressable
      onPress={onPress}
      disabled={inactive}
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityHint={accessibilityHint}
      accessibilityState={{ disabled: inactive, busy: loading }}
      style={({ pressed }) => [
        styles.button,
        variant === 'primary' ? styles.primary : styles.ghost,
        variant === 'danger' && styles.danger,
        pressed && styles.pressed,
        disabled && !loading && styles.disabled,
      ]}>
      {loading ? (
        <Loader label={`${label}…`} />
      ) : (
        <Text role="label" color={variant === 'primary' ? 'onYellow' : variant === 'danger' ? 'red' : 'text'}>
          {label}
        </Text>
      )}
    </Pressable>
  );
}

type FieldProps = Pick<
  TextInputProps,
  | 'value'
  | 'onChangeText'
  | 'autoComplete'
  | 'textContentType'
  | 'keyboardType'
  | 'autoCapitalize'
  | 'returnKeyType'
  | 'autoFocus'
  | 'onSubmitEditing'
  | 'placeholder'
> & {
  label: string;
  error?: string | null;
  hint?: string;
  secret?: boolean;
};

/** A labelled text field with an error line and, for passwords, a Show/Hide toggle. */
export function TextField({ label, error, hint, secret, ...input }: FieldProps) {
  const [focused, setFocused] = useState(false);
  const [hidden, setHidden] = useState(true);
  return (
    <View style={styles.field}>
      <Text role="labelSmall" color="text2">
        {label}
      </Text>
      <View style={[styles.box, focused && styles.boxFocused, error ? styles.boxError : null]}>
        <TextInput
          {...input}
          accessibilityLabel={label}
          accessibilityHint={hint}
          secureTextEntry={secret && hidden}
          autoCorrect={false}
          placeholderTextColor={colors.text2}
          selectionColor={colors.yellow}
          cursorColor={colors.yellow}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          style={styles.input}
        />
        {secret ? (
          <Pressable
            onPress={() => setHidden((h) => !h)}
            accessibilityRole="button"
            accessibilityLabel={hidden ? 'Show password' : 'Hide password'}
            style={styles.toggle}>
            <Text role="labelSmall" color="yellow">
              {hidden ? 'Show' : 'Hide'}
            </Text>
          </Pressable>
        ) : null}
      </View>
      {error ? (
        <Text role="bodySmall" color="red" accessibilityRole="alert">
          {error}
        </Text>
      ) : hint ? (
        <Text role="bodySmall" color="text2">
          {hint}
        </Text>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  button: {
    minHeight: 52,
    borderRadius: radius.pill,
    paddingHorizontal: space.s6,
    alignItems: 'center',
    justifyContent: 'center',
  },
  primary: { backgroundColor: colors.yellow },
  ghost: { backgroundColor: colors.raised },
  danger: { borderWidth: 1, borderColor: strokes.red },
  pressed: { transform: [{ scale: 0.97 }] },
  disabled: { opacity: 0.5 },
  field: { gap: space.s2 },
  box: {
    minHeight: touch.min + 4,
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.raised,
    borderRadius: 16,
    borderCurve: 'continuous',
    borderWidth: 1.5,
    borderColor: colors.border,
    paddingLeft: space.s4,
  },
  boxFocused: { borderColor: colors.yellow },
  boxError: { borderColor: colors.red },
  input: {
    flex: 1,
    minHeight: touch.min,
    color: colors.text,
    fontFamily: FONT_FAMILY,
    fontSize: type.body.fontSize,
    fontWeight: type.body.fontWeight,
    paddingRight: space.s4,
  },
  toggle: { minHeight: touch.min, minWidth: touch.min, paddingHorizontal: space.s4, justifyContent: 'center' },
});
