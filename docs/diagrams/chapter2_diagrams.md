# KinLAN — Chapter 2 diagram drafts

Drafts for Chapter 2 (System Design) of the final report and for the Nov 17 progress report. They're written in Mermaid, so they render in VS Code (Markdown preview with a Mermaid extension) and on GitHub. Redraw the final versions in draw.io for the report, following the same structure.

Source: `docs/KinLAN_Technical_Plan.md`, Sections 1, 3, 4 and 5.

---

## 2.1 Network architecture

```mermaid
flowchart LR
    subgraph LAN["Local network (one per site)"]
        direction TB
        D1["Devices<br/>(phones, PCs, TVs, IoT)"]
        GW["Router / default gateway"]
        AG["KinLAN Agent<br/>Python 3.12 on a Windows PC<br/>discovery · monitor · diagnose · port check<br/>SQLite offline buffer"]
        AG -- "ARP (layer 2)<br/>ICMP echo (layer 3)<br/>TCP connect (layer 4)" --> D1
        AG -- "ICMP echo" --> GW
    end

    subgraph CLOUD["Cloud"]
        direction TB
        API["KinLAN API<br/>FastAPI on Render<br/>auth · ingest · alerts · reports"]
        DB[("PostgreSQL<br/>Neon")]
        API -- "SQL over TLS" --> DB
    end

    subgraph CLIENTS["Circle members"]
        direction TB
        APP["KinLAN app<br/>Android APK"]
        WEB["KinLAN web<br/>static site"]
    end

    PUSH["Expo Push → FCM"]
    NET(("Internet<br/>1.1.1.1 · 8.8.8.8 · DNS"))

    GW --- NET
    AG -- "HTTPS POST /agent/ingest (every 30 s)" --> API
    API -- "HTTPS long-poll: commands" --> AG
    APP <-- "HTTPS REST + JWT" --> API
    WEB <-- "HTTPS REST + JWT" --> API
    API -- "alerts" --> PUSH --> APP
```

**Key point for the defense:** the agent only makes *outbound* HTTPS connections, so it works behind any home router (NAT) with no port forwarding.

---

## 2.2 Use case diagram

Mermaid has no UML use-case shape, so this draft uses a flowchart: rectangles are actors and rounded boxes are use cases. In draw.io, use the UML "Actor" and "Use Case" shapes.

```mermaid
flowchart LR
    O["👤 Owner"]
    A["👤 Admin"]
    V["👤 Viewer"]
    AG["🖥️ Agent<br/>(system actor)"]
    SC["⏱️ Scheduler<br/>(system actor)"]

    subgraph SYS["KinLAN"]
        direction TB
        UC1(["Sign up / sign in"])
        UC2(["View dashboard, devices,<br/>charts and alerts"])
        UC3(["Export PDF report"])
        UC4(["Run scan, ping test,<br/>diagnose or port check"])
        UC5(["Rename / trust devices,<br/>acknowledge alerts"])
        UC6(["Create site and<br/>pairing code"])
        UC7(["Create Circle, invite and<br/>manage members"])
        UC8(["Join a Circle<br/>with invite code"])
        UC9(["Pair with a site"])
        UC10(["Upload measurements<br/>and heartbeat"])
        UC11(["Execute remote commands"])
        UC12(["Detect unreachable sites,<br/>roll up data, apply retention"])
        UC13(["Receive push alerts"])
    end

    V --> UC1 & UC2 & UC3 & UC8 & UC13
    A --> UC1 & UC2 & UC3 & UC4 & UC5 & UC6 & UC8 & UC13
    O --> UC1 & UC2 & UC3 & UC4 & UC5 & UC6 & UC7 & UC13
    AG --> UC9 & UC10 & UC11
    SC --> UC12
```

Roles are cumulative: an Admin can do everything a Viewer can, and an Owner everything an Admin can (technical plan, Section 4.2).

---

## 2.3 Flowchart: agent main loop

```mermaid
flowchart TD
    S([Start agent]) --> C{Paired?}
    C -- No --> P["Ask for 6-digit pairing code<br/>Show consent prompt"] --> PR["POST /agent/pair<br/>Save encrypted token"] --> B["Baseline scan<br/>(no alerts)"] --> L
    C -- Yes --> L["Start periodic tasks"]

    L --> M["Every 10 s: ping gateway and 1.1.1.1"]
    L --> SC["Every 5 min: ARP scan"]
    L --> U["Every 30 s: upload outbox"]
    L --> CP["Continuously: long-poll for commands"]

    M --> F{3 failures in a row<br/>and 8.8.8.8 fails?}
    F -- No --> W1["Write sample to SQLite outbox"]
    F -- Yes --> G{Gateway OK?}
    G -- Yes --> O1["Open outage: cause = ISP"]
    G -- No --> O2["Open outage: cause = LAN"]
    O1 --> DG["Run diagnose automatically"]
    O2 --> DG
    DG --> W1

    U --> R{Upload succeeded?}
    R -- "Yes (2xx)" --> DEL["Delete sent rows<br/>Backlog left? Send next batch"]
    R -- No --> BO["Back off 5 s → 5 min"] --> U

    CP --> CMD{Command received?}
    CMD -- Yes --> EX["Run scan / ping_test / diagnose / port_check"] --> RES["POST result"]
    CMD -- No --> CP
```

