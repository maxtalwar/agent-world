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
6. **Hidden facts are plain-word season rules.** The rulebook says how each
   season changes production in words (for example, winter regrowth is much
   lower) but not by exactly how much. Production rules are the same on every
   seed and across the map; there are no secret per-seed or per-area
   multipliers. Agents learn the size of each effect from what they observe.
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

## Current build values

`participant-v9` uses `hidden_world_mode: "seeded-v3"` (in
`agent_world/hidden_world.py`). Earlier modes stay in the code so recorded runs
remain reproducible.

- **Seasons:** described in words only; the underlying rates are unchanged
  from v8.1.
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
| `seeded-v3` | Current recipe | Stronger shocks and plain-word seasons only |

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
9. **Tuning gate.** Before any paid run: play the world with the scripted
   brain and one cheap model, and require that two different reasonable plans
   diverge in score. If they converge, the judgement is not real and the
   parameters go back for revision.
   First check, 2026-11-06: not passed. `SurvivalBrain` loses all ten agents on
   both seeds even under v8.1 settings, so it cannot show divergence. The gate
   needs scripted plans that survive, or a stronger model.
   GPT-6 Luna pilot, seed 11, 2026-11-06 (`gpt-6-luna-v9-pilot-20261106`): the
   world ran cleanly to tick 80 with no harness failures, but all ten agents
   died between ticks 30 and 74 with no structures built. 36% of actions were
   invalid, from tick 0. The low-effort v8.1 control
   (`gpt-6-luna-v81-low-control-20261106`) also built nothing and lost seven of
   ten agents, so the collapse is mostly the model.
   GPT-6.1 Sol pilot, seed 11, 2026-11-06 (`gpt-6-1-sol-v9-pilot-20261106`): all
   ten agents survived both winters at final mean health 76.0, with raw
   Capability 88.1, Execution 96.4, and Production 217.0. The world is playable
   and separates these two models. One model on one seed does not pass the gate.
   Terra one-change ablation, 2026-11-07 (`terra-ablate-*-20261106`), final mean
   health against Terra's v8.1 runs, seeds 11 / 41, one run each:

   | Change from v8.1 | Seed 11 | Seed 41 |
   |---|---:|---:|
   | None (v8.1, medium effort) | 61.3 | 45.5 |
   | Low effort | 41.7 | 31.8 |
   | Two winters | 41.7 | 20.8 |
   | Hidden facts | 61.2 | 54.3 |
   | Shocks | 65.2 | 40.4 |
   | Full v9 | 16.7 | 0.9 |

   Effort and length carry the difficulty; hidden facts and shocks as built do
   not, and Sol was barely affected by all four. v9 spreads the middle of the
   board but does not yet raise the ceiling. Hidden facts and shocks need to be
   much stronger before the next paid run.
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
