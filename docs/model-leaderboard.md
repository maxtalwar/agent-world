# Agent World model leaderboard

Participant v8.1: medium effort, ten original agents, 60 ticks, seeds 11 and 41, no healing. This compact table contains the accepted studies admitted to the source catalog. The live dashboard also contains subsequently finalized managed studies; the [complete current rescoring report](v81-endpoint-winter-rescoring.md) compares all nine available models.

Capability rescoring: Final original-population health minus 10% of health lost during the last winter per original agent; minimum zero. Original trial identity retained (endpoint-winter-damage-v1).

| Model | Capability | Execution | Production | Cost/run | Mean time/decision |
|---|---:|---:|---:|---:|---:|
| GPT-6 Astra | 80.1 | 96.7 | 244.7 | $43.27 | 10.98s |
| GPT-5.6 Terra | 10.1 | 90.1 | 165.0 | $8.50 | 11.61s |
| GPT-5.4 Mini | 4.5 | 88.4 | 86.8 | $3.90 | 23.25s |
| GPT-5.6 Luna | 3.6 | 86.6 | 108.2 | $0.65 | 17.25s |

Original certification and provenance exceptions are unchanged. Gemini admission includes the owner-accepted evidence exception recorded in the source catalog. Cost is API-list equivalent per world, not subscription drawdown. Execution and Production are diagnostic columns, not components of Capability.

See the [rescoring definition and evidence](v81-endpoint-winter-rescoring.md), [original v8.1 projection](model-leaderboard-v81-original-score.md), and historical [v8](model-leaderboard-v8-original.md), [v7](model-leaderboard-v7.md), and [v6](model-leaderboard-v6.md).

Astra cost/run is **$43.27**, averaging $43.799260 (seed 11) and $42.741980 (seed 41), including 20 discarded attempts. See [the cost evidence](astra-v81-cost.json). Standard API-equivalent pricing uses $10/M uncached input, $1/M cached input, $12.50/M cache writes and $50/M output from the [official Astra model page](https://developers.openai.com/api/docs/models/gpt-6-astra). Reasoning is already included in output. Maximum recorded request sizes were 16,210 and 15,923 input tokens, below the 272K long-context threshold. This is not a subscription charge.
