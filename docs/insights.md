# Insights journal

A running log of the interesting things this project has taught us about
specific models, about LLMs in general, and about running agent societies.
This is the project's institutional memory: benchmarks and experiments answer
the question they were built for, but the surprising things they reveal along
the way die in chat transcripts unless they land here.

**If you are an agent working in this repo: when a run, experiment, debug
session, or benchmark surfaces something genuinely interesting — a model
quirk, a capability inversion, an emergent behavior, a harness effect that
masqueraded as model behavior — append an entry.** Rules:

- One entry per insight, newest first, dated.
- State the insight in one bold sentence a stranger could evaluate, then the
  evidence with concrete numbers and pointers to runs/docs. No evidence, no
  entry.
- Distinguish model behavior from harness artifacts explicitly — several
  entries below exist precisely because the two were conflated at first.
- Update or strike entries that later evidence overturns; note why. Do not
  silently delete.
- Routine results (model X scored Y) belong in benchmark reports, not here.
  The bar is: would a researcher who read every leaderboard still be surprised?

---

## 2026-07-28 — GPT-5.5 is smart but misallocates deliberation: at medium effort it simply doesn't think

**GPT-5.5 spent ~0 reasoning tokens on 92% of its benchmark decisions at
`model_reasoning_effort=medium` — and lost to its own predecessor because of
it.** The knob demonstrably binds: on a small math prompt 5.5@medium reasons
like 5.4@medium (43 vs 40 tokens), and on the actual sim prompt 5.5@high
spends ~516 tokens. But at medium on the big structured decision prompt, 5.5
adaptively judges the task easy and answers cold every time, while 5.4 at the
identical setting deliberates ~1,000 tokens. The failure profile matches
rushing, not weakness: 29–32 action-point budget overruns per run vs 2 for
5.4. Effort labels are promises about *ceilings*, not spend, and their
semantics shift between model generations of the same family.
Evidence: `runs/benchmarks/gpt-5-5-participant-v4-certified-seeds11-41-20260728-132823`
(reasoning/decision 31–34 vs 760–811 for GPT-5.4), controlled probes 2026-07-28.

## 2026-07-28 — Reasoning spend and score are wildly decoupled across models

**Deliberation efficiency varies by two orders of magnitude:** on the same
board, Spark burns ~5,011 reasoning tokens per decision for 71.5 execution,
GPT-5.4-mini ~1,260 for 72.1, GPT-5.4 ~785 for 86.8, and GPT-5.5 ~32 for 82.7.
Sonnet 4.6 posted the #2 competence score with *zero* deliberation (thinking
was force-disabled under v4). Tokens spent thinking predict neither rank nor
execution quality across model families.
Evidence: participant-v5 leaderboard Reasoning/decision column.

## 2026-07-28 — Sonnet 4.6 ran a society on discipline and talk, not deliberation

**With extended thinking disabled entirely, Sonnet 4.6 took second place
overall (competence 67.8) and posted the best survival on the board (19/20
agents alive) plus the highest entrepreneurship score recorded (32.8).** Its
style is distinctive: it communicates 4–6× more than any GPT model (83
messages per 100 agent-ticks vs 13–21) and keeps everyone alive, while
tolerating a high invalid-proposal rate (23%). Coordination-by-chatter beat
deliberation-per-decision on this task.
Evidence: `runs/benchmarks/claude-sonnet-4-6-participant-v4-certified-seeds11-41-20260728-141113`.

## 2026-07-28 — Provider-side output constraints hide format competence differences

**GPT-5.4 recorded 0 malformed decisions in 946 because the Codex API
physically constrains tool-call output to the schema; Haiku 4.5, asked for
the same JSON with prompt-only enforcement, failed 50 of 50 decisions.** Of
Haiku's failures, 8 were valid JSON wrapped in markdown fences (a chat
transport habit, not a competence failure) and 42 were real schema violations
(fields it was never told about once the schema left the prompt). Two
lessons: (1) cross-provider "format failure" comparisons are meaningless
unless enforcement is matched; (2) a fence-stripping salvage step is
mandatory before charging a chat model with a contract violation.
Evidence: `runs/benchmarks/claude-haiku-4-5-participant-v4-20260728-fixed`
(aborted diagnostic), adapter fix in `agent_world/claude_brain.py`.

