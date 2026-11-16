---
name: KinLAN
description: Your people, your network. A dark, calm network monitor whose first read is five status lights.
colors:
  ground: "#0B0B0C"
  card: "#161618"
  raised: "#1F1F23"
  hairline: "#2C2C31"
  text: "#F5F5F7"
  text-secondary: "#A1A1AA"
  signal-yellow: "#FFD60A"
  on-yellow: "#0B0B0C"
  status-green: "#30D158"
  status-orange: "#FF9F0A"
  status-red: "#FF453A"
  on-red: "#0B0B0C"
  unlit: "#2A2A2F"
  unlit-ring: "#5E5E66"
  tint-green: "rgba(48, 209, 88, 0.14)"
  tint-orange: "rgba(255, 159, 10, 0.16)"
  tint-red: "rgba(255, 69, 58, 0.16)"
typography:
  display:
    fontFamily: "Manrope, sans-serif"
    fontSize: "36px"
    fontWeight: 800
    lineHeight: "40px"
    letterSpacing: "-1.26px"
    fontFeature: "tnum"
  headline:
    fontFamily: "Manrope, sans-serif"
    fontSize: "28px"
    fontWeight: 800
    lineHeight: "34px"
    letterSpacing: "-0.56px"
  title-large:
    fontFamily: "Manrope, sans-serif"
    fontSize: "22px"
    fontWeight: 800
    lineHeight: "28px"
    letterSpacing: "-0.26px"
  title:
    fontFamily: "Manrope, sans-serif"
    fontSize: "16px"
    fontWeight: 700
    lineHeight: "22px"
  body:
    fontFamily: "Manrope, sans-serif"
    fontSize: "15px"
    fontWeight: 500
    lineHeight: "22px"
  body-small:
    fontFamily: "Manrope, sans-serif"
    fontSize: "13px"
    fontWeight: 500
    lineHeight: "18px"
  label:
    fontFamily: "Manrope, sans-serif"
    fontSize: "15px"
    fontWeight: 800
    lineHeight: "20px"
  label-small:
    fontFamily: "Manrope, sans-serif"
    fontSize: "12px"
    fontWeight: 700
    lineHeight: "16px"
  silkscreen:
    fontFamily: "Manrope, sans-serif"
    fontSize: "11px"
    fontWeight: 800
    lineHeight: "14px"
    letterSpacing: "1.32px"
rounded:
  digit: "14px"
  field: "16px"
  row: "20px"
  card: "24px"
  sheet: "28px"
  pill: "999px"
spacing:
  s1: "4px"
  s2: "8px"
  s3: "12px"
  s4: "16px"
  s5: "20px"
  s6: "24px"
  s8: "32px"
  gutter: "16px"
  card: "20px"
  section: "32px"
