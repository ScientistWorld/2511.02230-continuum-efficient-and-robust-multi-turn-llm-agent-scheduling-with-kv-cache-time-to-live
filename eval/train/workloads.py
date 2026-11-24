"""Synthetic multi-turn agent traces (SWE-Bench-like and BFCL-like).

Program-level statistics follow Table 1 of the paper (turns, tokens per
program, tool-time mean/SD).  Tool calls come from a per-workload catalogue of
named tools, each with its own long-tailed duration distribution, plus rare
very long calls (timeouts / hung tools).  Every trace draws its *own* tool
parameters (medians, spreads, popularity) around the catalogue, so a scheduler
has to learn them online; nothing about a particular trace can be written down
in advance.  Optionally, tool behaviour shifts abruptly part-way through a
trace (backend contention / API variability).

Randomness comes from a keyed hash (BLAKE2b in counter mode), so a trace is a
pure function of its seed string.
"""

from __future__ import annotations

import hashlib
import math
import struct

CATALOGUE = {
    # name: (median_s, log_sigma, popularity)
    "swebench": {
        "cat": (0.05, 0.8, 0.17),
        "ls": (0.04, 0.7, 0.09),
        "grep": (0.15, 1.0, 0.13),
        "sed": (0.06, 0.7, 0.13),
        "find": (0.40, 1.0, 0.06),
        "git": (0.10, 0.8, 0.06),
        "python": (0.50, 1.2, 0.13),
        "pytest": (2.00, 1.0, 0.07),
        "pip": (5.00, 0.8, 0.03),
        "make": (1.50, 1.1, 0.04),
        "cd": (0.01, 2.8, 0.05),  # Fig. 5b: slowest 10% carry 94% of the time
        "echo": (0.02, 0.5, 0.04),
    },
    "bfcl": {
        "web_search": (1.00, 0.5, 0.28),
        "fetch_url": (1.00, 1.34, 0.32),  # Fig. 5a: slowest 10% carry 52.5%
        "extract": (0.30, 0.6, 0.14),
        "calculator": (0.02, 0.5, 0.09),
        "translate": (0.80, 0.5, 0.09),
        "pdf_parse": (3.00, 0.9, 0.08),
    },
}

DATASETS = {
    "swebench": {"turn_mean": 10.9, "turn_sd": 2.1, "tokens_mean": 70126, "tokens_sd": 19732,
                 "token_scale": 1.0, "out_mean": 1100.0, "out_sd": 500.0},
    # The paper scales BFCL token counts by 0.4 to fit the context window.
    "bfcl": {"turn_mean": 6.3, "turn_sd": 2.3, "tokens_mean": 93256, "tokens_sd": 68687,
             "token_scale": 0.4, "out_mean": 700.0, "out_sd": 350.0},
}

MEDIAN_JITTER = 1.2  # per-trace, per-tool median factor exp(U(-j, j))
SPEED_JITTER = 1.2  # per-trace factor on all tool medians exp(U(-j, j)) (environment speed)
TIMEOUT_P = 0.003  # probability that a call hangs until a timeout
TIMEOUT_RANGE = (30.0, 120.0)
TOOL_CAP_S = 300.0
MAX_CONTEXT = 120_000


class HashRNG:
    """Deterministic RNG: BLAKE2b(key, counter) -> uniform doubles."""

    def __init__(self, key: str):
        self._key = hashlib.blake2b(key.encode(), digest_size=32).digest()
        self._ctr = 0
        self._pool: list[float] = []

    def random(self) -> float:
        if not self._pool:
            self._ctr += 1
            digest = hashlib.blake2b(struct.pack("<Q", self._ctr), key=self._key, digest_size=64).digest()
            self._pool = [((v >> 11) + 0.5) / 9007199254740992.0 for v in struct.unpack("<8Q", digest)]
        return self._pool.pop()

    def uniform(self, a: float, b: float) -> float:
        return a + (b - a) * self.random()

    def gauss(self, mu: float = 0.0, sigma: float = 1.0) -> float:
        u1, u2 = self.random(), self.random()
        return mu + sigma * math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)

    def expovariate(self, rate: float) -> float:
        return -math.log(self.random()) / rate

    def lognormal_mean_sd(self, mean: float, sd: float) -> float:
        s2 = math.log(1.0 + (sd * sd) / (mean * mean))
        return math.exp(self.gauss(math.log(mean) - 0.5 * s2, math.sqrt(s2)))

    def weighted(self, items: list, weights: list[float]):
        total = sum(weights)
        x = self.random() * total
        acc = 0.0
        for item, w in zip(items, weights):
            acc += w
            if x < acc:
                return item
        return items[-1]


