"""Main closed loop: run EnergyPlus, extract per-block metrics, debate+judge (or reuse
a cached precedent) for each block, patch the schedule, repeat."""
import json
import os
import shutil

from src.agents import build_client, propose, propose_repair
from src.carbon_signal import carbon_level
from src.ep_bridge import BLOCKS, apply_patch, get_block_metrics, get_errors, load_idf, run_sim, save_idf
from src.judge import adjudicate
from src.precedent_cache import PrecedentCache, discretize_state

INITIAL_SETPOINTS = {
    "night": {"heating_setpoint_c": 18.0, "cooling_setpoint_c": 27.0},
    "morning": {"heating_setpoint_c": 20.0, "cooling_setpoint_c": 25.0},
    "afternoon": {"heating_setpoint_c": 20.0, "cooling_setpoint_c": 25.0},
    "evening": {"heating_setpoint_c": 19.0, "cooling_setpoint_c": 26.0},
}

BLOCK_REPRESENTATIVE_HOUR = {"night": 3, "morning": 9, "afternoon": 15, "evening": 21}


def _log(transcript_path: str, record: dict) -> None:
    with open(transcript_path, "a") as f:
        f.write(json.dumps(record) + "\n")


def _simulate(idf_path: str, weather_path: str, out_dir: str, setpoints: dict) -> list:
    idf = load_idf(idf_path, weather_path)
    apply_patch(idf, setpoints)
    patched_idf_path = os.path.join(out_dir, "patched.idf")
    os.makedirs(out_dir, exist_ok=True)
    save_idf(idf, patched_idf_path)
    run_sim(patched_idf_path, weather_path, out_dir)
    return get_errors(out_dir)


def _run_iteration_with_repair(
    idf_path: str,
    weather_path: str,
    iter_dir: str,
    setpoints: dict,
    client,
    model: str,
    transcript_path: str,
    iteration: int,
):
    """Runs one simulation. On a severe/fatal error, feeds the error text to a Repair
    Agent per block, patches the corrected setpoints, and retries once. Returns
    (metrics, effective_setpoints) on success, or (None, None) if the repair retry
    also fails -- the caller falls back to the last known-good setpoints in that case."""
    errors = _simulate(idf_path, weather_path, iter_dir, setpoints)
    if not errors:
        return get_block_metrics(iter_dir), setpoints, os.path.join(iter_dir, "patched.idf")

    _log(transcript_path, {"iteration": iteration, "event": "sim_error", "errors": errors})
    error_text = "\n".join(errors)

    repaired_setpoints = {}
    for block in BLOCKS:
        block_name = block["name"]
        repair_proposal = propose_repair(client, model, block_name, setpoints[block_name], error_text)
        repaired_setpoints[block_name] = {
            "heating_setpoint_c": repair_proposal["heating_setpoint_c"],
            "cooling_setpoint_c": repair_proposal["cooling_setpoint_c"],
        }
        _log(transcript_path, {
            "iteration": iteration, "block": block_name, "event": "self_repair_proposal",
            "repair_proposal": repair_proposal,
        })

    retry_dir = os.path.join(iter_dir, "repair_retry")
    retry_errors = _simulate(idf_path, weather_path, retry_dir, repaired_setpoints)

    if not retry_errors:
        _log(transcript_path, {
            "iteration": iteration, "event": "self_repair_success", "setpoints": repaired_setpoints,
        })
        return get_block_metrics(retry_dir), repaired_setpoints, os.path.join(retry_dir, "patched.idf")

    _log(transcript_path, {
        "iteration": iteration, "event": "self_repair_failed_fallback", "errors": retry_errors,
    })
    return None, None, None


