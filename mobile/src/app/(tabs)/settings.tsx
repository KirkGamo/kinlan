import * as Clipboard from 'expo-clipboard';
import Constants from 'expo-constants';
import { router } from 'expo-router';
import { useState } from 'react';
import { Platform, Pressable, StyleSheet, Switch, View } from 'react-native';

import { useSites, type Circle, type Role, type Site } from '@/api/circles';
import { useMembers, type Member } from '@/api/overview';
import { canManage, selectCircle, selectSite, useCurrentCircle, useSelectedSite } from '@/api/selection';
import { pushSupported, useNotificationSwitches, useUpdateNotificationSwitches, type NotificationSwitches } from '@/api/push';
import { useMe, useSession } from '@/api/session';
import {
  useAlertSettings,
  useChangeRole,
  useCreateInvite,
  useDeleteAccount,
  useRemoveMember,
  useUpdateAlertSettings,
  type AlertSettings,
} from '@/api/settings';
import { Button, Card, Chips, Loader, Mark, Screen, SectionLabel, Sheet, StatusChip, Text, Wordmark } from '@/components/ui';
import { AccountButton, ROLE_WORD } from '@/features/account/account-sheet';
import { Avatar } from '@/features/account/avatar';
import { SITE_STATUS } from '@/features/overview/site-header';
import { haptics, setHapticsEnabled, useHapticsEnabled } from '@/haptics';
import { colors, radius, size, space } from '@/theme';

const ROLES: { key: Role; label: string }[] = [
  { key: 'viewer', label: 'Viewer' },
  { key: 'admin', label: 'Admin' },
  { key: 'owner', label: 'Owner' },
];
const ROLE_MEANS: Record<Role, string> = {
  viewer: 'Sees everything, changes nothing.',
  admin: 'Runs checks, names devices and changes alert settings.',
  owner: 'Everything, plus members, invites and deleting the Circle.',
};

/**
 * Settings: the Circle's members and invites (owners), its sites, the alert thresholds for the
 * site the tabs show (owners and admins), and your account.
 */
export default function SettingsScreen() {
  const { circles, circle } = useCurrentCircle();
  if (circles.isPending) {
    return (
      <Screen>
        <Card style={styles.center}>
          <Loader label="Loading" />
        </Card>
      </Screen>
    );
  }
  return (
    <Screen>
      <View style={styles.bar}>
        <View style={styles.title}>
          <Text role="titleLarge" accessibilityRole="header">
            Settings
          </Text>
          {circle ? (
            <Text role="bodySmall" color="text2">
              {`${circle.name} · you’re ${circle.role === 'admin' ? 'an' : 'the'} ${circle.role}`}
            </Text>
          ) : null}
        </View>
        <AccountButton />
      </View>
      {circle ? (
        <>
          {/* Keyed by Circle, so switching Circles closes any open sheet and resets the forms. */}
          <MembersSection key={`m-${circle.id}`} circle={circle} />
          <SitesSection key={`s-${circle.id}`} circle={circle} />
          <AlertsSection key={`a-${circle.id}`} circle={circle} />
          <PushSection key={`p-${circle.id}`} circle={circle} />
          {Platform.OS === 'web' ? null : <VibrationSection />}
        </>
      ) : null}
      <AccountSection key={`acc-${circle?.id}`} circle={circle} />
      {/* The brand sign-off at the foot of Settings (prototype "about"). */}
      <View style={styles.about} accessible accessibilityLabel={`KinLAN, version ${Constants.expoConfig?.version ?? ''}`}>
        <Mark width={54} />
        <Wordmark size={26} />
        <Text role="bodySmall" color="text2">
          {`Your people, your network. · v${Constants.expoConfig?.version ?? ''}`}
        </Text>
      </View>
    </Screen>
  );
}

// ---------------------------------------------------------------- members and invites

