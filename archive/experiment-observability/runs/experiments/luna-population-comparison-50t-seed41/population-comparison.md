# Luna population comparison: 20 agents vs 5 agents

Matched 50-tick runs using `gpt-5.6-luna`, low reasoning, seed 41, neutral objective, organic economy, and dispersed geography. Population was the only simulated-world variable changed.

## Results

| Metric | 20 agents | 5 agents |
|---|---:|---:|
| Living at tick 50 | 5/20 (25%) | 3/5 (60%) |
| Median lifespan | 36 | 50 |
| Agent decisions | 780 | 219 |
| Trade offers | 53 | 0 |
| Accepted trades | 3 | 0 |
| Offer conversion | 5.7% | n/a |
| Trade value | 17 | 0 |
| Gifts | 9 | 5 |
| Gifts per 100 agent-decisions | 1.15 | 2.28 |
| Invalid actions per decision | 56.2% | 51.1% |
| Groups | 0 | 0 |
| Structures | 0 | 0 |
| Wealth Gini | 0.1848 | 0.0638 |
| Model-decision failures | 5/780 (0.64%) | 2/219 (0.91%) |

The three completed physical trades in the 20-agent run were:

1. Tick 6: agent 8 gave 1 ore to agent 13 for 1 water.
2. Tick 12: agent 1 gave 1 fiber to agent 6 for 1 water.
3. Tick 33: agent 15 gave 2 fiber to agent 5 for 1 water.

All nine gifts in the 20-agent run and all five gifts in the 5-agent run were food/water aid. Neither population created groups, structures, productive assets, or construction projects.

## Interpretation

The larger population produced qualitatively different exchange behavior: agents created 53 offers and completed three real, physically settled trades, while the 5-agent population never offered a trade. This is evidence that contact and counterparty availability matter in this world.

It is not yet evidence of a mature market. Forty-nine offers expired, only 3 of 70 acceptance attempts succeeded, and the accepted exchanges were isolated water-for-material barters rather than repeat dealing, specialization, firms, or infrastructure investment. The larger run's measured division-of-labor index was also lower (0.296 vs 0.574), so stronger specialization does not explain the trade difference in this sample.

Population pressure was severe. The 20-agent world began losing agents at tick 20 and lost 75% of its population; the 5-agent world's first death was at tick 32 and it lost 40%. More potential counterparties came with substantially more competition for the same world resources.

This is one matched seed, not a causal estimate. Pair opportunities rise from 10 possible pairs with five agents to 190 with twenty agents, while total agent-decisions rose only 3.56x. Multi-seed replications are needed to distinguish population density, encounter probability, and resource pressure.

## Usage and execution quality

| Usage | 20 agents | 5 agents |
|---|---:|---:|
| Raw successful Luna calls | 805 | 217 |
| Behavior-producing successful calls | 775 | 217 |
| Raw exact credits | 164.410295 | 41.544555 |
| Behavior-producing credits | 158.171175 | 41.544555 |
| Restart overhead | 30 calls / 6.239120 credits | 0 calls / 0 credits |
| Prompt cache hit rate | 60.9% | 62.7% |
| Mean dynamic observation | 3,301 chars | 2,701 chars |

The 20-agent process was resumed twice while its worker count was raised to the previously validated value of 10. Only complete-tick checkpoints affected world behavior, but 30 successful calls from abandoned partial ticks remain in the raw usage ledger. The adjusted behavior-producing figure keeps the latest successful call for each agent/tick. The 5-agent process resumed once immediately after completing tick 25 and had no successful abandoned calls.

Because both simulations and Codex oversight overlapped, account-level plan snapshots cannot be added or assigned to either run. Across the shared window, the account meter moved approximately 52% to 81% in the five-hour window and 30% to 34% in the weekly window. Exact simulation-only usage is the credit accounting above.

## Artifacts

- `20-agents/run-report.json` and `20-agents/run-report.md`
- `20-agents/run.jsonl`, snapshot, usage ledger, checkpoint, and plan snapshots
- `5-agents/run-report.json` and `5-agents/run-report.md`
- `5-agents/run.jsonl`, snapshot, usage ledger, checkpoint, and plan snapshots
