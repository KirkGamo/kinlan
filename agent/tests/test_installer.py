"""The startup task (#91) with a fake Task Scheduler: nothing is registered on this PC."""

import subprocess
import sys

import pytest

from kinlan_agent import config, installer


class FakeScheduler:
    """Records schtasks calls and answers like Windows."""

    def __init__(self, installed_state=None, refuse_create=False):
        self.calls = []
        self.state = installed_state
        self.refuse_create = refuse_create

    def __call__(self, args):
        self.calls.append(args)
        verb = args[0]
        if verb == "/Create":
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


def test_install_registers_a_system_task_at_startup_and_starts_it(paired):
    tasks, said = FakeScheduler(), []
    assert installer.install(said.append, tasks, is_admin=lambda: True, home=paired) == 0
    create = tasks.calls[0]
    assert create[:3] == ["/Create", "/TN", "KinLAN Agent"]
    assert create[create.index("/SC") + 1] == "ONSTARTUP"
    assert create[create.index("/RU") + 1] == "SYSTEM"
    assert create[create.index("/RL") + 1] == "HIGHEST"
    assert tasks.calls[1] == ["/Run", "/TN", "KinLAN Agent"]
    assert "running now" in said[0]


def test_from_source_the_task_runs_a_small_launcher(paired):
    tasks = FakeScheduler()
    installer.install(lambda _: None, tasks, is_admin=lambda: True, home=paired)
    command = tasks.calls[0][tasks.calls[0].index("/TR") + 1]
    script = paired / "run-agent.cmd"
    assert command == f'"{script}"'
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
    assert tasks.calls[0][tasks.calls[0].index("/TR") + 1] == f'"{installed}" run'


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
