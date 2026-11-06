# Wireshark validation: discovery and diagnose (Nov 7, 2026)

Evidence for Chapter 4 (Results and Testing) and issue #15: every network test the agent performs shows up on the wire as the expected packets.

## Setup

| Item | Value |
|---|---|
| Network | Home Wi-Fi, 192.168.1.0/24, gateway 192.168.1.1 |
| Capture | `tshark` 4.6.9 on the Wi-Fi adapter (Npcap), no administrator rights |
| Capture filter | `arp or icmp or udp port 53 or tcp port 443` |
| Agent actions | One device scan (Scapy ARP), then one full diagnose with internet targets 8.8.8.8 and 9.9.9.9 |
| Raw captures | `course/evidence/2026-11-07_scan_and_diagnose.pcapng` and `2026-11-07_scan_after_fix.pcapng` (kept out of the public repository because they contain the household's MAC addresses) |

## Results

| Agent action | Layer | Wireshark display filter | Observed |
|---|---|---|---|
| Device scan (ARP sweep) | 2, data link | `arp.opcode==1 && eth.src==<this PC>` | 3 passes 2 s apart. The 5 devices that answered were asked once; the 250 silent addresses were asked 3 times (one pass plus two resends). |
| Device replies | 2, data link | `arp.opcode==2 && eth.dst==<this PC>` | 6 replies from the 5 other devices; the agent lists them plus this PC (6 devices on this run) |
| Diagnose step 2: router ARP | 2, data link | `arp.dst.proto_ipv4==192.168.1.1` | Windows SendARP request and reply for the gateway, just before the pings |
| Diagnose step 3: router ping | 3, network (LAN) | `icmp && ip.addr==192.168.1.1` | 3 echo requests, 3 replies |
| Diagnose step 4: internet ping | 3, network (WAN) | `icmp && (ip.addr==8.8.8.8 \|\| ip.addr==9.9.9.9)` | 8.8.8.8: 3 requests, 3 replies. 9.9.9.9: 3 requests, 3 replies |
| Diagnose step 5: DNS lookup | 7, application | `dns.qry.name=="example.com"` | Query from 192.168.1.13 to the PC's first DNS server (8.8.8.8); answer 60 ms later with 2 A records |
| Diagnose step 6: TCP 443 | 4, transport | `tcp.port==443 && ip.addr==8.8.8.8 && tcp.flags.syn==1` | One SYN and one SYN-ACK: the TCP handshake the agent times |
| Diagnose step 6: HTTPS | 7, application | `tls.handshake.extensions_server_name=="www.google.com"` | TLS ClientHello for `www.google.com` (the `generate_204` probe) |

Other applications on the PC also made TLS connections during the capture. A packet capture can't attribute traffic to a program, so only the agent's own probe (`www.google.com`) is cited above.

## Issue found and fixed

The first capture showed the ARP sweep also asking **192.168.1.0 and 192.168.1.255** (the network and broadcast addresses), 3 times each. Those addresses can never answer, so the requests were wasted. The agent now asks only host addresses (`discovery.arp_targets()`).

| Capture | ARP requests sent | Requests to .0 / .255 | Devices found |
|---|---|---|---|
| Before the fix | 756 | 6 | 6 |
| After the fix | 750 | 0 | 7 |

The device count differs because phones join and leave the network between runs; both runs found every device that was online.

## Taking the screenshots for the report

1. Open the `.pcapng` file from `course/evidence/` in Wireshark.
2. For each row of the Results table, paste its display filter into the filter bar and press Enter.
3. Take a screenshot of the packet list, with the packet details pane expanded on one request and its reply.
4. Annotate it: the protocol, the layer, and which agent action produced it. Blur MAC addresses and device names before putting screenshots in the report or slides.
