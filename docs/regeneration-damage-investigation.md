# Does healing conceal damage? — 2026-09-07

## Finding

It can, and Gemini is the clearest observed example: its health score rises
82.66 → 88.55 while total actual damage barely changes (946 → 938 HP across two
worlds). Restored health accounts for 5.16 of the 5.89 score-point improvement
(87.6%). Survival also improves 17 → 20 of 20 original agents. This is real
recovery value, but it should not be described as a comparable improvement in
damage prevention.

All four Codex treatments take less damage than their controls in both seeds;
their health gains include damage amount/timing improvements as well as healing.
The two Gemini seeds differ. Seed 11 takes **more** damage with healing
(282 → 380 HP), restores 151 HP, and nevertheless improves health score
90.06 → 91.84 and survivors 9 → 10. Seed 41 reduces damage 664 → 558 HP,
restores 206 HP and improves score 75.26 → 85.26. The pooled near-constant
damage therefore combines a worse-damage trajectory with a better one; it
should not be interpreted as both seeds repeating the same behavior.

No current treatment is at the ceiling. This investigation does not establish
whether more capable models will converge near 100 in a healing world.

## Matched evidence

Five models, two conditions, two seeds (11 and 41): twenty completed 60-tick
worlds with ten initial agents, medium reasoning and matching v8.1 world settings.
Only the three regeneration fields differ in the world configuration. The
healing prompt also describes the new rule, and decisions are newly sampled;
this is not a replay of identical behavior. Controls were run earlier, so
provider/time variation remains a limitation.

Gemini's healing worlds are now complete, superseding the tick-44 interim
comparison in [the previous report](regeneration-expanded-results.md). All
completed reports have clean integrity and 100% usage coverage. Healing runs
remain diagnostic experiments, not newly admitted benchmark results.

## Actual damage and recovery

Actual damage means HP lost, clipped to remaining health. A nominal 10-point
hit on an agent with 3 HP counts as 3 HP lost; nominal damage is separately
retained in the evidence artifact. Values below are totals across two worlds
(20 initial agents), not per-survivor averages.

| Model | Damage off → on, HP | HP restored with healing | Survivors off → on | Health score off → on |
|---|---:|---:|---:|---:|
| GPT-5.6 Sol | 1165 → 1010 | 382 | 20 → 19 | 77.61 → 85.94 |
| GPT-5.6 Terra | 1702 → 1415 | 261 | 11 → 18 | 66.05 → 76.33 |
| GPT-5.6 Luna | 1834 → 1587 | 99 | 8 → 14 | 64.12 → 69.48 |
| GPT-5.4 Mini | 1839 → 1686 | 114 | 6 → 11 | 55.90 → 62.49 |
| Gemini 3.7 Flash | 946 → 938 | 357 | 17 → 20 | 82.66 → 88.55 |

Without healing, cumulative actual damage is algebraically just initial health
minus final health. It adds no independent endpoint information there. Its use
here is to separate gross harm from restored health in the healing conditions.
With healing, initial HP − damage + restored HP exactly equals final HP for
every one of the 200 agents.

## Deaths do not make low damage automatically good

Damage totals stop growing after death. A dead population can therefore appear
to take less damage simply because it has fewer living agents exposed to it.
We retain all original agents, report deaths alongside damage, and inspect two
additional views rather than inventing a death penalty for a replacement score.

| Model | Damage per 100 living-agent ticks, off → on | First 24 ticks' damage, off → on |
|---|---:|---:|
| GPT-5.6 Sol | 97.08 → 84.24 | 160 → 25 |
| GPT-5.6 Terra | 157.16 → 120.73 | 280 → 197 |
| GPT-5.6 Luna | 169.97 → 144.54 | 317 → 332 |
| GPT-5.4 Mini | 200.11 → 173.46 | 593 → 511 |
| Gemini 3.7 Flash | 80.03 → 78.17 | 114 → 100 |

Living exposure counts the start of each tick, including a tick in which the
agent dies; it reconciles to completed decision opportunities. This denominator
is not the report's `observed_agent_ticks`, which retains the original population
for health scoring. The exposure-normalized rate improves for every model,
although survivor composition still makes it descriptive rather than causal.