components:
  button-primary:
    backgroundColor: "{colors.signal-yellow}"
    textColor: "{colors.on-yellow}"
    typography: "{typography.label}"
    rounded: "{rounded.pill}"
    padding: "0 24px"
    height: "52px"
  button-ghost:
    backgroundColor: "{colors.raised}"
    textColor: "{colors.text}"
    typography: "{typography.label}"
    rounded: "{rounded.pill}"
    padding: "0 24px"
    height: "52px"
  button-danger:
    backgroundColor: "{colors.raised}"
    textColor: "{colors.status-red}"
    typography: "{typography.label}"
    rounded: "{rounded.pill}"
    padding: "0 24px"
    height: "52px"
  fab-diagnose:
    backgroundColor: "{colors.signal-yellow}"
    textColor: "{colors.on-yellow}"
    typography: "{typography.label}"
    rounded: "{rounded.pill}"
    padding: "0 20px"
    height: "56px"
  text-field:
    backgroundColor: "{colors.raised}"
    textColor: "{colors.text}"
    typography: "{typography.body}"
    rounded: "{rounded.field}"
    padding: "0 16px"
    height: "52px"
  card:
    backgroundColor: "{colors.card}"
    textColor: "{colors.text}"
    rounded: "{rounded.card}"
    padding: "20px"
  list-row:
    backgroundColor: "{colors.card}"
    textColor: "{colors.text}"
    typography: "{typography.title}"
    rounded: "{rounded.row}"
    padding: "12px 16px"
    height: "68px"
  list-row-pressed:
    backgroundColor: "{colors.raised}"
  sheet:
    backgroundColor: "{colors.card}"
    textColor: "{colors.text}"
    rounded: "{rounded.sheet}"
    padding: "20px"
  chip:
    backgroundColor: "{colors.raised}"
    textColor: "{colors.text}"
    typography: "{typography.label-small}"
    rounded: "{rounded.pill}"
    padding: "0 16px"
    height: "36px"
  chip-selected:
    backgroundColor: "{colors.signal-yellow}"
    textColor: "{colors.on-yellow}"
  segmented-selected:
    backgroundColor: "{colors.signal-yellow}"
    textColor: "{colors.on-yellow}"
    typography: "{typography.label-small}"
    rounded: "{rounded.pill}"
    height: "40px"
  nav-tab-selected:
    backgroundColor: "{colors.signal-yellow}"
    textColor: "{colors.on-yellow}"
    typography: "{typography.label-small}"
    rounded: "{rounded.pill}"
  status-chip-ok:
    backgroundColor: "{colors.tint-green}"
    textColor: "{colors.status-green}"
    typography: "{typography.label-small}"
    rounded: "{rounded.pill}"
    height: "26px"
  status-chip-new:
    backgroundColor: "{colors.tint-orange}"
    textColor: "{colors.status-orange}"
    typography: "{typography.label-small}"
    rounded: "{rounded.pill}"
    height: "26px"
  status-chip-down:
    backgroundColor: "{colors.tint-red}"
    textColor: "{colors.status-red}"
    typography: "{typography.label-small}"
    rounded: "{rounded.pill}"
    height: "26px"
  status-chip-neutral:
    backgroundColor: "{colors.raised}"
    textColor: "{colors.text-secondary}"
    typography: "{typography.label-small}"
    rounded: "{rounded.pill}"
    height: "26px"
  status-light-pass:
    backgroundColor: "{colors.status-green}"
    size: "22px"
    rounded: "{rounded.pill}"
  status-light-fail:
    backgroundColor: "{colors.status-red}"
    size: "22px"
    rounded: "{rounded.pill}"
  status-light-unlit:
    backgroundColor: "{colors.unlit}"
    size: "22px"
    rounded: "{rounded.pill}"
  avatar-you:
    backgroundColor: "{colors.signal-yellow}"
    textColor: "{colors.on-yellow}"
    typography: "{typography.label-small}"
    size: "40px"
    rounded: "{rounded.pill}"
  avatar-member:
    backgroundColor: "{colors.raised}"
    textColor: "{colors.text}"
    typography: "{typography.label-small}"
    size: "40px"
    rounded: "{rounded.pill}"
---

# Design System: KinLAN

Written from the built app at the end of Sprint 3 (Nov 15, 2026), after the finish review against the Status Lights direction contract (`docs/design/direction.md`). The tokens above mirror `mobile/src/theme/` (`colors.ts`, `typography.ts`, `layout.ts`); when the two disagree, the code is the bug and this file is the intent. Screen behavior lives in `docs/design/briefs.md`, the brand layer in `docs/design/brand.md`, product truth in `PRODUCT.md`.

## Overview

**Creative North Star: "The Router at Night"**

KinLAN looks like the front panel of a modem in a dark room: a near-black ground, and on it five small lights that tell you, before you read a word, where the network is fine and where it breaks. Everything else stays quiet. Cards are a shade lighter than the ground, text is calm and plain, and colour appears only where something is working, waiting or wrong. The one loud colour, signal yellow, is reserved for the brand and for "this is the thing you're on or about to do": the selected tab, the primary button, the Diagnose pill, the health gauge and the chart line.

The mood is a calm instrument. It is precise like a good meter and never alarmist: a healthy network reads as a row of green lights and two words, "All good", and a broken one names the place and one next step. Density is moderate. One headline per screen, lists of 68-dp rows, generous 32-dp gaps between sections, and detail always one tap away in a bottom sheet rather than on the surface.

The world is Material Design 3 in structure (navigation bar, FAB, bottom sheets, chips, switches, edge-to-edge insets, system Back) and KinLAN in its theming. The app ships dark-first; there is no light theme yet.

**Key Characteristics:**
- A five-light strip (This PC, Router, Provider, DNS, Web) is the first read on Overview and Diagnose.
- Near-black tonal layering instead of shadows: ground, card, raised.
- Signal yellow for brand and selection only; status colours never borrow it.
- Every status is a colour plus a drawn icon plus a word.
- Manrope throughout, heavy and tightly tracked for headlines, tabular figures for every number.
- Pill-shaped controls, 20 to 28-dp rounded containers, no hard edges.
- Motion that ignites, rises and counts up, and collapses to a short fade under Reduce Motion.

## Colors

A black-and-graphite instrument panel with one brand yellow and three status colours, each used only for its meaning.

