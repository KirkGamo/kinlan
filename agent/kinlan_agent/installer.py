"""Start the agent at boot, without anyone signing in (plan, Sections 3.1 and 3.8).

``install`` copies the agent next to its data in ``%ProgramData%\\KinLAN`` and registers a Task
Scheduler task that runs it as SYSTEM with the highest privileges at startup (raw sockets for
ARP and ping need them, and SYSTEM can read the machine-scope DPAPI token). It also starts the
task at once, so monitoring begins without a reboot. ``uninstall`` stops and removes the task;
the pairing, buffer and logs stay, so installing again resumes where it left off.

Only one agent runs at a time (a machine-wide mutex), so ``run`` by hand while the task is
running exits instead of uploading everything twice.
"""

from __future__ import annotations

import csv
import io
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from kinlan_agent.config import home_dir

TASK = "KinLAN Agent"
EXE_NAME = "KinLAN-Agent.exe"
MUTEX = "Global\\KinLANAgent"

Runner = Callable[[list[str]], subprocess.CompletedProcess]


def _schtasks(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(["schtasks", *args], capture_output=True, text=True)


def frozen() -> bool:
    """True when running as the packaged KinLAN-Agent.exe (PyInstaller)."""
    return bool(getattr(sys, "frozen", False))


def launcher(home: Path | None = None) -> str:
    """The command the startup task runs. The packaged exe is copied into the data folder (so
    the download can be deleted); a source checkout gets a small .cmd that runs the package."""
    home = home or home_dir()
    if frozen():
        target = home / EXE_NAME
        source = Path(sys.executable)
        if source.resolve() != target.resolve():
            home.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        return f'"{target}" run'
    package_dir = Path(__file__).resolve().parent.parent
    script = home / "run-agent.cmd"
    home.mkdir(parents=True, exist_ok=True)
    script.write_text(
        f'@echo off\r\ncd /d "{package_dir}"\r\n"{sys.executable}" -m kinlan_agent run\r\n',
        encoding="utf-8",
    )
    return f'"{script}"'


def install(
    say: Callable[[str], None] = print,
    run: Runner = _schtasks,
    is_admin: Callable[[], bool] | None = None,
    home: Path | None = None,
) -> int:
    from kinlan_agent import config, tokenstore

    admin = (is_admin or tokenstore.is_admin)()
    if not admin:
        say("Installing needs an administrator terminal. Right-click PowerShell, choose "
            "\"Run as administrator\", and run this again.")
        return 1
    if not config.load().paired:
        say("Pair this PC first: kinlan-agent pair")
        return 1
    command = launcher(home)
    created = run(["/Create", "/TN", TASK, "/TR", command, "/SC", "ONSTARTUP",
                   "/RU", "SYSTEM", "/RL", "HIGHEST", "/F"])
    if created.returncode != 0:
        say(f"Windows refused the startup task: {(created.stderr or created.stdout).strip()}")
        return 1
    started = run(["/Run", "/TN", TASK])
    now = ", and it's running now." if started.returncode == 0 else "; restart the PC to start it."
    say("Installed. The KinLAN Agent now starts by itself when this PC starts" + now)
    say(f"Its log is in {(home or home_dir()) / 'logs'}. To remove it: kinlan-agent uninstall")
    return 0


def uninstall(
    say: Callable[[str], None] = print,
    run: Runner = _schtasks,
    is_admin: Callable[[], bool] | None = None,
) -> int:
    from kinlan_agent import tokenstore

    if not (is_admin or tokenstore.is_admin)():
        say("Removing the startup task needs an administrator terminal.")
        return 1
    if task_state(run) is None:
        say("The KinLAN Agent isn't installed as a startup task.")
        return 0
    run(["/End", "/TN", TASK])
    deleted = run(["/Delete", "/TN", TASK, "/F"])
    if deleted.returncode != 0:
        say(f"Windows refused to remove the task: {(deleted.stderr or deleted.stdout).strip()}")
        return 1
    say("Removed. The agent no longer starts at boot; your pairing and history are kept.")
    return 0


def task_state(run: Runner = _schtasks) -> str | None:
    """The task's status ("Running", "Ready", "Disabled"), or None if it isn't installed."""
    result = run(["/Query", "/TN", TASK, "/FO", "CSV", "/NH"])
    if result.returncode != 0:
        return None
    for row in csv.reader(io.StringIO(result.stdout)):
        if len(row) >= 3:
            return row[2].strip() or None
    return None


class AlreadyRunning(RuntimeError):
    pass


def single_instance(name: str = MUTEX):
    """Hold a machine-wide mutex for as long as the returned handle lives; raise AlreadyRunning
    if another agent holds it. A no-op outside Windows (tests, development elsewhere)."""
    if sys.platform != "win32":
        return None
    import ctypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    handle = kernel32.CreateMutexW(None, True, name)
    if not handle:  # a non-admin terminal may not create a Global name: run without the guard
        return None
    if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS
        kernel32.CloseHandle(ctypes.c_void_p(handle))
        raise AlreadyRunning
    return handle
