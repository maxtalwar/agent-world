# Participant v9 design — working spec

Status: design, not a recipe. Started 2026-09-22. Nothing here is registered,
locked, or launchable until `agent_world/recipes/participant-v9.json` exists
and passes the tuning gate below. v8.1 results are unaffected.

## Why

Fable 5.1 (85.0) and GPT-6 Astra (80.1) have saturated the v8.1 capability
score, which is final population health out of 100. Execution is 94–97 for
the top three. The one open-ended column, Production, already disagrees with
capability about who is best. Survival with a fixed population has an optimum
that a capable model reaches, and per-tick feedback lets any model hill-climb
to it. Harder puzzles only move the date. v9 changes what is measured and what
there is to decide, not the run length.

## Locked

1. **Low reasoning effort**, pinned per connector in the recipe and labeled
   on the board. Note: for frontier models reasoning is already a small share
   of tokens per decision (Astra 92, Fable 5.1 254 reasoning tokens against
   9,000–15,000 prompt tokens), so this buys speed and a harder ceiling more
   than it buys cost. Cost is governed by prompt size and caching.
2. **Score is healthy, well-provisioned life.** Each person, each tick,
   counts the value of what they consumed scaled by their health; summed over
   the run and divided by the founding population. Consumption, not
   production: a good counts once, when used, so churn and barter loops add
   nothing. Production, tech tier reached, and trade volume are diagnostic
   columns and are never ranked on.
3. **Hidden per-seed world parameters.** Rules stay public. Facts such as crop
   suitability by tile, winter severity, regrowth rates, and flood risk are
   absent from the rulebook and vary by seed. Agents infer them from
   observation and must commit before they are certain. This is where
   in-context learning lives.
4. **Population grows, and new people decide.** Reproduction is an investment:
   it costs food and an agent's time now and yields a working agent after a
   maturation delay. There are no non-deciding dependents; a rational agent
   would never create them.
5. **A compounding economy, as means only.** Tools multiply labor, irrigation
   multiplies land, roads multiply transport, storage multiplies time, and a
   second material tier unlocks durable tools and larger structures. Each
   mechanic must raise the return on another; anything an agent can ignore
   without loss is removed. None of it is scored directly.
6. **Same envelope.** Ten founding agents, two seeds (11 and 41), matched
   across models. Tick count is an open item below.
7. **Ranking is by the absolute score**, with per-seed values shown. No Elo:
   between pure single-model runs it adds no information, discards margins,
   and shifts historical ratings when new models enter. A draw margin is a
   display rule only, for models within seed noise of each other.
8. **Shelved for v10:** escalating pressure over an open horizon, because it
   lengthens runs and cost is the binding constraint.

## Open

1. **Growth limits.** Maturation delay (candidate: 15 ticks), food cost of a
   birth, and a hard cap (candidate: twice the founding population, so a run
   costs at most double today).
2. **The goods ladder.** Consumption tiers above subsistence — dry shelter,
   heated house, preserved food through winter, cloth, second-tier goods —
   with fixed weights and steeply rising cost. Calibration target: the
   scripted survival brain reaches tier one, a cheap model tier two, and no
   model in the first cohort tops out.
3. **Commitment decisions.** A handful of irreversible choices with delayed
   payoff and no clear best: settlement site, orchard versus farm,
   specialization, trade on credit. Enough to force judgement; few enough to
   keep the rulebook readable.
4. **Which parameters to hide**, and how much evidence the world yields about
   them, so learning is possible but not instant.
5. **Tick count.** 60 ticks with 12-tick seasons ends in the second spring and
   contains one winter. 72 ends in the second summer and adds no winter; the
   extra ticks are the easiest season. Two winters need 96 ticks at 12-tick
   seasons, or 80 ticks at 10-tick seasons. Cost scales linearly with
   decisions, so +20% ticks is +20% cost before any population growth.
6. **Prompt budget.** Measured on v8.1 ledgers: the rulebook is ~2,100 tokens
   and the observation grows from ~350 to ~1,600 tokens over a run; the CLI
   harnesses add 6,000–10,000 tokens of their own, cached. On Claude the
   rulebook already cache-hits; the cost was the observation being written to
   a one-hour cache at 2x on every call, fixed by `CLAUDE_CODE_PROMPT_CACHE_TTL=5m`
   (about 17% of a Fable run). On Codex, prompt caching is best-effort and
   never covered our content in testing, whichever position it was placed in,
   so every prompt token is billed at full price there. Budget for v9: static
   rulebook at most 2,500 tokens; the observation is not capped, since capping
   it would distort agent memory.
7. **Map size.** Larger makes roads and transport matter and raises
   observation size. Undecided.
8. **Tuning gate.** Before any paid run: play the world with the scripted
   brain and one cheap model, and require that two different reasonable plans
   diverge in score. If they converge, the judgement is not real and the
   parameters go back for revision.
9. **Optional side track.** Strategy-file experiment: each model writes a plan
   from the rules, identical cheap executors play it, compared against the
   same model playing live. Measures the value of in-context adaptation. Not
   on the main board.

## Engine work implied

New resources and a second material tier; kiln and smithy; yield multipliers
for tools, irrigation, and roads; storage and spoilage; reproduction and
maturation; hidden parameter generation per seed; consumption accounting and
the health-weighted score; recipe, execution lock, and leaderboard columns.
Touches world, rules, interface, scoring, and the dashboard. Weeks, not a
patch. Balance is the hard part and is gated above.