function MembersSection({ circle }: { circle: Circle }) {
  const members = useMembers(circle.id);
  const me = useMe();
  const isOwner = circle.role === 'owner';
  const [picked, setPicked] = useState<Member | null>(null);
  const [inviting, setInviting] = useState(false);

  return (
    <>
      <SectionLabel end={members.data ? String(members.data.length) : undefined}>Members</SectionLabel>
      {members.isPending ? (
        <Card style={styles.center}>
          <Loader label="Loading members" />
        </Card>
      ) : members.isError ? (
        <Text role="bodySmall" color="red">
          {members.error.message}
        </Text>
      ) : (
        members.data.map((m) => {
          const mine = m.user_id === me.data?.id;
          return (
            <Pressable
              key={m.user_id}
              disabled={!isOwner || mine}
              onPress={() => setPicked(m)}
              accessibilityRole={isOwner && !mine ? 'button' : undefined}
              accessibilityLabel={`${m.display_name}${mine ? ' (you)' : ''}, ${ROLE_WORD[m.role]}`}
              accessibilityHint={isOwner && !mine ? 'Change role or remove' : undefined}
              style={({ pressed }) => [styles.row, pressed && styles.pressed]}>
              <Avatar name={m.display_name} me={mine} />
              <View style={styles.rowText}>
                <Text role="title" numberOfLines={1}>
                  {mine ? `${m.display_name} (you)` : m.display_name}
                </Text>
                <Text role="bodySmall" color="text2" numberOfLines={1}>
                  {m.email}
                </Text>
              </View>
              <Text role="labelSmall" color="text2">
                {ROLE_WORD[m.role]}
              </Text>
            </Pressable>
          );
        })
      )}
      {isOwner ? <Button label="Invite a member" onPress={() => setInviting(true)} /> : null}
      <MemberSheet circle={circle} member={picked} onClose={() => setPicked(null)} />
      <InviteSheet circle={circle} open={inviting} onClose={() => setInviting(false)} />
    </>
  );
}

function MemberSheet({ circle, member, onClose }: { circle: Circle; member: Member | null; onClose: () => void }) {
  const change = useChangeRole(circle.id);
  const remove = useRemoveMember(circle.id);
  const [confirm, setConfirm] = useState(false);
  const close = () => {
    setConfirm(false);
    change.reset();
    remove.reset();
    onClose();
  };
  return (
    <Sheet open={member != null} onClose={close} title={member?.display_name ?? ''}>
      {member ? (
        <>
          <Text role="bodySmall" color="text2">
            {member.email}
          </Text>
          <Text role="silk" color="text2">
            Role
          </Text>
          <Chips
            label="Role"
            options={ROLES}
            value={(change.variables?.role as Role | undefined) ?? member.role}
            disabled={change.isPending}
            onChange={(role) => change.mutate({ userId: member.user_id, role })}
          />
          <Text role="bodySmall" color="text2">
            {ROLE_MEANS[(change.variables?.role as Role | undefined) ?? member.role]}
          </Text>
          {confirm ? (
            <Card style={styles.warn}>
              <Text role="body">{`Remove ${member.display_name} from ${circle.name}? They lose access to every site here.`}</Text>
              <Button label="Remove" variant="danger" loading={remove.isPending} onPress={() => remove.mutate(member.user_id, { onSuccess: close })} />
              <Button label="Keep them" variant="ghost" onPress={() => setConfirm(false)} />
            </Card>
          ) : (
            <Button
              label="Remove from this Circle"
              variant="danger"
              onPress={() => {
                haptics.reject(); // a destructive step is one tap away
                setConfirm(true);
              }}
            />
          )}
          {change.isError || remove.isError ? (
            <Text role="bodySmall" color="red" accessibilityRole="alert">
              {(change.error ?? remove.error)?.message}
            </Text>
          ) : null}
        </>
      ) : null}
    </Sheet>
  );
}

