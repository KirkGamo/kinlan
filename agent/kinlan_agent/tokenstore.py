"""Where the agent keeps its token (plan, Section 3.1).

The token is encrypted with Windows DPAPI in **machine scope**, so the agent running as
SYSTEM at boot can read a token saved while an administrator ran ``pair``. Per-user
Credential Manager couldn't do that. When run elevated, the file's permissions are also
narrowed to SYSTEM and Administrators.
"""

from __future__ import annotations

import ctypes
import subprocess
import sys
from pathlib import Path

from kinlan_agent.config import home_dir

CRYPTPROTECT_LOCAL_MACHINE = 0x4
_DESCRIPTION = "KinLAN agent token"
_SYSTEM_SID, _ADMINS_SID = "*S-1-5-18", "*S-1-5-32-544"


def token_path() -> Path:
    return home_dir() / "agent.token"


def _protect(data: bytes) -> bytes:
    if sys.platform != "win32":  # development on other systems only; the agent ships for Windows
        return data
    import win32crypt

    return win32crypt.CryptProtectData(
        data, _DESCRIPTION, None, None, None, CRYPTPROTECT_LOCAL_MACHINE
    )


def _unprotect(data: bytes) -> bytes:
    if sys.platform != "win32":
        return data
    import win32crypt

    return win32crypt.CryptUnprotectData(data, None, None, None, CRYPTPROTECT_LOCAL_MACHINE)[1]


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False


def _restrict(path: Path) -> None:
    """Only SYSTEM and Administrators may read the file (needs an elevated prompt)."""
    if sys.platform == "win32" and is_admin():
        subprocess.run(
            [
                "icacls",
                str(path),
                "/inheritance:r",
                "/grant:r",
                f"{_SYSTEM_SID}:F",
                f"{_ADMINS_SID}:F",
            ],
            check=False,
            capture_output=True,
        )


def save_token(token: str, path: Path | None = None) -> Path:
    path = path or token_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_protect(token.encode()))
    _restrict(path)
    return path


def load_token(path: Path | None = None) -> str | None:
    """The saved token, or None if there isn't one or it can't be decrypted."""
    path = path or token_path()
    try:
        return _unprotect(path.read_bytes()).decode()
    except (OSError, UnicodeDecodeError):
        return None
    except Exception:  # pywintypes.error: wrong machine, damaged file
        return None


def delete_token(path: Path | None = None) -> None:
    (path or token_path()).unlink(missing_ok=True)
