"""Discrete-event reproduction of Continuum's KV-cache TTL scheduler.

This implements the paper's computational steps: tool-call history tracking,
the simplified Equation (2) empirical-CDF TTL search, pin/unpin with expiration,
deadlock prevention, and TTL-aware program-level FCFS priority.
"""

from __future__ import annotations

import argparse
import heapq
import json
import math
from collections import defaultdict, deque
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean
from typing import Any

from data.workloads import Program, Turn, load_workload


@dataclass
class Request:
    program_id: str
    program_arrival_s: float
    arrival_s: float
    turn: Turn
    total_turns: int
    seq: int


@dataclass
class Pin:
    program_id: str
    expires_s: float
    mem: float
    program_arrival_s: float


class ContinuumSimulator:
    def __init__(
        self,
        programs: list[Program],
        *,
        policy: str,
        capacity: float = 8.0,
        offload: bool = False,
        cold_start_k: int = 100,
    ) -> None:
        self.programs = {p.program_id: p for p in programs}
        self.policy = policy
        self.capacity = capacity
        self.offload = offload
        self.cold_start_k = cold_start_k
        self.time = 0.0
        self.counter = 0
        self.events: list[tuple[float, int, str, Any]] = []
        self.queue: list[Request] = []
        self.running_mem = 0.0
        self.pins: dict[str, Pin] = {}
        self.tool_history: dict[str, list[float]] = defaultdict(list)
        self.global_tool_history: list[float] = []
        self.wait_history: deque[float] = deque(maxlen=200)
        self.progress_observations: list[tuple[int, int]] = []
        self.pending_tool_start: dict[str, tuple[str, float]] = {}
        self.completed: dict[str, float] = {}
        self.program_start = {p.program_id: p.arrival_s for p in programs}
        self.attained_service: dict[str, float] = defaultdict(float)
        self.metrics = {
            "requests": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "ttl_decisions": 0,
            "expired_pins": 0,
            "deadlock_unpins": 0,
            "pin_time_s": 0.0,
            "peak_pinned_mem": 0.0,
            "queue_wait_s": 0.0,
        }
        for p in programs:
            self._push(p.arrival_s, "arrival", (p.program_id, 0))

    def _push(self, when: float, kind: str, payload: Any) -> None:
        self.counter += 1
        heapq.heappush(self.events, (when, self.counter, kind, payload))

    @property
    def pinned_mem(self) -> float:
        return sum(pin.mem for pin in self.pins.values())

    @property
    def free_mem(self) -> float:
        return self.capacity - self.running_mem - self.pinned_mem

    def run(self) -> dict[str, Any]:
        while self.events:
            self.time, _, kind, payload = heapq.heappop(self.events)
            if kind == "arrival":
                self._on_arrival(*payload)
            elif kind == "finish":
                self._on_finish(payload)
            elif kind == "tool_done":
                self._push(self.time, "arrival", payload)
            self._schedule()
        completion_times = [self.completed[pid] - self.program_start[pid] for pid in self.completed]
        makespan = max(self.completed.values()) - min(self.program_start.values())
        avg_completion = mean(completion_times)
        p90 = sorted(completion_times)[int(0.9 * (len(completion_times) - 1))]
        p95 = sorted(completion_times)[int(0.95 * (len(completion_times) - 1))]
        return {
            "policy": self.policy,
            "offload": self.offload,
            "programs": len(self.programs),
            "completed_fraction": len(self.completed) / max(1, len(self.programs)),
            "avg_completion_time_s": avg_completion,
            "p90_completion_time_s": p90,
            "p95_completion_time_s": p95,
            "throughput_jobs_per_s": len(self.completed) / makespan,
            "cache_hit_rate": self.metrics["cache_hits"] / max(1, self.metrics["cache_hits"] + self.metrics["cache_misses"]),
            "avg_queue_wait_s": self.metrics["queue_wait_s"] / max(1, self.metrics["requests"]),
            "peak_pinned_memory_fraction": self.metrics["peak_pinned_mem"] / self.capacity,
            "expired_pin_fraction": self.metrics["expired_pins"] / max(1, self.metrics["ttl_decisions"]),
            "deadlock_unpins": self.metrics["deadlock_unpins"],
            "raw": dict(self.metrics),
        }

    def _on_arrival(self, program_id: str, turn_index: int) -> None:
        program = self.programs[program_id]
        if program_id in self.pending_tool_start:
            tool_name, start_s = self.pending_tool_start.pop(program_id)
            duration = max(0.0, self.time - start_s)
            self.tool_history[tool_name].append(duration)
            self.global_tool_history.append(duration)
        turn = program.turns[turn_index]
        self.queue.append(Request(program_id, program.arrival_s, self.time, turn, len(program.turns), self.counter))

    def _on_finish(self, request: Request) -> None:
        self.running_mem -= request.turn.mem
        if request.turn.tool_name is None:
            self.completed[request.program_id] = self.time
            self.pins.pop(request.program_id, None)
            return
        self.pending_tool_start[request.program_id] = (request.turn.tool_name, self.time)
        self._maybe_pin(request, request.turn.tool_name)
        self._push(self.time + request.turn.tool_time_s, "tool_done", (request.program_id, request.turn.turn_index + 1))

    def _maybe_pin(self, request: Request, tool_name: str) -> None:
        ttl = 0.0
        if self.policy == "continuum":
            ttl = self._calc_ttl(request, tool_name)
        elif self.policy == "static_ttl":
            ttl = 0.25
        elif self.policy == "infercept":
            expected = mean(self.global_tool_history) if self.global_tool_history else 1.0
            ttl = expected if self._miss_cost(request) > expected else 0.0
        if ttl <= 0.0:
            return
        self.metrics["ttl_decisions"] += 1
        self.metrics["pin_time_s"] += ttl
        self.pins[request.program_id] = Pin(
            request.program_id,
            self.time + ttl,
            request.turn.mem,
            request.program_arrival_s,
        )
        self.metrics["peak_pinned_mem"] = max(self.metrics["peak_pinned_mem"], self.pinned_mem)

    def _calc_ttl(self, request: Request, tool_name: str) -> float:
        benefit = self._miss_cost(request) + self._avg_wait() * self._memoryfulness()
        if len(self.global_tool_history) <= self.cold_start_k:
            return max(0.0, math.log(benefit)) if benefit > 1.0 else 0.0
        samples = self.tool_history[tool_name]
        if len(samples) <= self.cold_start_k:
            samples = self.global_tool_history
        candidates = sorted(set([0.0] + samples))
        best_ttl = 0.0
        best_score = 0.0
        n = len(samples)
        for ttl in candidates:
            prob = sum(1 for sample in samples if sample <= ttl) / n
            score = prob * benefit - ttl
            if score > best_score:
                best_score = score
                best_ttl = ttl
        return best_ttl

    def _miss_cost(self, request: Request) -> float:
        if request.turn.turn_index == 0:
            return request.turn.prefill_s
        return request.turn.reload_s if self.offload else request.turn.prefill_s

    def _avg_wait(self) -> float:
        return mean(self.wait_history) if self.wait_history else 0.0

    def _memoryfulness(self) -> float:
        if len(self.progress_observations) < 3:
            return 1.0
        xs = [x for x, _ in self.progress_observations]
        ys = [y for _, y in self.progress_observations]
        mx, my = mean(xs), mean(ys)
        vx = sum((x - mx) ** 2 for x in xs)
        vy = sum((y - my) ** 2 for y in ys)
        if vx == 0.0 or vy == 0.0:
            return 1.0
        corr = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / math.sqrt(vx * vy)
        return max(0.0, -corr)

    def _expire_pins(self) -> None:
        queued_programs = {r.program_id for r in self.queue}
        for pid, pin in list(self.pins.items()):
            if self.time > pin.expires_s and pid not in queued_programs:
                self.metrics["expired_pins"] += 1
                del self.pins[pid]

    def _fits(self, request: Request) -> bool:
        reusable = self.pins[request.program_id].mem if request.program_id in self.pins else 0.0
        return self.free_mem + reusable >= request.turn.mem

    def _priority_key(self, request: Request) -> tuple:
        pinned = request.program_id in self.pins
        if self.policy in {"continuum", "static_ttl"}:
            return (0 if pinned else 1, request.program_arrival_s, request.arrival_s)
        if self.policy == "plas":
            return (self.attained_service[request.program_id], request.arrival_s)
        return (request.arrival_s,)

    def _schedule(self) -> None:
        while True:
            self._expire_pins()
            if not self.queue:
                return
            self.queue.sort(key=self._priority_key)
            selected_index = next((i for i, req in enumerate(self.queue) if self._fits(req)), None)
            if selected_index is None:
                if not self.pins:
                    return
                victim = max(self.pins.values(), key=lambda p: p.program_arrival_s)
                del self.pins[victim.program_id]
                self.metrics["deadlock_unpins"] += 1
                continue
            request = self.queue.pop(selected_index)
            pin = self.pins.pop(request.program_id, None)
            hit = pin is not None and self.time <= pin.expires_s
            self.running_mem += request.turn.mem
            wait = self.time - request.arrival_s
            self.metrics["requests"] += 1
            self.metrics["queue_wait_s"] += wait
            self.progress_observations.append((request.turn.turn_index, request.total_turns - request.turn.turn_index))
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
    parser = argparse.ArgumentParser()
    parser.add_argument("--workload", type=Path, required=True)
    parser.add_argument("--policy", choices=["vllm", "plas", "infercept", "static_ttl", "continuum"], required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--capacity", type=float, default=8.0)
    parser.add_argument("--offload", action="store_true")
    args = parser.parse_args()
    result = ContinuumSimulator(
        load_workload(args.workload),
        policy=args.policy,
        capacity=args.capacity,
        offload=args.offload,
    ).run()
    result["workload"] = str(args.workload)
    result["capacity"] = args.capacity
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
