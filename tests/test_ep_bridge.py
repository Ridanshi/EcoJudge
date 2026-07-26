import os

from src.ep_bridge import (
    BLOCKS,
    load_idf,
    apply_patch,
    save_idf,
    run_sim,
    get_errors,
    get_block_metrics,
)

MODELS_DIR = os.path.join(os.path.dirname(__file__), "..", "models")
BASELINE_IDF = os.path.join(MODELS_DIR, "baseline.idf")
WEATHER = os.path.join(MODELS_DIR, "weather.epw")


def test_blocks_cover_all_24_hours():
    all_hours = set()
    for block in BLOCKS:
        all_hours.update(block["hours"])
    assert all_hours == set(range(1, 25))


def test_apply_patch_rewrites_schedules(tmp_path):
    idf = load_idf(BASELINE_IDF, WEATHER)
    verdicts = {
        "night": {"heating_setpoint_c": 16.0, "cooling_setpoint_c": 28.0},
        "morning": {"heating_setpoint_c": 20.0, "cooling_setpoint_c": 25.0},
        "afternoon": {"heating_setpoint_c": 19.0, "cooling_setpoint_c": 24.0},
        "evening": {"heating_setpoint_c": 21.0, "cooling_setpoint_c": 26.0},
    }
    apply_patch(idf, verdicts)
    out_path = str(tmp_path / "patched.idf")
    save_idf(idf, out_path)

    with open(out_path) as f:
        content = f.read()
    assert "16.0" in content or "16" in content
    assert "Htg-SetP-Sch" in content
    assert "Clg-SetP-Sch" in content


def _shorten_run_period(idf):
    run_periods = idf.idfobjects["RUNPERIOD"]
    run_periods[0].Begin_Month = 7
    run_periods[0].Begin_Day_of_Month = 1
    run_periods[0].End_Month = 7
    run_periods[0].End_Day_of_Month = 3


def _add_required_outputs(idf):
    idf.newidfobject(
        "OUTPUT:VARIABLE",
        Key_Value="*",
        Variable_Name="Zone Air Relative Humidity",
        Reporting_Frequency="Hourly",
    )
    idf.newidfobject(
        "OUTPUT:METER",
        Key_Name="Electricity:Facility",
        Reporting_Frequency="Hourly",
    )


def test_full_pipeline_runs_energyplus_and_extracts_metrics(tmp_path):
    idf = load_idf(BASELINE_IDF, WEATHER)
    _shorten_run_period(idf)
    _add_required_outputs(idf)

    verdicts = {
        "night": {"heating_setpoint_c": 16.0, "cooling_setpoint_c": 29.0},
        "morning": {"heating_setpoint_c": 20.0, "cooling_setpoint_c": 25.0},
        "afternoon": {"heating_setpoint_c": 19.0, "cooling_setpoint_c": 24.0},
        "evening": {"heating_setpoint_c": 21.0, "cooling_setpoint_c": 26.0},
    }
    apply_patch(idf, verdicts)

    idf_path = str(tmp_path / "patched.idf")
    save_idf(idf, idf_path)

    out_dir = str(tmp_path / "out")
    run_sim(idf_path, WEATHER, out_dir)

    errors = get_errors(out_dir)
    assert errors == [], f"unexpected severe/fatal errors: {errors}"

    metrics = get_block_metrics(out_dir)
    assert set(metrics.keys()) == {"night", "morning", "afternoon", "evening"}
    for block_name, values in metrics.items():
        assert 10.0 < values["avg_temp_c"] < 35.0
        assert 0.0 < values["avg_rh_pct"] < 100.0
        assert -3.0 < values["avg_pmv"] < 3.0
        assert values["kwh"] > 0.0
