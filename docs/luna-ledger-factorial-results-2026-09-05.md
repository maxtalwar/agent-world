# Luna reasoning × town ledger results — 2026-09-05

Eight completed diagnostic runs: low/high × board off/on × seeds 11/41,
10 agents, 50 ticks, participant-v7 world defaults. All launched from
0b3173cdb60ae036ec702843d8577f20a7b68081. No leaderboard admission or recipe change.

## Results

Scores pool raw numerators and denominators across seeds before applying
agent_world.benchmarks.score_benchmark_counts with participant-v7.
Counts below sum both worlds; health is out of 2,000 starting health capacity.
API-list costs are for both runs combined, not subscription charges.

| Reasoning | Board | Execution | Competence | Survivors /20 | Health | Signed living-value change | Accepted trades | Completed farms | API-list cost |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Low | Off | 77.83 | 25.29 | 4 | 79 | -178.0 | 0 | 0 | $0.79 |
| Low | On | 78.92 | 27.17 | 4 | 99 | -170.0 | 3 | 0 | $1.08 |
| High | Off | 84.00 | 43.01 | 8 | 230 | -31.0 | 11 | 5 | $1.75 |
| High | On | 83.97 | 33.29 | 8 | 96 | -102.5 | 10 | 1 | $2.29 |

All four pooled entrepreneurship scores are zero because signed living-value
creation is negative. Enterprise supply is 2, 7, 14, and 17 respectively.
High/off seed 41 has positive value creation (+11.5) and entrepreneurship
4.8; pooling loses that positive result. Zero does not mean no commerce.

## Board effect

At low effort, board on raises competence by 1.88 points, with unchanged
survival, slightly more health, and three rather than zero accepted trades.
It does not repair low-effort performance.

At high effort, board on lowers pooled competence by 9.72 points. Survivor
totals match, but health falls 230 to 96 (58% lower), and living terminal value
falls 239 to 167.5 (30% lower). Five farms become one; successful harvest
events fall from 25 to two and farming events from 17 to one. Chopping falls
30 to four. The board condition has 908 successful moves versus 681, 396
gathers versus 334, and 387 waits versus 504. These are event counts, not
normalized action rates; board on also retains more lifetime decisions
(941 versus 896). Completed trades remain similar (10 versus 11), as do
offers (43 versus 42) and gifts (27 each). More public information did not
produce more completed commerce in these worlds.

High-effort agents post 323 notes versus 100 at low effort. At one AP per
note, this consumes 8.58% versus 2.92% of four AP per recorded decision.
Sampled notes report resource coordinates, depleted deposits, trade offers,
and urgent needs. This is real use of the feature, but observing posts does
not establish that recipients used them successfully. The treatment combines
the baseline instruction to post, global information access, and posting
cost; it cannot isolate which component caused the behavioral shift.

The interpretation is consistent with communication and movement displacing
some productive investment, but is not a demonstrated causal mechanism.
There is no measured counterfactual showing how the posting AP would be spent.

## Seed sensitivity and reasoning interaction

| Condition | Competence seed 11 /41 | Survivors seed 11 /41 | Health seed 11 /41 | First death tick 11 /41 |
|---|---|---|---|---|
| Low/off | 31.18 /17.92 | 3 /1 | 60 /19 | 32 /27 |
| Low/on | 32.87 /19.67 | 3 /1 | 67 /32 | 27 /28 |
| High/off | 39.06 /46.52 | 3 /5 | 112 /118 | 26 /26 |
| High/on | 39.67 /25.50 | 6 /2 | 67 /29 | 39 /35 |

High reasoning improves competence in every matched seed/board comparison.
Its pooled gain is +17.72 with board off and +6.12 with board on.
The pooled difference-in-differences is -11.60 points; the paired-seed
interaction differences are -1.08 and -22.77. This is exploratory interaction
evidence, heavily influenced by seed 41, not a precise estimated effect.

At high effort, board on delays first deaths in both worlds. It adds three
endpoint survivors in seed 11 but loses three in seed 41. Endpoint health
falls in both. Thus the board cannot simply be described as killing agents;
it changes the timing and distribution of survival and productive activity.

## Reasoning and accounting

Actual reasoning tokens per decision are 298 (low/off), 332 (low/on),
1,104 (high/off), and 1,286 (high/on). High effort uses roughly 3.7–3.9 times
as much recorded reasoning. Median end-to-end decision latency is 10.0,
10.8, 21.8, and 24.5 seconds respectively. Cost totals use the repository's
summarize_usd_cost and existing rate card; all eight runs total about $5.91
at equivalent API list prices. No new pricing claim or subscription charge
is inferred.

Every run reached tick 50 with a run_completed event, clean benchmark-integrity
status, and 100% distinct tick/agent usage coverage. Model-output failures
remain recorded: 7 low/off, 2 low/on, 1 high/off, 1 high/on. They differ from
provider or harness failures; none of the latter compromised these runs.
All world configs match except seed and town_ledger_output_mode. All use
self_declared transfers, one worker, and fresh connector-v3 conversations.
Model and effort identity are requested_only, consistent with the accepted
Codex CLI policy. Reports carry benchmark_protocol_not_declared and a missing
benchmark fingerprint mismatch because they are experiments, not certified
trials; these do not indicate divergent launch sources.

## Implications

The board is not the main explanation for Luna's weak low-reasoning scores:
removing it does not improve those outcomes. High reasoning matters much more.
For this model, high/off is the strongest pooled condition and develops
substantially more agricultural production. These results support trying a
board-free world for the next benchmark design, but do not establish that
medium reasoning will be sufficient: Luna medium was not tested. They also
do not establish the Grok effect, whose factorial study remains incomplete.

Keep the existing v7 results under their original recipe identity. Any future
published benchmark with changed mechanics or effort needs a new recipe ID.
No additional model runs are authorized by this report.

## Evidence

[Machine-readable counts, scores, and source hashes](luna-ledger-factorial-evidence-2026-09-05.json)
retain the per-seed metrics, reliability, action counts, and API-list accounting.
Each source is runs/managed/gpt-5-6-luna-{low,high}-ledger-{off,on}-20260905/seed-{11,41}/
with run-report.json, run-manifest.json, run.jsonl, and run-usage.jsonl.
[Predeclared design](ledger-factorial-experiment-2026-09-05.md).
