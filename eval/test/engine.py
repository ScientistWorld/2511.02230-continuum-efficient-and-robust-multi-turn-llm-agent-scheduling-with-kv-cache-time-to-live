"""Discrete-event model of an LLM serving engine running multi-turn agent programs.

This file is the environment's "physics".  It is owned by eval/ and is identical
on the train and test sides (eval/train/engine.py and eval/test/engine.py are
independent copies).  A scheduling *policy* only decides

  * how long to retain a finished request's KV cache when it ends in a tool call
    (``retain_s``, 0 = release it to the evictable cache immediately),
  * the priority order of the waiting queue,
  * which retained entry to drop when the engine is stuck,
  * optionally, early release of retained entries.

Everything else -- memory capacity, prefill / reload / decode timing, prefix-
cache (LRU) behaviour, admission, tool durations -- is fixed here.

Engine rules (vLLM v1 scheduler semantics, as in the authors' released code):

* Memory is counted in KV tokens.  A running request holds prompt+output tokens.
* Admission walks the policy's order and stops at the first request that does
  not fit (head-of-line blocking; no backfilling).
* When a request finishes, its KV is either *retained* for ``retain_s`` seconds
  (cannot be evicted by admission) or put into an LRU prefix cache, which counts
  as free memory and is evicted oldest-first when an admission needs space.
* A retained entry whose time is up is released into the LRU cache unless the
  program's next request is already waiting.
* If the head of the queue does not fit, nothing is running and entries are
  retained, the engine asks the policy for a victim and releases it (this is the
  only forced release; with something running the engine waits).
* The next request of a program reuses its KV if it is still retained or still
  in the LRU cache (incremental prefill only); otherwise it pays a full prefill
  (or, with CPU offload, a reload of the old KV plus the incremental prefill).
"""

from __future__ import annotations

import heapq
import json
import math
import os
import select
import subprocess
from collections import OrderedDict, deque
from dataclasses import dataclass, field

# --------------------------------------------------------------------------
# Hardware / model profile: Llama-3.1-70B, tensor parallel over 4 GPUs with
# ~141 GB each (about 1M tokens of KV cache after the weights).
# --------------------------------------------------------------------------

BYTES_PER_TOKEN = 327680  # fp16 K+V, 80 layers x 8 kv heads x 128 dims
CAPACITY_TOKENS = 1_000_000  # KV-cache budget (tokens) left after the weights
RELOAD_BYTES_PER_S = 4e9  # effective host -> GPU KV reload rate (offload connector)
MAX_RETAIN_S = 1e6  # largest accepted retention value (seconds)


# Iteration-level GPU model (vLLM chunked prefill, token budget 2048):
#   iteration time = ITER_FIXED                      (weights read, launch)
#                  + TOK_COST   * tokens in batch    (linear-layer compute)
#                  + KV_READ    * sum of decoding contexts   (attention reads)
#                  + ATTN_PF    * chunk * prefill prefix     (prefill attention)
# Every decoding request emits one token per iteration; the chunk goes to the
# earliest-admitted request that still has to reload (CPU offload) or prefill.
# Reloading offloaded KV is on the critical path of the iteration (LOAD_COST
# per token, no attention), as observed for the paper's offload baselines.
TOKEN_BUDGET = 2048
ITER_FIXED = 0.012
TOK_COST = 9.0e-5
KV_READ = 2.4e-8
ATTN_PF = 1.6e-9
LOAD_COST = BYTES_PER_TOKEN / RELOAD_BYTES_PER_S


def iteration_s(n_decode: int, decode_ctx: float, chunk: float, prefix: float, loading: bool = False) -> float:
    base = ITER_FIXED + TOK_COST * n_decode + KV_READ * decode_ctx
    if loading:
        return base + LOAD_COST * chunk
    return base + TOK_COST * chunk + ATTN_PF * chunk * prefix


def prefill_s(tokens: float, prefix: float = 0.0) -> float:
    """Stand-alone time to prefill ``tokens`` new tokens after ``prefix`` cached ones."""
    if tokens <= 0:
        return 0.0
    chunks = math.ceil(tokens / TOKEN_BUDGET)
    return chunks * ITER_FIXED + TOK_COST * tokens + ATTN_PF * tokens * (prefix + tokens / 2.0)


def reload_s(tokens: float) -> float:
    """Stand-alone time to reload ``tokens`` tokens of KV from host memory."""
    if tokens <= 0:
        return 0.0
    return math.ceil(tokens / TOKEN_BUDGET) * ITER_FIXED + LOAD_COST * tokens


