# Agent World model leaderboard

Updated 2026-09-05. Participant v7 uses low reasoning, the frontier-generalists
world, 50 ticks, and seeds 11 and 41. Seven models have completed both seeds.
Scores pool raw counts before applying the frozen formulas; ranks are by
sustained competence, independently within each protocol.

The [v6 leaderboard](model-leaderboard-v6.md) remains available separately.
Do not compare ranks across protocols. The source catalog and generated
[database](../data/model-benchmarks.sqlite) retain both fields.

## Participant v7

| Rank | Model | Execution | Competence | Entrepreneurship | Reasoning/decision | Cost/run |
|---:|---|---:|---:|---:|---:|---:|
| 1 | Muse Spark 1.2 | 87.1 | 65.4 | 0.0 | 1,618 tok | $13.04 |
| 2 | Grok 4.5 | 88.7 | 38.7 | 0.0 | 2,800 tok | $15.35 |
| 3 | GPT-5.6 Terra | 72.2 | 36.0 | 0.0 | 210 tok | $6.99 |
| 4 | Grok 4.6 | 86.7 | 32.6 | 0.0 | 738 tok | $10.47 |
| 5 | GPT-5.6 Luna | 77.7 | 23.3 | 0.0 | 331 tok | $0.63 |
| 6 | GPT-5.5 | 77.4 | 20.0 | 0.0 | 2 tok | $13.22 |
| 7 | GPT-5.4 Mini | 68.8 | 0.0 | 0.0 | 401 tok | $1.62 |

Cost/run is the mean token-derived API-list-price equivalent per seed, not the
subscription charge. Prices use the dated rate card in the database; Muse's
native injected context is included in its recorded token count. Reported
reasoning tokens are measurements, not an equal compute budget across providers.

All 14 admitted cells completed with clean benchmark integrity and full usage
coverage. Model-output quality flags remain recorded for Luna, Muse, and one
Grok 4.5 seed; these are distinct from invalid evidence. Grok used the corrected
user-turn rulebook connector. Its cancelled tool attempts and checkpoint
recoveries remain in the raw evidence; the earlier missing-rulebook trials
are excluded. Requested-only model identity is accepted for Muse/OpenAI;
Grok's exact native build response labels were reconciled explicitly.

Muse Spark 1.1 is excluded because provider 429s have prevented any completed
ticks. GPT-6 Astra, Fable 5.1, Gemini, and Muse Spark 1.3 have no completed v7
study in this batch.

See [v7 outcomes and evidence](v7-leaderboard-results-2026-09-05.md) for survival,
latency, seed sensitivity, and limitations.
