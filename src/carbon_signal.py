"""Static mocked hourly grid carbon-intensity signal (gCO2/kWh). Explicitly mocked --
not a live grid API -- documented here and in the demo video to avoid overclaiming."""

HOURLY_CARBON_INTENSITY_G_PER_KWH = {
    0: 320, 1: 310, 2: 305, 3: 300, 4: 305, 5: 320,
    6: 380, 7: 430, 8: 460, 9: 440, 10: 410, 11: 390,
    12: 380, 13: 385, 14: 400, 15: 420, 16: 450, 17: 480,
    18: 500, 19: 470, 20: 430, 21: 390, 22: 360, 23: 335,
}


def get_carbon_intensity(hour_of_day: int) -> int:
    if not 0 <= hour_of_day <= 23:
        raise ValueError(f"hour_of_day must be 0-23, got {hour_of_day}")
    return HOURLY_CARBON_INTENSITY_G_PER_KWH[hour_of_day]


def carbon_level(hour_of_day: int) -> str:
    intensity = get_carbon_intensity(hour_of_day)
    if intensity < 350:
        return "low"
    if intensity <= 440:
        return "medium"
    return "high"