### Primary
- **Signal Yellow** (`signal-yellow`): brand and selection only. The selected tab pill, the selected segment and chip, primary buttons (with black `on-yellow` text), the Diagnose FAB, the health gauge arc, the internet line and its fade in the latency chart, the pairing countdown, focused field borders, the cursor, and your own avatar. Never a status.

### Status
- **Healthy Green** (`status-green`): a passing light, "Online", "Healthy", "Working", a passed Diagnose rung. Chip background `tint-green`.
- **Degraded Orange** (`status-orange`): new, slow or needs review: the "New" chip and map badge, a slow Provider light, warnings, deductions in the health card. Chip background `tint-orange`.
- **Down Red** (`status-red`): failing and destructive: a failing light and its breathing ring, a failed rung outline, "Down", "Critical", the alert badge, errors, and the danger button's label and hairline. Text on a red fill is `on-red` black (5.78:1); white fails at 3.4:1.

### Neutral
- **Night Ground** (`ground`): every screen's background, the splash, the app icon field.
- **Panel Graphite** (`card`): cards, list rows, sheets, the navigation bar.
- **Raised Graphite** (`raised`): one step up: ghost buttons, chips, fields, sheet icon tiles and grab handles, pressed rows, icon wells.
- **Hairline** (`hairline`): field borders and grid lines in the chart; the only stroke colour in the system.
- **Readout White** (`text`): primary text and icons (16.6:1 on `card`).
- **Muted Steel** (`text-secondary`): secondary lines, captions, silkscreen labels, the router line in the chart (7.05:1 on `card`).
- **Unlit Lamp** (`unlit`) with **Lamp Rim** (`unlit-ring`): a light that isn't lit, unchecked rungs, empty reply cells, the switch's off track.

