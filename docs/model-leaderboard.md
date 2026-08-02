# Agent World model-selection leaderboard

**Last updated: 2026-08-02.** This is the canonical agent-facing table for
choosing models for new Agent World benchmark runs. It contains the complete
closed Participant v6 field plus the GPT-5.6 Luna Max controlled reasoning
variant. Use this snapshot as the best cross-model evidence until Participant
v7 has a sufficiently broad replicated field.

Models are ranked by sustained competence. Scores combine the raw counts from
seeds 11 and 41 before applying the frozen formula; they are not averages of
rounded seed scores.

| Rank | Model | Execution | Competence | Entrepreneurship | Reasoning/decision | Cost/run |
|---:|---|---:|---:|---:|---:|---:|
| 1 | Fable 5 | 89.7 | 86.2 | 130.5 | ~615 tok | $57.86 |
| 2 | Opus 5 | 91.4 | 79.2 | 77.5 | ~287 tok | $24.00 |
| 3 | Opus 4.8 | 85.0 | 76.7 | 54.5 | ~1,195 tok | $30.84 |
| 4 | GPT-5.6 Sol | 88.3 | 74.4 | 26.9 | 317 tok | $19.98 |
| 5 | Sonnet 4.6 | 84.6 | 71.6 | 31.7 | ~1,765 tok | $26.44 |
| 6† | GPT-5.6 Luna Max | 88.6 | 65.1 | 34.1 | 3,773 tok | $2.96 |
| 7† | Opus 4.7 | 84.0 | 60.8 | 25.9 | ~383 tok | $17.76 |
| 8† | GPT-5.4 | 88.5 | 58.4 | 16.4 | 800 tok | $13.13 |
| 9† | Sonnet 5 | 70.5 | 49.8 | 0.0 | ~287 tok | $9.76 |
| 10† | Opus 4.6 | 84.7 | 47.3 | 0.0 | ~216 tok | $26.16 |
| 11† | GPT-5.6 Terra | 82.0 | 43.6 | 0.0 | 226 tok | $7.25 |
| 12† | GPT-5.6 Luna | 81.6 | 35.5 | 0.0 | 474 tok | $0.79 |
| 13† | GPT-5.5 | 84.6 | 34.7 | 0.0 | 19 tok | $13.12 |
| 14† | GPT-5.4 Mini | 73.5 | 26.6 | 0.0 | 1,362 tok | $3.02 |
| 15† | GPT-5.3 Codex Spark | 72.2 | 20.0 | 0.0 | 5,198 tok | unavailable |
| 16† | Haiku 4.5 | 79.8 | 0.0 | 0.0 | ~1,830 tok | $8.09 |
| 17† | GPT-5 Mini | 78.9 | 0.0 | 0.0 | 0 tok | $2.33 |
| 18† | GPT-5.4 Nano | 61.2 | 0.0 | 0.0 | 0 tok | $1.05 |

† Luna Max intentionally changes the Participant v6 reasoning effort from
medium to max. Its rank, and the shifted ranks below it, are analytical rather
than entries in the closed standard-effort v6 pool. The variant preserved the
v6 world and trial settings but launched from a newer clean commit, so do not
describe it as a standard v6 replication.

`~` marks Claude reasoning telemetry estimated under the common benchmark
estimator. `Cost/run` is the mean token-derived API-list-price equivalent for a
50-tick seed, not a subscription charge. Spark has no published matching API
rate, so its cost is not estimated by substitution.

## Practical model-selection readout

- **Highest demonstrated societal capability:** Fable 5, with the strongest
  competence and by far the strongest entrepreneurship, at the highest cost.
- **Strong standard-effort balance:** Opus 5 leads standard v6 execution and
  is second in competence at less than half Fable's estimated cost.
- **Strongest standard OpenAI result:** GPT-5.6 Sol.
- **Best demonstrated low-cost upside:** GPT-5.6 Luna Max. It is a controlled
  effort variant, but its $2.96/run result placed analytically sixth.
- **Cheap baseline or harness smoke:** standard GPT-5.6 Luna is only
  $0.79/run, but its much lower competence means it is not a substitute for
  Luna Max when model behavior is the object of study.

Model choice should still follow experimental purpose. Do not use this table
to replace matched-protocol comparisons: preserve the exact model ID,
reasoning effort, seed, provider, world preset, and launch commit required by
the study.

## Evidence and maintenance

- Fable's row includes the deterministically recovered seed-41 continuation
  and its frozen, verbatim-quote-verified
  [`gift-classifications.json`](../runs/benchmarks/claude-fable-5-participant-v6-provisional-seed11-20260729-220002/fable5-v6-seed41-recovered-tick32/gift-classifications.json).
- Luna Max provenance is recorded in its tracked
  [`study-manifest.json`](../runs/benchmarks/codex-gpt-5-6-luna-participant-v6-max-reasoning-variant-seeds11-41-20260801-135403/study-manifest.json).
- Behavioral interpretation and harness caveats live in
  [`insights.md`](insights.md); benchmark definitions live in
  [`model-benchmarks.md`](model-benchmarks.md).

When adding a model or corrected replication, update this document in the same
commit as the durable benchmark evidence. Recombine raw seed counts with the
frozen scoring formula, recalculate reasoning as total reasoning tokens divided
by total calls, and recalculate cost from each run's usage ledger. Never update
the table from a startup manifest, partial run, or arithmetic mean of rounded
seed scores.
