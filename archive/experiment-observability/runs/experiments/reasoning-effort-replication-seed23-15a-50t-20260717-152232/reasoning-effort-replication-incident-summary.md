# Seed 23 reasoning replication — aborted and excluded

## Question and design

The planned comparison was low versus medium versus high reasoning for a matched
population of five `gpt-5.6-sol`, five `gpt-5.6-terra`, and five `gpt-5.6-luna`
agents, 50 ticks, world seed 23, assignment seed 117, `organic-generalists`,
`compact-v2`, raw decisions, and `simultaneous-v1` turns.

## What happened

The user reported an OpenAI status page showing `gpt-5.6-sol` server-overload
errors. The first three conditions completed their tick targets but were degraded
by provider failures: low had 6 failures, medium 10, and high 10. New sequential
retries reduced but did not remove the problem: low had 1 failure and medium had 5.
The high retry was stopped at tick 42/50 at the user's request and is recorded as
interrupted; its preserved report has no terminal run event.

All six directories retain their raw event stream, snapshot, checkpoint, manifest,
report, usage log, and run log. The high retry manifest was reconciled to its
interrupted state after shutdown so the catalog does not show a live run.

## Decision

This is not valid comparison data. Do not pool or interpret outcome differences
across reasoning conditions. The six attempts consumed 2629.918607 exact
simulation credits in total, but those credits bought degraded observations rather
than a usable experiment.

## Next question

After Sol capacity is healthy, does the same low/medium/high ordering replicate on
a fresh matched seed with zero provider failures and complete usage coverage?
