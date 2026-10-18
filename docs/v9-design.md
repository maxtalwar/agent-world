# Participant v9 design — working spec

Status: design, not a recipe. Started 2026-09-22; revised 2026-10-18. Nothing
here is registered, locked, or launchable until
`agent_world/recipes/participant-v9.json` exists and passes the tuning gate
below. v8.1 results are unaffected.

## Why

Fable 5.1 (85.0) and GPT-6 Astra (80.1) have saturated the v8.1 capability
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
6. **Hidden per-seed world parameters.** Rules stay public. Facts such as crop
   suitability by tile, winter severity, regrowth rates, and flood risk are
   absent from the rulebook and vary by seed. Agents infer them from
   observation and must commit before they are certain.
7. **Random shocks.** Events such as drought, crop blight, or a severe winter,
   drawn per seed, so plans need buffers rather than only peak efficiency.
8. **Feedback unchanged.** Learning from action feedback is part of the
   intelligence being measured, and honest feedback is how agents discover
   the hidden parameters. `action_feedback_mode` stays at the v8.1 setting.
9. **Same envelope.** Ten founding agents, two seeds (11 and 41), matched
   across models.
10. **Ranking is by the absolute score**, with per-seed values shown. No Elo:
    between pure single-model runs it adds no information, discards margins,
    and shifts historical ratings when new models enter. A draw margin is a
    display rule only, for models within seed noise of each other.

## Open

1. **Which parameters to hide**, and how much evidence the world yields about
   them, so learning is possible but not instant.
2. **Shock design.** Which types, how often, how severe, and whether agents
   get any warning.
3. **Scoring horizon at 80 ticks.** v8.1 checkpoints (12, 24, …, 60) and the
   12-tick capability tail assume 12-tick seasons; set the v9 equivalents.
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
10. **Optional side track.** Strategy-file experiment: each model writes a plan
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

Hidden parameter generation per seed; a shock schedule drawn per seed; 10-tick
seasons over 80 ticks; recipe, execution lock, and leaderboard columns. If
population growth or the compounding economy stay in: new resources and a
second material tier, kiln and smithy, yield multipliers for tools,
irrigation, and roads, reproduction and maturation. Balance is the hard part
and is gated above.
