"""Diagnostic (not a hidden-test run): does the retention trade-off the paper
studies appear at all in the gym's simulator?  Same SWE-style generator and
simulator as swebench_scaled_no_offload, arrival rate swept upward.  If the
pin-everything brute force keeps beating the cost-model TTL even under heavy
load, retaining state is free in this simulator; if it loses at high load, the
gym's chosen load (0.13 programs/s) is simply too light."""
import json, statistics, subprocess, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
RT = HERE.parent
W = HERE / "workloads"; O = HERE / "runs"
env = {"PYTHONPATH": "/home/user", "PATH": "/usr/local/bin:/usr/bin:/bin"}
rows = []
for rate in [0.13, 0.3, 0.45, 0.6]:
    wl = W / f"swe_rate{rate}.json"
    if not wl.exists():
        W.mkdir(parents=True, exist_ok=True)
        subprocess.run([sys.executable, "/home/user/data/workloads.py", "--dataset", "swebench", "--programs", "120",
                        "--arrival-rate", str(rate), "--seed", "7", "--output", str(wl)], check=True)
    for pol in ["vllm", "ref", "pin_max", "static4"]:
        out = O / f"rate{rate}_{pol}.json"
        if not out.exists():
            O.mkdir(parents=True, exist_ok=True)
            if pol == "vllm":
                cmd = ["/home/user/method/continuum_sim.py", "--policy", "vllm"]
            elif pol == "static4":
                cmd = [str(RT / "common/sim_variants.py"), "--variant", "static", "--static-ttl", "4"]
            else:
                cmd = [str(RT / "common/sim_variants.py"), "--variant", pol]
            subprocess.run([sys.executable, *cmd, "--workload", str(wl), "--output", str(out)], check=True, env=env)
        d = json.loads(out.read_text())
        rows.append({"rate": rate, "policy": pol, **{k: d[k] for k in [
            "avg_completion_time_s", "p95_completion_time_s", "avg_queue_wait_s", "cache_hit_rate",
            "peak_pinned_memory_fraction", "deadlock_unpins", "completed_fraction"]}})
(HERE / "sweep.json").write_text(json.dumps(rows, indent=1) + "\n")
print("| arrival rate | policy | avg JCT s | P95 JCT s | queue wait s | hit rate | peak pinned | deadlock unpins |")
print("|---|---|---|---|---|---|---|---|")
for r in rows:
    print(f"| {r['rate']} | {r['policy']} | {r['avg_completion_time_s']:.1f} | {r['p95_completion_time_s']:.1f} | "
          f"{r['avg_queue_wait_s']:.2f} | {r['cache_hit_rate']:.2f} | {r['peak_pinned_memory_fraction']:.2f} | {r['deadlock_unpins']} |")
