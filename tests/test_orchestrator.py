import json

import src.orchestrator as orch


class _FakeIDF:
    pass


def _canned_metrics():
    return {
        "night": {"avg_temp_c": 21.0, "avg_rh_pct": 50.0, "avg_pmv": 0.1, "kwh": 10.0},
        "morning": {"avg_temp_c": 22.0, "avg_rh_pct": 50.0, "avg_pmv": 0.1, "kwh": 20.0},
        "afternoon": {"avg_temp_c": 23.0, "avg_rh_pct": 50.0, "avg_pmv": 0.1, "kwh": 30.0},
        "evening": {"avg_temp_c": 22.0, "avg_rh_pct": 50.0, "avg_pmv": 0.1, "kwh": 15.0},
    }


def test_repair_succeeds_after_sim_error(tmp_path, monkeypatch):
    calls = {"propose_repair": []}

    def fake_get_errors(out_dir):
        if "iter_0" in out_dir and "repair_retry" not in out_dir:
            return ["** Severe ** bad setpoint in Htg-SetP-Sch"]
        return []

    def fake_propose_repair(client, model, block_name, failed_setpoints, error_text):
        calls["propose_repair"].append(block_name)
        return {"agent": "repair", "heating_setpoint_c": 20.0, "cooling_setpoint_c": 25.0, "rationale": "repaired"}

    monkeypatch.setattr(orch, "load_idf", lambda idf_path, weather_path: _FakeIDF())
    monkeypatch.setattr(orch, "apply_patch", lambda idf, setpoints: None)
    monkeypatch.setattr(orch, "save_idf", lambda idf, path: None)
    monkeypatch.setattr(orch, "run_sim", lambda idf_path, weather_path, out_dir: None)
    monkeypatch.setattr(orch, "get_errors", fake_get_errors)
    monkeypatch.setattr(orch, "get_block_metrics", lambda out_dir, zone_name="SPACE1-1": _canned_metrics())
    monkeypatch.setattr(orch, "build_client", lambda: object())
    monkeypatch.setattr(
        orch, "propose",
        lambda persona, client, model, context: {
            "agent": persona, "heating_setpoint_c": 20.0, "cooling_setpoint_c": 25.0, "rationale": "x",
        },
    )
    monkeypatch.setattr(orch, "propose_repair", fake_propose_repair)

    work_dir = str(tmp_path / "work")
    cache_path = str(tmp_path / "cache.json")
    transcript_path = str(tmp_path / "transcript.jsonl")

    metrics = orch.run_loop(
        idf_path="dummy.idf",
        weather_path="dummy.epw",
        work_dir=work_dir,
        num_iterations=1,
        model="fake-model",
        cache_path=cache_path,
        transcript_path=transcript_path,
    )

    assert metrics is not None
    assert len(calls["propose_repair"]) == 4  # one call per block

    events = [json.loads(line) for line in open(transcript_path)]
    event_types = [e["event"] for e in events]
    assert "sim_error" in event_types
    assert "self_repair_success" in event_types
    assert event_types.count("self_repair_proposal") == 4


def test_repair_fails_and_falls_back(tmp_path, monkeypatch):
    def fake_get_block_metrics(out_dir, zone_name="SPACE1-1"):
        raise AssertionError("get_block_metrics should not be called when both attempts error")

    def fake_propose(persona, client, model, context):
        raise AssertionError("propose should not be called when the iteration never produces metrics")

    monkeypatch.setattr(orch, "load_idf", lambda idf_path, weather_path: _FakeIDF())
    monkeypatch.setattr(orch, "apply_patch", lambda idf, setpoints: None)
    monkeypatch.setattr(orch, "save_idf", lambda idf, path: None)
    monkeypatch.setattr(orch, "run_sim", lambda idf_path, weather_path, out_dir: None)
    monkeypatch.setattr(orch, "get_errors", lambda out_dir: ["** Severe ** still broken"])
    monkeypatch.setattr(orch, "get_block_metrics", fake_get_block_metrics)
    monkeypatch.setattr(orch, "build_client", lambda: object())
    monkeypatch.setattr(orch, "propose", fake_propose)
    monkeypatch.setattr(
        orch, "propose_repair",
        lambda client, model, block_name, failed_setpoints, error_text: {
            "agent": "repair", "heating_setpoint_c": 20.0, "cooling_setpoint_c": 25.0, "rationale": "repaired",
        },
    )

    work_dir = str(tmp_path / "work")
    cache_path = str(tmp_path / "cache.json")
    transcript_path = str(tmp_path / "transcript.jsonl")

    metrics = orch.run_loop(
        idf_path="dummy.idf",
        weather_path="dummy.epw",
        work_dir=work_dir,
        num_iterations=1,
        model="fake-model",
        cache_path=cache_path,
        transcript_path=transcript_path,
    )

    assert metrics is None  # never produced a clean run

    events = [json.loads(line) for line in open(transcript_path)]
    event_types = [e["event"] for e in events]
    assert "self_repair_failed_fallback" in event_types