### Named Rules
**The Lights-Only Glow Rule.** Only status lights glow (a soft ring in the light's own colour). No other surface gets a glow, gradient border or coloured shadow.

**The Yellow Is Not a Status Rule.** Yellow never means "good", "warning" or "selected device is healthy". If a design wants yellow to carry state, use the status colour and keep yellow for selection.

**The Stale Never Green Rule.** When the agent is offline (data older than 2 minutes), every light goes unlit, online counts are hidden, and the verdict says "Agent offline". Old data is never shown in green.

## Typography

**Display Font:** Manrope (with the platform sans as fallback)
**Body Font:** Manrope
**Label Font:** Manrope, silkscreen style (uppercase, wide tracking)

**Character:** One geometric sans in nine roles. Heavy (800) and tightly tracked for headlines and big numbers so they read like a device readout; medium (500) for sentences, one step heavier than usual because light text on black thins out.

### Hierarchy
- **Display** (800, 36/40, -1.26 px tracking, tabular): the health score only.
- **Headline** (800, 28/34): the one headline per screen: the verdict, the Diagnose root cause, empty-state titles.
- **Title large** (800, 22/28): the site name in the header, sheet titles, Settings.
- **Title** (700, 16/22): row, person, rung and alert titles.
- **Body** (500, 15/22): sentences: verdict text, sheet text, steps, empty states.
- **Body small** (500, 13/18): secondary lines, facts, timestamps, the chart readout.
- **Label** (800, 15/20): buttons and the Diagnose FAB.
- **Label small** (700, 12/16): chips, status chips, the navigation bar, small controls.
- **Silkscreen** (800, 11/14, uppercase, +1.32 px tracking): section labels, light names, map captions; like the printing on a router's case.

Sizes are sp on Android, so they follow the phone's text-size setting; spacing stays in dp.

### Named Rules
**The One Headline Rule.** Each screen has exactly one Headline. On Overview it is the verdict, so the site name steps down to Title large.

**The Tabular Numbers Rule.** Every changing number (latency, counts, times, the score, the pairing code) uses tabular figures so it doesn't shift as it updates. Latency shows no decimals at or above 10 ms and one decimal below.

## Layout

A single column on a 4-dp grid. Screens sit 16 dp from the edges (`gutter`), cards pad 20 dp inside (the verdict card gets 24 dp on top), rows of one group sit 8 dp apart, and each section label has 32 dp above and 12 dp below, so space groups content rather than lines. Lists are 68-dp rows with 12 x 16 padding. Touch targets are 48 dp minimum (buttons 52, FAB 56, fields 52, chips 36 inside a 48-dp hit area).

The four tab screens share one shell: a header row (site name with its switcher on the left, your avatar on the right), content in a scroll view with pull to refresh, and the Material navigation bar at the bottom. Pushed screens (Diagnose, Pairing, onboarding) get a plain dark top bar with the title and system Back, and no avatar.

The light strip is a fixed five-column instrument: five equal columns whatever the width; light names are capped at the silkscreen size while their values scale. The network map draws in a square card at the content width; above 10 devices its nodes shrink to 32 dp and only the selected device is named.

The web build uses the same layout at phone width. There is no tablet or desktop layout yet.

## Elevation & Depth

Depth is tonal, not shadowed. Three surfaces stack: `ground` (the page), `card` (cards, rows, sheets, the navigation bar) and `raised` (controls and nested facts). A pressed row moves from `card` to `raised` instead of lifting.

Only two shadows exist: the soft glow ring on a lit status light (its own colour, 8-dp blur, no offset), and a soft ambient shadow under the Diagnose FAB so it reads over content scrolling beneath it. Bottom sheets sit over a 60% black scrim instead of casting shadow.

**The Flat-By-Default Rule.** Surfaces are flat. If something needs to stand out, give it a lighter tonal step or yellow, never a drop shadow.

## Shapes

Everything is rounded and nothing is sharp. Containers use continuous ("squircle") corners: cards 24 dp, list rows 20 dp, sheets 28 dp on the top corners, fields 16 dp, pairing-code tiles 14 dp. Every control is a full pill: buttons, chips, segments, the selected tab, status chips, the FAB. Lights, avatars, map nodes and rung badges are circles.

Strokes are rare and thin: the 1.5-dp hairline on fields (yellow when focused, red on error), the 2-dp selection ring on the current site or Circle, the 2.5-dp status ring on map nodes, and the red hairline on danger buttons.

## Components

### Buttons
Pill-shaped, confident, one primary per view.
- **Shape:** full pill (`rounded.pill`), 52 dp tall, 24 dp side padding, Label type.
- **Primary:** signal yellow with black text. The one main action: Continue, Run again, Pair the agent, Copy code.
- **Ghost:** raised graphite with white text. Secondary actions: Acknowledge, Review, Add a site, Sign out.
- **Danger:** raised graphite with a red label and a red hairline. Destructive actions only: Remove from this Circle, Leave, Delete account. Never filled red.
- **Pressed:** scales to 0.97 (120 ms). **Loading:** the five-dot loader replaces the label. **Disabled:** 50% opacity.
- **FAB (Diagnose):** a 56-dp yellow pill with the prototype's magnifier-and-pulse glyph and "Diagnose", bottom-right above the navigation bar, owners and admins only.

### Status chips
The system's way of saying state.
- **Style:** a 26-dp pill with a drawn 14-dp icon and a word in Label small: check plus green on green tint (Healthy, Online, Trusted), dot plus orange on orange tint (New, Warning, Degraded), triangle plus red on red tint (Down, Critical, Failing), dash plus muted on raised (Offline, Not paired, Not checked).
- **Rule:** never colour alone, never a text glyph for the icon.

### Choice chips and the segmented switch
- **Chips:** 36-dp pills in a horizontal scroll, in three variants. Fill (device type, alert thresholds): raised, the selected one yellow with black text. Filter (the Devices filters): `card` with muted text, the selected one white with black text. Outline ("Whose is this?"): raised, the selected one ringed in 2-dp yellow with white text.
- **Segmented switch:** a graphite track holding equal pills (People | Status | Map); the selected segment is the yellow pill.

### Cards / Containers
- **Corner Style:** 24 dp continuous.
- **Background:** `card` on the `ground`.
- **Verdict card:** the one card with the perforated texture: a 9-dp grid of 1.1-dp dots in `text` at 8%, strongest at the top-right corner and faded out by 60% of the way across.
- **Shadow Strategy:** none (see Elevation).
- **Internal Padding:** 20 dp; 8-dp gaps between children.

### List rows
- 68-dp `card` rows with 20-dp corners and 12 x 16 padding: an optional 40-dp icon well or avatar, a Title line, a Body-small line, and a status chip or action on the right. Pressed rows turn `raised`. Used for sites, devices, people, members, problems and alerts.

### Inputs / Fields
- **Style:** a 52-dp `raised` box, 16-dp corners, 1.5-dp hairline border, Label-small label above, Body text, muted placeholder.
- **Focus:** the border and the cursor turn yellow.
- **Error:** red border and a red Body-small line below; otherwise a muted hint line. Passwords get a yellow Show/Hide text button.

### Bottom sheets
- `card` surface with 28-dp top corners over a 60% scrim; slide up in 350 ms (decelerate). A 36 x 4 grab handle, then the head: an optional 52-dp `raised` icon tile (18-dp corners), the Title large heading with an optional meta line under it (a status chip and a short fact), and a 44-dp round close button. Facts sit below a top hairline as label-left (muted Body small) and value-right (Body small at 700, tabular) rows. Content scrolls past 72% of the screen height. Closes with the button, the scrim, Esc, system Back, or a drag down on the handle and head: past 30% of its height or a quick flick it closes (a tick as it crosses that point, the scrim fading with it), otherwise it springs back (a short fade under Reduce Motion). The body keeps its own scrolling. Used for the light layer, device detail, the account sheet, the site switcher, member and invite.

### Navigation
- Material navigation bar on `card` with a top hairline: four destinations (Overview, Devices, Alerts, Settings). The active destination is a yellow pill with black icon and label; inactive ones are muted. Alerts carries a red count badge with black numerals. On web the same bar is drawn with headless tabs.

### The light strip (signature)
- Five equal columns in a card: a 22-dp lamp (green, orange or red, with its glow, or an unlit lamp with a rim), the layer name in Silkscreen, and its value in Label small with tabular figures. On open and after a site switch the lights ignite left to right (110-ms stagger, each scaling to 1.18 and settling). A failing light keeps a slow red breathing ring (2.4 s). Tapping a lamp opens its layer sheet. Diagnose maps its six steps onto these five lights.

### The network map (signature)
- The router in the middle (52-dp node), the internet above it, devices on a ring, the agent's PC at the bottom; nodes are circles with a type icon and a status ring, plus an orange badge and the word "New" for new devices. Links carry live numbers; a provider outage breaks the internet link in red dashes. The selected node gets a yellow ring and its link turns yellow while the others dim. A caption says it shows who shares the network, not wiring.

### Avatars
- Initials on a 40-dp circle (32 in group headers): yellow with black initials for you, raised graphite with white initials for everyone else. Never a status colour.

### Loader
- Five small lights blinking in sequence (yellow), the brand's replacement for a spinner. It also fills the loading slot of buttons.

## Haptics
Haptics confirm what the user did; they never announce what the network did.

- **Tick:** a different tab, segment or chip, the pull-to-refresh release, and a sheet drag crossing its close point. Pressing the current choice again is silent.
- **Toggle:** switches, on and off.
- **Confirm:** the result of something the user started went well: a ping with replies, a diagnose where all six pass, the agent connecting while you wait on Pair, a device marked trusted, a code copied.
- **Reject:** the result went badly (no replies, a root cause, no result), or a destructive step is one tap away (Remove, Leave, Delete account).

**The Quiet Network Rule.** Polling, background refreshes, new alerts and push arrivals never vibrate the open app; the system notification already did. One vibration per action, and ordinary buttons, scrolling and opening a sheet stay silent.

Android uses the system's own patterns (`Segment_Tick`, `Toggle_On/Off`, `Confirm`, `Reject`), so the phone's touch-feedback setting is respected. Settings → Feel → Vibration turns them all off for this phone. Web does nothing.

## Do's and Don'ts

### Do:
- **Do** lead every screen that shows a network with the five-light strip, and keep the five layer names and their order (This PC, Router, Provider, DNS, Web).
- **Do** pair every status with its colour, a drawn icon and a word, using the four status chip tones.
- **Do** keep signal yellow to brand and selection: one primary button per view, the selected tab, segment or chip, the FAB, the gauge and the chart line.
- **Do** build depth from `ground`, `card` and `raised`, and press rows by stepping them to `raised`.
- **Do** use Manrope through the nine roles, and tabular figures for every number that changes.
- **Do** put detail in a bottom sheet one tap away and keep the surface to plain words.
- **Do** design the four states for every screen: loading (five-dot loader or unlit strip), empty (a message and an action), error (a "Couldn't load" chip and Try again), stale (unlit lights, "Last seen", hidden online counts).
- **Do** honour Reduce Motion: every movement becomes a 120-ms fade, and loops stop.

### Don't:
- **Don't** use yellow for a status, or green, orange or red for decoration.
- **Don't** show green lights, "Online" counts or "All good" from data older than 2 minutes.
- **Don't** add drop shadows, gradient borders or glows to anything but a lit status light and the FAB.
- **Don't** use square corners or outlined-only primary buttons; controls are pills.
- **Don't** fill a button red; destructive actions are red-labelled ghost buttons.
- **Don't** use avatars in status colours, or emoji and text glyphs as icons.
- **Don't** suggest KinLAN can block a device or present the map as a wiring diagram.
- **Don't** write "family" in UI copy; groups are Circles.
- **Don't** put the perforated texture on more than the verdict card and the splash (`docs/design/brand.md`).
