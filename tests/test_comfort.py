from src.comfort import compute_pmv


def test_reference_case_matches_verified_library_output():
    # Verified 2026-07-25 against pythermalcomfort==2.10.0 directly: pmv_ppd(tdb=25, tr=25,
    # vr=0.1, rh=50, met=1.2, clo=0.5, standard="ISO") == {"pmv": 0.08, "ppd": 5.1}
    pmv = compute_pmv(zone_air_temp_c=25.0, zone_rh_pct=50.0)
    assert round(pmv, 2) == 0.08


def test_hotter_zone_increases_pmv():
    cool_pmv = compute_pmv(zone_air_temp_c=22.0, zone_rh_pct=50.0)
    hot_pmv = compute_pmv(zone_air_temp_c=28.0, zone_rh_pct=50.0)
    assert hot_pmv > cool_pmv


def test_colder_zone_decreases_pmv():
    baseline_pmv = compute_pmv(zone_air_temp_c=22.0, zone_rh_pct=50.0)
    cold_pmv = compute_pmv(zone_air_temp_c=16.0, zone_rh_pct=50.0)
    assert cold_pmv < baseline_pmv
