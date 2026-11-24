#!/bin/bash
# Shared helpers for redteam/<name>/run.sh.
#
# run_hidden_test DIR
#   Puts DIR/artifacts in place as /home/user/outputs (exactly where an agent's
#   method leaves its artifacts), optionally leaves DIR/agent_scores_test.json
#   at scoring/scores_test.json (a file the agent could leave behind), runs the
#   gym's hidden test `bash scripts/evaluate_test.sh` with NO arguments, keeps
#   whatever scoring/scores_test.json is on disk afterwards, then restores the
#   gym's outputs/ and scoring/scores_test.json.

RT="${RT:-/home/user/redteam}"
PY="${PY:-$(command -v python3 || command -v python)}"
export PYTHONPATH=/home/user:${PYTHONPATH:-}

fresh_dir() {  # fresh_dir DIR -> empties DIR/artifacts and old scores
  rm -rf "$1/artifacts" "$1/scores_test.json" "$1/scores_train.json" "$1/test_rc.txt" "$1/test_stdout.log"
}

run_hidden_test() {
  local dir="$1"
  local bak="$RT/.bak_$$"
  mkdir -p "$bak"
  cd /home/user
  cp -a outputs "$bak/outputs"
  cp -a scoring/scores_test.json "$bak/scores_test.json"
  rm -rf outputs && cp -a "$dir/artifacts" outputs
  if [ -f "$dir/agent_scores_test.json" ]; then
    cp "$dir/agent_scores_test.json" scoring/scores_test.json
  fi
  set +e
  bash scripts/evaluate_test.sh > "$dir/test_stdout.log" 2>&1
  local rc=$?
  set -e
  echo "$rc" > "$dir/test_rc.txt"
  cp scoring/scores_test.json "$dir/scores_test.json"
  # visible train slice, for context only (headline mean delay is train-only)
  bash scripts/evaluate_train.sh outputs "$dir/scores_train.json" > /dev/null 2>&1 || true
  # restore the gym's own files
  rm -rf outputs && cp -a "$bak/outputs" outputs
  cp -a "$bak/scores_test.json" scoring/scores_test.json
  rm -rf "$bak"
  echo "[$(basename "$dir")] hidden test rc=$rc"
}