def _draw_tool_params(rng: HashRNG, dataset: str) -> dict:
    """Per-trace tool parameters drawn around the catalogue."""
    params = {}
    speed = math.exp(rng.uniform(-SPEED_JITTER, SPEED_JITTER))
    for name, (median, sigma, pop) in CATALOGUE[dataset].items():
        params[name] = [
            speed * median * math.exp(rng.uniform(-MEDIAN_JITTER, MEDIAN_JITTER)),
            sigma * math.exp(rng.uniform(-0.25, 0.25)),
            pop * math.exp(rng.gauss(0.0, 0.4)),
        ]
    return params


def _draw_shifts(rng: HashRNG, params: dict, n_programs: int) -> list:
    """Two abrupt changes: at a program index, some tools get much slower/faster."""
    shifts = []
    names = sorted(params)
    for lo, hi in ((0.2, 0.45), (0.55, 0.8)):
        at = int(n_programs * rng.uniform(lo, hi))
        chosen: list[str] = []
        while len(chosen) < 3:
            name = rng.weighted(names, [params[n][2] for n in names])
            if name not in chosen:
                chosen.append(name)
        changes = {}
        for name in chosen:
            factor = math.exp(rng.uniform(math.log(4.0), math.log(12.0)))
            changes[name] = factor if rng.random() < 0.6 else 1.0 / factor
        shifts.append((at, changes))
    return shifts


def generate(seed: str, dataset: str, *, programs: int, arrival_rate: float,
             turn_multiplier: int = 1, shift: bool = False) -> list[dict]:
    """Return a list of programs: {pid, arrival, turns: [(prompt, output, tool, tool_time)]}.

    ``dataset`` is "swebench", "bfcl", or "mixed" (each program is SWE-like or
    BFCL-like with equal probability; both tool catalogues are live).
    """
    rng = HashRNG(f"{seed}|{dataset}")
    kinds = ["swebench", "bfcl"] if dataset == "mixed" else [dataset]
    catalogues = {k: _draw_tool_params(rng, k) for k in kinds}
    shifts = {k: (_draw_shifts(rng, catalogues[k], programs) if shift else []) for k in kinds}
    arrival = 0.0
    out = []
    for pid in range(programs):
        for k in kinds:
            for at, changes in shifts[k]:
                if pid == at:
                    for name, factor in changes.items():
                        catalogues[k][name][0] *= factor
        kind = kinds[0] if len(kinds) == 1 else (kinds[0] if rng.random() < 0.5 else kinds[1])
        stats = DATASETS[kind]
        params = catalogues[kind]
        names = sorted(params)
        arrival += rng.expovariate(arrival_rate)
        n_base = max(2, int(round(rng.gauss(stats["turn_mean"], stats["turn_sd"]))))
        n_turns = n_base * turn_multiplier
        final = rng.gauss(stats["tokens_mean"], stats["tokens_sd"]) * stats["token_scale"]
        final = min(MAX_CONTEXT, max(6000.0, final)) / turn_multiplier
        prompt0 = final * rng.uniform(0.04, 0.12)
        outputs = [max(8.0, min(4000.0, rng.lognormal_mean_sd(stats["out_mean"], stats["out_sd"]))) / turn_multiplier
                   for _ in range(n_turns)]
        growth = final - prompt0 - sum(outputs)
        if growth < 0:
            scale = (final - prompt0) * 0.5 / sum(outputs)
            outputs = [o * scale for o in outputs]
            growth = final - prompt0 - sum(outputs)
        weights = [rng.uniform(0.3, 1.7) for _ in range(n_turns - 1)]
        wsum = sum(weights)
        tool_outputs = [growth * w / wsum for w in weights]
        turns = []
        prompt = prompt0
        for k in range(n_turns):
            out_tok = int(round(outputs[k]))
            p = int(round(prompt))
            if k == n_turns - 1:
                turns.append((p, out_tok, None, 0.0))
                break
            tool = rng.weighted(names, [params[n][2] for n in names])
            median, sigma, _ = params[tool]
            if rng.random() < TIMEOUT_P:
                tool_time = rng.uniform(*TIMEOUT_RANGE)
            else:
                tool_time = math.exp(rng.gauss(math.log(median), sigma))
            tool_time = min(TOOL_CAP_S, tool_time)
            turns.append((p, out_tok, tool, tool_time))
            prompt = p + out_tok + tool_outputs[k]
        out.append({"pid": pid, "arrival": arrival, "turns": turns})
    return out
