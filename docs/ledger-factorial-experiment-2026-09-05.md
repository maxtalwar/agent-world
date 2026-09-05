# Town ledger and reasoning factorial experiment — 2026-09-05

Status: predeclared diagnostic experiment; not leaderboard evidence.

The user authorized Grok 4.6 low/medium × town ledger on/off and
GPT-5.6 Luna low/high × town ledger on/off, each on matched seeds 11 and 41.
There are eight conditions and sixteen independent cells. Every cell uses
the participant-v7 recipe as experiment defaults: frontier-generalists,
10 agents, 16×16 world, 50 ticks, 12-tick seasons, fresh connector-v3
conversations, raw decisions, and self-declared transfer kinds. The horizon
retains the late survival collapse observed in the earlier studies.

Board on retains the current baseline instruction, public observations, and
one-AP posting action. Board off removes all three and rejects posting.
This estimates the combined feature effect, not the independent effects of
wording, information sharing, and opportunity cost. No other world or prompt
treatment is introduced. Existing benchmark recipes and results are preserved.
Both on and off are newly run from one clean commit, including the existing
Grok tool exclusions. Historical leaderboard cells are not reused as controls.

Configs are in configs/run-configs/ledger-factorial-20260905. Managed job
manifests record the exact clean source commit, cohort, requested model,
connector, resolved defaults, and owned output paths before model calls.
The native Grok CLI may report grok-4.6-build; Codex requested-only identity
is accepted and labelled honestly under the existing policy.
Each cell uses one worker; aggregate concurrency is at most sixteen model
requests across both providers. Quota pauses preserve the same checkpoint
with a twelve-hour allowance. Startup health gates and recovery are managed.

Primary comparisons: paired-seed changes in survival and sustained competence;
execution, health, signed living-value creation, enterprise supply, trade,
production/building, and action allocation explain the outcomes. Report
entrepreneurship components alongside its pooled score to expose floor effects.
For Grok compare board effects at each effort and the effort-by-board interaction;
repeat for Luna low/high. Report actual reasoning tokens, usage coverage,
provider/model-output failures, and API-list cost separately from subscription
charges. Two seeds establish exploratory evidence, not precise uncertainty.

Do not alter or rebuild the official leaderboard until the user chooses the
next protocol based on these results. Any changed published recipe needs a
new identity; preserve the current v7 evidence under its original identity.
