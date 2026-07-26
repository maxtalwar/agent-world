# GPT-5.3-Codex-Spark Participant v3 benchmark

## Result

The 2026-07-26 seed-11 trial is a **provisional Participant v3 benchmark**.
It completed all 50 ticks with 100% usage-ledger coverage and no quota,
provider, or harness failures.

| Primary benchmark | Score |
|---|---:|
| **Planning execution** | **66.64** |
| **Sustained competence** | **32.68** |
| **Entrepreneurial agency** | **2.12** |

The run recorded two malformed structured responses among 415 decision attempts
(0.48%). Under Participant v3 scoring revision 2, each is counted as one
invalid proposal attributable to the model. The surviving errors point inside
the returned `arguments_json` strings—one has no JSON value at character 0 and
one lacks a comma at character 32—so model contract violation remains the
high-confidence interpretation. The launch version did not retain the exact raw
responses, however, so revision 4 cannot independently replay them and absolute
attribution is unavailable. This legacy limitation is disclosed rather than
silently reclassifying the run.

## Supporting results

| Measure | Seed 11 |
|---|---:|
| Decisions | 415 |
| Submitted actions | 1,336 |
| Contention failures | 5 |
| Engine-invalid proposals | 442 |
| Malformed model outputs | 2 |
| Total scored invalid proposals | 444 (33.23% of submitted actions) |
| Action-point overruns | 44 |
| Survivors | 2 / 10 |
| Endpoint population health | 94 / 1,000 |
| Living-accessible terminal value | 45 |
| Total terminal value, including dead estates | 221 |
| Venture initiatives | 3 trade offers |
| Realized venture value | 3 |
| Accepted trades | 1 |
| Gifts / structures / groups | 0 / 0 / 0 |

## Trajectory and civilization

The civilization deteriorated after an initially plausible subsistence phase.
At tick 30, nine agents remained and sustained competence was 72.47. By tick
40, only six remained and competence had fallen to 55.97. At the official
tick-50 endpoint only two survived, with 94 total health, and competence fell
to 32.68.

Planning quality also declined from 69.17 at tick 30 to 66.64 at tick 50.
The dominant failures were repeated attempts to obtain unavailable water,
fiber, food, ore, and stone, plus action-point overruns. Same-tick contention
was rare, so the failure rate primarily reflects Spark's own planning rather
than unlucky simultaneous resolution.

There was almost no institutional or entrepreneurial development: no
structures, construction contributions, gifts, groups, claims, access fees, or
contracts. Three direct trade offers produced one accepted food-for-water
exchange worth three book-value units. Communication was limited to 11
whispers. The resulting society was therefore a fragmented, mobile
subsistence population rather than an accumulating or cooperative
civilization.

## Classification migration

The run launched under the initial Participant v3 source fingerprint. Scoring
revision 2 does not alter its world, prompts, fallback behavior, event ledger,
or civilization trajectory. It only distinguishes target-model malformed
output from external trial-integrity failures and adds those two failures to
the invalid-proposal numerator. The old fingerprint is explicitly allowlisted
for this one compatible migration; the report records that compatibility
instead of pretending the source fingerprints match.

The run artifacts are under
`runs/benchmarks/gpt-5-3-codex-spark-participant-v3-provisional-seed11-20260726-011031`.
