"""Discovery accuracy (plan §9): one agent scan, as the agent runs it, saved for comparison with
the router's DHCP client list taken at the same moment.

Run from agent/ with PYTHONPATH=. : python ../docs/test-results/scripts/discovery_snapshot.py out.json
"""

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from kinlan_agent import discovery, netinfo

info = netinfo.get_netinfo()
started = datetime.now(UTC)
result = discovery.scan(info)
out = {
    "at": started.isoformat(),
    "network": str(info.network),
    "gateway": info.gateway,
    "method": result.method,
    "duration_ms": result.duration_ms,
    "errors": result.errors,
    "devices": [d.to_dict() for d in result.devices],
}
Path(sys.argv[1]).write_text(json.dumps(out, indent=1))
print(f"{started:%H:%M:%S} UTC {info.network} via {result.method}: "
      f"{len(result.devices)} devices in {result.duration_ms} ms")
for d in result.devices:
    print(f"  {d.ip:<15} {d.mac}  {d.hostname or '':<24} {d.vendor or ''}")
