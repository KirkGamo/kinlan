import { router } from 'expo-router';
import { useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import type { Role } from '@/api/circles';
import { selectCircle, useCurrentCircle } from '@/api/selection';
import { useMe, useSession } from '@/api/session';
import { Button, Sheet, Text } from '@/components/ui';
import { colors, radius, space } from '@/theme';

import { Avatar } from './avatar';

export const ROLE_WORD: Record<Role, string> = { owner: 'Owner', admin: 'Admin', viewer: 'Viewer' };

/**
 * The avatar at the top right of the four tabs and its account sheet (briefs.md interaction
 * model): you, your role here, Your Circles to switch between, Account settings and Sign out.
 * Switching a Circle returns to Overview.
 */
export function AccountButton() {
  const me = useMe();
  const { circles, circle } = useCurrentCircle();
  const { signOut } = useSession();
  const [open, setOpen] = useState(false);
  const [leaving, setLeaving] = useState(false);
  const name = me.data?.display_name ?? '';

  return (
    <>
      <Pressable
        onPress={() => setOpen(true)}
        accessibilityRole="button"
        accessibilityLabel={`Account: ${name}`}
        accessibilityHint="Your Circles, account settings and sign out"
        hitSlop={4}
        style={({ pressed }) => [pressed && styles.pressed]}>
        <Avatar name={name || '?'} me size={40} />
      </Pressable>
      <Sheet open={open} onClose={() => setOpen(false)} title={name || 'Account'}>
        <Text role="bodySmall" color="text2">
          {me.data ? `${me.data.email}${circle ? ` · ${ROLE_WORD[circle.role]} in ${circle.name}` : ''}` : ''}
        </Text>
        <Text role="silk" color="text2">
          Your Circles
        </Text>
        <View style={styles.list}>
          {(circles.data ?? []).map((c) => {
            const current = c.id === circle?.id;
            return (
              <Pressable
                key={c.id}
                onPress={() => {
                  setOpen(false);
                  if (!current) {
                    selectCircle(c.id);
                    router.navigate('/');
                  }
                }}
                accessibilityRole="radio"
                accessibilityState={{ checked: current }}
                accessibilityLabel={`${c.name}, ${ROLE_WORD[c.role]}, ${c.site_count} ${c.site_count === 1 ? 'site' : 'sites'}`}
                style={({ pressed }) => [styles.row, current && styles.current, pressed && styles.pressed]}>
                <View style={styles.rowText}>
                  <Text role="title">{c.name}</Text>
                  <Text role="bodySmall" color="text2">
                    {`${ROLE_WORD[c.role]} · ${c.member_count} ${c.member_count === 1 ? 'member' : 'members'} · ${c.site_count} ${c.site_count === 1 ? 'site' : 'sites'}`}
                  </Text>
                </View>
                {current ? (
                  <Text role="labelSmall" color="yellow">
                    Showing
                  </Text>
                ) : null}
              </Pressable>
            );
          })}
        </View>
        <Button
          label="Create or join another Circle"
          variant="ghost"
          onPress={() => {
            setOpen(false);
            router.push('/onboarding');
          }}
        />
        <Button
          label="Account settings"
          variant="ghost"
          onPress={() => {
            setOpen(false);
            router.navigate('/settings');
          }}
        />
        <Button
          label="Sign out"
          variant="ghost"
          loading={leaving}
          onPress={() => {
            setLeaving(true);
            void signOut();
          }}
        />
      </Sheet>
    </>
  );
}

const styles = StyleSheet.create({
  pressed: { opacity: 0.75 },
  list: { gap: space.item },
  row: {
    minHeight: 64,
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
