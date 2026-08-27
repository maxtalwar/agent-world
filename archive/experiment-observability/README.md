# Experiment observability evidence archive

This directory preserves the historical run and report artifacts formerly kept
only on `codex/experiment-observability`. The obsolete engine, CLI, and
observatory implementation from that branch was deliberately not migrated.

## Provenance

- Source commit: `9bbd3cddbba07bb9f6cb4d1dcaa5549cc493a2be`
- Original paths: `runs/` and `reports/`
- Archived path rule: prefix every original path with
  `archive/experiment-observability/`
- Payload: 304 files totaling 4,702,909 bytes

`SOURCE-MANIFEST.tsv` records the original Git blob ID, byte count, original
path, and archived path for every migrated file. The migration validation
compared every archived file's Git blob ID with the source tree.

## Status

These are legacy research artifacts from the pre-benchmark-era experiment
framework. They include completed, partial, retried, excluded, calibration,
smoke, and tuning runs. They are evidence for `docs/research-ledger.md`, but
they are not entries in the current benchmark catalog or leaderboard and
should not be passed to current run-finalization tooling without an explicit
schema migration.

The historical `runs/catalog.json` and `runs/catalog.md` are preserved as
snapshots. The old `catalog-runs` implementation that generated them was
superseded and is not part of this archive.
