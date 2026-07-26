from src.precedent_cache import discretize_state, PrecedentCache


def test_discretize_state_is_stable_for_close_inputs():
    a = discretize_state(avg_zone_temp_c=22.1, avg_pmv=0.12, hour_block="morning", carbon_level="low")
    b = discretize_state(avg_zone_temp_c=22.4, avg_pmv=0.12, hour_block="morning", carbon_level="low")
    assert a == b  # both round to temp bucket 22


def test_discretize_state_differs_for_different_blocks():
    a = discretize_state(22.0, 0.1, "morning", "low")
    b = discretize_state(22.0, 0.1, "evening", "low")
    assert a != b


def test_store_and_lookup(tmp_path):
    cache_path = str(tmp_path / "cache.json")
    cache = PrecedentCache(cache_path)
    bucket = discretize_state(22.0, 0.1, "morning", "low")
    assert cache.lookup(bucket) is None
    verdict = {"heating_setpoint_c": 20.0, "cooling_setpoint_c": 25.0, "winner": "energy", "reason": "test"}
    cache.store(bucket, verdict)
    assert cache.lookup(bucket) == verdict


def test_cache_persists_across_instances(tmp_path):
    cache_path = str(tmp_path / "cache.json")
    bucket = discretize_state(22.0, 0.1, "morning", "low")
    verdict = {"heating_setpoint_c": 20.0, "cooling_setpoint_c": 25.0, "winner": "energy", "reason": "test"}
    PrecedentCache(cache_path).store(bucket, verdict)
    reloaded = PrecedentCache(cache_path)
    assert reloaded.lookup(bucket) == verdict


def test_invalidate_removes_entry(tmp_path):
    cache_path = str(tmp_path / "cache.json")
    cache = PrecedentCache(cache_path)
    bucket = discretize_state(22.0, 0.1, "morning", "low")
    cache.store(bucket, {"heating_setpoint_c": 20.0, "cooling_setpoint_c": 25.0, "winner": "energy", "reason": "x"})
    cache.invalidate(bucket)
    assert cache.lookup(bucket) is None
