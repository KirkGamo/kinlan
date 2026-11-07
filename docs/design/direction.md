# Visual direction: Status Lights (yellow, orange and black)

**Chosen Nov 7, 2026** with the Impeccable new-work flow (concept-seed, second hand): the user picked Status Lights, Impeccable's pick, over the rolled Listahan, the Orienteering Course and Boarding Pass & Gate Board challengers, and the plain Material Design 3 standard. **Re-skinned the same day at the user's request** into a modern yellow, orange and black world with smooth animations and transitions, after dark energy-dashboard references. The form (the five-light strip) is unchanged.

**Interactive prototype:** [`prototype/index.html`](prototype/index.html), all screens with the motion system, using synthetic data.

This is the repository copy. The working copy that Impeccable reloads is `.impeccable/surfaces/mobile-app-tabs-index-tsx.md` (local only, because `.impeccable/` is git-ignored). Update both together.

**DESIGN.md** is written from the built app at the end of Sprint 3 (#26); until then this contract is the visual reference.

---

## Surface brief: Overview (home) and the app shell

**Scope:** the Android app's Overview screen and the shell every screen shares (header, light strip, bottom navigation). Visitor mode: Operate. Screen behavior and states are in `docs/design/briefs.md` (section 1); product truth is in PRODUCT.md. Interactive reference: `docs/design/prototype/index.html`.

**Audience and job:** the caretaker, often arriving from a notification or "the internet is slow", needs to know in one glance whether anything is wrong and where. Members get the same read without technical words.

## Direction contract

THESIS: Every site's first read is a row of five labelled status lights (This PC, Router, Provider, DNS, Web) glowing on black: the diagnose path at a glance, so the caretaker sees where the network breaks before reading a word. It refuses the category default of a grey summary card with one accent and an "Online" badge.

OWN-WORLD: A near-black #0B0B0C ground with #161618 cards and #1F1F23 raised surfaces; 24 dp rounded cards and pill-shaped controls. One signal yellow #FFD60A carries brand and selection only: the selected tab, primary buttons (black text), the health gauge, chart lines with a yellow fade and the "checking" pulse. Status never borrows yellow: green #30D158 healthy, orange #FF9F0A degraded or new, red #FF453A down; unlit lights are #2A2A2F with a #5E5E66 ring; every status also carries an icon and a word. Text #F5F5F7, secondary #A1A1AA. Type: Manrope, bold and tightly tracked for headlines and big numbers, tabular figures throughout. Material 3 structure, navigation and controls, restyled; no glow except the soft ring on a lit light.

STORY: The caretaker opens KinLAN, watches the lights come on and sees which one is red, reads the verdict ("Internet down since 9:41: your router is fine, but your internet provider isn't responding"), then acts: Diagnose, review a new device, or wait. Members read the same lights and understand them without any terms.

FIRST VIEWPORT: Header on black (site name with switcher, yellow avatar); the light strip in a card, five equal columns; the verdict card (status chip, 24 sp bold title, one plain cause line, "Updated 10 s ago"); then Open problems, the health gauge (yellow semicircle with the score counting up), the 24-hour chart and devices. A yellow Diagnose pill sits bottom-right above the bottom navigation, whose selected tab is a yellow pill. Signature interaction: on open the lights ignite left to right; on the Diagnose screen each light pulses yellow while its check runs, then settles green or red, the failing light keeps a slow breathing ring and the rest stay unlit; tapping a light opens that layer's detail.

FORM: Status Lights, from the PON, LOS and Wi-Fi lights on ISP modems; position 1 on the ordered list, chosen by the user as Impeccable's pick over the rolled Listahan in the second hand; re-skinned Nov 7 at the user's request into a modern yellow, orange and black world with smooth motion, after dark energy-dashboard references. seed: seed:a7c1bacbc9895dfa

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

## Motion system

Only transform and opacity animate (Reanimated on the UI thread in the app).

| Moment | Motion | Timing |
|---|---|---|
| Press on a row, button or FAB | Scale to 0.95–0.98 | 120 ms, standard easing |
| Chips, segmented thumb, tab indicator | Slide or recolor in place | 220 ms, decelerate |
| Screen change (tabs) | Fade through with a 12 dp rise | 350 ms, decelerate |
| Pushed screen (Diagnose, Pairing) | Slide in 28 dp from the right and fade | 350 ms, decelerate |
| Light ignition on open | Lights come on left to right, each scaling 1.18 then settling | 110 ms stagger, about 900 ms in all |
| Diagnose check running | The light and its rung pulse yellow | 900 ms loop while running |
| Failing light | Slow breathing ring | 2.4 s loop |
| Lists and cards entering | Rise 10 dp and fade, staggered | 420 ms each, 40 ms stagger, at most 7 |
| Health gauge and score | Arc sweeps; number counts up (ease-out cubic) | 1.1 s |
| Latency chart | Line draws, then the yellow fade appears | 1.2 s |
| Network map | Nodes pop in; the broken internet link's dashes march | 500 ms each, 60 ms stagger; 1.4 s loop |
| Pairing code | Digits flip in; the waiting dot ripples | 520 ms, 60 ms stagger; 1.6 s loop |
| Bottom sheet (device, layer, invite) | Slides up over a fading scrim | 350 ms decelerate; closes the same way |
| Map selection | Yellow ring scales in; other nodes dim | 220 ms |
| Ping on the map | A dot travels the link and back for each echo; lost echoes turn red and fade | 260 ms each way |
| Toast | Rises 20 dp and fades in; leaves after 1.8 s | 220 ms |
| Splash | The mark's five dots ignite, then the wordmark and tagline rise in | 110 ms per dot, 420 ms words; about 2 s |
| Loading and pull to refresh | Five small dots light in sequence; pulling fills them one by one | 1.1 s loop; follows the finger |
| Back online | The broken map link redraws as solid green | 1.1 s |

Easings: decelerate `cubic-bezier(0.05, 0.7, 0.1, 1)` for arrivals, standard `cubic-bezier(0.2, 0, 0, 1)` for changes in place, accelerate `cubic-bezier(0.3, 0, 0.8, 0.15)` for exits.

**Reduce Motion:** every movement becomes a 120 ms fade, loops stop, and results appear at once.

## Brand system

The brand layer on top of this direction is in `docs/design/brand.md` (mark, wordmark, silkscreen labels, perforation on the verdict card and splash only, people-first devices, voice, signature moments). Two rules from it bind every screen: only status lights glow, and avatars never use the status colors.

## Light mapping and states

- **The six diagnose steps map to five lights:** This PC = step 1; Router = steps 2 and 3 (ARP and ping); Provider = step 4; DNS = step 5; Web = step 6.
- **Stale data never shows green:** when the agent is offline, every light goes unlit with "Last seen 9:41", and the verdict says the agent is offline.
- **Dark-first:** the app ships dark. A light theme is optional later and must keep the same status colors at 4.5:1.

## Unresolved

- Whether to add a light theme before submission, or leave it as future work.
- The Figma mockups use the earlier graphite palette; update the file's color tokens when Figma's call limit resets (the tokens drive every fill).

## Contrast check (Nov 7, dark palette)

Measured against WCAG 2.1 (PRODUCT.md requires 4.5:1 for text and 3:1 for icons and shapes):

| Pair | Ratio | Result |
|---|---|---|
| Text #F5F5F7 on card #161618 | 16.60:1 | Pass |
| Secondary #A1A1AA on card / on raised | 7.05:1 / 6.41:1 | Pass |
| Black text on yellow button | 13.94:1 | Pass |
| Yellow text on card | 12.80:1 | Pass |
| Orange / green / red text on card | 8.79:1 / 8.94:1 / 5.30:1 | Pass |
| Red light on black | 5.78:1 | Pass |
| Unlit ring #5E5E66 on black | 3.06:1 (#48484F failed at 2.17:1) | Pass |
| Dim grey #71717A on card | 3.74:1 | **Fails for text**: not used for text |
