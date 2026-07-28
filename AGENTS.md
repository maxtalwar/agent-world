# Repository workflow

- After making any workspace change, run the relevant validation, commit the change, and push the branch before handing work back to the user.
- Keep commits scoped and use clear, human-readable commit messages.
- Never commit secrets, local credentials, or populated environment files.
- Never launch a long-running model-backed simulation directly from the shared
  checkout. Launch every independently executing run cell with
  `scripts/run-isolated-cohort` so it runs from its own detached worktree,
  pinned to the clean launch commit. Use a distinct cohort ID for every seed or
  simultaneous cell. Keep that worktree until the run is complete and analyzed,
  and resume checkpoints through the same cohort ID and commit. A mixed-model
  simulation is one run cell and therefore uses one worktree.
