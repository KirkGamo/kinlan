# Product

<!-- impeccable:product-schema 1 -->

## Platform

android

The Android app is the primary product. The same Expo codebase is also exported as a static web app for members without Android; it shares the Android app's design language and has no push notifications. iOS is out of scope for this project.

## Stack

Decided in `docs/KinLAN_Technical_Plan.md` and the submitted proposal:
- **Mobile and web app:** Expo (React Native, TypeScript), Expo Router, React Native Paper (Material Design 3), TanStack Query, react-native-gifted-charts, expo-notifications.
- **Cloud API:** FastAPI (Python 3.12), PostgreSQL on Neon, hosted on Render.
- **Agent:** Python 3.12 on a Windows PC inside each network (Scapy + Npcap, icmplib, SQLite buffer), packaged with PyInstaller.

## Users

**Primary user: the caretaker.** In every Circle, one person sets KinLAN up and looks after the network: they install the agent on a PC, invite the others, and act when something breaks. They're the "techie" of a household, the dorm-mate others ask for help, the person who handles the office router, or a school lab technician. They know roughly what a router and an IP address are, but they aren't network engineers. Their jobs:
- see at a glance whether every network they look after is healthy;
- find out *where* a problem is (this device, the Wi-Fi, the router, or the internet provider) before deciding what to do;
- notice unknown devices and risky open ports;
- keep a record of outages and performance to show someone else, such as an ISP.

**Secondary users: everyday members** of a Circle (owner, admin or viewer role). They mostly check whether the network is OK and receive alerts. When their needs conflict with the caretaker's, **the caretaker's depth and control come first**, and members get a simple view on top of it.

**Who a Circle is:** any group of people who share a network and look out for it together: a household, roommates in a dorm, coworkers in a small office, or staff of a school laboratory. KinLAN is never positioned as a family-only product.

## Product Purpose

KinLAN lets a group of people watch over a shared network from anywhere. An agent inside the network discovers devices, measures latency and packet loss, finds which network layer failed when the connection breaks, and checks for risky open ports. It reports to a cloud API, and Circle members follow their networks from the app, with shared alerts and reports.

It exists because small networks rarely have IT staff, built-in tools (ping, arp) check one host at a time and only from inside the network, and tools like Wireshark need expertise.

**Success means:**
- a caretaker can pair a site, invite members and get the first useful result without help;
- when the internet breaks, the app says *which layer failed* in words a non-engineer understands;
- the group learns about outages and unknown devices from the app before someone has to ask "is the Wi-Fi down?";
- the product meets the CCS 234 final-project requirements: network discovery, connectivity testing, network statistics, report generation and security recommendations, deployed and usable by multiple people.

## Positioning

- **It locates the failure, not just the symptom.** A six-step diagnose walks the network layers in order (adapter → gateway ARP → gateway ping → internet ping → DNS → TCP/HTTPS) and stops at the first one that fails, so the answer is "your router is fine, but your internet provider is down," not just "no connection."
- **It's shared by design.** A Circle has roles (owner, admin, viewer), invite codes and alerts that reach every member, so watching the network isn't one person's private tool.
- **It keeps working when the internet doesn't.** The agent buffers measurements locally during an outage and uploads them afterward, so outage history has exact start times, durations and causes.

## Operating Context

- **Where the agent runs:** a Windows PC that stays on in the network being monitored (a home desktop, an office PC, a lab machine), started at boot.
- **Where people use the app:** on Android phones, often away from the network (on mobile data), when an alert arrives or when someone says the internet is slow; occasionally in a desktop browser through the web build.
- **Setup ritual:** the caretaker creates a Circle and a site in the app, gets a 6-digit pairing code, enters it on the PC running the agent, reviews the devices found in the first (baseline) scan, then invites members with invite codes.
- **Evaluation context:** the project is graded by a CCS 234 panel at West Visayas State University, with a live demonstration, a 5–10 minute video and a defense (Dec 8–10, 2026). Testing happens on networks the developer owns or is allowed to monitor (at least two), with several user accounts.

## Capabilities and Constraints

