"""Config file, token storage, `pair` and `status`."""

import sys

import httpx
import pytest

from kinlan_agent import config, pairing, tokenstore


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("KINLAN_HOME", str(tmp_path))
    return tmp_path


# ---------------------------------------------------------------- config


def test_missing_config_gives_defaults():
    settings = config.load()
    assert settings.api_url == config.DEFAULT_API_URL and not settings.paired
    assert settings.monitor_interval_s == 10 and settings.upload_interval_s == 30


def test_config_round_trips(home):
    settings = config.AgentConfig(
        api_url="http://127.0.0.1:8000", agent_id="a-1", site_name='Lola "L"'
    )
    config.save(settings)
    assert config.load() == settings
    assert (home / "config.toml").read_text(encoding="utf-8").startswith("# KinLAN Agent settings")


def test_bad_values_fall_back_to_defaults_without_crashing(home):
    (home / "config.toml").write_text(
        'monitor_interval_s = -5\nlog_level = "DEBUG"\nsurprise = 1\n', encoding="utf-8"
    )
    settings = config.load()
    assert settings.monitor_interval_s == 10 and settings.log_level == "DEBUG"


def test_a_broken_config_file_gives_defaults_and_status_explains(home):
    (home / "config.toml").write_text('agent_id = "a"\nagent_id = "b"\n', encoding="utf-8")
    assert config.load() == config.AgentConfig()
    assert "can't be read" in config.read_error()
    said = []
    assert pairing.status(say=said.append) == 1 and "can't be read" in said[0]


# ---------------------------------------------------------------- token


def test_token_round_trip_and_is_not_stored_in_plain_text(home):
    tokenstore.save_token("super-secret-agent-token")
    assert tokenstore.load_token() == "super-secret-agent-token"
    if sys.platform == "win32":  # DPAPI-encrypted
        assert b"super-secret-agent-token" not in (home / "agent.token").read_bytes()


def test_a_damaged_token_reads_as_missing(home):
    (home / "agent.token").write_bytes(b"\x00garbage")
    if sys.platform == "win32":
        assert tokenstore.load_token() is None
    tokenstore.delete_token()
    assert tokenstore.load_token() is None


# ---------------------------------------------------------------- pair


def fake_server(status=200, body=None):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["json"] = __import__("json").loads(request.content)
        return httpx.Response(
            status,
            json=body
            or {
                "agent_id": "agent-1",
                "agent_token": "tok-123",
                "site_id": "site-1",
                "site_name": "Home",
            },
        )

    return httpx.Client(transport=httpx.MockTransport(handler)), seen


class FakeInfo:
    network = "192.168.1.0/24"


def answers(*replies):
    it = iter(replies)
    return lambda _prompt: next(it)


def test_pair_asks_consent_then_saves_token_and_settings():
    client, seen = fake_server()
    said = []
    code = pairing.pair(
        "http://127.0.0.1:8000",
        ask=answers("yes", "482 913"),
        say=said.append,
        client=client,
        get_netinfo=lambda: FakeInfo(),
    )
    assert code == 0
    assert seen["url"] == "http://127.0.0.1:8000/api/v1/agent/pair"
    assert seen["json"]["code"] == "482913" and seen["json"]["network_cidr"] == "192.168.1.0/24"
    assert tokenstore.load_token() == "tok-123"
    settings = config.load()
    assert (settings.agent_id, settings.site_name, settings.api_url) == (
        "agent-1",
        "Home",
        "http://127.0.0.1:8000",
    )
    assert "Only monitor networks you own" in said[0] and 'Paired with "Home"' in said[-1]


def test_without_consent_nothing_is_sent():
    client, seen = fake_server()
    said = []
    assert pairing.pair("http://x", ask=answers("no"), say=said.append, client=client) == 1
    assert seen == {} and tokenstore.load_token() is None


def test_a_wrong_code_shows_the_servers_message():
    client, _ = fake_server(
        404,
        {"error": {"code": "pairing_code_invalid", "message": "That code is wrong or expired."}},
    )
    said = []
    assert (
        pairing.pair(
            "http://x",
            code="111111",
            ask=answers("yes"),
            say=said.append,
            client=client,
            get_netinfo=lambda: FakeInfo(),
        )
        == 1
    )
    assert said[-1] == "Pairing failed: That code is wrong or expired."


def test_codes_must_be_six_digits():
    said = []
    assert pairing.pair("http://x", code="12ab", ask=answers("yes"), say=said.append) == 1
    assert "6 digits" in said[-1]


def test_status_before_and_after_pairing():
    said = []
    assert pairing.status(say=said.append) == 1 and "Not paired" in said[0]
    config.save(config.AgentConfig(agent_id="agent-1", site_id="s", site_name="Home"))
    tokenstore.save_token("tok")
    said.clear()
    assert pairing.status(say=said.append) == 0
    assert any("Home" in line for line in said) and any("never" in line for line in said)
