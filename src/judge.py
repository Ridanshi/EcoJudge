"""Deterministic (non-LLM) arbitrator between Energy Advocate and Comfort Advocate
proposals. Decides using OBSERVED PMV from the simulation run just completed, not a
prediction of the candidate setpoints' future effect -- there is no fast surrogate
model for that here, so the judge only ever reasons about ground-truth measurements."""

PMV_BOUND = 0.5
HARD_HEATING_RANGE_C = (14.0, 24.0)
HARD_COOLING_RANGE_C = (20.0, 32.0)
MAX_SETPOINT_DELTA_C = 3.0


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def adjudicate(
    energy_proposal: dict,
    comfort_proposal: dict,
    observed_pmv: float,
    current_heating_c: float,
    current_cooling_c: float,
) -> dict:
    if abs(observed_pmv) > PMV_BOUND:
        winner = "comfort"
        chosen = comfort_proposal
        reason = (
            f"observed PMV {observed_pmv:.2f} outside +/-{PMV_BOUND} bound; "
            "comfort proposal wins on safety override"
        )
    else:
        delta_h = abs(energy_proposal["heating_setpoint_c"] - current_heating_c)
        delta_c = abs(energy_proposal["cooling_setpoint_c"] - current_cooling_c)
        if delta_h > MAX_SETPOINT_DELTA_C or delta_c > MAX_SETPOINT_DELTA_C:
            winner = "blend"
            chosen = {
                "heating_setpoint_c": (
                    energy_proposal["heating_setpoint_c"] + comfort_proposal["heating_setpoint_c"]
                ) / 2,
                "cooling_setpoint_c": (
                    energy_proposal["cooling_setpoint_c"] + comfort_proposal["cooling_setpoint_c"]
                ) / 2,
            }
            reason = (
                f"comfort currently satisfied (PMV {observed_pmv:.2f}) but energy proposal's "
                f"setpoint change exceeds {MAX_SETPOINT_DELTA_C}C cap; blending proposals"
            )
        else:
            winner = "energy"
            chosen = energy_proposal
            reason = (
                f"comfort currently satisfied (PMV {observed_pmv:.2f}); energy proposal "
                f"accepted within {MAX_SETPOINT_DELTA_C}C change cap"
            )

    heating_c = _clamp(chosen["heating_setpoint_c"], *HARD_HEATING_RANGE_C)
    cooling_c = _clamp(chosen["cooling_setpoint_c"], *HARD_COOLING_RANGE_C)
    if cooling_c <= heating_c:
        cooling_c = heating_c + 1.0

    return {
        "heating_setpoint_c": heating_c,
        "cooling_setpoint_c": cooling_c,
        "winner": winner,
        "reason": reason,
    }
