# Repository workflow

- After making any workspace change, run the relevant validation, commit the change, and push the branch before handing work back to the user.
- Keep commits scoped and use clear, human-readable commit messages.
- Never commit secrets, local credentials, or populated environment files.

# Research data

- Preserve every simulation run's raw events, snapshot, manifest, report, usage log, and checkpoint. Never overwrite or delete a degraded run; mark exclusions and write retries to a new directory.
- After analyzing a run or experiment, append the question, exact artifact paths, design, findings, uncertainty, decision, and next question to `docs/research-ledger.md`.
- Refresh the derived local run index with `python3 -m agent_world.cli catalog-runs` when run artifacts are added or moved.
