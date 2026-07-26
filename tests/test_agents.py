import json
from src.agents import propose, propose_repair


class _FakeMessage:
    def __init__(self, content):
        self.content = content


class _FakeChoice:
    def __init__(self, content):
        self.message = _FakeMessage(content)


class _FakeCompletion:
    def __init__(self, content):
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    def __init__(self, content):
        self._content = content

    def create(self, **kwargs):
        return _FakeCompletion(self._content)


class _FakeChat:
    def __init__(self, content):
        self.completions = _FakeCompletions(content)


class _FakeClient:
    def __init__(self, content):
        self.chat = _FakeChat(content)


def _context():
    return {
        "hour_block": "morning",
        "current_heating_setpoint_c": 20.0,
        "current_cooling_setpoint_c": 25.0,
        "avg_zone_temp_c": 22.0,
        "avg_zone_rh_pct": 45.0,
        "avg_pmv": 0.1,
        "kwh_this_block": 12.5,
        "carbon_level": "medium",
    }


def test_propose_parses_valid_json_response():
    fake_response = json.dumps({"heating_setpoint_c": 19.0, "cooling_setpoint_c": 26.0, "rationale": "save energy"})
    client = _FakeClient(fake_response)
    result = propose("energy", client, "fake-model", _context())
    assert result["agent"] == "energy"
    assert result["heating_setpoint_c"] == 19.0
    assert result["cooling_setpoint_c"] == 26.0
    assert result["rationale"] == "save energy"


def test_propose_handles_markdown_fenced_json():
    fake_response = "```json\n" + json.dumps({"heating_setpoint_c": 21.0, "cooling_setpoint_c": 24.0, "rationale": "keep comfy"}) + "\n```"
    client = _FakeClient(fake_response)
    result = propose("comfort", client, "fake-model", _context())
    assert result["agent"] == "comfort"
    assert result["heating_setpoint_c"] == 21.0


def test_propose_raises_on_malformed_json():
    client = _FakeClient("not json at all")
    try:
        propose("energy", client, "fake-model", _context())
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_propose_repair_parses_valid_json_response():
    fake_response = json.dumps({"heating_setpoint_c": 20.0, "cooling_setpoint_c": 25.0, "rationale": "revert to safer range"})
    client = _FakeClient(fake_response)
    failed_setpoints = {"heating_setpoint_c": 14.0, "cooling_setpoint_c": 32.0}
    result = propose_repair(client, "fake-model", "night", failed_setpoints, "** Severe  ** bad setpoint")
    assert result["agent"] == "repair"
    assert result["heating_setpoint_c"] == 20.0
    assert result["cooling_setpoint_c"] == 25.0


def test_propose_repair_raises_on_malformed_json():
    client = _FakeClient("nope")
    try:
        propose_repair(client, "fake-model", "night", {"heating_setpoint_c": 14.0, "cooling_setpoint_c": 32.0}, "error text")
        assert False, "expected ValueError"
    except ValueError:
        pass
