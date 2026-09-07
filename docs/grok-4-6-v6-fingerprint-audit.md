# Grok 4.6 Participant-v6 source-fingerprint compatibility audit

**Audit date:** 2026-09-06
**Disposition:** compatible; admit the corrected two-seed study to the canonical Participant-v6 leaderboard

## Evidence under review

- Study: `grok-4-6-grok-cli-participant-v6-fixed-seeds11-41-20260823-161608`
- Admitted v6 comparison checkout: `e8057f0044541ad3fd75f097ccda001da980d430`
- Grok launch checkout: `8bbd62e6b1bc7dc09b6239d3b6d3c4df6e59c793`
- Grok launch fingerprint: `8e68cf64dbb92792b6a5f27a860d34c44289cbec3420e8a9b5a1cb469215b6f8`
- Required seeds: 11 and 41

Both cells reached tick 50 with clean benchmark integrity, 100% usage-record
coverage, verified `grok-4.6-build` response identity, complete frozen v6 gift
classification, and API-list-price cost accounting. They used the locked v6
world and trial: ten agents, `frontier-generalists`, 50 ticks, medium reasoning,
raw decisions, `stateless-v3` plus stateless conversations, and simultaneous
turn resolution.

## Source comparison

The audit compared every commit from the admitted OpenRouter v6 checkout
through the Grok launch checkout and separately checked all behavior-defining
fingerprint files.

Of the common fingerprint core, only `benchmarks.py` and `cli.py` changed.
Those edits registered `grok_cli`, exposed Grok as a selectable model-backed
brain, and added its worker-limit field. The following world- and
behavior-defining files were unchanged: `brain_boundary.py`, `brain_runtime.py`,
`decision_failure.py`, `interface.py`, `maps.py`, `models.py`, `rules.py`,
`run_report.py`, `runner.py`, `session.py`, and `world.py`.

The other intervening changes either added the Grok provider adapter and its
registration, normalized unrelated Claude/OpenRouter response handling, added
OpenRouter price telemetry, or classified Grok failures for integrity reporting.
None changed Agent World's state transitions or v6 scoring. The Grok adapter
constructed observations through the common `build_static_context` and
`build_dynamic_observation` functions, used the common decision schema and
parser, and added only strategy-neutral coding-harness boundary instructions.

The seed-41 report retained a launch/report fingerprint mismatch because its
post-run report was generated after reporting and worker-concurrency maintenance.
The simulation itself resumed from the original pinned launch commit and
checkpoint. Worker count is operational under simultaneous turn resolution;
the reporting changes supplied the frozen gift classifier and separate API-list
cost accounting rather than changing the recorded world.

## Independent score reproduction

The current Participant-v6 scorer was applied directly to the pooled frozen raw
counts, bypassing the fingerprint admission gate. It reproduced the maintained
study result exactly:

| Metric | Reproduced score |
|---|---:|
| Effective execution | 91.45 |
| Sustained competence | 82.41 |
| Entrepreneurial agency | 92.60 |
| Economic productivity | 303.50 |

## Conclusion

The differing fingerprint reflects the addition and repair of the Grok provider
boundary plus post-run reporting maintenance, not a different Participant-v6
world or scoring standard. The corrected seeds are compatible, poolable, and
admitted as a replicated Participant-v6 result. The earlier Grok identity-bug
study remains an excluded invalid diagnostic and is not part of this result.
