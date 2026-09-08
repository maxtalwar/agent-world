# v8.1 endpoint health and winter damage rescoring

2026-09-07. Reanalysis of the existing completed, accepted v8.1 worlds, seeds 11 and 41. No simulations were rerun. This is a separately versioned score projection (`endpoint-winter-damage-v1`), not a change to the historical recipe or its certification.

## Definition

**Capability = max(0, final health per original agent − 0.10 × winter health lost per original agent).**

Dead agents retain their original population slots and contribute zero. Pool the raw health totals across both required worlds before rounding. Winter damage already reduces final health; the additional term makes it count 1.1 times as much as damage outside winter. Damage before winter receives no winter surcharge.

The last complete winter consists of action ticks 36–47: health immediately before action 36 minus health immediately after action 47 (the completed-state boundary at 48). Earlier damage is present on both boundaries and cancels. The source worlds have no healing, so this boundary difference is actual health lost, including deaths, rather than a net damage/healing approximation. This projection rejects healing-enabled worlds and different recipe identities.

The initially considered 30% surcharge would clip Mini, GPT-5.5 and Luna to zero. The deployed 10% surcharge is a modest explicit weighting that avoids this observed floor effect; it is a design choice, not an empirically validated optimal weight. Future near-total failures can still hit the zero floor.

## Scores

| Model | Original full-run mean | Final health | Winter health lost | New capability |
|---|---:|---:|---:|---:|
| GPT-6 Astra | 92.38 | 81.25 | 11.45 | 80.11 |
| Gemini 3.7 Flash | 82.66 | 52.70 | 24.15 | 50.29 |
| GPT-5.6 Sol | 77.61 | 41.75 | 38.45 | 37.91 |
| Gemini 3.6 Flash | 76.02 | 36.70 | 40.85 | 32.62 |
| Muse Spark 1.2 | 74.36 | 28.60 | 37.20 | 24.88 |
| GPT-5.6 Terra | 66.05 | 14.90 | 48.10 | 10.09 |
| GPT-5.5 | 56.43 | 9.50 | 37.45 | 5.76 |
| GPT-5.4 Mini | 55.90 | 8.05 | 35.10 | 4.54 |
| GPT-5.6 Luna | 64.12 | 8.30 | 47.35 | 3.57 |

Astra has completed and is included in this dashboard snapshot. Original ordering among the top six is unchanged. Luna falls behind GPT-5.5 and Mini. The Gemini 3.7–Sol gap changes from 5.05 under the original full-run mean to 10.95 under endpoint health alone, then 12.38 with the winter surcharge. Most of that change comes from selecting the endpoint, not the winter weight.

These scores answer a different question from the old average; the numerical drop is not evidence that the models became less capable.

## Winter-weight sensitivity

| Model | Endpoint only | 10% extra | 20% extra | 30% extra |
|---|---:|---:|---:|---:|
| GPT-6 Astra | 81.25 | 80.11 | 78.96 | 77.81 |
| Gemini 3.7 Flash | 52.70 | 50.29 | 47.87 | 45.46 |
| GPT-5.6 Sol | 41.75 | 37.91 | 34.06 | 30.21 |
| Gemini 3.6 Flash | 36.70 | 32.62 | 28.53 | 24.45 |
| Muse Spark 1.2 | 28.60 | 24.88 | 21.16 | 17.44 |
| GPT-5.6 Terra | 14.90 | 10.09 | 5.28 | 0.47 |
| GPT-5.5 | 9.50 | 5.75 | 2.01 | 0.00 |
| GPT-5.4 Mini | 8.05 | 4.54 | 1.03 | 0.00 |
| GPT-5.6 Luna | 8.30 | 3.57 | 0.00 | 0.00 |

## Evidence and reproducibility

The [machine-readable reanalysis](v81-endpoint-winter-rescoring.json) contains source report paths and hashes, event hashes, original health curves, pooled counts and the exact policy. Reconstruction must agree with the frozen endpoint and full-run health totals. Original reports, recipe digests and acceptance decisions are retained.

The source-catalog database retains frozen results in `model_results` and adds `model_score_reanalyses` for this projection. `production_leaderboard` selects the applicable new score. The web dashboard applies the same helper to its accepted managed studies, which include additional studies not yet in the compact source-catalog projection.

See [terminal supplies comparison](sol-gemini-terminal-supplies.md) for what the health score does not capture.
