# Revised v8 second batch

The user requested full benchmarks for GPT-5.5, GPT-5.6 Sol and Muse Spark 1.2.
All use participant-v8-revised, seeds 11/41, medium effort, ten agents,
60 ticks, no board, corrected capacity feedback, per-action Execution and
equal-weight Capability.

Pinned simulation source: 39232e4729d28111b794054c48895c527bf0ad07

Jobs:
- gpt-5-5-v8-revised-20260906
- gpt-5-6-sol-v8-revised-20260906
- muse-spark-1-2-v8-revised-20260906

Configs: configs/run-configs/v8-revised-20260906/.
Manifests: runs/jobs/JOB_ID/job.json.
Evidence: runs/managed/JOB_ID/seed-N/.
The managed runner records distinct cohorts, isolated source, detached sessions
and logs before returning. Seed 41 releases after seed 11's startup health gate.
Codex uses four workers per cell and ChatGPT account authentication; Muse uses
two workers and native Meta account credentials. Exact model IDs and medium
effort are explicit. No substitutions are authorized. Requested-only identity
is accepted when the native CLI does not independently echo the serving model.
API-list cost must remain separate from account/subscription cost.

The existing monitor task and 15-minute heartbeat own follow-up, with low
reasoning. Controllers own quota waits, bounded recovery and finalization.
Read status once per unfinished study; inspect each resolved startup gate once.
On ready completion verify clean integrity, all expected seeds, 100% usage,
recipe/source provenance, API-list cost and declared-transfer accounting.
Remove each verified completed study from the heartbeat prompt, and pause the
heartbeat when its worklist is empty. Do not inspect previous completed batches,
Grok or Muse Spark 1.1. Do not launch further models/seeds or admit results
from the monitor workflow.
