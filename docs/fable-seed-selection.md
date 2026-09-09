# Fable single-seed selection

2026-09-09. User requested a single Fable world to conserve subscription quota. Choose seed **41** for future Fable benchmarks, including 5.1; pause and retain seed 11 of the active Fable 5 study. Explicit seed choices override the default. This changes launch scope, not recipe identity or certification rules. A single completed seed is provisional, not replicated.

## Evidence and method

Verified `data/model-benchmarks.sqlite` (95 runs, integrity OK), then included the additional accepted managed studies exposed on the v8.1 leaderboard. Compare all 13 completed paired models under the same v8.1 endpoint/winter score. Exclude Fable and incomplete Gemini 3.8; do not choose using the target model’s observed performance. Each model has equal weight. The [evidence table](fable-seed-selection.json) records individual scores and source hashes.

| Model | Seed 11 | Seed 41 | Paired |
|---|---:|---:|---:|
| GPT-6 Astra | 81.39 | 78.82 | 80.11 |
| Gemini 3.7 Flash | 70.37 | 30.20 | 50.28 |
| GPT-5.6 Sol | 32.80 | 43.01 | 37.91 |
| Grok 4.6 | 40.02 | 26.04 | 33.03 |
| Gemini 3.6 Flash | 38.37 | 26.86 | 32.62 |
| Sonnet 5 | 42.28 | 15.64 | 28.96 |
| Muse Spark 1.2 | 23.83 | 25.93 | 24.88 |
| Muse Spark 1.3 | 20.44 | 18.23 | 19.34 |
| GPT-5.6 Terra | 15.16 | 5.02 | 10.09 |
| GPT-5.5 | 7.46 | 4.05 | 5.75 |
| GPT-5.4 Mini | 7.67 | 1.41 | 4.54 |
| GPT-5.6 Luna | 9.35 | 0.00 | 3.56 |
| Haiku 4.5 | 0.00 | 0.00 | 0.00 |

Seed 41 reverses 4 of the 78 pairwise model comparisons relative to the paired ranking; seed 11 reverses 8. Seed 41 also ties Luna and Haiku at zero although their paired scores differ. These counts use unrounded values.

Seed 11 has a +4.47 point mean difference from the paired score; seed 41 has −4.30. Mean absolute differences are 5.41 and 5.24 respectively. Do not interpret the small absolute-error advantage as evidence of neutrality: with two seeds their distances from the arithmetic mean are identical before the zero floor. The discrepancy here arises from applying the score floor after pooling raw counts.

Seed 41 is therefore a pragmatic choice for preserving the overall ordering, and a somewhat harder observed world, not a proven unbiased world. Its most consequential reversal is Sol above Gemini 3.7. Seed 11 also reverses important comparisons, including Sol versus Grok, Gemini 3.6 and Sonnet. Choosing after examining this dataset is exploratory and not an independent validation. There are no repeat runs within a seed to separate map difficulty from model response randomness. Do not calibrate or inflate Fable’s score by the average seed difference. For direct comparisons, show the other models’ seed-41 scores alongside Fable; retain the ordinary paired leaderboard results.

No additional provider calls were made for this analysis. Original reports and benchmark results are unchanged.
