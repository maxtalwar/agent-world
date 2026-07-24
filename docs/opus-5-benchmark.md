# Opus 5 mixed-civilization benchmark

## Question

How does Claude Opus 5 perform relative to Opus 4.8 when it replaces the Opus
cohort inside an otherwise identical mixed Agent World civilization?

## Design

The treatment study is:

`runs/experiments/opus-5-vs-4-8-mixed-30a-40t-seeds11-41-20260724-175444`

It reuses the two standard `stateless-v1` cells from:

`runs/experiments/stateless-v1-v3-civilization-30a-40t-seeds11-41-20260723-174150`

as the Opus 4.8 controls. The paired world seeds are 11 and 41. Every cell has
six Sol, six Terra, six Luna, six Opus, and six Sonnet agents and runs for 40
ticks. The only treatment change is:

- control: `6@claude:claude-opus-4-8`
- treatment: `6@claude:claude-opus-5`

All cells use `organic-generalists`, medium reasoning, baseline feedback, raw
decisions, simultaneous resolution, `stateless-v1`, stateless conversations,
stratified assignment seed 117, eight global workers, and four workers per
provider. An automatic tick-5 health gate rejects a cohort with at least two
failures and a failure rate above 20%.

Both existing controls completed tick 40 and passed the health gate. The seed
41 control had one isolated Sonnet decision failure, while its Opus 4.8 cohort
had none. The controls ran at commit `0a05b0f`; the only repository changes
between that commit and treatment launch state `cf99d93` were experiment
documentation. There were no changes under `agent_world/` or `tests/`.

## Interpretation policy

The comparison is a paired-seed replacement experiment, not 12 independent
Opus agents. Opus behavior can change the world seen by every other cohort, so
the analysis must examine both direct Opus outcomes and civilization-wide
spillovers.

Primary direct outcomes are provider reliability and latency, invalid proposals
per submitted action, contention separately, survival and death timing,
production, consumption, construction, ownership, trade, gifts, and
communication. Civilization outcomes include total survival, damage, wealth,
inequality, reserves, resource flows, entrepreneurship, commerce,
communication, cooperation, groups, institutions, and cross-cohort interaction
matrices.

Claims about Opus 5 should require the same direction across both paired seeds.
Failures must be normalized by submitted actions or decisions; economic
activity should be normalized by successful calls or starting population where
appropriate. Unchanged cohorts provide evidence about both systemic spillovers
and ordinary run-to-run variation.

## Deferred follow-up

A pure Opus 4.8 versus pure Opus 5 comparison would measure model behavior
without mixed-model interactions, but it is not required for this first
benchmark. It remains useful if the mixed study reveals an important difference
that needs cleaner attribution.
