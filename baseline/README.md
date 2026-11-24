# Baselines

The comparison baselines are owned by the evaluator so that every method is
measured against the same fixed reference points: `eval/train/baselines.py`
(visible) and an independent copy in `eval/test/`.

* `vllm` -- end-of-turn release + request-level FCFS (vLLM default).
* `program_fcfs` -- end-of-turn release + program-level FCFS.
* `plas` -- Autellix program-level attained service (least service first).
* `infercept` -- InferCept-style preserve-or-swap (offload experiments).

Run `bash scripts/baseline.sh` to score only the baselines on the train traces.
