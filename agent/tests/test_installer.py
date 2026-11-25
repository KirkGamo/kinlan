"""The startup task (#91) with a fake Task Scheduler: nothing is registered on this PC."""

import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from kinlan_agent import config, installer

NS = {"t": "http://schemas.microsoft.com/windows/2004/02/mit/task"}


class FakeScheduler:
    """Records schtasks calls and answers like Windows."""

    def __init__(self, installed_state=None, refuse_create=False):
        self.calls = []
        self.state = installed_state
        self.refuse_create = refuse_create
        self.task = None  # the XML definition given to /Create

    def __call__(self, args):
        self.calls.append(args)
        verb = args[0]
        if verb == "/Create":
            self.task = ET.fromstring(Path(args[args.index("/XML") + 1]).read_text("utf-16"))
            if self.refuse_create:
                return subprocess.CompletedProcess(args, 1, "", "ERROR: Access is denied.")
            self.state = "Ready"
        elif verb == "/Run":
            self.state = "Running"
        elif verb == "/Query":
            if self.state is None:
                return subprocess.CompletedProcess(args, 1, "", "ERROR: not found")
            return subprocess.CompletedProcess(
                args, 0, '"\\KinLAN Agent","N/A","' + self.state + '"\r\n', ""
            )
        elif verb == "/Delete":
            self.state = None
        return subprocess.CompletedProcess(args, 0, "SUCCESS", "")


@pytest.fixture
def paired(tmp_path, monkeypatch):
    monkeypatch.setenv("KINLAN_HOME", str(tmp_path))
    (tmp_path / "config.toml").write_text('agent_id = "a-1"\nsite_id = "s-1"\n', encoding="utf-8")
    assert config.load().paired
    return tmp_path


def find(task, path):
    return task.findtext(path, namespaces=NS)


def test_install_registers_a_system_task_at_startup_and_starts_it(paired):
    tasks, said = FakeScheduler(), []
    assert installer.install(said.append, tasks, is_admin=lambda: True, home=paired) == 0
    assert tasks.calls[0][:3] == ["/Create", "/TN", "KinLAN Agent"]
    # An XML definition, not /SC ONSTARTUP, which some Windows 11 builds reject.
    assert "/SC" not in tasks.calls[0]
    task = tasks.task
    assert task.find("t:Triggers/t:BootTrigger", NS) is not None
    assert find(task, "t:Principals/t:Principal/t:UserId") == "S-1-5-18"  # SYSTEM
    assert find(task, "t:Principals/t:Principal/t:RunLevel") == "HighestAvailable"
    assert tasks.calls[1] == ["/Run", "/TN", "KinLAN Agent"]
    assert "running now" in said[0]


def test_the_task_keeps_running_on_a_laptop(paired):
    tasks = FakeScheduler()
    installer.install(lambda _: None, tasks, is_admin=lambda: True, home=paired)
    settings = "t:Settings/t:"
    assert find(tasks.task, settings + "DisallowStartIfOnBatteries") == "false"
    assert find(tasks.task, settings + "StopIfGoingOnBatteries") == "false"
    assert find(tasks.task, settings + "ExecutionTimeLimit") == "PT0S"  # the default is 72 h
    assert find(tasks.task, settings + "MultipleInstancesPolicy") == "IgnoreNew"
    assert find(tasks.task, settings + "RestartOnFailure/t:Interval") == "PT1M"


def test_from_source_the_task_runs_a_small_launcher(paired):
    tasks = FakeScheduler()
    installer.install(lambda _: None, tasks, is_admin=lambda: True, home=paired)
    script = paired / "run-agent.cmd"
    assert find(tasks.task, "t:Actions/t:Exec/t:Command") == str(script)
    assert find(tasks.task, "t:Actions/t:Exec/t:Arguments") is None
    text = script.read_text(encoding="utf-8")
    assert "-m kinlan_agent run" in text and sys.executable in text


def test_the_packaged_exe_copies_itself_next_to_its_data(paired, tmp_path_factory, monkeypatch):
    download = tmp_path_factory.mktemp("Downloads") / "KinLAN-Agent.exe"
    download.write_bytes(b"MZ fake exe")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(download))
    tasks = FakeScheduler()
    installer.install(lambda _: None, tasks, is_admin=lambda: True, home=paired)
    installed = paired / "KinLAN-Agent.exe"
    assert installed.read_bytes() == b"MZ fake exe"  # the download can be deleted afterwards
    assert find(tasks.task, "t:Actions/t:Exec/t:Command") == str(installed)
    assert find(tasks.task, "t:Actions/t:Exec/t:Arguments") == "run"


def test_paths_are_escaped_in_the_task(tmp_path):
    odd = tmp_path / "Tom & Jerry's <PC>" / "KinLAN-Agent.exe"
    task = ET.fromstring(installer.task_xml(odd, "run").split("?>", 1)[1])
    assert find(task, "t:Actions/t:Exec/t:Command") == str(odd)


def test_install_needs_an_administrator_and_a_pairing(paired, tmp_path, monkeypatch):
    tasks, said = FakeScheduler(), []
    assert installer.install(said.append, tasks, is_admin=lambda: False, home=paired) == 1
    assert "administrator" in said[0] and tasks.calls == []
    monkeypatch.setenv("KINLAN_HOME", str(tmp_path / "unpaired"))
    assert installer.install(said.append, tasks, is_admin=lambda: True) == 1
    assert "Pair this PC first" in said[-1] and tasks.calls == []


def test_a_refused_task_is_reported(paired):
    said = []
    tasks = FakeScheduler(refuse_create=True)
    assert installer.install(said.append, tasks, is_admin=lambda: True, home=paired) == 1
    assert "Access is denied" in said[0]


def test_uninstall_stops_and_removes_the_task(paired):
    tasks, said = FakeScheduler(installed_state="Running"), []
    assert installer.task_state(tasks) == "Running"
    assert installer.uninstall(said.append, tasks, is_admin=lambda: True) == 0
    assert [c[0] for c in tasks.calls] == ["/Query", "/Query", "/End", "/Delete"]
    assert installer.task_state(tasks) is None
    assert installer.uninstall(said.append, tasks, is_admin=lambda: True) == 0
    assert "isn't installed" in said[-1]


@pytest.mark.skipif(sys.platform != "win32", reason="a Windows mutex")
def test_only_one_agent_runs_at_a_time():
    name = r"Local\KinLANAgentTest"
    first = installer.single_instance(name)
    with pytest.raises(installer.AlreadyRunning):
        installer.single_instance(name)
    import ctypes

    ctypes.WinDLL("kernel32").CloseHandle(ctypes.c_void_p(first))
    installer.single_instance(name)  # free again once the first agent is gone
