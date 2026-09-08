# Claude v8.1 provenance review — 2026-09-08

## Sonnet 5: admitted after infrastructure review

Both seeds reached tick 60. The sole trial and cohort quality flag is
`benchmark_code_fingerprint_mismatch`. Integrity is clean, usage coverage is
100%, model identity is verified, and declared transfer accounting is complete.

Reviewed `git diff f10ee284c840 0a9fe7ac3f77 -- agent_world`: the only changed
simulation-package file is `session.py`. It resets the quota wait allowance
at successful ticks, preserves lifetime wait totals, and avoids retrying before
a known reset when the allowance expires. No engine rules, observations,
prompts, action schemas, model/effort settings, recipe or scoring changed.
No accepted decisions were resampled in these Sonnet recoveries. Each recorded
pre-recovery event prefix still matches the completed event log byte for byte.
This is an infrastructure compatibility review under the user's instruction
to complete routine provenance reviews automatically, not an invented owner
exception. Original reports and fingerprints remain unchanged.

[
  {
    "seed": 11,
    "report_path": "runs/managed/web-claude-sonnet-5-f8f540cb1847/seed-11/run-report.json",
    "report_sha256": "7f1e77b30d77161ef2a7ce971ef021f72a8db9885730b7e02d5783e1323ea073",
    "recovery_path": "runs/jobs/web-claude-sonnet-5-f8f540cb1847/source-recovery/quota-windows-seed-11/recovery.json",
    "recovery_sha256": "6cade2ed7c495fd6fb7f8ac27ed73ced632d8840982138d7a43d86d3a0911ad9",
    "prefix_bytes": 3974743,
    "prefix_sha256": "a70a9e695c1f69774a99f4a080d5ea4e7ba0914890ff2c9110102327ec9102b1",
    "recipe_sha256": "8de610d3cd050f86bf4fb5e16a04708e069d099435b41d2729b4717d9a0da006"
  },
  {
    "seed": 41,
    "report_path": "runs/managed/web-claude-sonnet-5-f8f540cb1847/seed-41/run-report.json",
    "report_sha256": "0562ee5caae6d6909573d6e50da22d6a312e4181a885e49073d856949d58f431",
    "recovery_path": "runs/jobs/web-claude-sonnet-5-f8f540cb1847/source-recovery/quota-windows-seed-41/recovery.json",
    "recovery_sha256": "d9e464c311de65589ec3f16460b4b964e3eef487d769a43d518618799f3d5f85",
    "prefix_bytes": 3335694,
    "prefix_sha256": "ccf818d8e9e0e2de7b8304332c6b90a75101f723c6667414b0e0c7e5e67e9f5d",
    "recipe_sha256": "8de610d3cd050f86bf4fb5e16a04708e069d099435b41d2729b4717d9a0da006"
  }
]

## Haiku 4.5: an actual recovery deviation

Both seeds completed with clean integrity and full usage coverage. Their
quota repair additionally regenerated eight previously accepted but uncommitted
decisions per seed after the pending-decision cache was invalidated by the
source migration. Completed event prefixes are preserved and verified, but
this is not an unchanged-decision source migration. The previous authorization
explicitly classified this as `diagnostic_with_declared_deviation`.

Keep that classification pending a specific owner decision to admit results
with the resampling disclosed. Do not describe it as missing logs, failed
simulation completion, or an infrastructure review that has not been done.
Evidence: each job cell's `source_recovery_record`, including
`resampling_deviation` and archived partial-tick usage hashes.
