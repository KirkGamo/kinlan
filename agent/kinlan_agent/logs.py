r"""Logging to the console and ``%ProgramData%\KinLAN\logs\agent.log`` (5 files of 1 MB)."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from kinlan_agent.config import home_dir


def setup_logging(level: str = "INFO") -> None:
    folder = home_dir() / "logs"
    folder.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    file_handler = RotatingFileHandler(
        folder / "agent.log", maxBytes=1_000_000, backupCount=5, encoding="utf-8"
    )
    console = logging.StreamHandler()
    for handler in (file_handler, console):
        handler.setFormatter(fmt)
    root = logging.getLogger()
    root.handlers[:] = [file_handler, console]
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
