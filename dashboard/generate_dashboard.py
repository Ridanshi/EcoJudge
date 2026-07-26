"""Static matplotlib export comparing baseline vs closed-loop kWh and PMV per block.
Static, not a live server -- deliberate choice given the deadline (see spec: safer to
ship than to debug a live dashboard the night before submission)."""
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BLOCK_ORDER = ["night", "morning", "afternoon", "evening"]


def main():
    results_dir = os.path.join(REPO_ROOT, "results")
    with open(os.path.join(results_dir, "baseline_metrics.json")) as f:
        baseline = json.load(f)
    with open(os.path.join(results_dir, "closed_loop_metrics.json")) as f:
        closed_loop = json.load(f)

    baseline_kwh = [baseline[b]["kwh"] for b in BLOCK_ORDER]
    closed_loop_kwh = [closed_loop[b]["kwh"] for b in BLOCK_ORDER]
    baseline_pmv = [baseline[b]["avg_pmv"] for b in BLOCK_ORDER]
    closed_loop_pmv = [closed_loop[b]["avg_pmv"] for b in BLOCK_ORDER]

    total_baseline_kwh = sum(baseline_kwh)
    total_closed_loop_kwh = sum(closed_loop_kwh)
    pct_change = (total_closed_loop_kwh - total_baseline_kwh) / total_baseline_kwh * 100

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    x = range(len(BLOCK_ORDER))
    width = 0.35
    axes[0].bar([i - width / 2 for i in x], baseline_kwh, width, label="Baseline")
    axes[0].bar([i + width / 2 for i in x], closed_loop_kwh, width, label="Adversarial Court")
    axes[0].set_xticks(list(x))
    axes[0].set_xticklabels(BLOCK_ORDER)
    axes[0].set_ylabel("kWh")
    axes[0].set_title(f"Energy per block (total change: {pct_change:+.1f}%)")
    axes[0].legend()

    axes[1].plot(BLOCK_ORDER, baseline_pmv, marker="o", label="Baseline")
    axes[1].plot(BLOCK_ORDER, closed_loop_pmv, marker="o", label="Adversarial Court")
    axes[1].axhline(0.5, color="red", linestyle="--", linewidth=0.8, label="PMV comfort bound")
    axes[1].axhline(-0.5, color="red", linestyle="--", linewidth=0.8)
    axes[1].set_ylabel("PMV")
    axes[1].set_title("Thermal comfort per block")
    axes[1].legend()

    fig.tight_layout()
    out_path = os.path.join(results_dir, "dashboard.png")
    fig.savefig(out_path, dpi=150)
    print(f"saved {out_path}")
    print(f"total kWh: baseline={total_baseline_kwh:.2f}, closed_loop={total_closed_loop_kwh:.2f}, change={pct_change:+.1f}%")


if __name__ == "__main__":
    main()
