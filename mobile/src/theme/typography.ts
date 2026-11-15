import type { TextStyle } from 'react-native';

/**
 * The nine type roles from docs/design/direction.md, set in Manrope (Material 3 roles).
 * Sizes are in sp, so they follow the phone's text-size setting.
 */
export const FONT_FAMILY = 'Manrope';

type Role = Pick<TextStyle, 'fontSize' | 'lineHeight' | 'fontWeight' | 'letterSpacing' | 'textTransform'>;

export const type = {
  /** 36/40 · the health score */
  display: { fontSize: 36, lineHeight: 40, fontWeight: '800', letterSpacing: -1.26 },
  /** 28/34 · tab-screen titles, the verdict, the root cause */
  headline: { fontSize: 28, lineHeight: 34, fontWeight: '800', letterSpacing: -0.56 },
  /** 22/28 · site name, sheet and pushed-screen titles */
  titleLarge: { fontSize: 22, lineHeight: 28, fontWeight: '800', letterSpacing: -0.26 },
  /** 16/22 · row, person and check titles */
  title: { fontSize: 16, lineHeight: 22, fontWeight: '700' },
  /** 15/22 · sentences (one step heavier than 400: light text on black) */
  body: { fontSize: 15, lineHeight: 22, fontWeight: '500' },
  /** 13/18 · secondary lines, facts, captions */
  bodySmall: { fontSize: 13, lineHeight: 18, fontWeight: '500' },
  /** 15/20 · buttons */
  label: { fontSize: 15, lineHeight: 20, fontWeight: '800' },
  /** 12/16 · chips, navigation, small controls */
  labelSmall: { fontSize: 12, lineHeight: 16, fontWeight: '700' },
  /** 11/14 · silkscreen labels: uppercase, wide tracking (docs/design/brand.md) */
  silk: { fontSize: 11, lineHeight: 14, fontWeight: '800', letterSpacing: 1.32, textTransform: 'uppercase' },
} as const satisfies Record<string, Role>;

export type TypeRole = keyof typeof type;
