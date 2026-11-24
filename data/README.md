# Data

No external data.  Agent traces are synthetic and generated in memory by the
evaluator: `eval/train/workloads.py` (public train seeds) and an independent
copy in `eval/test/` (hidden seeds).  Program shapes follow Table 1 of the paper
(turns, tokens per program); tool calls come from named tools with long-tailed
durations whose parameters are re-drawn for every trace.  To inspect a train
trace: `python -c "from eval.train.evaluate import _trace; print(_trace('bfcl_scaled_no_offload', 0)[0])"`.
