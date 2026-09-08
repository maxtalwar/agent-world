# Haiku 4.5 v8.1 admission — 2026-09-08

The repository owner explicitly approved standard benchmark admission after
reviewing the recovery deviation: eight previously generated but uncommitted
decisions per seed were lost during quota recovery and regenerated. Completed
simulation ticks and original conditions were preserved. The replacement
responses were not selected based on their outcomes.

This decision supersedes the pending admission decision in
[the Claude provenance review](claude-v81-provenance-20260908.md). Both seeds
completed tick 60 with clean integrity, verified model identity, full usage
coverage and complete transfer accounting. The recorded source migration and
partial-tick resampling remain disclosed; no original report, event, usage
record or checkpoint is rewritten. This is a specific owner acceptance, not
a general waiver for other runs or other integrity failures.

## Accepted report identities

```json
[
  {
    "report_path": "runs/managed/web-claude-haiku-4-5-20251001-cdc35c0408ed/seed-11/run-report.json",
    "report_sha256": "8e2a7dcd5b557e18e7717beeaa112ae6f3497ed5ac183ab637c8fabf785b4f90",
    "run_id": "web-claude-haiku-4-5-20251001-cdc35c0408ed",
    "seed": 11,
    "model": "claude-haiku-4-5-20251001",
    "recipe": "participant-v8-revised",
    "recipe_sha256": "8de610d3cd050f86bf4fb5e16a04708e069d099435b41d2729b4717d9a0da006",
    "approved_by": "Repository owner",
    "approved_at": "2026-09-08",
    "reason": "Owner approved standard admission with disclosed quota-recovery source migration and regeneration of eight unfinished decisions per seed. Completed ticks and original evidence preserved.",
    "review_path": "docs/reviews/haiku-v81-admission-20260908.md"
  },
  {
    "report_path": "runs/managed/web-claude-haiku-4-5-20251001-cdc35c0408ed/seed-41/run-report.json",
    "report_sha256": "7db9a708d12f5940667a5033831ce10377ff1e06a7a7256135b21033a8723373",
    "run_id": "web-claude-haiku-4-5-20251001-cdc35c0408ed",
    "seed": 41,
    "model": "claude-haiku-4-5-20251001",
    "recipe": "participant-v8-revised",
    "recipe_sha256": "8de610d3cd050f86bf4fb5e16a04708e069d099435b41d2729b4717d9a0da006",
    "approved_by": "Repository owner",
    "approved_at": "2026-09-08",
    "reason": "Owner approved standard admission with disclosed quota-recovery source migration and regeneration of eight unfinished decisions per seed. Completed ticks and original evidence preserved.",
    "review_path": "docs/reviews/haiku-v81-admission-20260908.md"
  }
]
```
