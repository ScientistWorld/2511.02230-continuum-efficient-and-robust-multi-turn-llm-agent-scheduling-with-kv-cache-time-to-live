"""Write scoring/reference.json for the evaluator-owned engine (iteration 11).

Paper values are readings of the image-only figures (Figs. 8, 9, 10, 13, 15b);
see each experiment's source_note.  Run: python3 redteam/hardening/make_reference.py
"""
import json

METRICS = {
    "delay_reduction_x": {"higher_is_better": True, "coefficient": 1.0,
        "description": "Reference-baseline mean program completion time divided by the method's (pooled over the experiment's traces). Headline claim of the paper (average job completion time)."},
    "p95_delay_reduction_x": {"higher_is_better": True, "coefficient": 0.5,
        "description": "Per-trace reference-baseline P95 completion time divided by the method's, geometric mean over traces (paper Fig. 10 tail-latency claim)."},
    "p90_delay_reduction_x": {"higher_is_better": True, "coefficient": 0.5,
        "description": "Same as p95_delay_reduction_x at P90."},
    "throughput_improvement_x": {"higher_is_better": True, "coefficient": 0.5,
        "description": "Reference-baseline drain time of a trace divided by the method's (completed programs per second ratio); paper claims 1.10x-3.22x throughput."},
    "queue_wait_fraction": {"higher_is_better": False, "coefficient": -0.3,
        "description": "Constraint/cost side: total time requests wait for admission divided by total program completion time. Retaining KV that blocks other requests raises it; the paper's claim is that retention reduces per-turn queueing rather than shifting it onto other programs."},
}

def base(**kw):
    d = {"type": "baseline"}
    d.update(kw)
    return d

ONE = dict(delay_reduction_x=1.0, p90_delay_reduction_x=1.0, p95_delay_reduction_x=1.0, throughput_improvement_x=1.0)

