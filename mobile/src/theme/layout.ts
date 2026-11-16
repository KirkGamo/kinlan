import { Easing } from 'react-native-reanimated';

/** Spacing on a 4-dp grid (direction.md). In dp, so it doesn't grow with text size. */
export const space = {
  s1: 4,
  s2: 8,
  s3: 12,
  s4: 16,
  s5: 20,
  s6: 24,
  s8: 32,
  gutter: 16, // screen side margin (Material compact)
  card: 20, // inside cards and sheets
  item: 8, // between rows of one group
  section: 32, // above a section label; 12 below
} as const;

export const radius = {
  card: 24,
  row: 20,
  sheet: 28,
  tile: 18, // the sheet head's icon tile
  field: 16, // text fields
  inner: 14, // panels inside a card or row (Diagnose detail, pairing digits)
  small: 8, // ping reply cells, skeleton bars
  pill: 999,
} as const;

/** Component sizes used on more than one screen. */
export const size = {
  row: 68, // a list row: device, problem, rung, member, action
  loading: 120, // a card that only holds a loader
  well: 40, // round icon wells and avatars in rows
} as const;

/** Touch targets: 48 dp minimum (PRODUCT.md, Material). */
export const touch = { min: 48 } as const;

/**
 * Motion system (direction.md). Only transform and opacity animate. Reduce Motion turns every
 * movement into a 120 ms fade and stops loops.
 */
export const motion = {
  press: 120,
  small: 220,
  screen: 350,
  lightStagger: 110,
  reducedFade: 120,
  easing: {
    decelerate: Easing.bezier(0.05, 0.7, 0.1, 1), // arrivals
    standard: Easing.bezier(0.2, 0, 0, 1), // changes in place
    accelerate: Easing.bezier(0.3, 0, 0.8, 0.15), // exits
  },
} as const;
