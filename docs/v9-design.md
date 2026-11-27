# Participant v9 design — working spec

Status: first build on branch `claude/participant-v9`; recipe registered there,
not on main. Started 2026-09-22; revised 2026-11-06. Not launchable for
certification until the tuning gate below passes. v8.1 results are unaffected:
with `hidden_world_mode: "off"`, scripted v7 and v8.1 runs on seeds 11 and 41
match main byte for byte.

## Why

Opus 5.5 (89.9), Fable 5.1 (85.0), and GPT-6 Astra (80.1) have saturated the v8.1 capability
score, which is final population health out of 100. Execution is 94–97 for
the top three. v9 is a difficulty ramp: the same health-based score in a
harder world. It does not remove the ceiling, so it buys headroom rather than
ending saturation; an unbounded design is shelved below for a later version.

## Locked

1. **Low reasoning effort**, pinned per connector in the recipe and labeled
   on the board. Note: for frontier models reasoning is already a small share
   of tokens per decision (Astra 92, Fable 5.1 254 reasoning tokens against
   9,000–15,000 prompt tokens), so this buys speed and a harder ceiling more
   than it buys cost. Cost is governed by prompt size and caching.
2. **Score stays health-based capability**, as in v8.1. No consumption score
   (see Shelved).
3. **Generalists.** Keep `specialization_mode: "generalists"`.
4. **Two winters: 80 ticks with 10-tick seasons.** The run ends at the close
   of the second winter. About 33% more decisions, and so cost, than v8.1
   before any other change.
5. **No harsher exposure damage.** Winter and storm damage stay at v8.1
   values; low effort already raises difficulty, and stacking both would
   confound which change moved the scores.
6. **Hidden facts are stated plainly, never contradicted.** The rulebook says
   how each season changes production in words (for example, winter regrowth
   is much lower) but not by exactly how much, and says that some land farms
   better than other land without saying where. Season rates are the same on
   every seed. Soil quality follows the land (near water, beside mountains)
   with seeded local variation. Agents learn the details from what they
   observe.
   (Decided 2026-11-07, replacing the earlier per-seed regrowth, winter
   severity, and crop suitability settings, which contradicted the stated
   rules.)
7. **Random shocks.** Events such as drought, crop blight, or a severe winter,
   drawn per seed, so plans need buffers rather than only peak efficiency.
8. **Seed-determined worlds.** Shocks and hidden parameters are computed from
   the seed alone, before the run starts and independent of agent actions, as
   `is_storm_tick` is. They must not draw from the shared `self.rng`, whose
   sequence depends on which tiles agents have used, so models on one seed
   would drift apart. The event is matched across models; its damage is not,
   since that is what is measured. A test must prove that different agent
   actions leave the schedule and parameters unchanged.
9. **Feedback unchanged.** Learning from action feedback is part of the
   intelligence being measured, and honest feedback is how agents discover
   the hidden parameters. `action_feedback_mode` stays at the v8.1 setting.
10. **Same envelope.** Ten founding agents, two seeds (11 and 41), matched
    across models.
11. **Ranking is by the absolute score**, with per-seed values shown. No Elo:
    between pure single-model runs it adds no information, discards margins,
    and shifts historical ratings when new models enter. A draw margin is a
    display rule only, for models within seed noise of each other.

## Decisions, 2026-11-21

- **Scoring:** v9 is ranked like v8.1, on final original-population health
  minus 10% of health lost in the last winter, floored at zero
  (`endpoint-winter-damage-v9` in `data/run-sources.json`, ticks 71-80).
- **Certification:** three required seeds (11, 41, 73), given run-to-run noise
  of about 16 points on one seed.
- **Investment is in:** `participant-v9` uses `invest-v2`. Unused options are
  acceptable; they leave room for stronger models.
- **Leakage:** not a concern; seeds stay public.

Opus 5.5 on the settled world, seed 41 (`claude-opus-5-5-v9-seed41-20261121`):
all ten alive, final health 62.6, endpoint score about 61.2, Execution 93.7,
about $21 at list prices. It built one farm plot (on rich soil, tended once),
preserved food twice, and made no tools or clothing. With the seed 11 run of
the same world (about 57.4), Opus averages about 59 on v9 against 89.9 on
v8.1.

Seed 73 (`claude-opus-5-5-v9-seed73-20261121`): all ten alive but final health
29.1, endpoint score about 26.2, Execution 93.2. Seed 73 has the earliest and
longest first drought (ticks 2-15), and Opus took heavy damage in both winters
(178 and 287 health points across the population). It built two farm plots and
two storage, tended three times, and crafted nothing.

Three-seed reading for Opus 5.5 on the settled world, one run each: 57.4, 61.2,
26.2; mean about 48.3, against 89.9 on v8.1. The spread across seeds is as
large as the run-to-run noise on one seed, so a single model's mean is
uncertain by roughly +/-10 points. These are experiments, not certified
benchmark runs.

## Current build values

