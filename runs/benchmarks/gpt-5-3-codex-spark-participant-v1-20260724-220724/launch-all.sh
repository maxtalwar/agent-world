#!/usr/bin/env bash
set -euo pipefail

benchmark_root="/Users/maxtalwar/Desktop/agent-world/runs/benchmarks/gpt-5-3-codex-spark-participant-v1-20260724-220724"
repo_root="/Users/maxtalwar/Desktop/agent-world"

launch_seed() {
  local seed="$1"
  local out_dir="${benchmark_root}/seed-${seed}"
  local screen_name="aw-bench-spark-s${seed}"

  mkdir -p "$out_dir"
  screen -dmS "$screen_name" bash -lc "cd '$repo_root' && exec python3 -m agent_world.cli run \
    --benchmark-protocol participant-v1 \
    --brain codex \
    --model gpt-5.3-codex-spark \
    --seed '$seed' \
    --out '$out_dir/run.jsonl' \
    --snapshot '$out_dir/run-snapshot.json' \
    --progress > '$out_dir/run.log' 2>&1"
}

launch_seed 11
launch_seed 41
