# Matched v6.1 ledger comparison - 2026-09-08

Astra posted 5.72 times as many town-ledger notes as Sol, but Sol completed more formal trades. Astra built more structures and retained more health. Posting volume alone does not establish useful coordination or explain the survival difference.

Both restoration-batch jobs are ready with seeds 11/41 complete. The Sol terminal event passed a one-time finalize --dry-run audit: clean integrity, 100% usage, complete frozen transfer accounting, requested-only model provenance, and no blockers. No leaderboard admission is made.

The comparison follows [the handoff](benchmark-recipe-restoration-20260908.md): Sol sol-v61-ledger-comparison-20260908 versus retained Astra web-gpt-6-astra-1dafc66aaaea. Both use ten agents, 50 ticks, matched seeds, medium effort, an initially empty one-AP global board and delivery contracts. Sol pins d813d711; Astra pins 13f7616. The handoff documents replay equivalence and the historical recipe alias. Restored v6 is a separate world and is not pooled here. Original reports and provenance remain untouched.

The metrics database passed verification (89 runs, no integrity or foreign-key errors). The exact Astra managed ID was not returned by the run-ID query; this comparison relies on its ready manifest and original artifacts, not assumed database admission.

## Frozen per-seed scores

| Model / seed | Execution | Competence | Enterprise | Productivity | Alive | Health / original agent |
|---|---:|---:|---:|---:|---:|---:|
| Sol / 11 | 89.32 | 88.2 | 110.86 | 248.88 | 10/10 | 65.7 |
| Sol / 41 | 89.45 | 73.14 | 109.22 | 180.75 | 9/10 | 31.6 |
| Astra / 11 | 96.73 | 96.96 | 105.61 | 507.0 | 10/10 | 88.8 |
| Astra / 41 | 94.84 | 93.19 | 135.34 | 426.0 | 10/10 | 72.8 |

Scores are copied from frozen reports, without averaging rounded seed scores. All four cells are ready with clean integrity and full usage coverage. Requested-only model provenance is retained.

## Notes and content

| Model / seed | Notes | Notes / agent-tick | Unique bodies | Near repeats | Resource | Need | Offer | Coordination | Notes by successive ten-tick blocks |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Sol / 11 | 43 | 0.086 | 43 | 2 | 35 | 13 | 9 | 18 | 14 / 10 / 6 / 9 / 4 |
| Sol / 41 | 44 | 0.088 | 44 | 2 | 43 | 14 | 17 | 18 | 15 / 9 / 6 / 7 / 7 |
| Astra / 11 | 243 | 0.486 | 243 | 1 | 231 | 110 | 25 | 210 | 50 / 48 / 44 / 51 / 50 |
| Astra / 41 | 255 | 0.510 | 255 | 2 | 248 | 95 | 16 | 214 | 50 / 54 / 57 / 45 / 49 |

Categories are overlapping lexical screens, not human semantic labels. Exact uniqueness normalizes body case/whitespace; near repetition means SequenceMatcher similarity >=0.85 to an earlier body within the seed. Patterns and all note texts are retained in the evidence. All bodies are exactly unique, but recurring updates change quantities, locations, skills and access status. String uniqueness is not proof of new information.

All ten agents posted in each world. Sol agents posted 3-6 times in seed 11 and 3-7 in seed 41; Astra agents posted 22-28 and 23-31. Astra maintained roughly five notes per world tick. Sol front-loaded resource discovery, followed by episodic offers, shelter needs and urgent requests. Denominators use the report-defined 500 observed agent-ticks per seed. Sol seed 41 has 498 decisions after a late death: its rate per actual decision is 44/498=0.0884 instead of 0.088 per report agent-tick.

## Subsequent outcomes and episodes

Sol recorded 68 offer-trade and 15 accept-trade events versus Astra's one offer and zero acceptances. These event counts are not a deduplicated bargain-conversion estimate. Sol built 13 structures with 28 contributions; Astra built 30 with 59. Sol had 34 gift events versus Astra's 39; frozen classifications, not these raw event labels, govern scored consideration. Sol retained 19/20 agents and 48.65 health per original agent; Astra retained 20/20 and 80.8.

Astra seed 41: agent-5 posted a shared-shelter proposal at tick 11 and updated requirements at ticks 12-13. The ledger records its wood/fiber contribution at tick 12 (line 851), agent-3's two stone at tick 13 (line 915), then agent-5's final wood and three-agent shelter completion (lines 925-926). The tick-14 note accurately reported completion. Local speech and observations were also available, so this correspondence does not prove a board effect.

Sol seed 41: agent-7's tick-45 note directed agent-8 to carry two stone west to structure-4 at [2,0]. Agent-8 contributed exactly that stone and completed the two-agent shelter at tick 47 (lines 3602-3603). Sol therefore showed task-specific board use despite lower posting volume. An earlier stone contract was proposed at tick 27, accepted at 28 and defaulted at 29; a second proposal at 32 was cancelled. Neither model completed a contract in these worlds.

The supported distinction is sustained public infrastructure/status reporting versus sparse situational reporting, alongside more formal trade for Sol and more construction/survival for Astra. Two seeds do not establish causality or a general model ranking.

## Evidence and reproduction

Run python3 scripts/compare-v61-ledger.py to regenerate [source hashes, every note, per-agent counts, categories and line-numbered economic events](v61-ledger-comparison-20260908.json). [The script](../scripts/compare-v61-ledger.py) retains original source paths and recipe digests. Inputs are the original ledgers, reports, usage records, manifests and frozen classifications.

## Cost and latency

| Model / seed | API-list USD | Median recorded decision seconds |
|---|---:|---:|
| Sol / 11 | 24.71 | 24.12 |
| Sol / 41 | 24.94 | 25.06 |
| Astra / 11 | 40.69 | 12.63 |
| Astra / 41 | 39.86 | 13.23 |

Cost is API-list equivalent, not subscription spending. Latency is recorded end-to-end call duration, including adapter retry time where present, not world runtime.
