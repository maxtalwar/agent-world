# Cursor Model Experiment

This study introduces Cursor-subscription models into Agent World while retaining the established medium-reasoning, baseline-feedback controls.

## Phase 1: Grok 4.5 mixed-population replication

The first launch below is retained as an audit artifact but excluded from analysis:

`runs/experiments/cursor-grok-mixed-six-models-30a-50t-seeds11-41-20260722-213210`

Cursor preflight resolved `cursor-grok-4.5-medium` on only one representative brain in each run. The other four Grok brains kept the unavailable `cursor-grok-4.5` base alias, produced decision-failure fallback waits, and contaminated both civilizations. Seed 11 was stopped after 29 completed ticks and seed 41 after 26. Their study and run manifests are marked `aborted_excluded`; do not include them in model comparisons.

The clean replacement study is:

`runs/experiments/cursor-grok-mixed-six-models-30a-50t-seeds11-41-replacement-20260722-221203`

Before launch, a five-agent Cursor smoke run produced five successful calls and all five usage records reported `cursor-grok-4.5-medium`. The replacement cells use the same seeds and controls as the excluded launch and have the automatic tick-5 health gate enabled.

Two 50-tick replications use world seeds 11 and 41. Each civilization contains 30 agents: five Sol, five Terra, five Luna, five Opus, five Sonnet, and five Grok 4.5. Codex serves the OpenAI cohorts, Claude Code serves the Anthropic cohorts, and Cursor Agent serves Grok.

Controls are fixed at the `organic-generalists` preset, medium reasoning effort, baseline action feedback, raw decisions, stratified assignment seed 117, eight global workers, and four workers per provider. The Cursor resolver must select `cursor-grok-4.5-medium`; analysis should confirm the resolved response model rather than relying only on the requested alias.

Treat the two seeds as replications. Model comparisons should normalize failures by submitted actions and survival/economic activity by starting population. Provider, quota, structured-output, and missing-usage failures must be reported separately from agent planning errors. Primary outcomes are invalid proposals, contention, survival, movement, communication, trade, gifts, construction, asset ownership, upkeep, access policy, and institutional formation.

## Startup model-health workflow

Every new CLI run now performs an automatic model-response health check after five completed ticks. It groups `agent_response` events by model cohort and inspects only harness/provider failures such as invalid structured output or a failed model call. Invalid actions and contention are deliberately excluded because they are agent behavior, not runtime health.

The run stops with `startup_health_check_failed` when a cohort has at least two failures and more than 20% of its first-five-tick responses failed. A passing run records a public `run_health_check` event so the check is auditable without a person polling the process. `--startup-health-check-tick 0` disables the gate, and the tick and threshold can be configured for specialized runs.
