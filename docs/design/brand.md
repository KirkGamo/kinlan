# KinLAN brand system (Nov 7, 2026)

KinLAN should not look like a generic dark dashboard. Its identity comes from the two halves of its name: **kin**, the people a network serves, and **LAN**, the router and its status lights. Everything below follows from those two ideas. This page feeds the brand section of DESIGN.md (end of Sprint 3). The interactive reference is `docs/design/prototype/index.html`; the source files are in `docs/design/brand/`.

## 1. The mark: five lights in an arc

- **What it is:** five yellow dots on a shallow arc. It is the five-light strip (This PC, Router, Provider, DNS, Web) bent into part of a circle, so it reads as a modem's light panel and as a Circle of people at once.
- **Geometry:** dots of radius 9 on an arc of radius 60, at 40°, 65°, 90°, 115° and 140° (viewBox `0 16 120 50`). See `brand/kinlan-mark.svg`.
- **Color:** signal yellow `#FFD60A` on near-black `#0B0B0C`. The mark is never green or red: those colors mean status.
- **App icon** (`brand/kinlan-icon.svg`): the mark centered on black, inside Android's adaptive-icon safe zone, over a faint perforated texture.
- **Clear space:** at least one dot diameter on every side. Minimum size: 24 dp wide.

## 2. The wordmark

- **"kin"** in Manrope ExtraBold, lower case and tightly tracked (−1.6 at 44 px), in text white.
- **"LAN"** in the silkscreen style (see 3), in yellow, at about half the height of "kin".
- The lockup is the mark followed by the wordmark (`brand/kinlan-wordmark.svg`); in the app the mark sits above the wordmark (splash, About).
- In prose the name is written **KinLAN**.

## 3. Hardware details: silkscreen and perforation

Borrowed from the object the concept came from, the ISP modem:

- **Silkscreen labels:** 10 px, ExtraBold, uppercase, letter-spacing 1.4 px, like the printing on a router's case. Use them for light names, section labels, the map's link labels (`WAN · 27 MS`, `WAN · NO REPLY SINCE 9:41`) and small captions such as "Whose is this?". Never for sentences.
- **Perforation:** a faint dot grid (9 px pitch, 8% white) like a modem's vent holes, fading out from one corner. Use it on **two surfaces only**: the verdict card and the splash. If it appears everywhere, it stops being a signature.
- **Only status lights glow.** Nothing else gets a colored glow or shadow, the yellow Diagnose button included. That scarcity is what makes a lit light mean something.

## 4. People first

The feature that makes KinLAN *Kin*LAN: a device can belong to a Circle member.

- **Device detail** asks "Whose is this?" with one chip per member plus "Shared". A new device asks it right away.
- **Devices tab** defaults to a **People** view: Needs review first, then one group per member (avatar, name, "2 of 2 online"), then "Shared and unassigned". Status and Map stay one tap away.
- **Overview** has a **Your people** row: each member's avatar and how many of their devices are online. Tapping it opens the People view.
- **Map:** owned devices carry their owner's initial in a small avatar on the node.
- **Avatars:** initials on a circle. You are yellow; other members are white or grey. Avatars never use the status colors.
- **Privacy rule:** KinLAN counts *devices* online per person. It never says a person "is home" or tracks where someone is. Device ownership is optional and editable by owners and admins.

## 5. Voice

Calm, specific, never alarmist; it names the person or place, says what's fine first, then what isn't, and ends with what to do.

| Write | Not |
|---|---|
| Your router is fine. Your internet provider isn't answering. | Error: WAN unreachable |
| Someone new joined: Galaxy-A15. Whose is it? | Unknown device detected |
| Home is back online after 7 min. Your provider fixed it. | Connectivity restored |
| Lito's phone isn't answering. Is it switched on? | Host 192.168.1.16 timed out |
| Every light is green. Nothing needs you. | All systems operational |

Technical terms stay available one tap down (the Diagnose rungs, the device facts), never in the first line.

## 6. Signature moments

| Moment | What happens | Motion |
|---|---|---|
| Splash (cold start) | The mark's five dots ignite left to right, then "kinLAN" and "Your people, your network." rise in | 110 ms per dot, then 420 ms; about 2 s in all |
| Loading | Instead of a spinner, five small dots light in sequence (the strip as a loader) | 1.1 s loop, 110 ms stagger |
| Pull to refresh | Dragging down fills the five lights one by one; letting go after the fifth refreshes and re-runs the light ignition | Follows the finger; 220 ms settle |
| Outage starts | The failing light breathes; a double haptic pulse | 2.4 s loop; 20-60-20 ms vibration |
| Back online | The broken red link on the map redraws itself as a solid green line; the Provider light turns green; a triple haptic pulse | 1.1 s line draw |
| Light ignition | One soft haptic tick per light | 8 ms each |

Reduce Motion: the splash and loaders become short fades, the map link appears healed at once, and haptics are off.

## 7. Don'ts

- Don't use yellow for a status, or green/red for branding.
- Don't put the perforation on more than the two surfaces above.
- Don't add glows, gradients or illustrations of routers and cables; the lights are the illustration.
- Don't write "family" (KinLAN serves homes, dorms, offices and labs).
- Don't show people's presence or location.
