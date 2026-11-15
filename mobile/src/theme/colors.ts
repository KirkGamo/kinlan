/**
 * Colour tokens from docs/design/direction.md (contrast-checked: text ≥ 4.5:1, icons ≥ 3:1).
 * Yellow is brand and selection only; status always pairs its colour with an icon and a word.
 */
export const colors = {
  bg: '#0B0B0C',
  card: '#161618',
  raised: '#1F1F23',
  border: '#2C2C31',

  text: '#F5F5F7',
  text2: '#A1A1AA', // secondary text: 7.05:1 on card

  yellow: '#FFD60A', // brand and selection only, never a status
  onYellow: '#0B0B0C',

  green: '#30D158', // healthy
  orange: '#FF9F0A', // degraded or new
  red: '#FF453A', // down
  onRed: '#0B0B0C', // black on red is 5.78:1; white fails at 3.4:1

  unlit: '#2A2A2F', // a status light that isn't lit
  unlitRing: '#5E5E66',
} as const;

/** Tinted chip backgrounds behind status text (the text uses the full colour). */
export const tints = {
  green: 'rgba(48, 209, 88, 0.14)',
  orange: 'rgba(255, 159, 10, 0.16)',
  red: 'rgba(255, 69, 58, 0.16)',
} as const;

export type ColorToken = keyof typeof colors;
