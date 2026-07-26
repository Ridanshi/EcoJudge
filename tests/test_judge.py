from src.judge import adjudicate


def _proposal(heating, cooling):
    return {"heating_setpoint_c": heating, "cooling_setpoint_c": cooling, "rationale": "test"}


def test_comfort_wins_when_observed_pmv_violates_bound():
    energy = _proposal(18.0, 28.0)
    comfort = _proposal(21.0, 24.0)
    verdict = adjudicate(energy, comfort, observed_pmv=0.9, current_heating_c=20.0, current_cooling_c=25.0)
    assert verdict["winner"] == "comfort"
    assert verdict["heating_setpoint_c"] == 21.0
    assert verdict["cooling_setpoint_c"] == 24.0


def test_energy_wins_when_comfortable_and_change_within_cap():
    energy = _proposal(19.0, 27.0)
    comfort = _proposal(21.0, 24.0)
    verdict = adjudicate(energy, comfort, observed_pmv=0.1, current_heating_c=20.0, current_cooling_c=25.0)
    assert verdict["winner"] == "energy"
    assert verdict["heating_setpoint_c"] == 19.0
    assert verdict["cooling_setpoint_c"] == 27.0


def test_blend_when_comfortable_but_energy_change_too_aggressive():
    energy = _proposal(14.0, 32.0)  # >3C swing from current
    comfort = _proposal(21.0, 24.0)
    verdict = adjudicate(energy, comfort, observed_pmv=0.1, current_heating_c=20.0, current_cooling_c=25.0)
    assert verdict["winner"] == "blend"
    assert verdict["heating_setpoint_c"] == (14.0 + 21.0) / 2
    assert verdict["cooling_setpoint_c"] == (32.0 + 24.0) / 2


def test_output_is_clamped_to_hard_ranges():
    energy = _proposal(5.0, 40.0)
    comfort = _proposal(8.0, 38.0)
    verdict = adjudicate(energy, comfort, observed_pmv=0.9, current_heating_c=20.0, current_cooling_c=25.0)
    assert verdict["heating_setpoint_c"] >= 14.0
    assert verdict["cooling_setpoint_c"] <= 32.0


def test_cooling_never_at_or_below_heating():
    energy = _proposal(23.0, 23.0)
    comfort = _proposal(23.0, 23.0)
    verdict = adjudicate(energy, comfort, observed_pmv=0.1, current_heating_c=20.0, current_cooling_c=25.0)
    assert verdict["cooling_setpoint_c"] > verdict["heating_setpoint_c"]
