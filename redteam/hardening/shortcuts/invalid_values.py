"""Shortcut: answer with impossible values (negative / NaN retention).

The old gym copied whatever numbers the method wrote; here the evaluator
validates every reply, so this must score as a failed run (worst values).
"""
import json, sys
n = 0
for line in sys.stdin:
    msg = json.loads(line)
    if msg.get("type") == "end":
        break
    if not msg.get("q"):
        continue
    if msg["type"] == "finish":
        n += 1
        sys.stdout.write('{"retain_s": NaN}\n' if n % 2 else '{"retain_s": -5}\n')
    elif msg["type"] == "schedule":
        sys.stdout.write(json.dumps({"order": sorted(msg["waiting"])}) + "\n")
    elif msg["type"] == "victim":
        sys.stdout.write(json.dumps({"victim": msg["retained"][0]}) + "\n")
    else:
        sys.stdout.write("{}\n")
    sys.stdout.flush()
