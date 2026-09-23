# Interleaved cache follow-up and Claude TTL savings

## Preregistered scope

Two managed diagnostic passes use participant-v8-revised world defaults,
seed 11, 20 agents, one tick, one worker, Codex CLI 0.156.0, medium effort,
and shared-prefix-fork-v1. In lexicographic decision order, the first pass
alternates Astra/Sol; the second alternates Sol/Astra. Every agent observation
is therefore tested once by each model. All calls share identical static
rulebook content. Each pass initializes one template per model: 40 decisions
and four initializations in total. No additional seeds or full benchmarks.
First-pass templates are not reused in the second pass.

Check actual chronological model order, paired request hashes, static hashes,
unique fork sessions and delta usage. Compare full-prefix, partial-prefix,
and zero-read frequencies, normalized by each model's template input size;
different native model instructions may still yield different token counts.
Record start/end times and per-model gaps. This controls rulebook and coarse
call ordering, not hidden routing, model-native prompts, or wall-time equality.
Two template groups per model are not independent statistical replications.

Estimate Claude savings offline from cataloged native Claude Code benchmark
ledgers: Fable 5.1 v8-revised seed 41 and Opus 5[1m] v8-revised seeds 11/41.
Retain each seed separately; using existing replications spends no calls.
Also include older Fable 5 and Opus 5 v6 records as labeled supplementary
historical estimates if their usage coverage supports it. Do not substitute
OpenRouter evidence or relabel historical results.

Hold each ledger's input/output/cache token counts fixed and price writes
at 2x versus 1.25x base input. Report the historical leaderboard's already-1.25x
column separately from an inferred 1-hour baseline. Check TTL provenance;
if historical per-duration counters are absent, label that baseline conditional
rather than claiming a verified historical charge. Shorter TTL may increase
rewrites after idle gaps, which the fixed-token calculation does not predict.
No subscription-quota conversion and no behavioral-performance claims.
Transfer accounting is not needed for this token-cost diagnostic.

## Completed interleaved result

Both passes completed at tick 1 from source
5ccd2fa82f4c38fc56743a1905a13f422242b4db. All 20 counterbalanced observation
hashes match, with model assignment reversed and the chronological model order
verified. All 40 decision calls share static hash
b0bd9f0d40224a72f93e4be099e65f75a2b44298106121c7f417ab84dabe0a4d.
There are 40 unique child sessions and four template initializations.

| Pass | Astra near-template / partial / miss | Sol near-template / partial / miss |
| --- | ---: | ---: |
| Astra first | 10 / 0 / 0 | 10 / 0 / 0 |
| Sol first, observations swapped | 7 / 2 / 1 | 7 / 2 / 1 |
| Total | 17 / 2 / 1 | 17 / 2 / 1 |

Astra's near-template reads were 14,336 tokens against a 14,504-token template;
its partial reads were 10,880. Sol's were 13,056 against a 13,290-token template,
with partial reads of 9,856. Each model reused roughly 91% of template tokens
on average across both passes. A byte-identical Agent World rulebook does not
require equal token totals across model-native CLI prompts and tokenizers.

The two zero-read calls occurred consecutively late in the second pass, about
14 seconds apart; partial hits followed for both models. Same-model idle gaps
were only 8.5-30.5 seconds. This was not a long idle break. The symmetric
aggregate result and clustered degradation do not support a persistent Astra
caching advantage. They are consistent with time-varying cache availability
or routing, but counters cannot reveal the root cause. Because Sol's rulebook
also changed from the earlier study, this is not a clean causal attribution
of that earlier difference to routing alone.

All 40 decisions parsed successfully, with 100% usage coverage and no
provider/harness/quota failures. Action-level invalid rates were 1.0% and 2.2%;
those small first-tick behavioral differences are not performance conclusions.
The four initializations plus decisions cost $1.421000 API equivalent. Exact
models were requested natively; Codex did not independently report resolved
response-model identities. No Claude calls were needed for the ledger analysis.

## Updated savings versus benchmark costs

Applying this follow-up's hit frequencies with the method below gives:

| Model and historical baseline | Recorded benchmark | Projected fork run | Saving |
| --- | ---: | ---: | ---: |
| Astra v8-revised seed 11, 600 decisions | $43.80 | $30.63 | $13.17 / 30.1% |
| Sol v6 seed 11, 500 decisions | $14.69 | $11.47 | $3.23 / 22.0% |

