"""Thin wrapper around pythermalcomfort's ISO 7730 PMV/PPD model with fixed
office-typical assumptions (no separate mean-radiant-temp sensor or clothing/activity
input exists in this simulation, so these are fixed constants, not measured)."""
from pythermalcomfort.models import pmv_ppd

AIR_VELOCITY_M_S = 0.1
METABOLIC_RATE_MET = 1.2
CLOTHING_INSULATION_CLO = 0.5


def compute_pmv(zone_air_temp_c: float, zone_rh_pct: float) -> float:
    # limit_inputs=False: the library's default clips out-of-range inputs to NaN (its
    # ISO 7730 applicability check). Our setpoints can legitimately push zone temps
    # outside that narrow range during the debate loop, and PMV here is only an
    # internal decision signal, not a regulatory-compliance number -- a real (if
    # extrapolated) value is more useful than NaN breaking the judge/cache downstream.
    result = pmv_ppd(
        tdb=zone_air_temp_c,
        tr=zone_air_temp_c,
        vr=AIR_VELOCITY_M_S,
        rh=zone_rh_pct,
        met=METABOLIC_RATE_MET,
        clo=CLOTHING_INSULATION_CLO,
        standard="ISO",
        limit_inputs=False,
    )
    return float(result["pmv"])
