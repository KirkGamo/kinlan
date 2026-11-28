"""The agent's settings file, ``%ProgramData%\\KinLAN\\config.toml`` (plan, Section 3.7).

Every value has a default, so a missing or partly written file never crashes the agent.
``KINLAN_HOME`` moves the whole folder (config, token, buffer, logs), which tests and
development use to stay out of ProgramData.

One PC can monitor several sites, one per network (a laptop at home and in a lab; #94). The
first site's pairing is at the top of the file, as before; each further site is a
``[[sites]]`` table with its own token (``agent-<site>.token``) and buffer
(``buffer-<site>.db``). :func:`site_configs` gives one :class:`AgentConfig` per site.
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError

from kinlan_agent.monitor import DEFAULT_INTERNET_CANDIDATES

DEFAULT_API_URL = "https://kinlan-api.onrender.com"


def home_dir() -> Path:
    override = os.environ.get("KINLAN_HOME")
    if override:
        return Path(override)
    return Path(os.environ.get("PROGRAMDATA", Path.home())) / "KinLAN"


def config_path() -> Path:
    return home_dir() / "config.toml"


class SiteEntry(BaseModel):
    """A further site this PC is paired with, monitored while it's on that site's network."""

    agent_id: str
    site_id: str
    site_name: str | None = None
    home_gateway_mac: str | None = None
    home_network: str | None = None


SITE_FIELDS = tuple(SiteEntry.model_fields)


class AgentConfig(BaseModel):
    api_url: str = DEFAULT_API_URL
    agent_id: str | None = None
    site_id: str | None = None
    site_name: str | None = None
    # The site's network (homenet.py): its router's MAC, and the subnet for messages.
    home_gateway_mac: str | None = None
    home_network: str | None = None
    monitor_interval_s: float = Field(10, ge=1)
    upload_interval_s: float = Field(30, ge=1)
    scan_interval_s: float = Field(300, ge=30)
    # Name lookup and HTTPS, so the app's DNS and Web lights are live (#96).
    web_check_interval_s: float = Field(300, ge=60)
    internet_targets: list[str] = Field(default_factory=lambda: list(DEFAULT_INTERNET_CANDIDATES))
    port_check_time: str = "03:00"
    max_scan_prefix: int = Field(22, ge=16, le=30)
    log_level: str = "INFO"
    sites: list[SiteEntry] = Field(default_factory=list)
    # Which pairing a per-site config is: None for the first site, else its site id. Not saved.
    slot: str | None = Field(None, exclude=True)

    @property
    def paired(self) -> bool:
        return bool(self.agent_id)


def site_configs(settings: AgentConfig) -> list[AgentConfig]:
    """One config per paired site, sharing the file's other settings: the first site, then
    each ``[[sites]]`` entry."""
    configs = [settings.model_copy(update={"sites": []})] if settings.paired else []
    for entry in settings.sites:
        configs.append(
            settings.model_copy(update={**entry.model_dump(), "sites": [], "slot": entry.site_id})
        )
    return configs


def load_site(site_id: str | None) -> AgentConfig | None:
    """The current config of one site, read again from the file (setup may have changed it)."""
    return next((c for c in site_configs(load()) if c.site_id == site_id), None)


def token_file(site: AgentConfig) -> Path:
    return home_dir() / ("agent.token" if site.slot is None else f"agent-{site.slot}.token")


def buffer_file(site: AgentConfig) -> Path:
    return home_dir() / ("buffer.db" if site.slot is None else f"buffer-{site.slot}.db")


def load(path: Path | None = None) -> AgentConfig:
    """Read the file; unknown keys are ignored and bad values fall back to defaults."""
    path = path or config_path()
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return AgentConfig()
    known = {k: v for k, v in data.items() if k in AgentConfig.model_fields}
    try:
        return AgentConfig(**known)
    except ValidationError:
        good = {}
        for key, value in known.items():
            try:
                AgentConfig(**{key: value})
                good[key] = value
            except ValidationError:
                continue
        return AgentConfig(**good)


def read_error(path: Path | None = None) -> str | None:
    """Why the file can't be read (it exists but isn't valid TOML), or None if it's fine."""
    path = path or config_path()
    try:
        tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return f"{path} can't be read: {exc}"
    return None


def _toml_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return repr(value)
    if isinstance(value, list):
        return "[" + ", ".join(_toml_value(v) for v in value) + "]"
    text = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{text}"'


def save(config: AgentConfig, path: Path | None = None) -> Path:
    """Write every setting (skipping unset ones), replacing the file in one step."""
    path = path or config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# KinLAN Agent settings. Written by `kinlan-agent pair`; safe to edit."]
    for key, value in config.model_dump(exclude={"sites"}).items():
        if value is not None:
            lines.append(f"{key} = {_toml_value(value)}")
    for entry in config.sites:  # tables come after every top-level key in TOML
        lines.append("\n[[sites]]")
        for key, value in entry.model_dump().items():
            if value is not None:
                lines.append(f"{key} = {_toml_value(value)}")
    tmp = path.with_suffix(".tmp")
    tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    tmp.replace(path)
    return path
