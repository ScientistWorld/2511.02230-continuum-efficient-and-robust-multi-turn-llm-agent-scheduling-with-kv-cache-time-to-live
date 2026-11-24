"""Prior-work scheduling baselines, owned by eval/ so every method is compared
against the same fixed reference points.  They speak the same message protocol
as an external policy (see briefing/evaluation.md) but run in-process.
"""

from __future__ import annotations

from .engine import reload_s


class _Base:
    def __init__(self):
        self.program_arrival: dict[int, float] = {}
        self.retained: set[int] = set()

    def handle(self, msg: dict):
        kind = msg["type"]
        if kind == "init":
            self.offload = bool(msg["offload"])
            return {"ok": True}
        if kind == "arrive":
            self.program_arrival.setdefault(msg["program"], msg["program_arrival"])
            self.on_arrive(msg)
            return None
        if kind == "start":
            self.retained.discard(msg["program"])
            self.on_start(msg)
            return None
        if kind == "finish":
            self.on_finish(msg)
            if msg.get("tool") is None:
                return None
            retain = self.retain(msg)
            if retain > 0:
                self.retained.add(msg["program"])
            return {"retain_s": retain}
        if kind == "schedule":
            self.retained = set(msg["retained"])
            return {"order": self.order(msg)}
        if kind == "victim":
            return {"victim": max(msg["retained"], key=lambda p: (self.program_arrival.get(p, 0.0), p))}
        return None

    def on_arrive(self, msg):
        pass

    def on_start(self, msg):
        pass

    def on_finish(self, msg):
        pass

    def retain(self, msg) -> float:
        return 0.0

    def order(self, msg) -> list[int]:
        return sorted(msg["waiting"])


class VLLM(_Base):
    """End-of-turn release + request-level FCFS (vLLM default scheduler)."""


class ProgramFCFS(_Base):
    """End-of-turn release + program-level FCFS (order by program arrival)."""

    def __init__(self):
        super().__init__()
        self.rid_program: dict[int, int] = {}

    def on_arrive(self, msg):
        self.rid_program[msg["req"]] = msg["program"]

    def order(self, msg):
        return sorted(msg["waiting"], key=lambda r: (self.program_arrival[self.rid_program[r]], r))


class PLAS(_Base):
    """Autellix program-level attained service: least service so far first."""

    def __init__(self):
        super().__init__()
        self.rid_program: dict[int, int] = {}
        self.attained: dict[int, float] = {}

    def on_arrive(self, msg):
        self.rid_program[msg["req"]] = msg["program"]

    def on_finish(self, msg):
        self.attained[msg["program"]] = self.attained.get(msg["program"], 0.0) + msg["service_s"]

    def order(self, msg):
        return sorted(msg["waiting"], key=lambda r: (self.attained.get(self.rid_program[r], 0.0), r))


class InferCept(_Base):
    """InferCept-style preserve-or-swap with asynchronous offload costs.

    Preserve (keep the KV on the GPU until the tool returns, no expiry) when the
    memory held while waiting for the tool (kv * expected tool time) is smaller
    than the memory held while the KV is swapped back in (kv * reload time);
    otherwise swap out.  The expected tool time is the running mean of that
    tool's observed durations (global mean for unseen tools).  Preserved
    requests resume ahead of the FCFS queue.
    """

    def __init__(self):
        super().__init__()
        self.rid_program: dict[int, int] = {}
        self.tool_sum: dict[str, float] = {}
        self.tool_n: dict[str, int] = {}
        self.all_sum = 0.0
        self.all_n = 0

    def on_arrive(self, msg):
        self.rid_program[msg["req"]] = msg["program"]
        if msg.get("tool") is not None:
            t = msg["tool_time_s"]
            self.tool_sum[msg["tool"]] = self.tool_sum.get(msg["tool"], 0.0) + t
            self.tool_n[msg["tool"]] = self.tool_n.get(msg["tool"], 0) + 1
            self.all_sum += t
            self.all_n += 1

    def retain(self, msg):
        tool = msg["tool"]
        if self.tool_n.get(tool):
            expected = self.tool_sum[tool] / self.tool_n[tool]
        elif self.all_n:
            expected = self.all_sum / self.all_n
        else:
            expected = 1.0
        # Without offload the alternative is a full recompute (rebuild_s).
        swap = reload_s(msg["kv_tokens"]) if self.offload else msg["rebuild_s"]
        return 1e6 if expected < swap else 0.0

    def order(self, msg):
        retained = set(msg["retained"])
        return sorted(msg["waiting"], key=lambda r: (self.rid_program[r] not in retained, r))


BASELINES = {
    "vllm": VLLM,
    "program_fcfs": ProgramFCFS,
    "plas": PLAS,
    "infercept": InferCept,
}
