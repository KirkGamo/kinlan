/**
 * Turns a site summary into what the Overview shows: five status lights, one verdict and the
 * open problems (docs/design/briefs.md section 1; light mapping in docs/design/direction.md).
 * Pure functions, so every state can be reasoned about without a device.
 */
import type { SiteSummary } from '@/api/circles';
import type { ChipTone } from '@/components/ui';

/** Data older than this is stale: no green lights, and the verdict says the agent is offline. */
export const STALE_MS = 2 * 60_000;
/** A diagnose run lights DNS and Web for this long; after that they read "Not checked". */
export const DIAGNOSE_FRESH_MS = 60 * 60_000;
/** Above this, internet latency reads as slow (the server's default alert threshold). */
export const SLOW_MS = 150;

export type LightState = 'pass' | 'warn' | 'fail' | 'unlit';
export type Light = { state: LightState; value: string };

export const LAYERS = [
  {
    name: 'This PC',
    title: 'Network adapter',
    layer: 'Physical / data link',
    what: 'The PC running the agent is on, has a network connection and reports in.',
  },
  {
    name: 'Router',
    title: 'Router (ARP and ping)',
    layer: 'Data link + network (LAN)',
    what: 'Your router answers on the local network. The agent pings it every few seconds.',
  },
  {
    name: 'Provider',
    title: 'Internet provider',
    layer: 'Network (WAN)',
    what: 'Traffic leaves your router and reaches the internet: public servers answer ping.',
  },
  {
    name: 'DNS',
    title: 'Name lookup (DNS)',
    layer: 'Application (DNS)',
    what: 'Website names turn into addresses. Checked each time a diagnose runs.',
  },
  {
    name: 'Web',
    title: 'Secure web',
    layer: 'Transport + application',
    what: 'A secure connection to a website works (TCP port 443, then HTTPS). Checked each time a diagnose runs.',
  },
] as const;

export function isStale(summary: SiteSummary, now: number): boolean {
  if (summary.status === 'unreachable' || !summary.last_seen_at) return true;
  return now - Date.parse(summary.last_seen_at) > STALE_MS;
}

/** Latency in ms: no decimals above 10 ms, one below (briefs.md shared rules). */
export function ms(value: number | null | undefined): string {
  if (value == null) return '—';
  return value >= 10 ? `${Math.round(value)} ms` : `${value.toFixed(1)} ms`;
}

export function clock(iso: string): string {
  const d = new Date(iso);
  return `${d.getHours()}:${String(d.getMinutes()).padStart(2, '0')}`;
}

/** "Today 9:41" (or just "9:41" with `today` empty), else "Nov 16, 9:41". */
export function day(iso: string, today = 'Today'): string {
  const d = new Date(iso);
  if (d.toDateString() === new Date().toDateString()) return today ? `${today} ${clock(iso)}` : clock(iso);
  return `${d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}, ${clock(iso)}`;
}

/** "10 s ago", "3 min ago", "2 h ago". */
export function ago(iso: string, now: number): string {
  const s = Math.max(0, Math.round((now - Date.parse(iso)) / 1000));
  if (s < 60) return `${s} s ago`;
  const m = Math.round(s / 60);
  if (m < 60) return `${m} min ago`;
  const h = Math.round(m / 60);
  return h < 48 ? `${h} h ago` : `${Math.round(h / 24)} days ago`;
}

export function lights(summary: SiteSummary, now: number): Light[] {
  const off: Light = { state: 'unlit', value: '—' };
  if (isStale(summary, now)) return [off, off, off, off, off];

  const pc: Light = { state: 'pass', value: 'Online' };

  const g = summary.gateway;
  const router: Light = !g ? off : g.ok ? { state: 'pass', value: ms(g.rtt_ms) } : { state: 'fail', value: 'No reply' };

  const i = summary.internet;
  const notChecked: Light = { state: 'unlit', value: 'Not checked' };
  let provider: Light;
  if (router.state === 'fail') provider = notChecked;
  else if (summary.open_outage_since || (i && !i.ok)) provider = { state: 'fail', value: 'No reply' };
  else if (!i) provider = off;
  else provider = { state: (i.rtt_ms ?? 0) > SLOW_MS ? 'warn' : 'pass', value: ms(i.rtt_ms) };

  // DNS and Web are only measured by a diagnose run, so they light only from a recent one.
  const d = summary.last_diagnose;
  const fresh = d && now - Date.parse(d.finished_at) < DIAGNOSE_FRESH_MS;
  const fromDiagnose = (n: number): Light => {
    if (provider.state === 'fail' || provider.state === 'unlit' || !fresh) return notChecked;
    const step = d.steps.find((s) => s.n === n);
    if (!step || step.status === 'skipped') return notChecked;
    // step.ms is how long the check took, not latency, so a pass just reads OK.
    return step.status === 'pass' ? { state: 'pass', value: 'OK' } : { state: 'fail', value: 'Failing' };
  };

  return [pc, router, provider, fromDiagnose(5), fromDiagnose(6)];
}