PROFILE = {
    "bytes_per_token": BYTES_PER_TOKEN,
    "token_budget": TOKEN_BUDGET,
    "iteration_s": "0.012 + 9e-5*decode_seqs + 2.4e-8*sum(decode ctx) + chunk cost",
    "prefill_chunk_cost": "9e-5*chunk + 1.6e-9*chunk*prefix",
    "reload_chunk_cost": "chunk*327680/4e9",
}


class PolicyError(Exception):
    """The policy crashed, timed out, or broke the protocol."""


class EngineError(Exception):
    """Internal inconsistency (a bug in eval/, never the policy's fault)."""


# --------------------------------------------------------------------------
# Policy transports
# --------------------------------------------------------------------------


class InProcessPolicy:
    """Adapter for eval-owned baselines (objects with ``handle(msg)``)."""

    def __init__(self, impl):
        self.impl = impl

    def notify(self, msg: dict) -> None:
        self.impl.handle(msg)

    def ask(self, msg: dict) -> dict:
        reply = self.impl.handle(msg)
        if not isinstance(reply, dict):
            raise EngineError(f"baseline returned {reply!r} for {msg['type']}")
        return reply

    def close(self) -> None:
        pass


class SubprocessPolicy:
    """Talks to a policy program over stdin/stdout, one JSON object per line.

    Notifications are buffered and flushed together with the next query.
    The child gets a CPU-time limit (load-independent) and a very generous
    wall-clock backstop that only catches hung processes.
    """

    def __init__(self, command, cwd, env, stderr_path, cpu_limit_s=900, idle_timeout_s=1800):
        def _limits():
            try:
                import resource

                resource.setrlimit(resource.RLIMIT_CPU, (cpu_limit_s, cpu_limit_s + 5))
            except Exception:
                pass

        self._stderr = open(stderr_path, "ab")
        try:
            self.proc = subprocess.Popen(
                command,
                cwd=cwd,
                env=env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=self._stderr,
                preexec_fn=_limits,
                bufsize=0,
            )
        except OSError as exc:
            self._stderr.close()
            raise PolicyError(f"cannot start policy {command!r}: {exc}") from exc
        self.idle_timeout_s = idle_timeout_s
        self._out: list[bytes] = []
        self._buf = b""
        self._fd = self.proc.stdout.fileno()

    def notify(self, msg: dict) -> None:
        self._out.append(json.dumps(msg, separators=(",", ":")).encode() + b"\n")

    def _flush(self) -> None:
        data = b"".join(self._out)
        self._out.clear()
        try:
            self.proc.stdin.write(data)
            self.proc.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise PolicyError(f"policy closed its input ({exc}); exit code {self.proc.poll()}") from exc

    def _readline(self) -> bytes:
        while b"\n" not in self._buf:
            ready, _, _ = select.select([self._fd], [], [], self.idle_timeout_s)
            if not ready:
                raise PolicyError(f"policy produced no reply for {self.idle_timeout_s}s")
            chunk = os.read(self._fd, 1 << 16)
            if not chunk:
                raise PolicyError(f"policy exited (code {self.proc.poll()}) before replying")
            self._buf += chunk
        line, self._buf = self._buf.split(b"\n", 1)
        return line

    def ask(self, msg: dict) -> dict:
        self.notify(msg)
        self._flush()
        line = self._readline()
        try:
            reply = json.loads(line)
        except (ValueError, UnicodeDecodeError) as exc:
            raise PolicyError(f"non-JSON reply to {msg['type']}: {line[:200]!r}") from exc
        if not isinstance(reply, dict):
            raise PolicyError(f"reply to {msg['type']} is not a JSON object: {line[:200]!r}")
        return reply

    def close(self) -> None:
        try:
            self.notify({"type": "end"})
            self._flush()
        except PolicyError:
            pass
        try:
            self.proc.stdin.close()
        except OSError:
            pass
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait()
        self._stderr.close()

    def kill(self) -> None:
        try:
            self.proc.kill()
            self.proc.wait(timeout=10)
        except Exception:
            pass
        try:
            self._stderr.close()
        except Exception:
            pass


# --------------------------------------------------------------------------
# Engine
# --------------------------------------------------------------------------


@dataclass
class Request:
    rid: int
    pid: int
    turn: int
    arrival: float
    prompt: int
    output: int
    tool: str | None
    tool_time: float
    prev_kv: int  # KV tokens the previous turn left behind (0 for turn 0)
    # runtime state while running
    admitted: float = 0.0
    seq: int = 0
    load_left: float = 0.0  # KV tokens still to reload from host memory
    pf_left: float = 0.0  # prefill tokens left
    pf_prefix: float = 0.0  # tokens already in KV while prefilling
    dec_left: float = 0.0  # output tokens left
    ctx: float = 0.0  # context while decoding

    @property
    def need(self) -> int:
        return self.prompt + self.output


