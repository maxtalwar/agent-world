# Cursor Model Experiment

This study introduces Cursor-subscription models into Agent World while retaining the established medium-reasoning, baseline-feedback controls.

## Phase 1: Grok 4.5 mixed-population replication

Experiment root:

`runs/experiments/cursor-grok-mixed-six-models-30a-50t-seeds11-41-20260722-213210`

Two 50-tick replications use world seeds 11 and 41. Each civilization contains 30 agents: five Sol, five Terra, five Luna, five Opus, five Sonnet, and five Grok 4.5. Codex serves the OpenAI cohorts, Claude Code serves the Anthropic cohorts, and Cursor Agent serves Grok.

Controls are fixed at the `organic-generalists` preset, medium reasoning effort, baseline action feedback, raw decisions, stratified assignment seed 117, eight global workers, and four workers per provider. The Cursor resolver must select `cursor-grok-4.5-medium`; analysis should confirm the resolved response model rather than relying only on the requested alias.

Treat the two seeds as replications. Model comparisons should normalize failures by submitted actions and survival/economic activity by starting population. Provider, quota, structured-output, and missing-usage failures must be reported separately from agent planning errors. Primary outcomes are invalid proposals, contention, survival, movement, communication, trade, gifts, construction, asset ownership, upkeep, access policy, and institutional formation.