export type Verdict = { tone: ChipTone; chip: string; title: string; text: string };

export function verdict(summary: SiteSummary, now: number, lit: Light[] = lights(summary, now)): Verdict {
  if (isStale(summary, now)) {
    const seen = summary.last_seen_at ? `last seen ${clock(summary.last_seen_at)}` : 'not seen yet';
    return {
      tone: 'neutral',
      chip: 'Offline',
      title: `Agent offline, ${seen}`,
      text: 'The lights come back when the PC running the agent is on and connected. Until then KinLAN can’t check this network.',
    };
  }
  const [, router, provider, dns, web] = lit;
  if (router.state === 'fail') {
    return {
      tone: 'down',
      chip: 'Down',
      title: 'Router not responding',
      text: 'The PC can’t reach your router. Check that the router is on and the PC is connected to it.',
    };
  }
  if (provider.state === 'fail') {
    const since = summary.open_outage_since ? ` since ${clock(summary.open_outage_since)}` : '';
    return {
      tone: 'down',
      chip: 'Down',
      title: `Internet down${since}`,
      text: 'Your router is fine, but your internet provider isn’t responding.',
    };
  }
  if (dns.state === 'fail') {
    return {
      tone: 'down',
      chip: 'Down',
      title: 'Websites can’t be found',
      text: 'The internet works, but name lookup (DNS) failed in the last diagnose.',
    };
  }
  if (web.state === 'fail') {
    return {
      tone: 'down',
      chip: 'Down',
      title: 'Secure websites don’t open',
      text: 'Names resolve, but the secure web check failed in the last diagnose. A firewall may be blocking it.',
    };
  }
  if (provider.state === 'warn' || summary.status === 'degraded') {
    return {
      tone: 'new',
      chip: 'Degraded',
      title: 'Internet is slow',
      text: `Internet replies take ${provider.value}. Video calls and games may stutter.`,
    };
  }
  return {
    tone: 'ok',
    chip: 'Healthy',
    title: 'All good',
    text: `Router ${router.value}, internet ${provider.value}. Nothing needs attention.`,
  };
}

export type Problem = {
  key: string;
  title: string;
  next: string;
  tone: ChipTone;
  chip: string;
  to: '/alerts' | '/devices';
};

/** Open problems, most urgent first. Empty when nothing needs attention. */
/** `manage`: an owner or admin. A viewer can't acknowledge or trust, so their next step is to read. */
export function problems(
  summary: SiteSummary,
  now: number,
  v: Verdict = verdict(summary, now),
  manage = true,
): Problem[] {
  const out: Problem[] = [];
  if (isStale(summary, now)) {
    out.push({
      key: 'agent',
      title: 'The agent isn’t reporting',
      next: 'Turn on the PC with the agent: it starts by itself. If it still doesn’t report, run KinLAN-Agent.exe there.',
      tone: 'neutral',
      chip: 'Offline',
      to: '/alerts',
    });
  } else if (v.tone === 'down') {
    out.push({ key: 'outage', title: v.title, next: 'See what happened in Alerts.', tone: 'down', chip: 'Down', to: '/alerts' });
  }
  if (summary.needs_review > 0) {
    const n = summary.needs_review;
    out.push({
      key: 'review',
      title: `${n} new ${n === 1 ? 'device' : 'devices'} to review`,
      next: manage ? 'Say whose it is, or mark it as trusted.' : 'An admin can name them and mark them as trusted.',
      tone: 'new',
      chip: 'New',
      to: '/devices',
    });
  }
  // Alerts usually repeat the rows above (an outage, a new device), so they get a row of
  // their own only when nothing else explains them.
  const n = summary.open_alerts;
  if (out.length === 0 && n > 0) {
    out.push({
      key: 'alerts',
      title: `${n} open ${n === 1 ? 'alert' : 'alerts'}`,
      next: manage ? 'Read and acknowledge them in Alerts.' : 'Read them in Alerts.',
      tone: 'new',
      chip: 'Open',
      to: '/alerts',
    });
  }
  return out;
}