@dataclass
class Retained:
    tokens: int
    expires: float
    seq: int


@dataclass
class Program:
    pid: int
    arrival: float
    turns: list  # list of (prompt, output, tool, tool_time)
    done_at: float | None = None
    last_finish: float = 0.0
    waits: list = field(default_factory=list)


_GPU, _ARR, _EXP = 0, 1, 2  # event order at equal timestamps
_EPS = 1e-7


def _num(value, name: str, lo: float, hi: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PolicyError(f"{name} must be a number, got {value!r}")
    value = float(value)
    if not math.isfinite(value) or value < lo or value > hi:
        raise PolicyError(f"{name}={value!r} outside [{lo}, {hi}]")
    return value


class Engine:
    def __init__(self, programs: list[dict], *, offload: bool, policy, capacity: int = CAPACITY_TOKENS):
        self.capacity = capacity
        self.offload = offload
        self.policy = policy
        self.programs = {p["pid"]: Program(p["pid"], p["arrival"], p["turns"]) for p in programs}
        for prog in self.programs.values():
            for prompt, output, _tool, _tt in prog.turns:
                if prompt + output > capacity:
                    raise EngineError("request larger than capacity")
        self.t = 0.0
        self.events: list = []
        self._seq = 0
        self._rid = 0
        self.waiting: dict[int, Request] = {}  # rid -> request, arrival order
        self.waiting_pids: dict[int, int] = {}  # pid -> rid
        self.running: dict[int, Request] = {}
        self.running_tokens = 0
        self.retained: dict[int, Retained] = {}
        self.retained_tokens = 0
        self.cache: OrderedDict[int, int] = OrderedDict()  # pid -> tokens, LRU first
        self.cache_tokens = 0
        self.dirty = False
        # GPU fluid state
        self._gpu_version = 0
        self._rate = None  # (iteration_s, chunk, head) for the current segment
        # statistics
        self.hits = 0
        self.misses = 0
        self.retain_decisions = 0
        self.expired_unused = 0
        self.forced_releases = 0
        self.retained_token_seconds = 0.0
        self.peak_retained = 0
        self.busy_s = 0.0
        self.prefill_tokens = 0.0
        for prog in self.programs.values():
            self._push(prog.arrival, _ARR, (prog.pid, 0))

    # -- helpers ---------------------------------------------------------
    def _push(self, when: float, kind: int, payload) -> None:
        self._seq += 1
        heapq.heappush(self.events, (when, kind, self._seq, payload))

    def _free_for_admission(self) -> int:
        return self.capacity - self.running_tokens - self.retained_tokens

    def _release(self, pid: int) -> None:
        entry = self.retained.pop(pid)
        self.retained_tokens -= entry.tokens
        self._cache_put(pid, entry.tokens)
        self.dirty = True

    def _cache_put(self, pid: int, tokens: int) -> None:
        if pid in self.cache:
            self.cache_tokens -= self.cache.pop(pid)
        self.cache[pid] = tokens
        self.cache_tokens += tokens

    # -- GPU fluid model -------------------------------------------------------
    def _plan(self) -> None:
        """Fix the iteration rate for the next segment and schedule its end."""
        self._gpu_version += 1
        decoders = []
        head = None
        for r in self.running.values():  # dict order = admission order
            if r.load_left > 0 or r.pf_left > 0:
                if head is None:
                    head = r
            elif r.dec_left > 0:
                decoders.append(r)
        if not decoders and head is None:
            self._rate = None
            return
        n = len(decoders)
        ctx = sum(r.ctx for r in decoders)
        chunk = prefix = 0.0
        loading = False
        if head is not None:
            loading = head.load_left > 0
            left = head.load_left if loading else head.pf_left
            chunk = min(float(max(1, TOKEN_BUDGET - n)), left)
            prefix = 0.0 if loading else head.pf_prefix + head.pf_left / 2.0
        it = iteration_s(n, ctx, chunk, prefix, loading)
        self._rate = (it, chunk, head, decoders, loading)
        horizon = math.inf
        if decoders:
            horizon = min(r.dec_left for r in decoders) * it
        if head is not None:
            horizon = min(horizon, (head.load_left if loading else head.pf_left) / chunk * it)
        self._push(self.t + max(horizon, 0.0), _GPU, self._gpu_version)

    def _advance(self, when: float) -> None:
        dt = when - self.t
        if dt < -1e-9:
            raise EngineError("time went backwards")
        if dt > 0:
            self.retained_token_seconds += self.retained_tokens * dt
            if self._rate is not None:
                it, chunk, head, decoders, loading = self._rate
                steps = dt / it
                self.busy_s += dt
                for r in decoders:
                    r.dec_left -= steps
                    r.ctx += steps
                if head is not None:
                    done = chunk * steps
                    if loading:
                        head.load_left -= done
                    else:
                        head.pf_left -= done
                        head.pf_prefix += done
                        self.prefill_tokens += done
            self.t = when

    def _gpu_event(self) -> None:
        for r in list(self.running.values()):
            if 0 < r.load_left <= _EPS * 100:
                r.load_left = 0.0
            if r.load_left <= 0 and 0 < r.pf_left <= _EPS * 100:
                r.pf_left = 0.0
            if r.load_left <= 0 and r.pf_left <= 0 and r.dec_left <= _EPS * 100:
                self._on_finish(r)

    # -- event handlers --------------------------------------------------
    def _on_arrival(self, pid: int, turn: int) -> None:
        prog = self.programs[pid]
        prompt, output, tool, tool_time = prog.turns[turn]
        prev_kv = 0
        msg = {"type": "arrive", "t": self.t, "req": self._rid, "program": pid, "turn": turn,
               "program_arrival": prog.arrival, "prompt_tokens": prompt}
        if turn > 0:
            p_prompt, p_output, p_tool, _ = prog.turns[turn - 1]
            prev_kv = p_prompt + p_output
            msg["tool"] = p_tool
            msg["tool_time_s"] = self.t - prog.last_finish
        req = Request(self._rid, pid, turn, self.t, prompt, output, tool, tool_time, prev_kv)
        self._rid += 1
        self.waiting[req.rid] = req
        self.waiting_pids[pid] = req.rid
        self.dirty = True
        self.policy.notify(msg)

    def _on_finish(self, req: Request) -> None:
        del self.running[req.rid]
        self.running_tokens -= req.need
        prog = self.programs[req.pid]
        prog.last_finish = self.t
        self.dirty = True
        kv = req.need
        base = {"type": "finish", "t": self.t, "req": req.rid, "program": req.pid, "turn": req.turn,
                "tool": req.tool, "kv_tokens": kv, "service_s": self.t - req.admitted}
        if req.tool is None:
            prog.done_at = self.t
            self.policy.notify(base)
            return
        base.update({"rebuild_s": reload_s(kv) if self.offload else prefill_s(kv),
                     "running_tokens": self.running_tokens, "retained_tokens": self.retained_tokens,
                     "q": True})
        reply = self.policy.ask(base)
        retain = _num(reply.get("retain_s"), "retain_s", 0.0, MAX_RETAIN_S)
        if retain > 0.0:
            self.retain_decisions += 1
            self._seq += 1
            self.retained[req.pid] = Retained(kv, self.t + retain, self._seq)
            self.retained_tokens += kv
            self.peak_retained = max(self.peak_retained, self.retained_tokens)
            self._push(self.t + retain, _EXP, (req.pid, self._seq))
        else:
            self._cache_put(req.pid, kv)
        self._push(self.t + req.tool_time, _ARR, (req.pid, req.turn + 1))

    def _on_expire(self, pid: int, seq: int) -> None:
        entry = self.retained.get(pid)
        if entry is not None and entry.seq == seq:
            self.dirty = True  # the release itself happens in _release_expired

    def _release_expired(self) -> None:
        for pid in [p for p, e in self.retained.items() if e.expires <= self.t + 1e-12 and p not in self.waiting_pids]:
            self.expired_unused += 1
            self._release(pid)

    # -- admission ---------------------------------------------------------
    def _fits(self, req: Request) -> bool:
        reuse = self.retained[req.pid].tokens if req.pid in self.retained else 0
        return req.need <= self._free_for_admission() + reuse

    def _admit(self, req: Request) -> None:
        del self.waiting[req.rid]
        del self.waiting_pids[req.pid]
        hit = False
        if req.pid in self.retained:
            entry = self.retained.pop(req.pid)
            self.retained_tokens -= entry.tokens
            hit = True
        elif req.pid in self.cache:
            self.cache_tokens -= self.cache.pop(req.pid)
            hit = True
        empty = self.capacity - self.running_tokens - self.retained_tokens - self.cache_tokens
        while empty < req.need:
            if not self.cache:
                raise EngineError("admitted a request that does not fit")
            _, tokens = self.cache.popitem(last=False)
            self.cache_tokens -= tokens
            empty += tokens
        self.running_tokens += req.need
        self._seq += 1
        req.admitted, req.seq = self.t, self._seq
        if req.turn == 0:
            req.pf_left, req.pf_prefix = float(req.prompt), 0.0
        else:
            delta = float(max(1, req.prompt - req.prev_kv))
            if hit:
                self.hits += 1
                req.pf_left, req.pf_prefix = delta, float(req.prev_kv)
            else:
                self.misses += 1
                if self.offload:
                    req.load_left = float(req.prev_kv)
                    req.pf_left, req.pf_prefix = delta, float(req.prev_kv)
                else:
                    req.pf_left, req.pf_prefix = float(req.prompt), 0.0
        req.dec_left = float(max(1, req.output))
        req.ctx = float(req.prompt)
        self.running[req.rid] = req
        prog = self.programs[req.pid]
        wait = self.t - req.arrival
        prog.waits.append(wait)
        self.policy.notify({"type": "start", "t": self.t, "req": req.rid, "program": req.pid,
                            "turn": req.turn, "hit": hit, "wait_s": wait})

    def _schedule(self) -> None:
        self._release_expired()
        if not self.waiting or not self.dirty:
            return
        self.dirty = False
        waiting_ids = list(self.waiting)
        reply = self.policy.ask({"type": "schedule", "t": self.t, "waiting": waiting_ids,
                                 "retained": sorted(self.retained), "free_tokens": self._free_for_admission(),
                                 "running": len(self.running), "q": True})
        release = reply.get("release", [])
        if not isinstance(release, list):
            raise PolicyError("release must be a list of program ids")
        for pid in release:
            if isinstance(pid, bool) or not isinstance(pid, int) or pid not in self.retained:
                raise PolicyError(f"release names a program that holds no retained KV: {pid!r}")
            self._release(pid)
        order = reply.get("order")
        if not isinstance(order, list) or len(order) != len(waiting_ids) \
                or any(isinstance(x, bool) or not isinstance(x, int) for x in order) \
                or set(order) != set(waiting_ids):
            raise PolicyError("order must be a permutation of the waiting request ids")
        for rid in order:
            req = self.waiting[rid]
            while not self._fits(req):
                if self.running:
                    return  # head-of-line blocking: wait for memory to free up
                if not self.retained:
                    raise EngineError("idle engine cannot admit the head request")
                victim = self.policy.ask({"type": "victim", "t": self.t, "retained": sorted(self.retained),
                                          "head": rid, "q": True}).get("victim")
                if isinstance(victim, bool) or not isinstance(victim, int) or victim not in self.retained:
                    raise PolicyError(f"victim must be a program holding retained KV, got {victim!r}")
                self.forced_releases += 1
                self._release(victim)
            self._admit(req)

    # -- main loop -------------------------------------------------------------
    def run(self, max_events: int = 20_000_000) -> dict:
        self.policy.ask({"type": "init", "capacity_tokens": self.capacity, "offload": self.offload,
                         "profile": PROFILE, "q": True})
        n = 0
        while self.events:
            when = self.events[0][0]
            self._advance(when)
            replan = False
            while self.events and self.events[0][0] <= when:
                _, kind, _, payload = heapq.heappop(self.events)
                n += 1
                if kind == _GPU:
                    if payload == self._gpu_version:
                        self._gpu_event()
                        replan = True
                elif kind == _ARR:
                    self._on_arrival(*payload)
                else:
                    self._on_expire(*payload)
            before = len(self.running)
            self._schedule()
            if replan or len(self.running) != before:
                self._plan()
            if n > max_events:
                raise EngineError("event budget exceeded")
        if self.waiting or self.running:
            raise EngineError("simulation ended with unfinished requests")
        self.policy.close()
        return self._summary()

    def _summary(self) -> dict:
        progs = sorted(self.programs.values(), key=lambda p: p.pid)
        done = [p for p in progs if p.done_at is not None]
        first = min(p.arrival for p in progs)
        last = max(p.done_at for p in done) if done else first
        return {
            "programs": len(progs),
            "completed": len(done),
            "completion_s": [p.done_at - p.arrival for p in done],
            "wait_total_s": sum(w for p in done for w in p.waits),
            "requests": sum(len(p.waits) for p in done),
            "makespan_s": last - first,
            "hits": self.hits,
            "misses": self.misses,
            "retain_decisions": self.retain_decisions,
            "expired_unused": self.expired_unused,
            "forced_releases": self.forced_releases,
            "retained_token_seconds": self.retained_token_seconds,
            "peak_retained_tokens": self.peak_retained,
            "gpu_busy_s": self.busy_s,
            "prefill_tokens": self.prefill_tokens,
            "capacity": self.capacity,
        }
