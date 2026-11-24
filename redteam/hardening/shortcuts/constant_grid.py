"""Shortcut: per-workload constant TTL picked by grid search on the train split
(the old gym's 'static grid' shortcut).  The workload family is recognised
from the offload flag and the first tool names seen; the table comes from
redteam/hardening/grid_choice.json (written from train scores by run_hardening).
Priority = pinned first, then program FCFS (as the reference)."""
import json, sys
sys.path.insert(0, ".")
from method.continuum_policy import Continuum
table = json.load(open("redteam/hardening/grid_choice.json"))
SWE = {"cat", "ls", "grep", "sed", "find", "git", "python", "pytest", "pip", "make", "cd", "echo"}
pol = Continuum(mode="fixed")
offload, seen = False, set()
for line in sys.stdin:
    msg = json.loads(line)
    if msg.get("type") == "end":
        break
    if msg["type"] == "init":
        offload = bool(msg["offload"])
    if msg["type"] == "finish" and msg.get("tool"):
        seen.add("swe" if msg["tool"] in SWE else "bfcl")
        fam = ("offload" if offload else ("mixed" if len(seen) > 1 else next(iter(seen))))
        pol.fixed_ttl = float(table.get(fam, 2.0))
    reply = pol.handle(msg)
    if msg.get("q"):
        sys.stdout.write(json.dumps(reply if reply is not None else {}) + "\n")
        sys.stdout.flush()