No agent dies in the first 24 completed ticks (event ticks 0–23), so that common
prefix has identical exposure. Luna is an informative exception there: damage
increases 317 → 332 even though its full-run total falls. The treatment is not
uniformly better at prevention at every stage. Nominal, unclipped full-run
damage also falls for every model, so the main result is not an overkill-clipping
artifact. None of these views makes cumulative damage alone a safe ranking metric.

## Where do the health-score gains come from?

An exact accounting identity separates the existing score into damage and
healing components. For a completed T-tick world with N original agents:

`health score = 100 − sum(damage[t] × (T − t))/(N × T) + sum(healing[t] × (T − t))/(N × T)`

Ticks are zero-based and damage/healing are actual HP changes. An early loss or
recovery contributes to more subsequent health observations. Dead slots remain
zero. This identity matches all twenty reported raw health totals exactly.

| Model | Total score gain | Change in damage amount/timing component | Restored-health component |
|---|---:|---:|---:|
| GPT-5.6 Sol | +8.33 | +4.28 | +4.05 |
| GPT-5.6 Terra | +10.28 | +6.50 | +3.78 |
| GPT-5.6 Luna | +5.36 | +3.30 | +2.06 |
| GPT-5.4 Mini | +6.59 | +4.85 | +1.74 |
| Gemini 3.7 Flash | +5.89 | +0.73 | +5.16 |

These are bookkeeping components, not experimentally isolated causal effects.
Healing changes survival, resource use and later decisions, which can change
future damage. Subtracting the healing component does **not** simulate what the
same agents would have done without healing; some would have died earlier.

The distinction changes how to interpret widening gaps. Sol's advantage over
Mini grows by 1.74 score points, but Sol's extra weighted healing contributes
2.31 points of separation. The damage amount/timing component offsets 0.57
points of that widening. Thus the wider score gap is not evidence of a wider
damage-prevention gap in these runs. Sol versus Luna has both effects; Terra
versus Luna also shows a substantial widening in the damage component.

Gemini's 357 restored HP contribute more score credit than Sol's 382 restored
HP (5.16 versus 4.05 points), because timing matters: earlier restoration remains
in more health observations. Total healed HP alone cannot explain score effects.

## Completed Gemini versus Sol

Gemini's full-run lead over Sol narrows from **5.05 to 2.61 points** with healing,
but Gemini still leads (88.55 versus 85.94). Gemini takes 938 HP damage compared
with Sol's 1,010, and ends with 20 survivors compared with Sol's 19. Final
original-population health is 70.95% versus 68.60%. The original hypothesis that
healing would reward Sol's greater survival enough to overtake Gemini is not
supported by these two treatment seeds: Gemini now preserves its whole population.

This is an observed comparison in this world, not a claim about general model
intelligence. Only 5/20 Gemini agents and 1/20 Sol agents finish at or above 90 HP;
Terra has 1/20 and Luna/Mini 0/20. Present results do not exhibit universal
near-full-health saturation. They cannot rule it out for future stronger models.

## Interpretation

Keep the v8.1 recipe unchanged while deciding the next design. The investigation
shows why recovery and prevention should be discussed separately: Gemini gets
most of its score lift by recovering, while the Codex treatments also improve
the damage component substantially. Whether recovery should earn that credit is
an objective choice, not a mechanical bug or something settled by gap size.

Cumulative damage is a useful diagnostic, but replacing health with it would
introduce its own death/exposure problems. The evidence does not yet require a
longer benchmark or more paid experiments. Astra's separately authorized v8.1
run will add a stronger-model observation in the unchanged, irreversible-damage
world; it is not a matched Astra healing experiment.

## Reproduction and audit

Run `python3 scripts/analyze-regeneration-damage.py --output /tmp/regeneration-damage.json`
from the repository root. No provider calls occur. The script uses the prior
trajectory artifact solely as the explicit cell inventory, then reads current
completed reports and event ledgers. It verifies completion, coverage, configuration
matching, live decision exposure, 200 per-agent health balances, exact endpoint
health/survivor counts and full-horizon score identities. Paths and source/report/
ledger hashes are retained in [the detailed output](regeneration-damage-analysis.json).
Nominal damage, per-agent deaths, live exposure and all health/damage/healing
curves remain available there. Cause counts can overlap within one damage event;
they are not mutually exclusive damage amounts.
