# First v8 ranking audit — 2026-09-05 Pacific

This is an offline diagnostic of admitted v6 and v8 evidence. No model calls,
new replications, scoring changes, or retrospective leaderboard edits were
performed. Independent population-health sums reproduce the scoring counts;
recomputed Capability and Execution reproduce every published v8 seed score.

Reproduce: python3 scripts/audit-v8-first-cohort.py /tmp/v8-first-cohort-audit.json

The [machine-readable audit](v8-first-cohort-audit.json) includes per-seed
components, health trajectories, original recipes, settings, source hashes,
reasoning telemetry, and action/error counts. Historical rescoring and shorter
prefixes are diagnostic comparisons, not additional benchmark trials.

## Execution measures whole-plan reliability and favors shorter plans

| Model | Actions/decision | V8 Execution | Legacy action-feasibility diagnostic |
|---|---:|---:|---:|
| GPT-5.4 Mini | 1.68 | 65.30 | 75.59 |
| GPT-5.5 | 3.54 | 52.00 | 81.28 |
| GPT-5.6 Luna | 2.79 | 63.09 | 81.76 |
| GPT-5.6 Terra | 3.33 | 63.31 | 83.08 |

Action feasibility uses the repository's legacy raw invalid-proposal and
submitted-action counts, with contention excluded. It is a diagnostic,
not a replacement official score, and includes legacy penalty conventions.

The whole-plan rule deliberately prevents easy-action padding from diluting
errors: one bad item fails a decision. But short plans have fewer opportunities
to fail; useful valid work before or after a bad item earns no headline credit.
Short plans can leave AP unused. Plan length therefore confounds interpretation
as broad execution ability.

Not all extra actions are ambitious work: 5.5 proposed 1,184 waits out of 3,278
actions; Mini proposed 219 out of 1,476. Removing waits still leaves 5.5 with
2,094 other actions versus Mini's 1,257. Seventeen 5.5 decisions fail only
because of invalid waits, accounting for 1.84 points, not the entire gap.

The strongest control uses the old v6 evidence: rescoring identical decisions
with the new whole-plan rule yields Mini 66.49, Terra 61.90, Luna 60.07, and
5.5 57.49. This execution inversion exists without new model responses.
Old headline Execution also included purposeful activity; its scale and
ranking are not interchangeable with whole-plan reliability.

## Capability is sensitive to late survival in collapsing worlds

| Model | Mean health, ticks 1–60 | Mean health, ticks 49–60 | Capability |
|---|---:|---:|---:|
| GPT-5.4 Mini | 50.28 | 7.55 | 19.49 |
| GPT-5.5 | 51.71 | 4.53 | 15.30 |
| GPT-5.6 Luna | 56.88 | 1.38 | 8.86 |
| GPT-5.6 Terra | 61.13 | 16.17 | 31.44 |

The formula is sqrt(full-horizon mean health * final-season mean health).
Mini has the weakest full-horizon health, but retains more late health than
5.5 and Luna. Across two worlds, Mini ends with five survivors, versus five
for 5.5, one for Luna, and eight for Terra. Endpoint total health is 115 for
Mini, 71 for 5.5, and 1 for Luna, out of 2,000 possible.

Mini leads 5.5 and Luna on final Capability in both seeds; one exceptional seed
does not explain it. Two worlds still cannot establish a stable model ranking.

Using the same formula on the first 50 ticks of these v8 runs, with ticks
39–50 as the tail, gives Terra 45.11, Luna 34.77, 5.5 32.15, Mini 31.86.
These are prefix diagnostics, not hypothetical new 50-tick trials.
The tick-60 ordering depends heavily on the extra ten ticks and shifted tail.

Mini built no structures. 5.5 completed four farms; Luna one farm; Terra five
farms and a shelter. Production ranks Mini last. This distinguishes late
survival from productive development. No arithmetic error was found.
The concern is construct validity: whether late population health deserves
the broad headline name and determines the row order.

## Misleading feedback is a real environment defect

World._action_work in agent_world/world.py first confirms source resources
exist, then clamps extraction quantity by _carry_room. If that becomes zero,
the failure can say “No water is available.” (or another resource) instead of
identifying carrying capacity.

The runs contain 211 such errors for Mini, 153 for 5.5, 184 for Luna, and 230
for Terra. All requested positive quantities; these errors trace to carrying
capacity rather than zero-quantity requests. Observations expose capacity,
but explicit feedback points toward the wrong remedy. This shared defect does
not establish its causal contribution to the ranking, nor a different rulebook
for different models.

## Connector and effort checks

All eight v8 cells share the same source, recipe, world settings apart from
seed, connector-v3/fresh-conversation boundary, medium request, and recorded
static-prompt hash:
b0bd9f0d40224a72f93e4be099e65f75a2b44298106121c7f417ab84dabe0a4d.

The Codex connector passes exact model and effort generically. Integrity and
usage checks pass. Identity remains requested-only under the accepted policy;
that is not independent confirmation of what the provider served.

Recorded reasoning tokens per call differ: Mini about 1,150, Luna 510,
Terra 284, and 5.5 48. The same qualitative difference exists in v6
(Mini about 1,360 versus 5.5 about 19), so it does not by itself explain
the new inversion. Named medium is not equal computation.
No new missing-rulebook or model-specific effort hardcoding was found.

V6 and v8 raw world settings match except the added board/transfer controls,
but prompt hashes, source revisions, dates, and horizons differ. Historical
versus current runs cannot isolate any one of those changes.

## Recommendation

Review the benchmark design without tuning it to a preferred model ranking.
Fix capacity feedback with explicit new source/recipe provenance. Reconsider
whole-plan success as headline Execution; evaluate partial action credit per
decision with explicit controls for no-ops and padding. If across-run survival
is the intended capability construct, consider full-horizon health as the
headline component and final-season health as a diagnostic.

Do not immediately shorten the world just to reverse this result: late
collapse is real information. First test whether feedback, survival difficulty,
and recovery opportunities make the extra horizon a useful resilience test
or mostly a collapse threshold. Existing results remain frozen. Changes to
published recipes require a new recipe ID; additional model experiments need
authorization and the repository seed policy.
