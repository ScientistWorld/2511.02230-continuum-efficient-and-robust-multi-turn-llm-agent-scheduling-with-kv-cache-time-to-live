"""Continuum (arXiv 2511.02230) as a scheduling policy for the gym's serving engine.

Reads one JSON message per line on stdin and answers queries on stdout
(protocol: briefing/evaluation.md).  Implements the paper's computational steps:

* Tool-call handler (Sec. 5.1): for every program, the interval between a
  request's finish and the program's next arrival is recorded as the duration
  of the tool named in that request's output -- per tool S[f] and globally S.
* TTL cost model (Sec. 4.1-4.2, Eq. 2): on a finish that ends in a tool call,
      Benefit = Prefill-Reload(r) + T * eta
      tau*    = argmax_tau  P(tau, f) * Benefit - tau
  where P is the empirical CDF of S[f] (or of S when |S[f]| <= K), evaluated
  by enumerating the recorded durations (and tau = 0).  T is the sliding-
  window mean queueing delay of requests whose KV had been evicted; eta =
  -Corr(k, N - k) over completed programs (memoryfulness).
* Cold start: while |S| <= K the TTL is the optimum under Exp(1) tool
  durations and eta = 1, i.e. tau = ln(Benefit) (0 if Benefit <= 1).  K = 100.
* Priority (Sec. 4.3): requests of programs holding a live pin first, then
  program-level FCFS (program arrival time).
* Deadlock prevention (Sec. 5.2): when the engine is stuck, unpin the pinned
  program with the latest program arrival.

Variants (for the paper's ablation and for the gym's sanity checks) are
selected with command-line flags; the default is the paper's method.
"""

from __future__ import annotations

import argparse
import bisect
import json
import math
import sys
from collections import deque


class Continuum:
    def __init__(self, *, k: int = 100, wait_window: int = 100, mode: str = "continuum",
                 fixed_ttl: float = 0.0, history_window: int = 0, fifo: bool = False,
                 shared_miss: bool = False, wait_weight: float = 1.0, priority: str = "paper"):
        self.k = k
        self.mode = mode
        self.fixed_ttl = fixed_ttl
        self.history_window = history_window
        self.fifo = fifo
        self.shared_miss = shared_miss
        self.wait_weight = wait_weight
        self.priority = priority
        self.offload = False
        self.tool_hist: dict[str, list[float]] = {}  # sorted
        self.tool_fifo: dict[str, deque] = {}
        self.global_hist: list[float] = []  # sorted
        self.global_fifo: deque = deque()
        self.n_global = 0
        self.waits: deque = deque(maxlen=wait_window)
        self.wait_sum = 0.0
        self.program_arrival: dict[int, float] = {}
        self.rid_program: dict[int, int] = {}
        self.rid_turn: dict[int, int] = {}
        self.turns_seen: dict[int, int] = {}
        # running sums for eta = -Corr(k, N - k)
        self._n = 0
        self._sx = self._sy = self._sxx = self._syy = self._sxy = 0.0

    # -- statistics ------------------------------------------------------
    def _record_tool(self, tool: str, duration: float) -> None:
        hist = self.tool_hist.setdefault(tool, [])
        bisect.insort(hist, duration)
        bisect.insort(self.global_hist, duration)
        self.n_global += 1
        if self.history_window > 0:
            fifo = self.tool_fifo.setdefault(tool, deque())
            fifo.append(duration)
            if len(fifo) > self.history_window:
                old = fifo.popleft()
                del hist[bisect.bisect_left(hist, old)]
            self.global_fifo.append(duration)
            if len(self.global_fifo) > self.history_window * 4:
                old = self.global_fifo.popleft()
                del self.global_hist[bisect.bisect_left(self.global_hist, old)]

    def _avg_wait(self) -> float:
        return self.wait_sum / len(self.waits) if self.waits else 0.0

    def _record_wait(self, wait: float) -> None:
        if len(self.waits) == self.waits.maxlen:
            self.wait_sum -= self.waits[0]
        self.waits.append(wait)
        self.wait_sum += wait

    def _eta(self) -> float:
        if self._n < 3:
            return 1.0
        n = self._n
        vx = self._sxx - self._sx * self._sx / n
        vy = self._syy - self._sy * self._sy / n
        if vx <= 1e-12 or vy <= 1e-12:
            return 1.0
        corr = (self._sxy - self._sx * self._sy / n) / math.sqrt(vx * vy)
        return max(0.0, -corr)

    def _record_program(self, n_turns: int) -> None:
        for k in range(n_turns):
            x, y = float(k), float(n_turns - k)
            self._n += 1
            self._sx += x
            self._sy += y
            self._sxx += x * x
            self._syy += y * y
            self._sxy += x * y

    # -- TTL -------------------------------------------------------------
    def calc_ttl(self, tool: str, rebuild_s: float, scale: float = 1.0) -> float:
        if self.mode == "fixed":
            return self.fixed_ttl
        if self.mode == "none":
            return 0.0
        benefit = rebuild_s * scale + self.wait_weight * self._avg_wait() * self._eta()
        if self.mode == "static" or self.n_global <= self.k:
            return math.log(benefit) if benefit > 1.0 else 0.0
        samples = self.tool_hist.get(tool, [])
        if len(samples) <= self.k:
            samples = self.global_hist
        n = len(samples)
        best_ttl, best = 0.0, 0.0
        for i, v in enumerate(samples):
            score = (i + 1) / n * benefit - v
            if score > best:
                best, best_ttl = score, v
        return best_ttl

    # -- protocol --------------------------------------------------------
    def handle(self, msg: dict):
        kind = msg["type"]
        if kind == "arrive":
            pid = msg["program"]
            self.program_arrival.setdefault(pid, msg["program_arrival"])
            self.rid_program[msg["req"]] = pid
            self.turns_seen[pid] = msg["turn"] + 1
            if msg["turn"] > 0 and msg.get("tool") is not None:
                self._record_tool(msg["tool"], float(msg["tool_time_s"]))
            return None
        if kind == "start":
            if msg["turn"] > 0 and not msg["hit"]:
                self._record_wait(float(msg["wait_s"]))
            self.rid_program.pop(msg["req"], None)
            return None
        if kind == "finish":
            if msg.get("tool") is None:
                self._record_program(self.turns_seen.pop(msg["program"], msg["turn"] + 1))
                return None
            scale = 1.0
            if self.shared_miss:
                scale = max(1.0, (msg["running_tokens"] + msg["kv_tokens"]) / max(1.0, msg["kv_tokens"]))
            return {"retain_s": self.calc_ttl(msg["tool"], float(msg["rebuild_s"]), scale)}
        if kind == "schedule":
            if self.fifo:
                return {"order": sorted(msg["waiting"])}
            pinned = set(msg["retained"])
            rp, pa = self.rid_program, self.program_arrival
            if self.priority == "progress":
                ts = self.turns_seen
                order = sorted(msg["waiting"], key=lambda r: (rp[r] not in pinned, -ts.get(rp[r], 0), pa[rp[r]], r))
            else:
                order = sorted(msg["waiting"], key=lambda r: (rp[r] not in pinned, pa[rp[r]], r))
            return {"order": order}
        if kind == "victim":
            return {"victim": max(msg["retained"], key=lambda p: (self.program_arrival.get(p, 0.0), p))}
        if kind == "init":
            self.offload = bool(msg.get("offload"))
            return {"ok": True}
        return None


