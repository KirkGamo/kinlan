# Mockups (Sprint 1, issue #17)

Mid-fidelity Android mockups of the five key screens, in the Status Lights direction (`docs/design/direction.md`), for the Nov 17 progress report and Chapter 2.

**Figma file:** https://www.figma.com/design/4i7Nuehl6zDbeMDWdtZAmM (page "KinLAN mockups")

## What's in the file

- **Built from Material 3:** status bar, app bar, navigation bar, extended FAB and segmented button are instances of the Material 3 Design Kit; frames are 412 × 917 dp (Material's baseline phone).
- **KinLAN components:** `KinLAN/Status light` (Pass, Warn, Fail, Unlit, with Label and Value text), `KinLAN/Status chip` (Down, Degraded, Healthy, New, Unknown: icon + word + color) and `KinLAN/Icons` (home, devices, notifications, settings, network check).
- **Color tokens:** the collection "KinLAN / Status Lights" holds the 20 contrast-checked colors from the direction contract; every fill in the mockups is bound to one.
- **One detached instance:** the Overview's app bar is detached because Material's app bar always reserves a leading navigation icon, and the home screen has no back or menu action.

## Status

| Screen | Status |
|---|---|
| 01 Overview: provider outage | Done |
| 02 Devices: list | Built; visual check pending |
| 03 Devices: network map | Built; the List \| Map switch still shows "List" selected (to fix) |
| 04 Diagnose | Not built yet |
| 05 Onboarding: pairing | Not built yet |
| 06 Alerts | Not built yet |

The build stopped on Nov 7 when the Figma Starter plan's monthly limit for MCP tool calls was reached.

All names, devices and addresses in the mockups are synthetic.
