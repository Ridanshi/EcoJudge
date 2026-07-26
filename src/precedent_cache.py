"""JSON-file-backed cache of prior judge verdicts, keyed by discretized building state.
Skips redundant Energy/Comfort LLM debate calls when the same state bucket recurs --
this is what answers the hackathon's required 'prompt latency management' write-up."""
import json
import os
from typing import Optional


def discretize_state(avg_zone_temp_c: float, avg_pmv: float, hour_block: str, carbon_level: str) -> str:
    temp_bucket = round(avg_zone_temp_c)
    pmv_bucket = round(avg_pmv * 2) / 2  # nearest 0.5
    return f"{hour_block}|temp={temp_bucket}|pmv={pmv_bucket}|carbon={carbon_level}"


class PrecedentCache:
    def __init__(self, path: str):
        self.path = path
        if os.path.exists(path):
            with open(path, "r") as f:
                self._data = json.load(f)
        else:
            self._data = {}

    def lookup(self, bucket: str) -> Optional[dict]:
        return self._data.get(bucket)

    def store(self, bucket: str, verdict: dict) -> None:
        self._data[bucket] = verdict
        self._save()

    def invalidate(self, bucket: str) -> None:
        self._data.pop(bucket, None)
        self._save()

    def _save(self) -> None:
        with open(self.path, "w") as f:
            json.dump(self._data, f, indent=2)
