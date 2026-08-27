# Run records

This directory contains the local simulation evidence base.

Git tracks the compact research record:

- run and experiment manifests
- machine-readable and human-readable reports
- aggregate summaries, comparisons, and statistical analyses
- the generated run catalog

Git intentionally does not track event JSONL, per-call usage JSONL, snapshots,
checkpoints, plan-usage captures, or console logs. Those files are canonical raw
artifacts but grow too quickly for ordinary Git history. They remain local until a
remote artifact archive is configured.

Never overwrite or delete a degraded run. Record its exclusion in the research ledger
and write any retry to a new directory. Rebuild this directory's derived index with:

```bash
python3 -m agent_world.cli catalog-runs
```

Interpretations and evidence pointers belong in
[`docs/research-ledger.md`](../docs/research-ledger.md).