---

## 2.4 Flowchart: layered diagnose

```mermaid
flowchart TD
    S([Diagnose]) --> T1{"1. Adapter up with a<br/>non-APIPA IPv4 address?"}
    T1 -- No --> R1["Root cause: physical / data link<br/>Cable, Wi-Fi or DHCP"]
    T1 -- Yes --> T2{"2. Gateway ARP resolves?"}
    T2 -- No --> R2["Root cause: data link<br/>Wrong Wi-Fi or VLAN"]
    T2 -- Yes --> T3{"3. Gateway answers ping?"}
    T3 -- No --> R3["Root cause: network (LAN)<br/>Router down or weak Wi-Fi"]
    T3 -- Yes --> T4{"4. 1.1.1.1 and 8.8.8.8<br/>answer ping?"}
    T4 -- No --> R4["Root cause: network (WAN)<br/>ISP outage"]
    T4 -- Yes --> T5{"5. DNS lookup works?"}
    T5 -- No --> R5["Root cause: application (DNS)<br/>Suggest 1.1.1.1"]
    T5 -- Yes --> T6{"6. TCP 443 + HTTPS<br/>request work?"}
    T6 -- No --> R6["Root cause: transport / application<br/>Firewall or captive portal"]
    T6 -- Yes --> OK["All layers healthy"]
```

The diagnosis stops at the first failing step; later steps are reported as *skipped*.

---

## 2.5 Sequence: outage detection and recovery

```mermaid
sequenceDiagram
    autonumber
    participant AG as Agent
    participant BUF as SQLite buffer
    participant API as KinLAN API
    participant SC as Scheduler
    participant APP as App (Circle members)

    AG->>API: Upload batch (heartbeat) every 30 s
    Note over AG: Internet goes down
    AG->>AG: 3 failed pings + 8.8.8.8 fails
    AG->>BUF: Open outage (start time, cause), keep sampling
    AG--xAPI: Uploads fail (back off)
    SC->>API: No heartbeat for > 120 s
    API->>APP: Push: "Site is unreachable"
    Note over AG: Internet comes back
    AG->>BUF: Close outage (end time)
    AG->>API: Upload backlog, oldest first
    API->>API: Store samples, close outage with exact duration
    API->>APP: Push: "Back online after 4 min 12 s (ISP outage)"
```

---

## 2.6 Entity-relationship diagram (core tables)

```mermaid
erDiagram
    USERS ||--o{ MEMBERSHIPS : has
    CIRCLES ||--o{ MEMBERSHIPS : has
    CIRCLES ||--o{ INVITES : issues
    CIRCLES ||--o{ SITES : owns
    SITES ||--o{ AGENTS : "paired with"
    SITES ||--o{ DEVICES : contains
    SITES ||--o{ PING_SAMPLES : records
    SITES ||--o{ PING_HOURLY : "rolled up into"
    SITES ||--o{ OUTAGES : logs
    SITES ||--o{ ALERTS : raises
    SITES ||--o{ COMMANDS : queues
    SITES ||--o{ REPORTS : generates
    DEVICES ||--o{ PING_TESTS : "tested by"
    DEVICES ||--o{ PORT_FINDINGS : has
    USERS ||--o{ PUSH_TOKENS : registers

    USERS {
        uuid id PK
        string email UK
        string password_hash
        string display_name
    }
    CIRCLES {
        uuid id PK
        string name
        uuid created_by FK
    }
    MEMBERSHIPS {
        uuid circle_id PK
        uuid user_id PK
        enum role "owner | admin | viewer"
    }
    SITES {
        uuid id PK
        uuid circle_id FK
        string name
        enum status
        cidr cidr
        inet gateway_ip
    }
    AGENTS {
        uuid id PK
        uuid site_id FK
        string token_hash UK
        string version
    }
    DEVICES {
        uuid id PK
        uuid site_id FK
        string mac
        inet ip
        string vendor
        bool trusted
        bool baseline
    }
    PING_SAMPLES {
        bigint id PK
        uuid site_id FK
        enum target "gateway | internet"
        timestamptz ts
        float rtt_ms
        bool ok
    }
    OUTAGES {
        uuid id PK
        uuid site_id FK
        timestamptz started_at
        timestamptz ended_at
        enum cause "isp | lan | unknown"
    }
    ALERTS {
        uuid id PK
        uuid site_id FK
        string type
        enum severity
    }
```

The full column list is in the technical plan, Section 5.2. `invites`, `pairing_codes`, `refresh_tokens`, `alert_settings`, `ingest_batches`, `commands`, `reports`, `ping_hourly`, `ping_tests`, `port_findings` and `push_tokens` are shown as relationships only, to keep the diagram readable.
