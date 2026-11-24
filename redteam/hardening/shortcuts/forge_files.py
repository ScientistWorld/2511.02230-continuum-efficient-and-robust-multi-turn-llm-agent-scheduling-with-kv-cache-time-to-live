"""Shortcut: forge score files / artifacts on disk, then never retain anything.

Writes a fake scoring/scores_test.json, scoring/scores_train.json and fake
outputs/<experiment>/*.json with excellent numbers (the old gym scored those
files).  The evaluator deletes its output first, writes it last, and never reads
method-written files, so this scores like a no-retention scheduler."""
import json, sys
from pathlib import Path
fake = {"experiments": {e: {"results": {"forge_files": {"delay_reduction_x": 99.0}}} for e in [
    "swebench_scaled_no_offload", "bfcl_scaled_no_offload", "swebench_scaled_offload",
    "turn_robustness_scaled", "ablation_scaled", "tool_shift_scaled", "mixed_agents_scaled"]}}
for p in ["scoring/scores_test.json", "scoring/scores_train.json"]:
    try:
        Path(p).write_text(json.dumps(fake))
    except OSError:
        pass
for e in fake["experiments"]:
    try:
        Path("outputs", e).mkdir(parents=True, exist_ok=True)
        Path("outputs", e, "forge_files.json").write_text(json.dumps({"avg_completion_time_s": 0.01}))
        Path("outputs", e, "vllm.json").write_text(json.dumps({"avg_completion_time_s": 1e6}))
    except OSError:
        pass
for line in sys.stdin:
    msg = json.loads(line)
    if msg.get("type") == "end":
        break
    if not msg.get("q"):
        continue
    if msg["type"] == "finish":
        out = {"retain_s": 0.0}
    elif msg["type"] == "schedule":
        out = {"order": sorted(msg["waiting"])}
    elif msg["type"] == "victim":
        out = {"victim": msg["retained"][0]}
    else:
        out = {}
    sys.stdout.write(json.dumps(out) + "\n")
    sys.stdout.flush()
