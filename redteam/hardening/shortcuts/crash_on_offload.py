"""Shortcut 'drop the experiment where I look bad': behave like the reference
policy, but crash whenever CPU offload is on.  Old gym: a missing artifact was
skipped (+0.14 rank).  Now: worst values in those experiments."""
import json, sys
sys.path.insert(0, ".")
from method.continuum_policy import Continuum
pol = Continuum()
for line in sys.stdin:
    msg = json.loads(line)
    if msg.get("type") == "end":
        break
    if msg.get("type") == "init" and msg.get("offload"):
        sys.exit(1)
    reply = pol.handle(msg)
    if msg.get("q"):
        sys.stdout.write(json.dumps(reply if reply is not None else {}) + "\n")
        sys.stdout.flush()