function InviteSheet({ circle, open, onClose }: { circle: Circle; open: boolean; onClose: () => void }) {
  const invite = useCreateInvite(circle.id);
  const [role, setRole] = useState<Role>('viewer');
  const [copied, setCopied] = useState(false);
  const code = invite.data?.code;
  const close = () => {
    invite.reset();
    setCopied(false);
    onClose();
  };
  return (
    <Sheet open={open} onClose={close} title="Invite a member">
      {code ? (
        <>
          <Text role="body" color="text2">
            {`Share this code. They open KinLAN, choose “Join with an invite code” and type it. It joins them as ${ROLE_WORD[invite.data!.role].toLowerCase()}.`}
          </Text>
          <View style={styles.code} accessible accessibilityLabel={`Invite code ${code.split('').join(' ')}`}>
            <Text role="display" tabular selectable>
              {code}
            </Text>
          </View>
          <Text role="bodySmall" color="text2">
            Works once and expires in 7 days.
          </Text>
          <Button
            label={copied ? 'Copied' : 'Copy code'}
            onPress={async () => {
              await Clipboard.setStringAsync(code);
              haptics.confirm();
              setCopied(true);
              setTimeout(() => setCopied(false), 2_000);
            }}
          />
          <Button label="Make another" variant="ghost" onPress={() => invite.reset()} />
        </>
      ) : (
        <>
          <Text role="silk" color="text2">
            They join as
          </Text>
          <Chips label="Role for the new member" options={ROLES.filter((r) => r.key !== 'owner')} value={role} onChange={setRole} />
          <Text role="bodySmall" color="text2">
            {ROLE_MEANS[role]}
          </Text>
          <Button label="Make an invite code" loading={invite.isPending} onPress={() => invite.mutate(role)} />
          {invite.isError ? (
            <Text role="bodySmall" color="red" accessibilityRole="alert">
              {invite.error.message}
            </Text>
          ) : null}
        </>
      )}
    </Sheet>
  );
}

// ---------------------------------------------------------------- sites

function SitesSection({ circle }: { circle: Circle }) {
  const sites = useSites(circle.id);
  const manage = canManage(circle);
  return (
    <>
      <SectionLabel>Sites</SectionLabel>
      {sites.isPending ? (
        <Card style={styles.center}>
          <Loader label="Loading sites" />
        </Card>
      ) : sites.isError ? (
        <Text role="bodySmall" color="red">
          {sites.error.message}
        </Text>
      ) : sites.data.length === 0 ? (
        <Card>
          <Text role="body" color="text2">
            No sites yet. A site is one network, like your home Wi-Fi or a lab.
          </Text>
        </Card>
      ) : (
        sites.data.map((s) => <SiteRow key={s.id} site={s} manage={manage} />)
      )}
      {manage ? (
        <Button
          label="Add a site"
          variant="ghost"
          onPress={() => router.push({ pathname: '/onboarding/new-site', params: { circle: circle.id } })}
        />
      ) : null}
    </>
  );
}

function SiteRow({ site, manage }: { site: Site; manage: boolean }) {
  const st = SITE_STATUS[site.status];
  const pair = site.status === 'pending' && manage;
  return (
    <Pressable
      onPress={() => {
        if (pair) router.push({ pathname: '/onboarding/pair', params: { site: site.id } });
        else {
          selectSite(site.id);
          router.navigate('/');
        }
      }}
      accessibilityRole="button"
      accessibilityLabel={`${site.name}, ${st.label}. ${pair ? 'Pair the agent' : 'Show on Overview'}`}
      style={({ pressed }) => [styles.row, pressed && styles.pressed]}>
      <View style={styles.rowText}>
        <Text role="title">{site.name}</Text>
        <Text role="bodySmall" color="text2">
          {site.cidr ? `${site.cidr} · router ${site.gateway_ip ?? 'unknown'}` : 'Waiting for its agent'}
        </Text>
      </View>
      {pair ? (
        <Text role="labelSmall" color="yellow">
          Pair the agent
        </Text>
      ) : (
        <StatusChip tone={st.tone} label={st.label} />
      )}
    </Pressable>
  );
}

