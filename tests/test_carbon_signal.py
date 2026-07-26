import pytest
from src.carbon_signal import get_carbon_intensity, carbon_level


def test_known_low_hour():
    assert get_carbon_intensity(3) == 300
    assert carbon_level(3) == "low"


def test_known_high_hour():
    assert get_carbon_intensity(18) == 500
    assert carbon_level(18) == "high"


def test_known_medium_hour():
    assert get_carbon_intensity(9) == 440
    assert carbon_level(9) == "medium"


def test_invalid_hour_raises():
    with pytest.raises(ValueError):
        get_carbon_intensity(24)
    with pytest.raises(ValueError):
        get_carbon_intensity(-1)