`participant-v9` uses `hidden_world_mode: "seeded-v3"` (in
`agent_world/hidden_world.py`) and `investment_mode: "invest-v2"`. Earlier modes stay in the code so recorded runs
remain reproducible.

- **Seasons:** described in words only; the underlying rates are unchanged
  from v8.1.
- **Soil:** each tile is poor (x0.4), normal (x1.0), or rich (x1.7) for farming.
  Land within two tiles of water scores up, land beside mountains scores down,
  and a seeded nudge per 4x4 area adds local variation. The rulebook says only
  that some land is better for farming than other land.
- **Shocks:** one of each per year from a seed-derived schedule, with no
  advance warning; an active shock appears as `season.shock`.

| Shock | Window | Length | Regrowth | Farm output |
|---|---|---|---:|---:|
| Drought | Spring-summer | 50-70% of window | x0.25 | x0.35 |
| Blight | Autumn | 30-50% | x1.0 | x0.1 |
| Cold snap | Winter | 30-50% | x0 | x0.25 |

- **Scoring:** outcome-production, revision 1, checkpoints 20/40/60/80, and a
  10-tick capability tail.
- **Build scope:** population growth, the compounding economy, tech trees, and
  commitment decisions are not in this build.

| Mode | Used by | Contents |
|---|---|---|
| `seeded-v1` | Luna, Sol, and Terra v9 pilots | Per-seed regrowth and winter factors, crop suitability x0.5-1.5, weaker shocks, rulebook hint |
| `facts-v1`, `shocks-v1` | Terra ablation | One half of `seeded-v1` each |
| `seeded-v2` | Opus 5.5 test | Crop x0.4-1.7, stronger shocks, no hint; exact season numbers that its hidden factors contradicted |
| `seeded-v3` | Current recipe | Stronger shocks, plain-word seasons, and soil that follows the land |

## Investment world (experimental)

`investment_mode: "invest-v1"` (default `"off"`) makes capital pay back over a
run without making foraging worse; wild food already has a natural ceiling of
about 3.3 food per tick of regrowth across the map. Not yet in the recipe.

- **Tools:** +50% work output (advanced: +100%), lasting 30 uses (advanced: 60),
  up from +1 output for 6 uses.
- **Farm fertility:** a farm plot gains a level every 4 uses, up to 4; each level
  adds one food per tend, and every two add one passive food.
- **Shocks spare farms:** farm output stays at least x0.8 in a drought, x0.5 in a
  blight, and unchanged in a cold snap; wild regrowth is still cut fully.
- **Preserved food:** 2 food + 1 wood make 2 preserved food that never spoils.
- **Clothing:** 3 fiber make cloth; 2 cloth + 1 fiber at a workshop make
  clothing, which cuts winter and storm exposure by 2 each and lasts 20
  exposed ticks.

The rulebook states these plainly without exact numbers. New recipes and items
stay out of the published recipe and accounting tables.

First test, Opus 5.5, full v9 (`seeded-v3`) plus `invest-v1`, seed 11
(`claude-opus-5-5-v9-invest-v1-20261111`; the launch commit's scorer rejected
the new recipes, so it was rescored after the fix into
`run-report-rescored.json`): all ten alive, final health 56.0, leaderboard
formula about 55.0, against 41.5 for the same world without investment.
Execution 94.3. Opus doubled farming (13 tends), built a workshop, wove 6
cloth from tick 16 and planned clothing but never made any, preserved food
only twice (tick 56), and made no tools. It still got most food by foraging.
Investment uptake is partial; the score gain may be partly the farm-sparing
shocks. One seed.

### invest-v2

Same capital mechanics as `invest-v1`, with three changes (2026-11-12):

- **No farm sparing:** shocks hit farms as in `seeded-v3`, except that irrigated
  farms keep at least x0.7 output in a drought.
- **Dormant winters:** all farms produce nothing in winter; irrigation no longer
  keeps them working. Irrigation still raises yield the rest of the year.
- **Folded rules:** no INVESTMENT heading. The facts sit in the existing item
  and structure lines, the winter season line says farms produce nothing, the
  irrigation line mentions droughts, and the inaccurate line that shocks hurt
  wild food more than farms is gone.

Opus 5.5, seed 11 (`claude-opus-5-5-v9-invest-v2-20261112`): nine alive (one
death at tick 79), final health 58.8, leaderboard formula about 57.4,
Execution 93.8. It barely invested: one farm plot, 7 tends, one batch of
preserved food at tick 57, no cloth, clothing, or tools, and more foraging
(170 gathered) than either earlier run. Its score was nonetheless the highest
of the three investment comparisons (no investment 41.5, invest-v1 55.0), so
the 41.5-to-57 spread on one seed is largely run-to-run variation, not
investment. With the INVESTMENT heading removed, Opus also used the new
options less, which may be a salience effect. Single runs cannot separate
these; the next step is repeat runs of one world to measure noise.