def run_loop(
    idf_path: str,
    weather_path: str,
    work_dir: str,
    num_iterations: int,
    model: str,
    cache_path: str,
    transcript_path: str,
    idf_snapshot_dir: str = None,
) -> dict:
    os.makedirs(work_dir, exist_ok=True)
    if os.path.exists(transcript_path):
        os.remove(transcript_path)
    if idf_snapshot_dir is not None:
        os.makedirs(idf_snapshot_dir, exist_ok=True)

    client = build_client()
    cache = PrecedentCache(cache_path)
    current_setpoints = {k: dict(v) for k, v in INITIAL_SETPOINTS.items()}
    last_good_setpoints = {k: dict(v) for k, v in INITIAL_SETPOINTS.items()}
    last_metrics = None

    for iteration in range(num_iterations):
        iter_dir = os.path.join(work_dir, f"iter_{iteration}")
        metrics, effective_setpoints, produced_idf_path = _run_iteration_with_repair(
            idf_path, weather_path, iter_dir, current_setpoints, client, model, transcript_path, iteration,
        )

        if metrics is None:
            current_setpoints = last_good_setpoints
            continue

        if idf_snapshot_dir is not None:
            shutil.copy(produced_idf_path, os.path.join(idf_snapshot_dir, f"iter_{iteration}.idf"))

        last_metrics = metrics
        last_good_setpoints = effective_setpoints
        current_setpoints = effective_setpoints

        new_setpoints = {}
        for block in BLOCKS:
            block_name = block["name"]
            block_metrics = metrics[block_name]
            hour = BLOCK_REPRESENTATIVE_HOUR[block_name]
            level = carbon_level(hour)
            bucket = discretize_state(block_metrics["avg_temp_c"], block_metrics["avg_pmv"], block_name, level)

            cached_verdict = cache.lookup(bucket)
            if cached_verdict is not None:
                verdict = cached_verdict
                _log(transcript_path, {
                    "iteration": iteration, "block": block_name, "event": "cache_hit",
                    "bucket": bucket, "verdict": verdict,
                })
            else:
                context = {
                    "hour_block": block_name,
                    "current_heating_setpoint_c": current_setpoints[block_name]["heating_setpoint_c"],
                    "current_cooling_setpoint_c": current_setpoints[block_name]["cooling_setpoint_c"],
                    "avg_zone_temp_c": block_metrics["avg_temp_c"],
                    "avg_zone_rh_pct": block_metrics["avg_rh_pct"],
                    "avg_pmv": block_metrics["avg_pmv"],
                    "kwh_this_block": block_metrics["kwh"],
                    "carbon_level": level,
                }
                energy_proposal = propose("energy", client, model, context)
                comfort_proposal = propose("comfort", client, model, context)
                verdict = adjudicate(
                    energy_proposal, comfort_proposal, block_metrics["avg_pmv"],
                    current_setpoints[block_name]["heating_setpoint_c"],
                    current_setpoints[block_name]["cooling_setpoint_c"],
                )
                cache.store(bucket, verdict)
                _log(transcript_path, {
                    "iteration": iteration, "block": block_name, "event": "debate",
                    "bucket": bucket, "energy_proposal": energy_proposal,
                    "comfort_proposal": comfort_proposal, "verdict": verdict,
                    "metrics": block_metrics,
                })

            new_setpoints[block_name] = {
                "heating_setpoint_c": verdict["heating_setpoint_c"],
                "cooling_setpoint_c": verdict["cooling_setpoint_c"],
            }

        current_setpoints = new_setpoints

    return last_metrics


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    final_metrics = run_loop(
        idf_path=os.path.join(repo_root, "models", "baseline.idf"),
        weather_path=os.path.join(repo_root, "models", "weather.epw"),
        work_dir=os.path.join(repo_root, "runs", "closed_loop"),
        num_iterations=5,
        model=os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile"),
        cache_path=os.path.join(repo_root, "results", "precedent_cache.json"),
        transcript_path=os.path.join(repo_root, "results", "transcript.jsonl"),
        idf_snapshot_dir=os.path.join(repo_root, "results", "idf_snapshots"),
    )
    print(json.dumps(final_metrics, indent=2))
