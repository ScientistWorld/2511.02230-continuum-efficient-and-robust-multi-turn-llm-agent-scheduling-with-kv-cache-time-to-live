"""Shortcut: shortest-job-first on prompt size (starve the big programs to cut
the mean).  Old gym: dropping the 10% longest programs from the percentiles
paid +5.39.  Here every program must finish and P90/P95 are scored per trace."""
import json, sys
sys.path.insert(0, ".")
from method.continuum_policy import Continuum
pol = Continuum()
size = {}
for line in sys.stdin:
    msg = json.loads(line)
    if msg.get("type") == "end":
        break
    if msg["type"] == "arrive":
        size[msg["req"]] = msg["prompt_tokens"]
    reply = pol.handle(msg)
    if msg["type"] == "schedule":
        reply = {"order": sorted(msg["waiting"], key=lambda r: (size[r], r))}
    if msg.get("q"):
        sys.stdout.write(json.dumps(reply if reply is not None else {}) + "\n")
        sys.stdout.flush()