def build(argv=None) -> Continuum:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--mode", choices=["continuum", "static", "fixed", "none"], default="continuum",
                    help="continuum = paper's method; static = cold-start TTL only (paper's Static TTL "
                         "ablation); fixed = constant TTL; none = never retain")
    ap.add_argument("--fixed-ttl", type=float, default=0.0)
    ap.add_argument("--k", type=int, default=100, help="cold-start threshold K (paper: 100)")
    ap.add_argument("--wait-window", type=int, default=100, help="sliding window for T")
    ap.add_argument("--history-window", type=int, default=0,
                    help="0 = keep all tool samples (paper); W = keep the last W per tool")
    ap.add_argument("--fifo", action="store_true", help="request-level FCFS instead of Continuum priority")
    ap.add_argument("--shared-miss", action="store_true",
                    help="(not in the paper) charge a miss's prefill to every running request")
    ap.add_argument("--wait-weight", type=float, default=1.0,
                    help="(not in the paper) weight of the queueing term T*eta in the benefit")
    ap.add_argument("--priority", choices=["paper", "progress"], default="paper",
                    help="(progress is not in the paper) break ties by turns already served")
    a = ap.parse_args(argv)
    return Continuum(k=a.k, wait_window=a.wait_window, mode=a.mode, fixed_ttl=a.fixed_ttl,
                     history_window=a.history_window, fifo=a.fifo, shared_miss=a.shared_miss,
                     wait_weight=a.wait_weight, priority=a.priority)


def main() -> None:
    policy = build()
    out = sys.stdout
    for line in sys.stdin:
        if not line.strip():
            continue
        msg = json.loads(line)
        if msg.get("type") == "end":
            break
        reply = policy.handle(msg)
        if msg.get("q"):
            out.write(json.dumps(reply if reply is not None else {}) + "\n")
            out.flush()


if __name__ == "__main__":
    main()
