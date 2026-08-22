# Ox Alpha Participant v6 repair-oracle diagnostic

**Analyzed: 2026-08-22. Classification: normalized diagnostic only.** These
scores are not official or leaderboard-eligible because the declared
`ox-alpha-schema-v1` repair oracle modified model outputs before contract
validation.

## Result

| Seed | Execution | Competence | Entrepreneurship | Calls | Repaired | Raw valid | Valid after repair | Living at tick 50 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 11 | 70.77 | 0.0 | 0.0 | 364 | 299 | 56 | 348 | 0/10 |
| 41 | 67.38 | 0.0 | 0.0 | 350 | 245 | 71 | 308 | 0/10 |
| **Pooled** | **69.13** | **0.0** | **0.0** | **714** | **544** | **127** | **656** | **0/20** |

The frozen Participant-v6 scorer was applied to pooled raw numerators and
denominators, not to an average of the rounded seed scores. Repair raised the
contract-valid rate from 127/714 (17.8%) to 656/714 (91.9%). It intervened on
544/714 responses (76.2%), so the normalized score cannot be treated as an Ox
Alpha benchmark result.

## Interface behavior

The oracle applied 548 transformations across 544 responses:

- 528 `type=say` to `mode=say` field renames;
- 17 singleton memory-object to string-array conversions;
- 3 lossless multi-field memory-object encodings.

Fifty-eight responses still failed after normalization: 40 omitted a message
mode without exposing the repairable `type=say` form, 11 exceeded the
180-character memory limit, five emitted more than four actions, and two used
a null message recipient. All were confirmed model-output violations. There
were no provider, quota, harness, or ambiguous-boundary failures, and usage
coverage was 100%.

The combined decision latency was 7.30 seconds median, 14.81 seconds p95, and
28.21 seconds maximum. The provider recorded 2,567,053 prompt tokens, 1,626,176
cached tokens, and 177,485 completion tokens. It reported zero reasoning
tokens; that is missing reasoning telemetry, not evidence that the mandatory
reasoning model performed no internal deliberation. The cataloged route price
was $0.

## World behavior

The repaired model executed substantially more reliably than the raw schema
contract suggested, but it did not sustain either population:

- all 20 agents died; deaths began at ticks 27 and 28 and ended at ticks 46
  and 43;
- survival exposure was 71.4%, but endpoint health and living-accessible value
  were both zero;
- survival-damage records named thirst 248 times and hunger 186 times;
- the agents completed seven structures and performed 13 farm actions, but
  only eight harvests followed; upkeep was missed 19 times and paid three;
- 652 engine-invalid proposals remained across 2,016 submitted actions;
- seven trades were offered and none accepted; no group, contract,
  cooperative build, or enterprise supply emerged;
- 576 communications produced no durable coordination outcome.

This is a useful capability separation. Ox Alpha's raw interface compliance
was extremely poor, and deterministic shape repair recovered most decisions.
The repaired societies nevertheless collapsed in both seeds. The low outcome
therefore cannot be explained solely by the JSON-schema mismatch. For rough
orientation only, the normalized execution score of 69.1 falls between GPT-5.3
Codex Spark (72.2) and Qwen3.8 Max (63.1), but its zero competence and the 76.2%
intervention rate make a leaderboard rank inappropriate.

## Decision

Retain both cells as diagnostic evidence under a separate repair-oracle model
variant. Do not certify, rank, or quote 69.13 as an official Ox Alpha score.
Future testing should use a route with true strict-schema enforcement, or a
model-native adapter that can express the same contract without repairing
semantic content.
