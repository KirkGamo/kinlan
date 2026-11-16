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
  /** 700 weight within the role's size: values in sheet facts (prototype). */
  strong?: boolean;
};

const TABULAR = { fontVariant: ['tabular-nums' as const] };
const STRONG = { fontWeight: '700' as const };

/** All text in the app goes through this, so every string uses a theme role and Manrope. */
export function Text({ role = 'body', color = 'text', align, tabular, strong, ...props }: TextProps) {
  return (
    <RNText
      {...props}
      style={[
        { fontFamily: FONT_FAMILY, color: colors[color], textAlign: align },
        type[role],
        tabular && TABULAR,
        strong && STRONG,
      ]}
    />
  );
}
