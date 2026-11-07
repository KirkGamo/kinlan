# Screen briefs: the 5 key screens

Written with the Impeccable `shape` flow (Sprint 1, Nov 7, 2026). These say **what each screen must do and how it behaves**, not how it looks: the visual direction (color, type, shape) is decided in DESIGN.md.

**Confirmed in the interview:**
- The Devices tab adds a **network map** as a List | Map switch (added Nov 7 at the user's request).
- A caretaker usually watches **1 site, sometimes 2–3**.
- The home screen answers **"Is anything wrong now?"** first.
- Push alerts **buzz only for outages and security**; latency and loss warnings stay in the app.

## Shared rules for every screen

- **Platform:** Android, Material Design 3. Bottom navigation with 4 destinations (Overview, Devices, Alerts, Settings); a top app bar with the site name, and a site switcher when there are 2–3 sites. The system Back gesture always works; content is edge-to-edge with safe insets.
- **Plain first, details on tap** (PRODUCT.md): every result leads with what it means; protocols, layers and numbers are one tap away.
- **Status is never color alone:** always a color, an icon and a word ("Healthy", "Degraded", "Down", "Unknown", "New").
- **Every screen designs four states:** loading (skeleton), empty (message + action), error (retry), stale (data older than 2 minutes shows "Last updated 3 min ago").
- **Roles:** viewers see everything but get no action buttons (Diagnose, Ping, Trust, Acknowledge); hide the actions rather than disabling them.
- **Wording:** "Circle", "members", "site", "agent"; never "family".
- **Numbers** use tabular figures; latency is shown in ms with no decimals above 10 ms.

---

## 1. Overview (home)

- **Job:** the caretaker opens the app, often from a notification or because someone says "the internet is slow", and needs to know in a second whether anything is wrong and what to do about it.
- **Focal moment:** a one-line **verdict** at the top with its status chip and the data's age:
  - "All good" (healthy)
  - "Internet down since 9:41 (internet provider)"
  - "Router not responding"
  - "Agent offline, last seen 9:41" (data is stale; actions that need the agent are unavailable, with the reason)
- **Below the verdict, in order:**
  1. **Open problems**, each a row with a plain title and a next step, tapping through to its screen. Hidden when there are none.
  2. **Health grade card:** the grade (A–F), score, and the largest reason, with "Why this grade?" expanding every deduction.
  3. **Connection now:** router and internet latency with a 24-hour line chart (router vs internet told apart by line style and labels), and loss.
  4. **Devices:** count online, and "N new to review" when there are untrusted new devices.
- **Primary action:** a **Diagnose** floating action button (owners and admins only) that opens the Diagnose screen and starts a run.
- **States and ranges:** pending (no agent paired yet: the whole screen becomes the pairing call to action), healthy, degraded, internet down, agent unreachable, loading, error, stale. Typical home: 5–30 devices; latency 1–300 ms.
- **Must not:** bury a current outage below charts; show a green verdict while data is stale.

## 2. Devices and Device detail

- **Job:** "Who's on my network?" Spot unknown devices, put names on them, and check one device's connection.
- **List (Devices tab):**
  - Groups in order: **Needs review** (new untrusted devices after the baseline, and the one-time baseline review), **Online**, **Offline**.
  - Each row: display name (custom name, else hostname, else manufacturer), manufacturer, IP, status chip, trusted badge.
  - Filter chips (All / Needs review / Online / Offline). No search needed below about 40 devices.
- **Map (a List | Map switch on the Devices tab; the list stays the default):**
  - A **logical network map**: the router at the center, the internet above it, and every device as a node around the router (a star, which is what one local network is).
  - **Links carry live numbers:** internet latency and loss on the router-to-internet link, router latency on the agent PC's link.
  - **Each node:** a type icon (router, computer, laptop, phone, TV, printer, unknown; the device type is inferred from the manufacturer and hostname and can be changed in Device detail), the display name, and a status ring and badge (Online, Offline, New); the agent's PC is marked.
  - **Tapping a node** selects it (yellow ring, its link turns yellow, the other nodes dim) and opens Device detail as a bottom sheet; closing the sheet clears the selection. Nodes are focusable and open with Enter or Space. The filter chips dim the nodes that don't match.
  - **Ping test on the map:** while a ping runs, each echo is drawn as a dot travelling along the device's link and back; a lost echo turns red and fades. Under Reduce Motion the dots are skipped and only the reply cells fill in.
  - **Outages show where the break is:** during a provider outage the router-to-internet link is drawn broken; when the router itself isn't responding, the agent PC's link is. The same location the Diagnose root cause names.
  - **Labelled honestly:** a caption says it shows which devices share the network, not how they're wired. ARP can't tell Wi-Fi from cable or see extenders.
  - **Range:** readable up to about 30 devices in one ring; beyond that, offline devices collapse into one "+N offline" node.
  - **Accessibility:** the map is an alternative view, never the only one. Screen readers get a text summary ("Router, 6 devices online, 1 new, internet 25 ms") and every action stays available from the list.
- **Detail:**
  - Identity: name and device type (both editable), manufacturer, MAC, IP, first and last seen. A "Private address" device explains in one line that the phone hides its real hardware address.
  - Actions (owners and admins): **Mark as trusted**, **Rename**, **Ping test**.
  - Ping test result card: five reply cells fill in live, then the plain line ("Responds well", "Responds, but unevenly", "isn't answering") and the numbers (replies, average, max, loss).
  - Ping history and any **risky open ports** with plain advice ("Telnet sends passwords unencrypted. Turn it off on this device.").
- **States:** online, offline, needs review, ping running, ping timed out (agent offline), viewer read-only. Range: 1–60 devices.
- **Must not:** suggest KinLAN can block a device (it can't; there's no router integration); present the map as a physical wiring diagram.

## 3. Diagnose

- **Job:** "Where exactly is the problem?" This is the product's signature: it locates the failing layer.
- **Structure:** a vertical **ladder of the six checks**, from "This PC" up to "Secure websites", each rung showing live status (waiting → running → pass / fail / skipped).
- **Focal moment:** once done, a **root-cause card** above the ladder with the plain summary and one next step, and the failing rung highlighted. When healthy, the card says everything checks out.
- **Details:** tapping a rung shows its layer, the test and the measurements (for example "ICMP echo to 8.8.8.8: 0 of 3 replies").
- **Actions:** Run again; the result's time; the last few diagnoses for comparison.
- **States:** waiting for the agent (up to 2 minutes, then "The agent didn't respond. Is the PC on?"), running (2–15 s), healthy, failed at step N, agent offline (can't run; shows the last result and why).
- **Must not:** show raw protocol names as the main message; animate so much that the result is slow to read.

## 4. Onboarding and Pairing

- **Job:** get a caretaker from sign-up to a first useful result without help, and let members join a Circle.
- **Flow for a caretaker:**
  1. Create a Circle (its name, for example "Home" or "Lab 3").
  2. Create the first site.
  3. **Pair the agent:** a large 6-digit code with a 10-minute countdown and a copy button, and short steps for the PC: download, run, enter the code, accept the consent prompt.
  4. A live **"Waiting for the agent…"** state that turns into "Connected".
  5. The **baseline review** card: "We found 14 devices. Review them."
- **Flow for a member:** "Join with an invite code" from the welcome screen, then straight to that Circle's Overview.
- **Skippable:** the baseline review and notification permission can be skipped and found later; creating a Circle and site can't, since nothing works without them.
- **States:** code expired (one tap for a new code), agent connected, first scan in progress, pairing failed (wrong or used code).
- **Must not:** hide the consent wording; make the PC steps depend on technical knowledge beyond running a downloaded program.

## 5. Alerts

- **Job:** know what needs attention, and trust that KinLAN won't cry wolf.
- **Structure:** a feed, newest first, grouped **Open** then **Resolved**, filtered by site when there are several.
  - Each alert: severity chip (icon + word), plain title, time, one-line next step; tapping goes to the related site, device or diagnose.
  - Resolved alerts show how they ended, for example "Back online after 4 min 12 s".
- **Actions:** Acknowledge (owners and admins), by swipe or button.
- **Push defaults:** buzz for site unreachable / back online, new unknown device and risky open port. High latency and packet loss appear in the app only. Each member can change this in Settings.
- **States:** empty ("No alerts. KinLAN will tell you when something needs attention."), loading, error, viewer read-only.
- **Must not:** repeat the same alert within 30 minutes while it's open (the server already suppresses this; the UI shouldn't fake it either).

---

## Interaction model (Nov 7, all screens)

Everything that shows a status can be tapped to explain it or act on it. The prototype (`docs/design/prototype/index.html`) implements each of these.

| Element | Tap or gesture | Result |
|---|---|---|
| Status light (Overview) | Tap | Layer sheet: what the layer checks, its state now, what that means, Run diagnose |
| Site name (header) | Tap | Site switcher menu with each site's state; switching re-runs the light ignition |
| Open problem row | Tap | Outage: opens Diagnose. New device: opens its Device detail |
| "Why this grade?" | Tap | Expands the deductions in place (each with its points) |
| Latency chart | Drag (or hover on web) | Crosshair and readout for that hour; "no reply" during an outage |
| Device row or map node | Tap | Device detail sheet: ping test, mark as trusted, rename, change type |
| Internet node | Tap | Outage summary with Run diagnose |
| Diagnose rung | Tap | Expands the technical detail of that check |
| Alert | Acknowledge, or Review for a new device | Acknowledged alerts slide out and move to Resolved; the badge counts down |
| Notification switch | Tap | Toggles, with a confirming toast |
| Invite a member | Tap | Invite sheet with the code and Copy |
| Copy code (pairing, invite) | Tap | "Copied" toast |

Sheets close with the close button, a tap on the scrim, Esc, or the Android back gesture, and return focus to what opened them. Pull to refresh stays on Overview, Devices and Alerts (`docs/design/research.md`).

## Open decisions for DESIGN.md (not decided here)

- ~~Visual direction~~ **Decided Nov 7: Status Lights** (`docs/design/direction.md`). Palette, type and the signature light strip are fixed there; exact dark-theme values are set during the build.
- How the Diagnose ladder looks (the brief fixes only its structure and states).
- ~~How the network map looks~~ **Drawn in the prototype (Nov 7):** type icons in rings, status badges, a red marching dashed link for an outage, a yellow selection ring.
- Chart styling, within the accessibility rules above.
