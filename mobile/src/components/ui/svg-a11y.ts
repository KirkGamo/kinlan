import { Platform } from 'react-native';
import type { SvgProps } from 'react-native-svg';

/**
 * Accessibility props for an <Svg>. react-native-svg hands its props to the DOM on the web, where
 * `accessible` and `accessibilityLabel` aren't attributes (React warns, and screen readers get
 * nothing), so the web gets ARIA instead.
 */

/** An icon or ornament next to text that already says it: hidden from screen readers. */
export const decorative: SvgProps = (
  Platform.OS === 'web' ? { 'aria-hidden': true } : { accessible: false }
) as SvgProps;

/** A chart or map that a screen reader reads as one image with this description. */
export function described(label: string): SvgProps {
  return (
    Platform.OS === 'web'
      ? { role: 'img', 'aria-label': label }
      : { accessible: true, accessibilityLabel: label }
  ) as SvgProps;
}
