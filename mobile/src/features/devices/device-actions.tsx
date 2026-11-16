import { useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import type { Device, Member } from '@/api/overview';
import { useUpdateDevice } from '@/api/devices';
import { Button, Sheet, StatusChip, Text, TextField } from '@/components/ui';
import { haptics } from '@/haptics';
import { colors, radius, space } from '@/theme';

import { ICON_PATHS, TYPE_LABEL } from './icons';
import { chip } from './model';

/**
 * Quick actions for a device row (long-press, or the row's TalkBack actions): ping it, trust it,
 * rename it, or open its details. Every action is also in the device sheet; this only saves taps.
 */
export function DeviceActions({
  device,
  siteId,
  members,
  stale,
  rename,
  onClose,
  onPing,
  onOpen,
}: {
  device: Device | null;
  siteId: string;
  members: Member[];
  stale: boolean;
  /** Open straight on the rename form (the row's Rename action for TalkBack). */
  rename: boolean;
  onClose: () => void;
  onPing: (id: string) => void;
  onOpen: (id: string) => void;
}) {
  const d = device;
  const st = d ? chip(d, stale) : null;
  return (
    <Sheet
      open={d != null}
      onClose={onClose}
      title={d?.display_name ?? 'Device'}
      icon={d ? ICON_PATHS[d.device_type] : undefined}
      meta={
        d && st ? (
          <>
            <StatusChip tone={st.tone} label={st.label} />
            <Text role="bodySmall" color="text2">
              {TYPE_LABEL[d.device_type]}
            </Text>
          </>
        ) : null
      }>
      {d ? (
        <Actions
          key={`${d.id}-${rename}`}
          d={d}
          siteId={siteId}
          members={members}
          stale={stale}
          startRenaming={rename}
          onClose={onClose}
          onPing={onPing}
          onOpen={onOpen}
        />
      ) : null}
    </Sheet>
  );
}

function Actions({
  d,
  siteId,
  members,
  stale,
  startRenaming,
  onClose,
  onPing,
  onOpen,
}: {
  d: Device;
  siteId: string;
  members: Member[];
  stale: boolean;
  startRenaming: boolean;
  onClose: () => void;
  onPing: (id: string) => void;
  onOpen: (id: string) => void;
}) {
  const update = useUpdateDevice(d.id, siteId, members);
  const [renaming, setRenaming] = useState(startRenaming);
  const [name, setName] = useState(d.custom_name ?? '');

  if (renaming) {
    const save = () =>
      update.mutate(
        { custom_name: name.trim() || null },
        {
          onSuccess: () => {
            haptics.confirm();
            onClose();
          },
          onError: haptics.reject,
        },
      );
    return (
      <>
        <TextField
          label="Name"
          value={name}
          onChangeText={setName}
          placeholder={d.hostname ?? d.vendor ?? 'Living room TV'}
          autoCapitalize="words"
          autoFocus
          returnKeyType="done"
          onSubmitEditing={save}
          hint="Leave empty to use the name the device reports."
        />
        <Button label="Save name" onPress={save} loading={update.isPending} />
        {update.isError ? (
          <Text role="bodySmall" color="red" accessibilityRole="alert">
            {update.error.message}
          </Text>
        ) : null}
      </>
    );
  }

  const canPing = !!d.ip && !stale;
  return (
    <View style={styles.list}>
      <Action
        title="Ping test"
        hint={canPing ? 'Five pings from the agent PC.' : stale ? 'The agent is offline.' : 'No IP address yet.'}
        disabled={!canPing}
        onPress={() => onPing(d.id)}
      />
      {d.trusted ? null : (
        <Action
          title="Mark as trusted"
          hint="It stops counting as a new device to review."
          onPress={() =>
            update.mutate(
              { trusted: true },
              {
                onSuccess: () => {
                  haptics.confirm();
                  onClose();
                },
                onError: haptics.reject,
              },
            )
          }
        />
      )}
      <Action title="Rename" hint="Give it a name everyone recognises." onPress={() => setRenaming(true)} />
      <Action title="Open details" hint="Whose it is, its addresses and open ports." onPress={() => onOpen(d.id)} />
      {update.isError ? (
        <Text role="bodySmall" color="red" accessibilityRole="alert">
          {update.error.message}
        </Text>
      ) : null}
    </View>
  );
}

function Action({ title, hint, disabled, onPress }: { title: string; hint: string; disabled?: boolean; onPress: () => void }) {
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      accessibilityRole="button"
      accessibilityLabel={title}
      accessibilityHint={hint}
      accessibilityState={{ disabled }}
      style={({ pressed }) => [styles.action, pressed && styles.pressed, disabled && styles.disabled]}>
      <Text role="title">{title}</Text>
      <Text role="bodySmall" color="text2">
        {hint}
      </Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  list: { gap: space.s2 },
  action: {
    minHeight: 68,
    justifyContent: 'center',
    gap: 2,
    paddingVertical: space.s3,
    paddingHorizontal: space.s4,
    borderRadius: radius.row,
    borderCurve: 'continuous',
    backgroundColor: colors.raised,
  },
  pressed: { opacity: 0.75 },
  disabled: { opacity: 0.5 },
});
