import { Text as RNText, type TextProps as RNTextProps } from 'react-native';

import { colors, FONT_FAMILY, type, type ColorToken, type TypeRole } from '@/theme';

export type TextProps = Pick<
  RNTextProps,
  | 'children'
  | 'numberOfLines'
  | 'accessibilityRole'
  | 'accessibilityLabel'
  | 'accessibilityLiveRegion'
  | 'selectable'
  | 'testID'
> & {
  /** A type role from the theme; never a raw font size. */
  role?: TypeRole;
  color?: ColorToken;
  align?: 'left' | 'center' | 'right';
  /** Tabular figures, so changing numbers don't shift (briefs.md: numbers are tabular). */
  tabular?: boolean;
};

const TABULAR = { fontVariant: ['tabular-nums' as const] };

/** All text in the app goes through this, so every string uses a theme role and Manrope. */
export function Text({ role = 'body', color = 'text', align, tabular, ...props }: TextProps) {
  return (
    <RNText
      {...props}
      style={[
        { fontFamily: FONT_FAMILY, color: colors[color], textAlign: align },
        type[role],
        tabular && TABULAR,
      ]}
    />
  );
}