Noise check, 2026-11-20: an exact repeat of the plain v9 run (same commit,
model, and seed; `claude-opus-5-5-v9-seeded-v3-repeat2-20261112`, paused at
tick 49 for quota and sign-in and resumed from its checkpoint) scored about
25.4 (final health 27.3, all ten alive, no farming) against the original 41.5.
Two runs of the same world on one seed differ by about 16 points. The two
investment runs (55.0, 57.4) are above both plain runs, which suggests a real
gain, but two runs each cannot establish its size. Single-run differences under
roughly 15 points, including the soil (-5) and plain-word season (+3) steps of
the Opus breakdown, should be treated as noise; the shocks step (-36) is not.

## Open

1. **Evidence rate.** Whether the first-build hidden values are learnable but
   not instant. Seeds 11 and 41 have similar regrowth (x0.98 and x1.03).
2. **Shock severity and warning.** First values are above; tune them at the gate.
3. **Seed noise.** How far a shock swings a two-seed score.
4. **Population growth.** Previously locked; not yet re-decided for the
   difficulty-ramp version. If kept: maturation delay (candidate: 15 ticks),
   food cost of a birth, and a hard cap (candidate: twice the founding
   population, so a run costs at most double today). New people decide;
   there are no non-deciding dependents.
5. **Compounding economy.** Previously locked; not yet re-decided. Tools
   multiply labor, irrigation multiplies land, roads multiply transport,
   storage multiplies time, and a second material tier unlocks durable tools
   and larger structures. Each mechanic must raise the return on another;
   anything an agent can ignore without loss is removed.
6. **Commitment decisions.** A handful of irreversible choices with delayed
   payoff and no clear best: settlement site, orchard versus farm,
   specialization, trade on credit. Enough to force judgement; few enough to
   keep the rulebook readable.
7. **Prompt budget.** Measured on v8.1 ledgers: the rulebook is ~2,100 tokens
   and the observation grows from ~350 to ~1,600 tokens over a run; the CLI
   harnesses add 6,000–10,000 tokens of their own, cached. On Claude the
   rulebook already cache-hits; the cost was the observation being written to
   a one-hour cache at 2x on every call, fixed by `CLAUDE_CODE_PROMPT_CACHE_TTL=5m`
   (about 17% of a Fable run). Follow-up testing found a native Codex path:
   CLI 0.156 ephemeral forks of a static-only template read 11,008 of 11,760
   new input tokens on two of three Luna calls; one missed. The opt-in
   `shared-prefix-fork-v1` mode accounts for initialization once and subtracts
   inherited cumulative usage. It is a new conversation treatment for explicit
   recipe selection, with best-effort cache reuse rather than guaranteed savings.
   See [the diagnostic and compatibility review](codex-prompt-cache-20260922.md).
   Budget for v9: static
   rulebook at most 2,500 tokens; the observation is not capped, since capping
   it would distort agent memory.
8. **Map size.** Larger makes roads and transport matter and raises
   observation size. Undecided.
9. **Tuning gate: dropped (2026-11-27).** Two different strategies scoring
   alike does not show the world is broken; they may be equally good, or one
   may be worse but better executed. v9 does not require it.
10. **Leakage.** Hidden values are hashes of public seeds in public code, so once
    the repo is open source anyone can compute them. Fix before publishing
    results: a private salt or rotating seeds.
11. **Reasoning parity.** Opus 5.5 cannot turn thinking off, so low effort is not
    the same setting on every connector.
12. **Optional side track.** Strategy-file experiment: each model writes a plan
    from the rules, identical cheap executors play it, compared against the
    same model playing live. Measures the value of in-context adaptation. Not
    on the main board.

## Shelved

1. **Health-weighted consumption score** (previously locked). Each person,
   each tick, would count the value of goods used up a weighted ladder
   (shelter, warmth, preserved food, cloth, second-tier goods), scaled by
   health. Rejected for now: it rewards consuming more, not living well
   efficiently. A model that keeps everyone at full health on less would rank
   lower, and any fixed weights build the designers' preferences into the
   ranking.
2. **An unbounded benchmark.** The long-term direction is a world complex
   enough that no model can solve it, as no one has solved entrepreneurship.
   Caveat: chess sustains a continuous rating because difficulty comes from
   the opponent; a fixed single-player world still has an optimum however
   complex it is. Unbounded headroom probably needs difficulty from other
   agents (mixed-model populations, competing settlements), which would
   reopen the no-Elo decision above.
3. **Escalating pressure over an open horizon**, because it lengthens runs
   and cost is the binding constraint.

## Engine work implied

Done on the branch: hidden parameters, the shock schedule, 10-tick seasons over
80 ticks, the recipe, and its execution lock. Merging refreshes the shared file
hashes that every published recipe checks. Leaderboard columns are not done. If
population growth or the compounding economy stay in: new resources and a
second material tier, kiln and smithy, yield multipliers for tools,
irrigation, and roads, reproduction and maturation. Balance is the hard part
and is gated above.