// ---------------------------------------------------------------- alert thresholds

const LATENCY = [100, 150, 250, 500].map((v) => ({ key: String(v), label: `${v} ms` }));
const LOSS = [2, 5, 10].map((v) => ({ key: String(v), label: `${v}%` }));
const OFFLINE = [120, 300, 600].map((v) => ({ key: String(v), label: `${v / 60} min` }));

function AlertsSection({ circle }: { circle: Circle }) {
  const sites = useSites(circle.id);
  const site = useSelectedSite(sites.data);
  const settings = useAlertSettings(site?.id);
  if (!site) return null;
  return (
    <>
      <SectionLabel end={site.name}>Alerts</SectionLabel>
      {settings.isPending ? (
        <Card style={styles.center}>
          <Loader label="Loading alert settings" />
        </Card>
      ) : settings.isError ? (
        <Text role="bodySmall" color="red">
          {settings.error.message}
        </Text>
      ) : (
        <Thresholds key={site.id} siteId={site.id} value={settings.data} manage={canManage(circle)} />
      )}
    </>
  );
}

function Thresholds({ siteId, value, manage }: { siteId: string; value: AlertSettings; manage: boolean }) {
  const update = useUpdateAlertSettings(siteId);
  const pick = (options: { key: string }[], v: number) =>
    options.find((o) => Number(o.key) === Math.round(v))?.key ?? null;
  return (
    <Card style={styles.thresholds}>
      <Setting label="Slow internet" hint="Alert when internet replies average more than this for 5 minutes.">
        {manage ? (
          <Chips label="Slow internet threshold" options={LATENCY} value={pick(LATENCY, value.latency_ms)} disabled={update.isPending} onChange={(k) => update.mutate({ latency_ms: Number(k) })} />
        ) : (
          <Text role="body">{`${Math.round(value.latency_ms)} ms`}</Text>
        )}
      </Setting>
      <Setting label="Lost data" hint="Alert when more than this share of pings gets no reply.">
        {manage ? (
          <Chips label="Lost data threshold" options={LOSS} value={pick(LOSS, value.loss_pct)} disabled={update.isPending} onChange={(k) => update.mutate({ loss_pct: Number(k) })} />
        ) : (
          <Text role="body">{`${value.loss_pct}%`}</Text>
        )}
      </Setting>
      <Setting label="Unreachable after" hint="How long the agent can be silent before the site counts as down.">
        {manage ? (
          <Chips label="Unreachable after" options={OFFLINE} value={pick(OFFLINE, value.offline_seconds)} disabled={update.isPending} onChange={(k) => update.mutate({ offline_seconds: Number(k) })} />
        ) : (
          <Text role="body">{`${Math.round(value.offline_seconds / 60)} min`}</Text>
        )}
      </Setting>
      <View style={styles.switchRow}>
        <View style={styles.rowText}>
          <Text role="title">New devices</Text>
          <Text role="bodySmall" color="text2">
            Alert when a device joins that wasn’t there at the first scan.
          </Text>
        </View>
        <Switch
          value={value.notify_new_device}
          disabled={!manage || update.isPending}
          onValueChange={(on) => {
            haptics.toggle(on);
            update.mutate({ notify_new_device: on });
          }}
          trackColor={{ false: colors.unlit, true: colors.yellow }}
          thumbColor={value.notify_new_device ? colors.onYellow : colors.text2}
          // react-native-web reads its own props for the thumb; without them it paints a default teal.
          {...({ activeThumbColor: colors.onYellow, activeTrackColor: colors.yellow } as object)}
          accessibilityLabel="Alert about new devices"
        />
      </View>
      {update.isError ? (
        <Text role="bodySmall" color="red" accessibilityRole="alert">
          {update.error.message}
        </Text>
      ) : null}
    </Card>
  );
}

