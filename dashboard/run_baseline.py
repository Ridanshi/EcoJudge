"""Runs the UNMODIFIED baseline schedule (EnergyPlus's own 5ZoneAirCooled defaults,
just with the shortened 3-day RunPeriod and extra outputs Task 7 already added) over
the same 3-day window, for a fair baseline-vs-closed-loop comparison."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ep_bridge import get_block_metrics, run_sim

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    idf_path = os.path.join(REPO_ROOT, "models", "baseline.idf")
    weather_path = os.path.join(REPO_ROOT, "models", "weather.epw")
    out_dir = os.path.join(REPO_ROOT, "runs", "baseline")

    run_sim(idf_path, weather_path, out_dir)
    metrics = get_block_metrics(out_dir)

    results_dir = os.path.join(REPO_ROOT, "results")
    os.makedirs(results_dir, exist_ok=True)
    with open(os.path.join(results_dir, "baseline_metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)

    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
