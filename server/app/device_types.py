"""Guess a device's type from its manufacturer and hostname, for its icon. Users can change it."""

from app.models import DeviceType

_HOSTNAME_HINTS: tuple[tuple[tuple[str, ...], DeviceType], ...] = (
    (("iphone", "android", "galaxy", "pixel", "redmi", "oppo", "vivo", "phone"), DeviceType.phone),
    (("ipad", "tablet", "tab-"), DeviceType.phone),
    (("laptop", "macbook", "notebook", "thinkpad"), DeviceType.laptop),
    (("desktop", "-pc", "pc-", "workstation", "imac"), DeviceType.computer),
    (("tv", "chromecast", "roku", "firestick", "appletv", "bravia", "tizen"), DeviceType.tv),
    (("printer", "epson", "canon", "brother", "laserjet", "deskjet"), DeviceType.printer),
    (("router", "gateway", "modem"), DeviceType.router),
)

_VENDOR_HINTS: tuple[tuple[tuple[str, ...], DeviceType], ...] = (
    (
        (
            "apple",
            "samsung",
            "xiaomi",
            "huawei",
            "oppo",
            "vivo",
            "realme",
            "oneplus",
            "motorola",
            "google",
            "nokia",
            "transsion",
            "private address",
        ),
        DeviceType.phone,
    ),
    (
        ("hp", "hewlett", "epson", "canon", "brother", "kyocera", "ricoh", "xerox"),
        DeviceType.printer,
    ),
    (
        (
            "tp-link",
            "cisco",
            "netgear",
            "d-link",
            "zte",
            "huawei technologies",
            "fiberhome",
            "china mobile",
            "ubiquiti",
            "mikrotik",
            "tenda",
            "asus",
        ),
        DeviceType.router,
    ),
    (("roku", "lg electronics", "sony", "tcl", "hisense", "skyworth"), DeviceType.tv),
    (
        ("intel", "dell", "lenovo", "acer", "micro-star", "gigabyte", "asrock", "realtek"),
        DeviceType.computer,
    ),
)


def infer_type(vendor: str | None, hostname: str | None, *, is_gateway: bool = False) -> DeviceType:
    if is_gateway:
        return DeviceType.router
    name = (hostname or "").lower()
    for hints, kind in _HOSTNAME_HINTS:
        if any(h in name for h in hints):
            return kind
    maker = (vendor or "").lower()
    for hints, kind in _VENDOR_HINTS:
        if any(maker.startswith(h) or f" {h}" in maker for h in hints):
            return kind
    return DeviceType.unknown