**Capabilities (all in scope):**
- network discovery: local IP, network range, active devices with vendor and hostname, new-device alerts after the baseline scan;
- connectivity testing: ping a selected device; layered diagnose, on demand or automatic when an outage starts;
- network statistics: per-device and per-site average/maximum latency and packet loss, history charts (1 h / 24 h / 7 d / 30 d), outage log;
- report generation: PDF report with devices, ping results, outage log, health grade and security recommendations;
- security: risky-port check (FTP, Telnet, SMB, RDP, VNC, router admin pages), unreachable-site and unknown-device alerts, health grade (A–F) with an explanation of every deduction;
- multi-user: Circles, roles, invites, push alerts, remote commands from the app to the agent.

**Constraints:**
- **Language:** English only for this project. Write copy plainly so it can be translated later.
- **Explanations:** plain language first, technical detail on tap. Every result leads with what it means for the user ("Your internet provider is down"), and a tap reveals the layer, the test and the measurements (for example, "ICMP echo to 1.1.1.1: 0 of 3 replies").
- **Terminology:** a group is a **Circle**; people in it are **members**; each monitored network is a **site**; the Windows program is the **agent**. UI copy never says "family" as the default.
- **Ethics:** the agent only scans the subnet it's on, asks for consent at pairing ("Only monitor networks you own or are authorized to monitor"), and checks a short list of well-known ports.
- **Deadline and scope:** solo developer; final submission Dec 4, 2026. If time runs short, the web build and the phone-side test are cut first.
- **Hosting:** free tiers (Render, Neon, Expo/EAS, Firebase); the agent `.exe` is unsigned, so Windows SmartScreen shows a warning.

**Undecided:**
- the exact visual design (to be recorded in DESIGN.md);
- whether the agent gets a small Windows status window (optional in the plan).

## Brand Commitments

- **Name:** KinLAN, from "kin on the LAN". Written with a capital *LAN* in text; `kinlan` in code, packages and URLs.
- **Tagline:** *Your people, your network.*
- **Personality:** calm, trustworthy, technical but friendly; warm, like people looking out for each other, but just as at home in an office as in a living room. A monitoring product should reassure, not alarm.
- **Visual (user's choice, Nov 7):** a modern, dark-first look in yellow, orange and black with smooth animations and transitions. Yellow is the brand and selection color only; status keeps its own colors (green, orange, red) with an icon and a word.
- **Brand (Nov 7):** the identity comes from kin (people) and LAN (the router's lights): a five-light arc mark, a kin/LAN wordmark, silkscreen labels, a perforated texture on two surfaces, devices that belong to people, and a calm voice that names the person or place. Full system: `docs/design/brand.md`.
- **Defense line:** "KinLAN means kin on the LAN: anyone who shares a network and watches over it together."

## Evidence on Hand

- No real users, testimonials, case studies, metrics or screenshots exist yet. Don't invent any: no fake reviews, user counts, uptime figures or customer logos.
- Real evidence will come from the test plan (`docs/KinLAN_Technical_Plan.md`, Section 9): discovery accuracy against router client lists, latency accuracy against Windows `ping`, Wireshark captures, outage tests, and a System Usability Scale survey with 5 participants. Use those results, once measured, as the only performance claims.
- Design and architecture drafts: `docs/diagrams/chapter2_diagrams.md`.

## Product Principles

1. **Say where, not just what.** Every problem the app reports points to a location (device, Wi-Fi, router, provider, DNS, firewall) and a next step.
2. **Serve the caretaker without losing the members.** Depth and control for the person who fixes things; a calm, simple status for everyone else.
3. **Plain words first, proof on demand.** Lead with meaning; keep the protocols, layers and numbers one tap away, never hidden and never in the way.
4. **Calm by default.** Alert only when something needs attention, never twice for the same thing, and always say when it's resolved.
5. **Honest numbers.** Show measured values with their time and source; label stale data; never fill gaps with guesses.

## Accessibility & Inclusion

- **Status is never conveyed by color alone:** every status pairs a color with an icon and a word (for example "Healthy", "Down"), because some users are colorblind.
- **Contrast:** text at least 4.5:1, icons and large text at least 3:1, in light and dark themes.
- **Touch targets:** at least 48 × 48 dp.
- **Text size:** layouts must still work when the phone's text size is enlarged.
- **Motion:** smooth and purposeful (lights igniting, cards rising, numbers counting up), never decorative loops on information the user must read; the phone's Reduce Motion setting turns every movement into a short fade and stops all loops.
- **Screen readers:** icon-only buttons have accessibility labels; live status changes are announced.
