import { useId } from 'react';
import { StyleSheet } from 'react-native';
import Svg, { Circle, Defs, LinearGradient, Mask, Pattern, RadialGradient, Rect, Stop } from 'react-native-svg';
import { decorative } from './svg-a11y';

import { colors } from '@/theme';

/**
 * The perforated texture (brand.md: verdict card and splash only): a 9-dp grid of faint dots,
 * strongest at the top-right corner and gone by about 60% of the way across (prototype `.perf`).
 * Sits behind the card's content; the card must clip its corners (overflow: hidden).
 * `from="center"` is the splash's version: strongest just above the middle, fading out evenly.
 */
export function Perforation({ from = 'corner' }: { from?: 'corner' | 'center' }) {
  const id = useId().replace(/[^a-zA-Z0-9]/g, '');
  return (
    <Svg style={StyleSheet.absoluteFill} pointerEvents="none" {...decorative}>
      <Defs>
        <Pattern id={`dots${id}`} width={9} height={9} patternUnits="userSpaceOnUse">
          <Circle cx={4.5} cy={4.5} r={1.1} fill={colors.text} fillOpacity={0.08} />
        </Pattern>
        {from === 'center' ? (
          <RadialGradient id={`fade${id}`} cx="50%" cy="46%" r="62%">
            <Stop offset="0" stopColor="#fff" stopOpacity={1} />
            <Stop offset="1" stopColor="#fff" stopOpacity={0} />
          </RadialGradient>
        ) : (
          <LinearGradient id={`fade${id}`} x1="1" y1="0" x2="0" y2="1">
            <Stop offset="0" stopColor="#fff" stopOpacity={1} />
            <Stop offset="0.6" stopColor="#fff" stopOpacity={0} />
          </LinearGradient>
        )}
        <Mask id={`mask${id}`}>
          <Rect width="100%" height="100%" fill={`url(#fade${id})`} />
        </Mask>
      </Defs>
      <Rect width="100%" height="100%" fill={`url(#dots${id})`} mask={`url(#mask${id})`} />
    </Svg>
  );
}
