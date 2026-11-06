# Visual direction: Status Lights

**Chosen Nov 7, 2026** with the Impeccable new-work flow (concept-seed, second hand). The user picked Status Lights, Impeccable's pick, over the rolled Listahan, the Orienteering Course and Boarding Pass & Gate Board challengers, and the plain Material Design 3 standard. The first hand (Watch Board, Status Lights, Star Atlas) was re-rolled.

This is a copy for the repository. The working copy that Impeccable reloads is `.impeccable/surfaces/mobile-app-tabs-index-tsx.md` (local only, because `.impeccable/` is git-ignored). Update both together.

**DESIGN.md** is written from the built app at the end of Sprint 3 (Impeccable writes it from the built world, not before the build); until then this contract is the visual reference for the Figma mockups and the Sprint 3 theme.

---


## Surface brief: Overview (home) and the app shell

**Scope:** the Android app's Overview screen and the shell every screen shares (top app bar, light strip, bottom navigation). Visitor mode: Operate. Screen behavior and states are in `docs/design/briefs.md` (section 1); product truth is in PRODUCT.md.

**Audience and job:** the caretaker, often arriving from a notification or "the internet is slow", needs to know in one glance whether anything is wrong and where. Members get the same read without technical words.

## Direction contract

THESIS: Every site's first read is a row of five labelled status lights (This PC, Router, Provider, DNS, Web): the diagnose path at a glance, so the caretaker sees where the network breaks before reading a word. It refuses the category default of a grey summary card with one accent and an "Online" badge.

OWN-WORLD: A graphite #2B2F36 shell (status bar, top app bar and light strip share it) over a panel-grey #F4F5F7 ground with white 12 dp cards. Lights are circles with a printed, condensed, uppercase label beneath (Roboto Condensed) and a value line (2 ms, Down, Skipped). Lit states on graphite: green #2FB344, amber #F0A202, red #F03E3E; unlit is a #3D424B fill with a #7A818C ring and means skipped or unknown. Status text and chips on light grounds use the darker green #1E7B30, amber #8A5A00 and red #C92A2A. Every light also carries its word. Body text is Roboto with tabular figures; Material 3 components themed graphite. No bezels, plastic texture or glow beyond a soft 4 dp ring on a lit light.

STORY: The caretaker opens KinLAN, sees which light is red, reads the verdict ("Internet down since 9:41: your router is fine, but your internet provider isn't responding"), then acts: Diagnose, review a new device, or wait. Members read the same lights and understand them without any terms.

FIRST VIEWPORT: Graphite top app bar (site name with switcher, avatar); directly below, the full-width light strip in five equal columns, about 76 dp tall; the verdict card on the grey ground (status word, 21 sp title, one plain cause line, "Updated 10 s ago"); then Open problems, the health grade card, the 24-hour chart and devices. The Diagnose extended FAB sits bottom-right above Material bottom navigation (Overview, Devices, Alerts, Settings). Signature interaction: on the Diagnose screen the same five lights come on one by one as each check passes, the failing one turns red and the rest stay unlit; tapping a light opens that layer's detail.

FORM: Status Lights, from the PON, LOS and Wi-Fi lights on ISP modems; position 1 on the ordered list, chosen by the user as Impeccable's pick over the rolled Listahan in the second hand. seed: seed:a7c1bacbc9895dfa

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

## Light mapping and states

- **The six diagnose steps map to five lights:** This PC = step 1; Router = steps 2 and 3 (ARP and ping); Provider = step 4; DNS = step 5; Web = step 6.
- **Stale data never shows green:** when the agent is offline, every light goes unlit with "Last seen 9:41", and the verdict says the agent is offline.
- **Light mode first; dark theme** keeps the graphite shell and darkens the ground and cards; the status colors stay and are checked for contrast in both.

## Unresolved

- Whether the Devices network map draws nodes as small lights (consistent) or as plain dots (quieter).
- Exact dark-theme ground and card values (set during the Sprint 3 build, checked for 4.5:1 text contrast).

## Contrast check (Nov 7)

Measured against WCAG 2.1 (PRODUCT.md requires 4.5:1 for text and 3:1 for icons and shapes):

| Pair | Ratio | Result |
|---|---|---|
| White text on graphite shell | 13.44:1 | Pass |
| Light label #C9CDD4 on graphite | 8.43:1 | Pass |
| Green / amber light on graphite | 4.90:1 / 6.32:1 | Pass |
| Red light on graphite | #E03131 2.98:1 fails; **#F03E3E 3.50:1** adopted | Pass |
| Unlit light ring on graphite | #3D424B alone 1.33:1 fails; **#7A818C ring 3.42:1** adopted | Pass |
| Body #1E2228 on panel grey | 14.64:1 | Pass |
| Status text on white | bright green 2.74:1 and amber 2.13:1 fail; **#1E7B30 5.34:1, #8A5A00 5.93:1, #C92A2A 5.46:1** adopted | Pass |
