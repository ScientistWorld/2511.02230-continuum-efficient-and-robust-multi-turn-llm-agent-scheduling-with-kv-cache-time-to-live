"""Scheduler variants used by the red-team audit.

Every variant subclasses the gym's own simulator (method/continuum_sim.py), so
the memory/timing model and the metric computation are exactly the ones the
reference uses.  Only the scheduling policy hooks are overridden -- which is
what a future agent editing method/ would do.

`_calc_ttl` is re-implemented with a sorted/bisect empirical CDF.  It returns
bit-identical TTLs to the original O(n^2) loop (same candidate order, same
float expressions, strict `>`), it is just faster; the `ref` variant checks
this against the gym's reference artifacts.
"""

from __future__ import annotations

import argparse
import bisect
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, "/home/user")

from data.workloads import load_workload  # noqa: E402
from method.continuum_sim import ContinuumSimulator  # noqa: E402

MAX_TOOL_S = 45.0  # generator caps tool time at 45 s


class VariantSim(ContinuumSimulator):
    def __init__(
        self,
        programs,
        *,
        variant: str,
        static_ttl: float | None = None,
        prior_workload: Path | None = None,
        starve_frac: float = 0.0,
        **kw,
    ) -> None:
        base_policy = "vllm" if variant == "vllm" else "continuum"
        super().__init__(programs, policy=base_policy, **kw)
        self.variant = variant
        self.static_ttl_value = static_ttl
        if variant == "coldstart_only":
            self.cold_start_k = 10**12
        if variant == "warm_history":
            # Paper Sec 4.2: tool statistics can be collected before serving
            # (e.g. during agent post-training) to avoid cold start.  We use a
            # *different-seed* trace from the same generator as the prior.
            for prog in load_workload(prior_workload):
                for turn in prog.turns:
                    if turn.tool_name is not None:
                        self.tool_history[turn.tool_name].append(turn.tool_time_s)
                        self.global_tool_history.append(turn.tool_time_s)
        self.starved: set[str] = set()
        if starve_frac > 0.0:
            work = {
                p.program_id: sum(t.decode_s + t.prefill_s + t.tool_time_s for t in p.turns)
                for p in programs
            }
            n = int(round(starve_frac * len(programs)))
            self.starved = set(sorted(work, key=work.get, reverse=True)[:n])

    # ---- fast, bit-identical empirical-CDF TTL search (paper Eq. 2) ----
    def _eq2_ttl(self, request, tool_name: str) -> float:
        benefit = self._miss_cost(request) + self._avg_wait() * self._memoryfulness()
        if len(self.global_tool_history) <= self.cold_start_k:
            return max(0.0, math.log(benefit)) if benefit > 1.0 else 0.0
        samples = self.tool_history[tool_name]
        if len(samples) <= self.cold_start_k:
            samples = self.global_tool_history
        ordered = sorted(samples)
        candidates = sorted(set([0.0] + samples))
        best_ttl = 0.0
        best_score = 0.0
        n = len(samples)
        for ttl in candidates:
            prob = bisect.bisect_right(ordered, ttl) / n
            score = prob * benefit - ttl
            if score > best_score:
                best_score = score
                best_ttl = ttl
        return best_ttl

    def _calc_ttl(self, request, tool_name: str) -> float:
        v = self.variant
        if v in ("ref", "coldstart_only", "warm_history", "true_deadlock_unpin"):
            return self._eq2_ttl(request, tool_name)
        if v == "nopin_fcfs":
            return 0.0
        if v == "static":
            return float(self.static_ttl_value)
        if v == "pin_max":
            return MAX_TOOL_S
        if v == "oracle":
            # Reads the *future* tool duration straight from the trace file.
            true_t = request.turn.tool_time_s
            benefit = self._miss_cost(request) + self._avg_wait() * self._memoryfulness()
            return true_t + 0.01 if benefit - true_t > 0.0 else 0.0
        if v == "starve":
            return self._eq2_ttl(request, tool_name)
        raise ValueError(v)

    def _on_arrival(self, program_id: str, turn_index: int) -> None:
        if program_id in self.starved and turn_index == 0:
            return  # admission control: never admit the longest programs
        super()._on_arrival(program_id, turn_index)

    def _schedule(self) -> None:
        if self.variant != "true_deadlock_unpin":
            return super()._schedule()
        # Only force-unpin when nothing is running (a real deadlock); otherwise
        # wait for running requests to finish and free memory.
        while True:
            self._expire_pins()
            if not self.queue:
                return
            self.queue.sort(key=self._priority_key)
            idx = next((i for i, r in enumerate(self.queue) if self._fits(r)), None)
            if idx is None:
                if not self.pins or self.running_mem > 1e-9:
                    return
                victim = max(self.pins.values(), key=lambda p: p.program_arrival_s)
                del self.pins[victim.program_id]
                self.metrics["deadlock_unpins"] += 1
                continue
            request = self.queue.pop(idx)
            pin = self.pins.pop(request.program_id, None)
            hit = pin is not None and self.time <= pin.expires_s
            self.running_mem += request.turn.mem
            wait = self.time - request.arrival_s
            self.metrics["requests"] += 1
            self.metrics["queue_wait_s"] += wait
            self.progress_observations.append(
                (request.turn.turn_index, request.total_turns - request.turn.turn_index)
            )
            if hit:
                self.metrics["cache_hits"] += 1
                service = request.turn.decode_s
            else:
                if request.turn.turn_index > 0:
                    self.metrics["cache_misses"] += 1
                    self.wait_history.append(wait)
                service = request.turn.decode_s + self._miss_cost(request)
            self.attained_service[request.program_id] += service
            self._push(self.time + service, "finish", request)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workload", type=Path, required=True)
    ap.add_argument("--variant", required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--capacity", type=float, default=8.0)
    ap.add_argument("--offload", action="store_true")
    ap.add_argument("--static-ttl", type=float, default=None)
    ap.add_argument("--prior-workload", type=Path, default=None)
    ap.add_argument("--starve-frac", type=float, default=0.0)
    a = ap.parse_args()
    sim = VariantSim(
        load_workload(a.workload),
        variant=a.variant,
        static_ttl=a.static_ttl,
        prior_workload=a.prior_workload,
        starve_frac=a.starve_frac,
        capacity=a.capacity,
        offload=a.offload,
    )
    res = sim.run()
    res["workload"] = str(a.workload)
    res["capacity"] = a.capacity
    res["policy"] = "continuum"
    res["variant"] = a.variant
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(res, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
