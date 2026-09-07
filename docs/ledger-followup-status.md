# Town-ledger follow-up: findings and continuation scope

Updated 2026-09-07.

## What was learned

The earlier causal study used Luna and Sol to test ledger adoption. In the
completed 10-tick Sol seed-11 pair, the baseline produced one note and no
contracts; the explicit public-novelty decision rule produced 29 notes,
six proposed contracts, four accepted contracts, and three settled contracts.
That establishes an adoption/coordination mechanism, not a long-horizon
survival benefit. See [the causal study](ledger-affordance-causal-study.md).

The September 5 follow-up used Luna and Grok, not Sol. It crossed ledger
on/off with low/high effort for Luna and low/medium effort for Grok. All used
10 generalist agents in the frontier world, 50 ticks, seeds 11 and 41,
connector-v3, fresh conversations, raw decisions, and launch commit
`0b3173cdb60ae036ec702843d8577f20a7b68081`. Ledger-on retained the one-action-point
cost. All eight Luna cells reached 50 ticks; Grok is incomplete.

### Completed Luna results

Values separated by a slash are seed 11 / seed 41, not pooled scores.
Competence and execution are the reports' participant-v7 diagnostic metrics,
not certified leaderboard results.

| Effort | Ledger | Notes | Final survivors (of 10) | Accepted trades | Competence | Execution |
| --- | --- | --- | --- | --- | --- | --- |
| Low | Off | 0 / 0 | 3 / 1 | 0 / 0 | 31.18 / 17.92 | 78.93 / 76.62 |
| Low | On | 54 / 46 | 3 / 1 | 1 / 2 | 32.87 / 19.67 | 77.67 / 80.22 |
| High | Off | 0 / 0 | 3 / 5 | 6 / 5 | 39.06 / 46.52 | 82.53 / 85.41 |
| High | On | 160 / 163 | 6 / 2 | 7 / 3 | 39.67 / 25.50 | 83.94 / 84.00 |

At low effort, enabling the ledger modestly increased trade and competence,
with unchanged final survivor counts. At high effort, it greatly increased
posting but produced conflicting survival effects between seeds; total final
survivors remained eight across the two worlds in both conditions. Accepted
trades were ten with the ledger versus eleven without it. More communication
therefore did not reliably translate into better outcomes in these runs.
Two paired seeds cannot establish a general effect, and posting's action cost
is part of the treatment. There were 0–5 model-output failures per cell and
zero reported external-decision failures; these are diagnostic runs with model
mistakes retained, not evidence of a perfectly reliable model boundary.

Evidence: `runs/jobs/gpt-5-6-luna-{low,high}-ledger-{on,off}-20260905/job.json`
and `runs/managed/gpt-5-6-luna-{low,high}-ledger-{on,off}-20260905/seed-{11,41}/run-report.json`.
Sol evidence: `runs/experiments/ledger-affordance-causal-20260830-221534/{sol_baseline,sol_decision_rule}/run-report.json`.

## User-approved Grok continuation scope

On September 7 the user reduced medium-effort continuation to **seed 11 only**
to conserve subscription quota. This applies to both
`grok-4-6-medium-ledger-on-20260905` and
`grok-4-6-medium-ledger-off-20260905`.
Seed 41 is withdrawn from their active job cell lists and retained under
`withdrawn_cells`; full original job manifests are backed up alongside them.
The original launch config remains intact as historical provenance. Resume
only the active cells through the managed interface; never reconstruct seed 41
from the original config. Partial outputs, checkpoints and usage are preserved.

Both low-effort Grok conditions retain **seeds 11 and 41** as explicitly
requested. This scope update did not launch or resume any model calls.