function Setting({ label, hint, children }: { label: string; hint: string; children: React.ReactNode }) {
  return (
    <View style={styles.setting}>
      <Text role="title">{label}</Text>
      <Text role="bodySmall" color="text2">
        {hint}
      </Text>
      {children}
    </View>
  );
}

// ---------------------------------------------------------------- push switches (yours)

const PUSH_ROWS: { key: keyof NotificationSwitches; title: string; hint: string }[] = [
  { key: 'outages', title: 'Outages', hint: 'A site goes down, or comes back online.' },
  { key: 'new_devices', title: 'New devices', hint: 'Someone new joins a network.' },
  { key: 'security', title: 'Risky open ports', hint: 'A device has a service open that it shouldn’t.' },
  { key: 'performance', title: 'Slow internet and lost data', hint: 'Off by default: these stay in the Alerts tab.' },
];

/** Each member's own push switches for this Circle; any role can change their own. */
function PushSection({ circle }: { circle: Circle }) {
  const switches = useNotificationSwitches(circle.id);
  const update = useUpdateNotificationSwitches(circle.id);
  return (
    <>
      <SectionLabel end="just you">Push notifications</SectionLabel>
      {!pushSupported ? (
        <Card>
          <Text role="body" color="text2">
            Push needs the Android app. On the web, open problems show on Overview and in Alerts.
          </Text>
        </Card>
      ) : switches.isPending ? (
        <Card style={styles.center}>
          <Loader label="Loading your notification settings" />
        </Card>
      ) : switches.isError ? (
        <Text role="bodySmall" color="red">
          {switches.error.message}
        </Text>
      ) : (
        <Card style={styles.thresholds}>
          {PUSH_ROWS.map((row) => {
            const on = switches.data[row.key];
            return (
              <View key={row.key} style={styles.switchRow}>
                <View style={styles.rowText}>
                  <Text role="title">{row.title}</Text>
                  <Text role="bodySmall" color="text2">
                    {row.hint}
                  </Text>
                </View>
                <Switch
                  value={on}
                  disabled={update.isPending}
                  onValueChange={(v) => {
                    haptics.toggle(v);
                    update.mutate({ [row.key]: v });
                  }}
                  trackColor={{ false: colors.unlit, true: colors.yellow }}
                  thumbColor={on ? colors.onYellow : colors.text2}
                  accessibilityLabel={`Push for ${row.title.toLowerCase()}`}
                  {...({ activeThumbColor: colors.onYellow, activeTrackColor: colors.yellow } as object)}
                />
              </View>
            );
          })}
          {update.isError ? (
            <Text role="bodySmall" color="red" accessibilityRole="alert">
              {update.error.message}
            </Text>
          ) : null}
        </Card>
      )}
    </>
  );
}

/** The in-app Vibration switch: saved on this phone, on by default. */
function VibrationSection() {
  const on = useHapticsEnabled();
  return (
    <>
      <SectionLabel end="this phone">Feel</SectionLabel>
      <Card>
        <View style={styles.switchRow}>
          <View style={styles.rowText}>
            <Text role="title">Vibration</Text>
            <Text role="bodySmall" color="text2">
              A light tap when you pick, switch or finish something. Follows your phone’s touch feedback setting.
            </Text>
          </View>
          <Switch
            value={on}
            onValueChange={(v) => {
              setHapticsEnabled(v);
              haptics.toggle(v); // plays only when turning on: the switch is already off otherwise
            }}
            trackColor={{ false: colors.unlit, true: colors.yellow }}
            thumbColor={on ? colors.onYellow : colors.text2}
            accessibilityLabel="Vibration"
          />
        </View>
      </Card>
    </>
  );
}

// ---------------------------------------------------------------- account