## 2026-07-23 — Luna outperforms Terra on action discipline despite being smaller and cheaper

**In all four 30-agent mixed-civilization cells, gpt-5.6-luna posted a lower
invalid-action rate than gpt-5.6-terra — 54–68 vs 68–95 invalid per 100
decisions — and lost fewer agents (2 deaths total vs 7).** Terra is the
bigger, more expensive model. Whatever Terra buys, it is not proposal
feasibility in a constrained action space; Luna reads the world state more
accurately per decision.
Evidence: `runs/experiments/stateless-v1-v3-civilization-30a-40t-seeds11-41-20260723-174150`
(per-cohort recount from raw ledgers, 2026-07-28).

## 2026-07-19 — How you present world feedback steers attention: better actions, less trade

**Switching failed-action feedback from bare rejections to causal
explanations made agents better at private plan correction and measurably
less social, in both matched seed pairs.** Trade offers fell 162→126,
messages per decision fell 0.363→0.322, while private capital formation rose
(six farms + two storages worth 92 book value vs six farms worth 60, seven
access grants vs one). The explanation payload wasn't larger on average, so
this is not a token-budget effect — it is consistent with semantic feedback
redirecting limited attention from social coordination toward local
correction and asset management. Presentation choices in the observation are
a real experimental variable, as strong as some model swaps.
Evidence: `docs/action-feedback-experiment.md` (civilization effects section).

## 2026-07-04 — Surplus is where society begins: one action point separates subsistence from institutions

**On the same seed, 5 GLM-5.2 agents at 3 action points per tick produced
zero groups, zero trades, and solo subsistence structures over 40 ticks; at 4
AP they produced a 5-member named polity, cooperative barn-raisings, communal
property, and a gift economy.** The 4th AP is pure slack — survival needs
consume roughly three — and that slack is what became politics. Related
finding from the same runs: given a full escrowed market, comfortable agents
ran the village on 27 outright gifts vs 1 completed trade, with the polity
founder providing 19 of the 27 (political leadership and redistribution fused
in one agent — a chiefdom, not a market). And the same world seed, re-run,
produced four rival one-member factions instead of one polity: institutions
here are path-dependent, not seed-determined.
Evidence: `reports/lakeside-settlement.md`, `runs/tweaked-attempt-c.*`,
`runs/live.*`.

## 2026-07-26 — Frontier models essentially do not trade

**Across every complete 50-tick benchmark trial on record, enterprise supply
sits at 0.6–1.8 units per 100 agent-ticks against a mechanics-based target of
20 — models post offers but almost never complete exchanges.** GPT-5.4, the
strongest model tested, completed 3 trades in 1,000 agent-ticks. The
entrepreneurship score behaves as a near-binary "does this model trade at
all" signal, and the benchmark deliberately reports that as a low score
rather than lowering the anchor. Interesting sub-pattern: Claude models
attempt commerce earlier and more often (Haiku offered a trade on tick 1)
but convert no better.
Evidence: `docs/model-benchmarks.md` (enterprise supply section),
participant-v4/v5 leaderboards.

## 2026-07-28 — Budgets are ceilings, not quotas: "effort parity" across providers is currently fictional

**There is no mechanism, on any provider, to make a model spend a fixed
amount of reasoning — budgets cap, effort requests, and models allocate.**
The same word ("medium") produced ~800 tokens/decision in one model, ~0 in
its successor, and was silently unsupported entirely on Haiku 4.5 (the API
rejects the effort parameter; the CLI drops it). Participant v5 exists
because of this: equal declared envelopes with measured spend is the only
honest cross-provider deliberation policy available today.
Evidence: participant-v5 design notes in `docs/model-benchmarks.md`,
2026-07-28 probe data.
