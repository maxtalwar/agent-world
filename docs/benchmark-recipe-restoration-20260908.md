# Historical v6 restoration and v6.1 separation — 2026-09-08

The owner requested restoration of the historical v6 setup, a new Astra v6
benchmark, and a matched Sol comparison against the completed message-board
Astra study. Both launches use seeds 11 and 41, medium effort, ten agents,
50 ticks, and the frozen external transfer classifier.

## Historical world

`participant-v6` now explicitly selects `world_revision=frontier-v6`.
`agent_world/world_revisions/frontier_v6/` preserves world.py, interface.py,
maps.py, rules.py and the Codex action schema from historical Sol launch
`7bbff8db635a0ea32a40c9bc812ca93c7ab34d65`. Only internal module import paths
are adapted. Shared model containers and modern provider transport, quota
handling, controllers and reporting remain current. The shared Codex system
and harness instructions were compared and are unchanged. Historical
stateless-v3/stateless names are aliases of connector-v3/fresh-conversation.

This restores the original rulebook, observations, valid actions, action
feedback and state transitions. It does not merely hide the ledger UI while
leaving delivery contracts enabled. Historical code is included in the run
fingerprint and its checkpoint class is explicitly supported on resume.
The previous recipe JSON was an erroneous reconstruction: changing it here
restores its original meaning, not an authorization to revise published worlds.

## The completed message-board study

`participant-v6-1` names the setup actually used by
`web-gpt-6-astra-1dafc66aaaea` at launch `13f7616`. Its ordinary organic world
includes delivery contracts and the one-action-point, initially empty town
ledger with baseline instructions. `data/benchmark-release-aliases.json`
explicitly maps the old v6 recipe digest `78d615cd...` into the v6.1 display
group. No job, report, accepted decision, source identity or original digest
is rewritten. Sol's new v6.1 recipe makes those formerly implicit defaults
explicit. Scores remain derived from each study's own reports.

## Verification

Without model calls, replaying every recorded decision reproduced all ten
agents' endpoint health, survival, inventory and positions at tick 50 for:

- Historical Sol v6 seed 11: `gpt-5-6-sol-participant-v6-provisional-seed11-20260728-195329/seed-11`.
- Historical Sol v6 seed 41: `gpt-5-6-terra-gpt-5-6-sol-participant-v6-seeds11-41-20260729-155943/sol-v6-seed41`.
- Both seeds of `web-gpt-6-astra-1dafc66aaaea`, using the unchanged current-world implementation underlying v6.1.

The first replay is a durable regression fixture, including initial static
and dynamic prompt hashes. Tests verify no board or delivery actions in v6,
their presence in v6.1, checkpoint resume, stale-review rejection, and correct
ranking when an explicitly reviewed restoration adds a new model to v6.
`data/benchmark-release-compatibility.json` permits only the exact restored
v6 digest to extend the historical table; it never replaces existing rows or
pools different studies' seeds.

## Preventing recurrence

The portal uses registered recipes from the reviewed checkout, never old job
worktrees as alternate recipe definitions. A reviewed execution lock records
each recipe digest and the implementation source hashes. Managed benchmark
planning and actual CLI startup fail before provider calls if the definition
or implementation changes. Stale portal reviews are rejected after retirement.
Existing pinned runs can continue against their original source.

After an intentional infrastructure change, validate compatibility before
running `python3 scripts/lock-benchmark-recipes` and committing the updated
lock. Behavior changes require a new recipe. The lock is deliberately not
regenerated during launch or by the portal. Normal experiments do not require
benchmark locks. New recipes need a reviewed lock before benchmark launch.

## Authorized runs and follow-up

- `configs/benchmarks/astra-v6-restored-20260908.json`: new historical v6 Astra benchmark.
- `configs/benchmarks/sol-v61-ledger-comparison-20260908.json`: Sol v6.1 comparison against the retained Astra seeds.

On completion, compare note count per agent-tick, unique versus repeated
content, resource/need/offer/coordination content, timing, agent participation,
and subsequent trades, contracts, infrastructure and survival. Posting volume
alone does not establish useful coordination. Preserve the distinction between
model behavior and the added global communication affordance.
