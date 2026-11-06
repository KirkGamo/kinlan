"""MAC address -> manufacturer, from the bundled IEEE OUI list (kinlan_agent/data/oui.txt).

The list is the public IEEE MA-L registry in ``OUI:Vendor`` form, taken from the copy
bundled with the mac-vendor-lookup package (0.1.15, MIT). Refresh it from
https://standards-oui.ieee.org/oui/oui.txt when needed.

The first three bytes of a MAC address (the OUI) identify the manufacturer. Phones and
laptops often use a *randomized* MAC per Wi-Fi network instead; those have the
"locally administered" bit set and no manufacturer, so they're labeled separately.
"""

from __future__ import annotations

from functools import lru_cache
from importlib import resources

PRIVATE_ADDRESS = "Private address"  # label for randomized (locally administered) MACs


@lru_cache(maxsize=1)
def _table() -> dict[str, str]:
    """Load ``OUI:Vendor`` lines into a dict keyed by upper-case 6-hex-digit OUI."""
    text = resources.files("kinlan_agent").joinpath("data/oui.txt").read_text(encoding="utf-8")
    table: dict[str, str] = {}
    for line in text.splitlines():
        oui, sep, vendor = line.partition(":")
        if sep and len(oui) == 6:
            table[oui.upper()] = vendor.strip()
    return table


def is_randomized(mac: str) -> bool:
    """True if the MAC is locally administered (bit 1 of the first byte is set).

    That's how Android, iOS and Windows mark per-network random addresses.
    """
    first_byte = int(mac.replace(":", "").replace("-", "")[:2], 16)
    return bool(first_byte & 0b10)


def lookup(mac: str) -> str | None:
    """Manufacturer for ``mac`` (any common format), ``PRIVATE_ADDRESS``, or None if unknown."""
    digits = "".join(ch for ch in mac if ch.isalnum()).upper()
    if len(digits) != 12:
        return None
    if is_randomized(digits):
        return PRIVATE_ADDRESS
    return _table().get(digits[:6])
