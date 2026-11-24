"""Pick the best constant TTL per workload family from TRAIN scores (the
'static grid overfit' shortcut) and write grid_choice.json."""
import json, sys
s = json.load(open(sys.argv[1]))["experiments"]
cands = {"fixed_ttl_1": 1, "fixed_ttl_2": 2, "fixed_ttl_4": 4, "fixed_ttl_8": 8, "fixed_ttl_16": 16,
         "bruteforce_retain45": 45}
fam = {"swe": ["swebench_scaled_no_offload"], "bfcl": ["bfcl_scaled_no_offload", "ablation_scaled", "tool_shift_scaled"],
       "mixed": ["mixed_agents_scaled"], "offload": ["swebench_scaled_offload", "turn_robustness_scaled"]}
choice = {}
for f, exps in fam.items():
    best = max(cands, key=lambda c: sum(s[e]["results"][c]["delay_reduction_x"] / s[e]["results"]["continuum"]["delay_reduction_x"] for e in exps))
    choice[f] = cands[best]
json.dump(choice, open(sys.argv[2], "w"), indent=1)
print("grid choice (train):", choice)
