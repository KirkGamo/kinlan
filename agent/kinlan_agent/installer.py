"""Start the agent at boot, without anyone signing in (plan, Sections 3.1 and 3.8).

``install`` copies the agent next to its data in ``%ProgramData%\\KinLAN`` and registers a Task
Scheduler task that runs it as SYSTEM with the highest privileges at startup (raw sockets for
ARP and ping need them, and SYSTEM can read the machine-scope DPAPI token). It also starts the
task at once, so monitoring begins without a reboot. ``uninstall`` stops and removes the task;
the pairing, buffer and logs stay, so installing again resumes where it left off.

The task is registered from an XML definition rather than ``/SC ONSTARTUP``: some Windows 11
builds reject that schedule type ("Invalid Schedule Type specified"), and its defaults would stop
the agent after 72 hours and never start it on battery, which matters on a laptop.

Only one agent runs at a time (a machine-wide mutex), so ``run`` by hand while the task is
running exits instead of uploading everything twice.
"""

from __future__ import annotations

import csv
import io
import os
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from xml.sax.saxutils import escape

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


def launcher(home: Path | None = None) -> tuple[Path, str]:
    """The program the startup task runs, and its arguments. The packaged exe is copied into
    the data folder (so the download can be deleted); a source checkout gets a small .cmd that
    runs the package."""
    home = home or home_dir()
    if frozen():
        target = home / EXE_NAME
        source = Path(sys.executable)
        if source.resolve() != target.resolve():
            home.mkdir(parents=True, exist_ok=True)
            _copy(source, target)
        return target, "run"
    package_dir = Path(__file__).resolve().parent.parent
    script = home / "run-agent.cmd"
    home.mkdir(parents=True, exist_ok=True)
    script.write_text(
        f'@echo off\r\ncd /d "{package_dir}"\r\n"{sys.executable}" -m kinlan_agent run\r\n',
        encoding="utf-8",
    )
    return script, ""


def _copy(source: Path, target: Path, tries: int = 20, wait_s: float = 0.5) -> None:
    """Copy the exe, waiting for a stopped agent to let go of the old one (an update)."""
    for attempt in range(tries):
        try:
            shutil.copy2(source, target)
            return
        except PermissionError:
            if attempt == tries - 1:
                raise
            time.sleep(wait_s)


def stop_agents(exe: Path, procs=None, me: int | None = None) -> int:
    """Stop every process running from ``exe`` except this one and its launcher. Ending the
    task stops only PyInstaller's launcher; the agent it started from the same exe keeps
    running and keeps the file open (seen Nov 26 updating 1.0.2). Returns how many stopped."""
    import psutil

    me = os.getpid() if me is None else me
    try:
        mine = {me} | {p.pid for p in psutil.Process(me).parents()}
    except psutil.Error:
        mine = {me}
    target = os.path.normcase(str(exe.resolve()))
    stopped = []
    for proc in psutil.process_iter(["name"]) if procs is None else procs:
        try:
            if proc.pid in mine or (proc.info.get("name") or "").lower() != EXE_NAME.lower():
                continue
            if os.path.normcase(str(Path(proc.exe()).resolve())) == target:
                proc.kill()
                stopped.append(proc)
        except (psutil.Error, OSError):
            continue
    if stopped and procs is None:
        psutil.wait_procs(stopped, timeout=5)
    return len(stopped)


def task_xml(program: Path, arguments: str) -> str:
    """The startup task: at boot, as SYSTEM with the highest privileges, on battery too, with
    no time limit, restarted every minute if it stops (it exits only on errors), one copy."""
    args = f"<Arguments>{escape(arguments)}</Arguments>" if arguments else ""
    return f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>KinLAN Agent: monitors this network for the KinLAN app.</Description>
  </RegistrationInfo>
  <Triggers>
    <BootTrigger><Enabled>true</Enabled></BootTrigger>
  </Triggers>
  <Principals>
    <Principal id="Agent">
      <UserId>S-1-5-18</UserId>
      <RunLevel>HighestAvailable</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <RestartOnFailure><Interval>PT1M</Interval><Count>999</Count></RestartOnFailure>
    <Enabled>true</Enabled>
  </Settings>
  <Actions Context="Agent">
    <Exec><Command>{escape(str(program))}</Command>{args}</Exec>
  </Actions>
</Task>
"""


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
    if task_state(run) == "Running":  # an update: stop the old agent so its exe can be replaced
        run(["/End", "/TN", TASK])
    if frozen():
        stop_agents((home or home_dir()) / EXE_NAME)
    program, arguments = launcher(home)
    with tempfile.TemporaryDirectory() as tmp:
        definition = Path(tmp) / "kinlan-agent-task.xml"
        definition.write_text(task_xml(program, arguments), encoding="utf-16")
        created = run(["/Create", "/TN", TASK, "/XML", str(definition), "/F"])
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
    if frozen():
        stop_agents(home_dir() / EXE_NAME)
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
