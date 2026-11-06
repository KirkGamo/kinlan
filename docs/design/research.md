# Design research notes (Sprint 1, Nov 7, 2026)

Research input for DESIGN.md, gathered with the UI/UX Pro Max skill. Per the technical plan (Section 8.1), this tool is research only: where its suggestions conflict with PRODUCT.md, Material Design 3 or the plan, those win.

## Queries run

| Query | Domain |
|---|---|
| network monitoring dashboard real-time status mobile utility (design system, density 8) | design system |
| status indicator color blind icon label | ux |
| live data stale timestamp refresh | ux |
| line chart time series latency | chart |
| empty state first run onboarding | ux |
| list performance navigation tabs | react-native stack |
| dashboard data dense tabular numbers | typography |

## Adopted

- **Status colors are the core of the palette:** operational green, degraded amber, incident red, plus a neutral for unknown/offline.
- **Never convey status by color alone** (rated High severity): every status pairs a color with an icon and a word. Matches PRODUCT.md.
- **Live data must show its age:** label data as live only when it is current, show the update time, and show a stale state.
- **Avoid decorative charts and hidden error states.**
- **Latency over time is a line chart.** Distinguish series (router vs internet) by line style and direct labels, never by hue alone; offer a text summary as the accessible fallback. Use a highlight marker for spikes and outages.
- **Data-dense screens need a sans-serif with tabular figures** for numbers, so values don't shift as they update.
- **Empty states show a helpful message and an action;** onboarding steps after the essentials are skippable.
- **Navigation:** typed routes; standard stack and tab navigation (Expo Router builds on React Navigation).

## Rejected, and why

| Suggestion | Why not |
|---|---|
| "Dark Mode (OLED)", light mode not recommended | The plan requires light and dark themes, following the phone's setting. |
| Playfair Display (serif) for body text | Editorial/luxury pairing; wrong for a task-focused Operate app. Use one sans-serif family (Roboto or Inter) with tabular figures. |
| Fira Code/Fira Sans or Exo/Roboto Mono pairings | A monospace face isn't needed; tabular figures in the main sans-serif give aligned numbers with less visual noise. |
| Landing-page structure (hero, CTA after metrics, "start trial") | KinLAN's screens are app UI, not marketing. |
| Glow effects (text-shadow) | Decorative; conflicts with "calm by default". |
| Hover and cursor rules | Phone-first app; touch targets and pressed states matter instead (48 dp minimum). |
| Pull to refresh disabled by default | Refreshing a status screen on demand is useful here; keep it on Overview, Devices and Alerts. |