function AccountSection({ circle }: { circle: Circle | undefined }) {
  const me = useMe();
  const { signOut } = useSession();
  const leave = useRemoveMember(circle?.id ?? '');
  const del = useDeleteAccount();
  const [confirm, setConfirm] = useState<'leave' | 'delete' | null>(null);
  const [signingOut, setSigningOut] = useState(false);

  return (
    <>
      <SectionLabel>Account</SectionLabel>
      <Card>
        {me.isPending ? (
          <Loader label="Loading your account" />
        ) : me.isError ? (
          <Text role="bodySmall" color="red">
            {me.error.message}
          </Text>
        ) : (
          <View style={styles.me}>
            <Avatar name={me.data.display_name} me />
            <View style={styles.rowText}>
              <Text role="title">{me.data.display_name}</Text>
              <Text role="bodySmall" color="text2">
                {me.data.email}
              </Text>
            </View>
          </View>
        )}
      </Card>
      <Button
        label="Sign out"
        variant="ghost"
        loading={signingOut}
        onPress={() => {
          setSigningOut(true);
          void signOut();
        }}
      />
      {circle && me.data ? (
        confirm === 'leave' ? (
          <Card style={styles.warn}>
            <Text role="body">{`Leave ${circle.name}? You lose access to its sites until someone invites you again.`}</Text>
            <Button
              label="Leave"
              variant="danger"
              loading={leave.isPending}
              onPress={() =>
                leave.mutate(me.data.id, {
                  onSuccess: () => {
                    setConfirm(null);
                    selectCircle('');
                    router.navigate('/');
                  },
                })
              }
            />
            <Button label="Stay" variant="ghost" onPress={() => setConfirm(null)} />
          </Card>
        ) : (
          <Button
            label={`Leave ${circle.name}`}
            variant="danger"
            onPress={() => {
              haptics.reject();
              setConfirm('leave');
            }}
          />
        )
      ) : null}
      {confirm === 'delete' ? (
        <Card style={styles.warn}>
          <Text role="body">
            Delete your account? This can’t be undone. Circles where you’re the only owner must be handed over or deleted first.
          </Text>
          <Button
            label="Delete my account"
            variant="danger"
            loading={del.isPending}
            onPress={() => del.mutate(undefined, { onSuccess: () => void signOut() })}
          />
          <Button label="Keep my account" variant="ghost" onPress={() => setConfirm(null)} />
        </Card>
      ) : (
        <Button
          label="Delete account"
          variant="danger"
          onPress={() => {
            haptics.reject();
            setConfirm('delete');
          }}
        />
      )}
      {leave.isError || del.isError ? (
        <Text role="bodySmall" color="red" accessibilityRole="alert">
          {(leave.error ?? del.error)?.message}
        </Text>
      ) : null}
    </>
  );
}

const styles = StyleSheet.create({
  center: { minHeight: size.loading, alignItems: 'center', justifyContent: 'center' },
  about: { alignItems: 'center', gap: space.s2, paddingTop: space.s8, paddingBottom: space.s2 },
  bar: { flexDirection: 'row', alignItems: 'flex-start', gap: space.s3 },
  title: { flex: 1, gap: 2 },
  row: {
    minHeight: size.row,
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.s3,
    backgroundColor: colors.card,
    borderRadius: radius.row,
    borderCurve: 'continuous',
    paddingHorizontal: space.s4,
    paddingVertical: space.s3,
  },
  pressed: { backgroundColor: colors.raised },
  rowText: { flex: 1, gap: 2 },
  warn: { gap: space.s3, borderWidth: 1, borderColor: colors.red },
  code: { alignItems: 'center', paddingVertical: space.s4, backgroundColor: colors.raised, borderRadius: radius.row },
  thresholds: { gap: space.s5 },
  setting: { gap: space.s2 },
  switchRow: { flexDirection: 'row', alignItems: 'center', gap: space.s3 },
  me: { flexDirection: 'row', alignItems: 'center', gap: space.s3 },
});
