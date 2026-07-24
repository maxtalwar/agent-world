#!/usr/bin/env bash
set -euo pipefail

experiment_root="/Users/maxtalwar/Desktop/agent-world/runs/experiments/opus-5-vs-4-8-mixed-30a-40t-seeds11-41-20260724-175444"
repo_root="/Users/maxtalwar/Desktop/agent-world"

launch_cell() {
  local seed="$1"
  local cell_id="seed${seed}-opus-5"
  local screen_name="aw-opus5-40t-s${seed}"
  local out_dir="${experiment_root}/${cell_id}"

  mkdir -p "$out_dir"
  screen -dmS "$screen_name" bash -lc "cd '$repo_root' && exec python3 -m agent_world.cli run \
    --preset organic-generalists \
    --population '6@codex:gpt-5.6-sol' \
    --population '6@codex:gpt-5.6-terra' \
    --population '6@codex:gpt-5.6-luna' \
    --population '6@claude:claude-opus-5' \
    --population '6@claude:claude-sonnet-5' \
    --reasoning-effort medium \
    --connector-profile stateless-v1 \
    --conversation-mode stateless \
    --ticks 40 \
    --seed '$seed' \
    --assignment-strategy stratified \
    --assignment-seed 117 \
    --decision-mode raw \
    --action-feedback-mode baseline \
    --max-workers 8 \
    --codex-max-workers 4 \
    --claude-max-workers 4 \
    --startup-health-check-tick 5 \
    --startup-health-max-failure-rate 0.2 \
    --out '$out_dir/run.jsonl' \
    --progress > '$out_dir/run.log' 2>&1"
}

launch_cell 11
launch_cell 41