EXPS = {
    "swebench_scaled_no_offload": {
        "description": "Coding-agent (SWE-Bench-like) programs, no CPU offload, overloaded operating point. Paper Fig. 8 (SWE-Bench row).",
        "source_note": "Fig. 8, Llama-3.1-8B on 1xB200 at the highest load (0.13 JPS): vLLM ~2010 s, Continuum ~1210 s -> 1.66x (70B/4xB200: ~1.68x; 8B/A100: ~1.55x; text: 'up to 2x'). Autellix/PLAS reads ~3700 s (~0.54x of vLLM); the scaled engine does NOT reproduce this PLAS degradation (PLAS ~1.0x here), so its paper reading is kept in this note rather than as a scored reference value.",
        "weight": 0.2, "reference_baseline": "vllm",
        "results": {"vllm": base(**ONE), "plas": base(),
                    "continuum": {"type": "proposed", "delay_reduction_x": 1.66}},
    },
    "bfcl_scaled_no_offload": {
        "description": "Web-search / function-calling (BFCL-like) programs, no CPU offload. Paper Fig. 8 (BFCL row).",
        "source_note": "Fig. 8, Llama-3.1-8B on 1xB200 at 5 JPS: vLLM ~316 s, Continuum ~213 s -> 1.48x (70B: ~1.14x; 8B/A100: ~1.33x). Autellix/PLAS ~293 s (~1.08x; engine: ~1.02x).",
        "weight": 0.2, "reference_baseline": "vllm",
        "results": {"vllm": base(**ONE), "plas": base(),
                    "continuum": {"type": "proposed", "delay_reduction_x": 1.48}},
    },
    "swebench_scaled_offload": {
        "description": "Coding-agent programs with CPU offload (lost KV is reloaded instead of recomputed). Paper Figs. 9 and 10.",
        "source_note": "Fig. 9, Llama-3.1-8B on 1xB200 at 0.13 JPS: vLLM ~1800 s, Continuum ~1130 s -> 1.59x; InferCept ~1650 s (~1.09x; the engine's InferCept is stronger, ~1.9-2.0x); Autellix+ ~1880 s (~0.96x; engine ~0.98x). Fig. 10 at 0.13 JPS: P90 vLLM ~2750 s vs ~1760 s -> 1.56x; P95 ~2850 s vs ~1790 s -> 1.59x.",
        "weight": 0.15, "reference_baseline": "vllm",
        "results": {"vllm": base(**ONE), "plas": base(), "infercept": base(),
                    "continuum": {"type": "proposed", "delay_reduction_x": 1.59,
                                  "p90_delay_reduction_x": 1.56, "p95_delay_reduction_x": 1.59}},
    },
    "turn_robustness_scaled": {
        "description": "Coding-agent programs with 3x the turns and 1/3 the tokens per turn, CPU offload. Paper Fig. 13 (3x multiplier).",
        "source_note": "Fig. 13 bar labels at the 3x multiplier (30.8 turns): vLLM 2.3x, InferCept 1.7x of Continuum's average job duration -> Continuum 2.3x over vLLM, InferCept ~1.35x over vLLM (engine's InferCept: ~2.6-3.0x, stronger than in the paper). At 5x the paper reports 3.7x.",
        "weight": 0.1, "reference_baseline": "vllm",
        "results": {"vllm": base(**ONE), "infercept": base(),
                    "continuum": {"type": "proposed", "delay_reduction_x": 2.3}},
    },
    "ablation_scaled": {
        "description": "Ablation (paper Fig. 15b, BFCL): program-level FCFS -> + static cold-start TTL -> full Continuum; ratios are taken against program-level FCFS.",
        "source_note": "Fig. 15(b) BFCL at 3.0 JPS: vLLM ~299 s, Program-level FCFS ~269 s, Static TTL ~226 s, Continuum ~206 s -> relative to program-level FCFS: vLLM 0.90x, Static TTL 1.19x, Continuum 1.31x. In Fig. 15(a) (SWE-Bench, high load) Static TTL and Continuum nearly coincide (~1.40x vs ~1.41x).",
        "weight": 0.1, "reference_baseline": "program_fcfs",
        "results": {"program_fcfs": base(**ONE),
                    "vllm": base(delay_reduction_x=0.90),
                    "static_ttl": base(delay_reduction_x=1.19),
                    "continuum": {"type": "proposed", "delay_reduction_x": 1.31}},
    },
    "tool_shift_scaled": {
        "description": "BFCL-like programs whose tool latencies change abruptly twice mid-trace (paper Sec. 3 motivation: tool latency varies with backend/API state). Not a paper figure; added so that tool-aware, adaptive retention is measured.",
        "source_note": "Benchmark extension with no paper figure. The proposed-method value is a PROXY, not a paper measurement: the Fig. 8 reading for the same program family (BFCL-like, Llama-3.1-8B/1xB200, 5 JPS: 1.48x). It only anchors the order of magnitude for the paper-consistency check.",
        "weight": 0.15, "reference_baseline": "vllm",
        "results": {"vllm": base(**ONE), "program_fcfs": base(), "continuum": {"type": "proposed", "delay_reduction_x": 1.48}},
    },
    "mixed_agents_scaled": {
        "description": "Coding-agent and web-agent programs sharing one engine (both tool catalogues live). Not a paper figure; added so that per-tool (rather than global) duration modelling matters.",
        "source_note": "Benchmark extension with no paper figure. The proposed-method value is a PROXY, not a paper measurement: the mean of the Fig. 8 readings for the two program families it mixes (SWE-Bench 1.66x, BFCL 1.48x -> 1.57x). It only anchors the order of magnitude for the paper-consistency check.",
        "weight": 0.1, "reference_baseline": "vllm",
        "results": {"vllm": base(**ONE), "program_fcfs": base(), "continuum": {"type": "proposed", "delay_reduction_x": 1.57}},
    },
}

for _n, _e in EXPS.items():
    _e["results"].setdefault("static_ttl", base())
out = {"experiments": {}}
for name, e in EXPS.items():
    out["experiments"][name] = {
        "description": e["description"],
        "source_note": e["source_note"],
        "weight": e["weight"],
        "primary_metric": "delay_reduction_x",
        "reference_baseline": e["reference_baseline"],
        "metrics": METRICS,
        "results": e["results"],
    }
assert abs(sum(e["weight"] for e in EXPS.values()) - 1.0) < 1e-9
json.dump(out, open("/home/user/scoring/reference.json", "w"), indent=2)
print("wrote reference.json")
