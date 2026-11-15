import { useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import Svg, { Path } from 'react-native-svg';

import type { Site, SiteStatus } from '@/api/circles';
import { Sheet, StatusChip, Text, type ChipTone } from '@/components/ui';
import { colors, radius, space } from '@/theme';

export const SITE_STATUS: Record<SiteStatus, { tone: ChipTone; label: string }> = {
  online: { tone: 'ok', label: 'Online' },
  degraded: { tone: 'new', label: 'Degraded' },
  unreachable: { tone: 'down', label: 'Unreachable' },
  pending: { tone: 'neutral', label: 'Not paired' },
};

/**
 * The Overview header: the site name (Title large, so it never competes with the verdict) and,
 * with two or more sites, a switcher listing each site with its state.
 */
export function SiteHeader({
  site,
  sites,
  sub,
  onSwitch,
}: {
  site: Site;
  sites: Site[];
  sub: string;
  onSwitch: (id: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const many = sites.length > 1;
  return (
    <View style={styles.head}>
      <Pressable
        disabled={!many}
        onPress={() => setOpen(true)}
        accessibilityRole={many ? 'button' : 'header'}
        accessibilityLabel={many ? `${site.name}. Switch site` : site.name}
        style={({ pressed }) => [styles.name, pressed && styles.pressed]}>
        <Text role="titleLarge" numberOfLines={1}>
          {site.name}
        </Text>
        {many ? (
          <Svg width={20} height={20} viewBox="0 0 24 24">
            <Path d="M7 10l5 5 5-5z" fill={colors.text} />
          </Svg>
        ) : null}
      </Pressable>
      <Text role="bodySmall" color="text2" tabular>
        {sub}
      </Text>
      <Sheet open={open} onClose={() => setOpen(false)} title="Switch site">
        <View style={styles.list}>
          {sites.map((s) => {
            const st = SITE_STATUS[s.status];
            const current = s.id === site.id;
            return (
              <Pressable
                key={s.id}
                onPress={() => {
                  setOpen(false);
                  onSwitch(s.id);
                }}
                accessibilityRole="radio"
                accessibilityState={{ checked: current }}
                accessibilityLabel={`${s.name}, ${st.label}`}
                style={({ pressed }) => [styles.row, current && styles.current, pressed && styles.pressed]}>
                <View style={styles.rowText}>
                  <Text role="title">{s.name}</Text>
                  <Text role="bodySmall" color="text2">
                    {current ? 'Showing now' : (s.cidr ?? 'Waiting for its agent')}
                  </Text>
                </View>
                <StatusChip tone={st.tone} label={st.label} />
              </Pressable>
            );
          })}
        </View>
      </Sheet>
    </View>
  );
}

const styles = StyleSheet.create({
  head: { gap: 2 },
  name: { flexDirection: 'row', alignItems: 'center', gap: space.s1, alignSelf: 'flex-start', minHeight: 44, borderRadius: radius.pill },
  pressed: { opacity: 0.7 },
  list: { gap: space.item },
  row: {
    minHeight: 68,
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.s3,
    backgroundColor: colors.raised,
    borderRadius: radius.row,
    paddingHorizontal: space.s4,
    paddingVertical: space.s3,
    borderWidth: 2,
    borderColor: 'transparent',
  },
  current: { borderColor: colors.yellow },
  rowText: { flex: 1, gap: 2 },
});
