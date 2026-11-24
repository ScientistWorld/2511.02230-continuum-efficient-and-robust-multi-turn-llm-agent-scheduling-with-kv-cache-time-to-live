# Scientist Constraints

## Interface

A method is a scheduling policy declared by `method/policies/<name>.json` and driven over the line-delimited JSON
protocol in `briefing/evaluation.md`. The evaluator (`eval/`) owns the serving engine, the traces, the baselines and
every scored number. It never reads files, numbers or verdicts written by a method.

## Fixed engine and workloads

GPU KV capacity, prefill/reload/decode timing, the offload model, trace generation, arrival rates and the baselines are
part of the evaluator and must not be changed. The paper's claim is about the serving policy, not about a larger GPU,
cheaper misses or an easier workload.

## Information available to a policy

Only what the engine sends: past arrivals, finishes, observed tool durations (after the tool returns), queue state.
Do not read trace generators, seeds or evaluator internals to learn future tool durations or arrivals. Hidden-test
traces exist only inside the evaluator.

## Failure is scored, not skipped

A method that crashes, hangs, breaks the protocol, returns impossible values or leaves any program unfinished gets the
worst value of every metric in that experiment. Every method on disk is scored in every experiment.

## Compliance Checklist

- [ ] Policy speaks the protocol in `briefing/evaluation.md` and finishes every program
- [ ] `eval/` and `data/` are unchanged and do not import from `method/`
- [ ] No access to trace generators, seeds or future information
- [ ] Scores come from `scripts/evaluate_train.sh` / `scripts/evaluate_test.sh`, not from method-written files
