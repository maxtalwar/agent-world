# Participant v7 results — 2026-09-05

Seven replicated studies, low reasoning, seeds 11/41, 50 ticks each.
All results below are pooled from raw counts. Two seeds show sensitivity, not
a confidence interval. Cost is an API-list equivalent, not a subscription bill.

| Rank | Model | Execution | Competence | Entrepreneurship | Reasoning/decision | Cost/run |
|---:|---|---:|---:|---:|---:|---:|
| 1 | Muse Spark 1.2 | 87.1 | 65.4 | 0.0 | 1,618 tok | $13.04 |
| 2 | Grok 4.5 | 88.7 | 38.7 | 0.0 | 2,800 tok | $15.35 |
| 3 | GPT-5.6 Terra | 72.2 | 36.0 | 0.0 | 210 tok | $6.99 |
| 4 | Grok 4.6 | 86.7 | 32.6 | 0.0 | 738 tok | $10.47 |
| 5 | GPT-5.6 Luna | 77.7 | 23.3 | 0.0 | 331 tok | $0.63 |
| 6 | GPT-5.5 | 77.4 | 20.0 | 0.0 | 2 tok | $13.22 |
| 7 | GPT-5.4 Mini | 68.8 | 0.0 | 0.0 | 401 tok | $1.62 |

| Model | Survived / 20 | Structures | Trades accepted | Decision latency median / p95 (s) | Competence seed range |
|---|---:|---:|---:|---:|---:|
| Muse Spark 1.2 | 17 | 5 | 0 | 13.4 / 22.5 | 2.7 |
| Grok 4.5 | 5 | 8 | 24 | 51.2 / 100.4 | 25.9 |
| GPT-5.6 Terra | 8 | 0 | 3 | 13.1 / 22.7 | 26.8 |
| Grok 4.6 | 5 | 9 | 6 | 18.0 / 30.0 | 32.0 |
| GPT-5.6 Luna | 4 | 0 | 1 | 13.4 / 22.7 | 16.0 |
| GPT-5.5 | 3 | 1 | 0 | 8.4 / 16.6 | 28.6 |
| GPT-5.4 Mini | 0 | 0 | 4 | 14.9 / 23.5 | 0.0 |

Muse retained 17 of 20 agents and leads this field on sustained competence.
Grok 4.5 and 4.6 built more structures, but each retained only five agents.
Construction and trading activity therefore did not translate into comparable
survival. All seven entrepreneurship scores are zero; that is not the same as
no trade, since the metric also requires positive value creation.

Evidence is indexed by the seven participant-v7 model keys in
[data/run-sources.json](../data/run-sources.json), including both seed reports,
manifests, token ledgers, and hashes in the generated database. The per-model
readiness audit accepts explicit requested identity where native response
attestation is unavailable. Exact Grok callable-to-build labels were checked
against retained native sessions; no arbitrary suffix matching is allowed.

Caveats: Grok's corrected connector delivers the rulebook in the user turn.
Original missing-rulebook evidence is excluded. Cancelled native tool calls
caused preserved checkpoint retries. WSL interruption also required recovery.
Some runs have model-output failures; their quality flags are retained, while
benchmark integrity remains clean. Latency is per recorded decision, not
elapsed benchmark time, and subscription harness overhead differs.

Rates: existing OpenAI/Grok 4.6 rate-card entries are retained; Grok 4.5 adds
$2 input/$0.30 cached/$6 output per million tokens, verified against
[its official model page](https://docs.x.ai/developers/models/grok-4.5).
Muse 1.2 adds $1.25 input/$0.15 cached/$4.25 output, checked in the signed-in
[Meta pricing documentation](https://dev.meta.ai/docs/pricing-rate-limits)
during the September 5 connector investigation. All requests are below
Grok's long-context threshold. Raw CLI-reported cost remains separate.

Muse 1.1 has no score: it has not completed a tick because its service returns
429. No model substitution or v6/v7 pooling was performed.

## Interpretation caveat added after audit

The historical v6/v7 comparison is not a reasoning-only experiment. The new
town-ledger action costs one AP and its baseline prompt solicits useful notes;
it was absent from the historical v6 Grok source. Grok 4.6 spent 414 AP on
successful notes across 900 decisions (11.5% of its nominal budget). Reasoning
fell from about 3743 tokens/decision at medium in v6 to 738 at low in v7.
Neither change's causal contribution has been isolated. Grok 4.5's historical
v6 result also used Cursor and was diagnostic.

All-zero pooled entrepreneurship obscures component differences: Grok 4.5
had 123 enterprise-supply value but negative pooled living value creation;
Muse had positive value creation but no enterprise supply. Grok 4.5 seed 11
alone scored 19.96 entrepreneurship. The official pooled zero is consistent
with the formula, not evidence that no entrepreneurial actions occurred.
