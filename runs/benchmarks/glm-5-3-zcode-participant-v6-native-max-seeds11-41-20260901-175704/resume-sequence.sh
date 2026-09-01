#!/usr/bin/env bash
set -euo pipefail

exec > >(tee -a /home/maxtalwar/agent-world/.worktrees/features/glm53-zcode-v6/runs/benchmarks/glm-5-3-zcode-participant-v6-native-max-seeds11-41-20260901-175704/resume-supervisor.log) 2>&1

cd /home/maxtalwar/agent-world/.worktrees/features/glm53-zcode-v6

scripts/run-isolated-cohort \
  --cohort glm53-zcode-v6-fixed-s41-20260901 \
  --commit e16492dc76f873388a9c197e4286bb44d555d903 \
  -- \
  python3 -m agent_world.cli run \
    --resume-checkpoint runs/benchmarks/glm-5-3-zcode-participant-v6-native-max-seeds11-41-20260901-175704/glm-5-3-zcode-v6-seed41/run-checkpoint.pkl \
    --ticks 50 \
    --quota-wait-hours 12 \
    --progress

scripts/run-isolated-cohort \
  --cohort glm53-zcode-v6-fixed-s11-20260901 \
  --commit e16492dc76f873388a9c197e4286bb44d555d903 \
  -- \
  python3 -m agent_world.cli run \
    --resume-checkpoint runs/benchmarks/glm-5-3-zcode-participant-v6-native-max-seeds11-41-20260901-175704/glm-5-3-zcode-v6-seed11/run-checkpoint.pkl \
    --ticks 50 \
    --quota-wait-hours 12 \
    --progress
