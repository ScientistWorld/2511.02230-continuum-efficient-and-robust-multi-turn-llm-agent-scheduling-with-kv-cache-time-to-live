"""Show that every hidden-test value is recomputable from agent-visible files:
the reference's own artifacts (which `scripts/reproduce.sh` regenerates) plus
the metric list in briefing/evaluation.md.  No hidden evaluator code needed."""
import json, math, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from agent_objective import test_like_values  # noqa: E402
RT = Path(__file__).resolve().parents[1]
ref = json.loads((RT / "ref_scores_test.json").read_text())
n = bad = 0
for e, v in ref["experiments"].items():
    for meth, vals in v["results"].items():
        mine = test_like_values(RT / "ref_outputs", e, meth)
        for k, x in vals.items():
            n += 1
            if not math.isclose(mine[k], x, rel_tol=0, abs_tol=0):
                bad += 1
print(f"recomputed {n} hidden-test values from visible artifacts; mismatches: {bad}")
