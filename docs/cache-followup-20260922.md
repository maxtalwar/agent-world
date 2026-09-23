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
