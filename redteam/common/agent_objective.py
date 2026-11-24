"""What a future agent can compute WITHOUT any hidden file.

The agent sees only its own artifacts (outputs/<exp>/<method>.json) and the
metric list in briefing/evaluation.md / scoring/TARGETS.md.  Every held-out
test metric is a field of those artifacts (or a ratio to the baseline
artifact), so the agent can recompute the hidden test values exactly.  This
module does that and defines a simple equal-weight objective an agent might
use to select hyper-parameters or to decide which artifacts to keep.
"""

from __future__ import annotations

import json
from pathlib import Path

BASE = {"swebench_scaled_no_offload": "vllm", "bfcl_scaled_no_offload": "vllm",
        "swebench_scaled_offload": "vllm", "turn_robustness_scaled": "vllm",
        "ablation_scaled": "plas"}
# direction from briefing/evaluation.md: lower completion time / memory pressure
# better; higher reuse / completion better.
DIRS = {
    "p90_completion_time_s": -1, "p95_completion_time_s": -1, "avg_queue_wait_s": -1,
    "cache_hit_rate": +1, "peak_pinned_memory_fraction": -1, "expired_pin_fraction": -1,
    "deadlock_unpins": -1, "completed_fraction": +1,
}


def test_like_values(art_dir: Path, exp: str, method: str = "continuum") -> dict | None:
    p = art_dir / exp / f"{method}.json"
    if not p.exists():
        return None
    a = json.loads(p.read_text())
    b = json.loads((art_dir / exp / f"{BASE[exp]}.json").read_text())
    v = {k: a[k] for k in DIRS if k in a}
    v["p90_delay_reduction_x"] = b["p90_completion_time_s"] / a["p90_completion_time_s"]
    v["p95_delay_reduction_x"] = b["p95_completion_time_s"] / a["p95_completion_time_s"]
    return v


def objective(v: dict, ref: dict) -> float:
    """Equal-weight symmetric relative improvement over the agent's own
    reproduction of the reference, across the listed metrics."""
    s = 0.0
    for k, d in DIRS.items():
        if k in v and k in ref:
            den = abs(v[k]) + abs(ref[k]) + 1e-9
            s += d * (v[k] - ref[k]) / den
    return s