The first pass's all-hit pattern alone would suggest about 43%/34% savings;
the second pass's pattern suggests about 17%/10%. The pooled 30%/22% values
are working estimates, not confidence intervals or guaranteed savings.
They replace the earlier sample's 43%/3% estimates as the latest frequency
sensitivity, while preserving the original measurements. Runs with normal
parallelism, different routing load, restarts, and longer histories remain
untested. Two template groups per model are not enough for strong statistical
claims. No full benchmark, scoring result, price card, or leaderboard changed.

## Claude: conditional savings against historical runs

The canonical database verified successfully: 105 runs, 47,211 decisions,
zero foreign-key errors. The selected v8-revised ledgers have complete
cache-write counts and exact native Claude model identities. Their five-minute
repricing reproduces each stored benchmark cost within $0.000002.

| Native model and benchmark | Calls | Conditional 1h cost | 5m cost | Saving |
| --- | ---: | ---: | ---: | ---: |
| Fable 5.1, v8-revised seed 41 | 600 | $69.48 | $53.99 | $15.49 / 22.3% |
| Fable 5, v8-revised seed 41 | 600 | $95.64 | $76.90 | $18.73 / 19.6% |
| Opus 5[1m], v8-revised seed 11 | 589 | $40.80 | $33.01 | $7.80 / 19.1% |
| Opus 5[1m], v8-revised seed 41 | 594 | $42.60 | $33.94 | $8.66 / 20.3% |

**The historical leaderboard already uses the 5m column.** These savings are
relative to a reconstructed one-hour-cache baseline, not another discount
from the displayed leaderboard number. For Fable 5.1 that means $69.48 to
$53.99, not $53.99 to a still-lower number.

The precise formula is recorded cache-write tokens times 0.75 times the base
input rate, divided by one million. Read tokens, uncached input and output
remain unchanged. Fable 5.1 uses $10 input/$0.25 cached/$50 output; Fable 5 uses
$10/$1/$50; Opus 5 uses $5/$0.50/$25. Writes change from 2x to 1.25x input.
This is a full-ledger estimate, unlike the earlier rough 17% Fable estimate.
No pricing change or output-token reduction is credited to caching.

Historical ledgers retained total writes but discarded the provider's nested
5m/1h counters; they did not snapshot the TTL environment setting. Therefore
the assumption that all original writes used one hour is not independently
verified. Current official Claude Code documentation says subscription
main-conversation calls default to one hour; the local configuration now
explicitly sets CLAUDE_CODE_PROMPT_CACHE_TTL=5m. That supports the mechanism,
but does not retroactively prove each benchmark request's TTL.

If only half the historical writes were one-hour writes, the dollar savings
would halve. If all were already five-minute writes, TTL savings would be zero.
Shorter expiry can also introduce extra rewrites after idle periods; this
fixed-token estimate does not model those. These are API-equivalent figures,
not measured subscription-quota consumption or actual charges.

The old Fable 5 and Opus 5 v6 ledgers lack cache-write counts on every row.
Their TTL savings are **unavailable**, not zero; no substitute model, provider,
or inferred write count is used.

Sources checked 2026-09-22:
[Claude cache pricing](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)
and [Claude Code TTL selection](https://code.claude.com/docs/en/prompt-caching).

## Codex estimation method

The follow-up changes both models to the same v8-revised rulebook. Sol's
historical comparison remains its v6 benchmark; the two recipes are not
pooled. To update the earlier run-cost approximation, transfer only the new
hit-class frequencies to the original model-specific prefix sizes, keeping
the prior matched startup input budget, historical prompt growth, historical
output budget, and one cold initialization unchanged.

A near-template read means cached tokens are within 256 tokens of the
template input length, allowing cache-block rounding. It is a proxy, not
wire-level proof of the exact cached text. Such hits map to the earlier
observed prefix lengths (14,336 Astra; 12,928 Sol). Zero reads map to zero;
partial reads must match an earlier observed partial boundary or analysis
stops for review. The follow-up found a new 10,880-token partial boundary on
Astra. Review confirmed the same static hash, CLI and 14,504-token template
size as the original Astra diagnostic, so that boundary transfers directly.
This avoids treating Sol's longer v8 prefix as a free
increase in the cacheable v6 rulebook. Updated costs remain scenarios based
on a small sample, not measured full-run reductions.

## Reproduction

Run `python3 scripts/analyze_cache_followup.py --output docs/cache-followup-20260922.json`.
The analyzer verifies terminal state, chronological interleaving, matched
observation hashes with swapped model assignment, shared source/static hashes,
unique fork sessions, template ownership, delta usage, and historical price
reproduction. It records artifact hashes and preserves unknown Claude write
coverage. The `--claude-only` option needs no diagnostic runs or model calls.
See the generated [measurement artifact](cache-followup-20260922.json).
