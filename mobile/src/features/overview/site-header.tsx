import { useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import Svg, { Path } from 'react-native-svg';

import type { Site, SiteStatus } from '@/api/circles';
import { Sheet, StatusChip, Text, type ChipTone } from '@/components/ui';
import { AccountButton } from '@/features/account/account-sheet';
import { colors, radius, space, touch } from '@/theme';

export const SITE_STATUS: Record<SiteStatus, { tone: ChipTone; label: string }> = {
  online: { tone: 'ok', label: 'Online' },
  degraded: { tone: 'new', label: 'Degraded' },
  unreachable: { tone: 'down', label: 'Unreachable' },
  pending: { tone: 'neutral', label: 'Not paired' },
};

/**
 * The tab header. Overview leads with the site name (Title large, so it never competes with the
 * verdict); the other tabs pass `title` and lead with the screen ("Devices", "Alerts"), with the
 * site in the line below (prototype). With two or more sites, the site name opens a switcher.
 */
export function SiteHeader({
  site,
  sites,
  sub,
  onSwitch,
  title,
}: {
  site: Site;
  sites: Site[];
  sub: string;
  onSwitch: (id: string) => void;
  /** The screen's name; when set, the site moves to the subtitle. */
  title?: string;
}) {
  const [open, setOpen] = useState(false);
  const many = sites.length > 1;
  const chevron = (size: number, color: string) => (
    <Svg width={size} height={size} viewBox="0 0 24 24">
      <Path d="M7 10l5 5 5-5z" fill={color} />
    </Svg>
  );
  return (
    <View style={styles.bar}>
      <View style={styles.head}>
        {title ? (
          <>
            <Text role="titleLarge" accessibilityRole="header" numberOfLines={1}>
              {title}
            </Text>
            <Pressable
              disabled={!many}
              onPress={() => setOpen(true)}
              accessibilityRole={many ? 'button' : undefined}
              accessibilityLabel={many ? `${site.name}, ${sub}. Switch site` : `${site.name}, ${sub}`}
              style={({ pressed }) => [styles.subRow, pressed && styles.pressed]}>
              <Text role="bodySmall" color={many ? 'text' : 'text2'}>
                {site.name}
              </Text>
              {many ? chevron(16, colors.text) : null}
              <Text role="bodySmall" color="text2" tabular numberOfLines={1}>
                {` · ${sub}`}
              </Text>
            </Pressable>
          </>
        ) : (
          <>
            <Pressable
              disabled={!many}
              onPress={() => setOpen(true)}
              accessibilityRole={many ? 'button' : 'header'}
              accessibilityLabel={many ? `${site.name}. Switch site` : site.name}
              style={({ pressed }) => [styles.name, pressed && styles.pressed]}>
              <Text role="titleLarge" numberOfLines={1}>
                {site.name}
              </Text>
              {many ? chevron(20, colors.text) : null}
            </Pressable>
            <Text role="bodySmall" color="text2" tabular>
              {sub}
            </Text>
          </>
        )}
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
      <AccountButton />
    </View>
  );
}

const styles = StyleSheet.create({
  bar: { flexDirection: 'row', alignItems: 'flex-start', gap: space.s3 },
  head: { flex: 1, gap: 2 },
  name: { flexDirection: 'row', alignItems: 'center', gap: space.s1, alignSelf: 'flex-start', minHeight: touch.min, borderRadius: radius.pill },
  subRow: { flexDirection: 'row', alignItems: 'center', alignSelf: 'flex-start', minHeight: 24, flexShrink: 1 },
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
