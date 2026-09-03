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

## 2026-09-03 — GLM 5.3 built a strong service economy despite failing one decision contract in five

**Across its two clean-integrity Participant-v6 diagnostic cells, GLM 5.3
created unusually strong enterprise and service activity even though 208 of
930 decisions failed the model-output contract, exposing a sharp split between
economic planning ability and concise schema compliance.** The pooled result
scored 62.55 competence, 80.60 entrepreneurship, and 135.88 economic
productivity: 12 of 20 agents survived, 14 structures were completed, 14 trades
settled, and 95.625 units of enterprise supply were recorded, including 34.625
of classified service income. Seed 11 produced an active commodity market and
two access-sharing shelter ventures; seed 41 produced a public-fee well with
three payments and a contributor dividend, plus paid shelter access and
survival aid distinguished by the frozen gift classifier. Reliability was much
weaker: 187 of the 208 failed decisions were overlong `intent` fields. No
provider, quota, harness, or ambiguous-envelope failures contaminated these
cells, so this is attributable model behavior rather than fabricated world
activity. The run remains diagnostic rather than leaderboard-certified because
it used the new ZCode connector and native Max effort instead of the closed v6
provider set and standardized medium effort. For context, the GLM 5.2 v6 pair
had pooled competence 13.27, one survivor, two structures, and zero enterprise,
but those OpenRouter/medium cells had invalid integrity; the provider, effort,
and integrity differences prevent treating the gap as a controlled
model-version effect.
Evidence:
`runs/benchmarks/glm-5-3-zcode-participant-v6-native-max-seeds11-41-20260901-175704`,
compared diagnostically with
`runs/benchmarks/glm-5-2-openrouter-participant-v6-replicated-seeds11-41-20260818-120919`.

## 2026-09-01 — A live terminal session is not a detached run supervisor

**Two healthy checkpointed ZCode cells vanished within seconds of the
15-minute boundary because they were launched as long-lived command sessions,
not under the repository's detached process pattern.** Both processes started
at 10:59 local time; their last partial-tick usage writes landed at 11:14:42
and 11:14:57. Neither ledger contains `run_completed`, `run_paused`,
`run_stopped`, or `run_failed`, both run manifests remained `running`, and the
kernel journal contains no OOM or killed-process evidence. Seed 41 had passed
its tick-5 health gate and seed 11 had correctly frozen at tick 2 for a ZCode
rate-limit wait before the external interruption. This was an operational
supervision failure, not model or provider behavior. Recovery reused the exact
checkpoints, cohort worktrees, and launch commit under a detached `tmux`
supervisor; the cells were sequenced to keep account-wide ZCode concurrency at
four rather than eight.
Evidence:
`runs/benchmarks/glm-5-3-zcode-participant-v6-native-max-seeds11-41-20260901-175704`.

## 2026-09-01 — An omitted provider prefix turned a ZCode rate limit into a fake model collapse

**A ZCode `[1302][Rate limit reached for requests]` response was cached as a
quota failure inside the connector but omitted from v6's shared failure
taxonomy, so 184 provider refusals were laundered into agent `wait` actions and
the world advanced to tick 50 as if GLM 5.3 had chosen them.** Seed 11 made only
19 real provider calls for 203 recorded decisions: 18 valid decisions, one
confirmed model-contract failure, and 184 cached quota messages. Because the
quota prefix was unrecognized, the five-tick health gate reported success,
all agents died by tick 23, and the run emitted a normal completion report.
This was a harness artifact, not model behavior and not a valid score. The
parallel seed 41 was manually stopped at completed tick 9; its preserved
ledger contains 85 valid decisions and five model-contract failures, plus ten
usage rows from the interrupted incomplete tick. The repair adds every ZCode
failure class to the common taxonomy and a regression proving the exact 1302
message discards the incomplete tick and pauses at the completed-tick
checkpoint. Both original cells are retained but explicitly invalidated; a
clean study must launch from the repaired commit rather than resume evidence
whose source fingerprint lacked the guard.
Evidence:
`runs/benchmarks/glm-5-3-zcode-participant-v6-native-max-seeds11-41-20260901-171953`,
`agent_world/metrics.py`, `tests/test_session.py`.

## 2026-07-31 — Opus 5 converted a small reasoning budget into the strongest society yet

**Claude Opus 5 averaged only 287 estimated reasoning tokens per decision—about
the same as Sonnet 5 and 76% fewer than Opus 4.8—yet became the first current
participant-v6 cohort to lead execution (91.4), competence (79.2), and
entrepreneurship (71.8) simultaneously.** It kept 20/20 agents alive, created
312.25 net living-accessible value, and generated 66 units of enterprise
supply across the matched seeds. The difference was not verbosity: Opus 5
organized five completed shelters plus a storage asset, five cooperative
builds, 18 access grants, and a real procurement chain in which one agent
bought stone and used it to finish another agent's shelter. In seed 41, Agent
2 answered an advertised stone bounty, mined and hauled the final input,
received a contributor ownership share and permanent shelter access, then
collected coin, fiber, and food from the two co-owners. Both runs had clean
model, provider, and harness integrity with zero decision failures and full
usage coverage. This is a model-behavior result and a counterexample to the
idea that the recent benchmark regressions are explained by lower test-time
token spend alone: strategy and coordination quality can improve sharply at
the same measured spend.
Evidence:
`runs/benchmarks/claude-opus-5-participant-v6-certified-seeds11-41-20260730-233421`,
`runs/benchmarks/claude-sonnet-5-participant-v6-certified-seeds11-41-20260729-164053`,
`runs/benchmarks/claude-opus-4-8-participant-v6-seeds11-41-20260729-155748`.

## 2026-07-31 — More reasoning within the 5.6 family did not buy better long-horizon planning

**GPT-5.6-Terra used 226 reasoning tokens per decision—less than half Luna's
474—yet finished ahead in competence (43.6 versus 35.5) because it formed five
assets including a shelter, while Luna completed only one farm.** Immediate
execution was nearly identical (82.0 Terra versus 81.6 Luna), and the advantage
did not come from richer coordination: Terra produced only 42 communications,
zero gifts, and one accepted trade across both worlds, compared with Luna's
212 communications, 14 gifts, and two accepted trades. Terra instead retained
9/20 agents versus Luna's 8/20 and finished with 262.0 living-accessible value
versus 176.25. Its shelter was still late and private, and both models scored
zero entrepreneurship, so Terra was not broadly capable at institution
building. The result is nevertheless a within-generation counterexample to
reasoning volume as the dominant explanation: how a model allocates actions
into durable capital can matter more than doubling its measured deliberation.
Both Terra runs had clean model, provider, and harness integrity, while Luna's
seed 41 had one isolated malformed decision that is too small to explain the
gap.
Evidence:
`runs/benchmarks/gpt-5-6-terra-gpt-5-6-sol-participant-v6-seeds11-41-20260729-155943`,
`runs/benchmarks/claude-opus-4-6-gpt-5-6-luna-participant-v6-certified-seeds11-41-20260729-033735`.

## 2026-07-30 — Devin's Luna family name silently overrode the requested reasoning effort

**A Devin run declared as `model=gpt-5.6-luna` and
`reasoning_effort=low` completed successfully with
`response_model=gpt-5-6-luna-medium`, so the friendly family name does not
preserve the experiment's requested effort.** The clean one-agent, one-tick
smoke completed in 10.184 seconds with one valid decision, zero decision
failures, 100% usage-record coverage, and a four-action response that gathered
fiber, built a farm plot, gathered food, and waited. Its usage ledger nevertheless
reported `resolved_reasoning_effort=null` and the medium model variant. A
separate no-prompt ACP session using the explicit
`gpt-5-6-luna-low` model ID reported that exact low variant, confirming the
issue is family-alias resolution at the connector boundary rather than the
account lacking Luna Low. Until the connector maps family plus effort onto an
exact account variant, benchmark launches should use explicit Devin model IDs
or treat declared effort as unverified. Devin ACP also exposed context
occupancy (13,466 of 1,000,000 tokens) but no per-turn input, output, reasoning,
or cost counters, so usage coverage is complete at the call-record level while
token accounting remains unavailable.
Evidence:
`runs/devin-luna-smoke-20260730/run-usage.jsonl`,
`runs/devin-luna-smoke-20260730/run-report.json`,
`runs/devin-luna-smoke-20260730/run-manifest.json`.

## 2026-07-30 — The apparent Windsurf CLI was an editor launcher, not an agent boundary

**A direct “Windsurf connector” would have silently targeted the wrong
interface: the installed `windsurf` command exposed only editor-launch flags,
while its supported headless successor was the Devin CLI's versioned ACP
server.** During connector discovery, `windsurf --help` contained no
noninteractive Cascade or prompt command and the desktop updater migrated the
installed application to Devin Desktop. The bundled `devin` executable exposed
both single-turn automation and `devin acp`; a live protocol probe returned ACP
version 1, `agentInfo.name=affogato`, session create/load support, Ask-mode
configuration, and the account model option. This is a harness distinction,
not a model result: editor automation or a private Cascade endpoint would have
made provenance and failure semantics unauditable. The implemented connector
therefore names the connector after its actual runtime and records
`provider=devin_cli` with `connector_runtime=devin_cli`; its deterministic tests cover the ACP
handshake, saved-login isolation, streamed usage, malformed output, timeout,
quota/auth failures, and bounded-session continuation.
Evidence: `agent_world/devin_brain.py`, `tests/test_devin_brain.py`,
`README.md` (“Devin subscription agents”).

## 2026-07-30 — Sonnet 5 formed more capital than Sonnet 4.6 but chose a strictly worse portfolio

**Sonnet 5 completed 20 structures across two clean Participant v6 worlds—six
more than Sonnet 4.6—but built no shelters, settled no trades or gifts, and
finished with only 11/20 survivors versus Sonnet 4.6's 17/20.** Every Sonnet 5
asset was a farm or storage structure. The worlds looked strong at tick 30:
all 20 agents were alive and seed competence was 83.0/88.6, with living value
334.0/370.25. By tick 50, competence had fallen to 53.6/45.2 and nine agents
had died; every death occurred at zero water, usually under compounding winter
or storm exposure. This was not inactivity or a provider failure. Both runs
had clean model output and full usage coverage, and the agents generated 610
communications, 24 venture initiatives, four trade offers, three access
grants, and one genuinely co-financed storage build. The failure was conversion
and portfolio choice: all trade offers expired, both attempted gifts were
invalid, shared-access farms produced no enterprise supply, and repeated
promises to share resources did not become transfers. The newer model therefore
showed greater willingness to invest but substantially weaker institutional
execution than Sonnet 4.6, which built five shelters and converted cooperation
into 53.6 entrepreneurship.
Evidence:
`runs/benchmarks/claude-sonnet-5-participant-v6-certified-seeds11-41-20260729-164053`,
`runs/benchmarks/claude-haiku-4-5-claude-sonnet-4-6-gpt-5-4-participant-v6-certified-seeds11-41-20260729-004549`.

## 2026-07-30 — A liquid spot market did not compensate for missing survival capital

**GPT-5-mini settled 21 trades and executed 35 gifts across two worlds—far
more exchange than the stronger Sonnet and Opus cohorts—yet lost all 20 agents
because it built four farms and no shelters.** The exchange was ledger-real:
79 units of enterprise supply moved to other agents, including repeated
food-water, fiber-food, coin-resource, and wood-water swaps. Some early trades
were circular reversals, so volume overstated durable commerce, but the market
was not merely conversational. The agents also produced 106 units of own farm
output and left 466.25 units of terminal value in their estates. None remained
living-accessible after extinction. This separates allocation from liquidity:
agents can find counterparties, settle exchanges, and practice mutual aid
while collectively failing to finance the one asset class needed to survive
winter.
Evidence:
`runs/benchmarks/cursor-gpt-5-mini-participant-v6-certified-seeds11-41-20260729-181911`.

## 2026-07-29 — Gift counts can hide an informal market for scarce services

**Opus 4.8 recorded only one accepted trade and zero access-fee revenue, yet
three transfers classified as gifts followed explicit shelter-access bargains,
including two delivered services and one unfulfilled advance.** In seed 11,
Agent 9 agreed to pay four coins plus three fiber for Agent 1's winter shelter;
its fiber-maintenance and gift attempts failed, but Agent 1 granted access and
Agent 9 successfully transferred the four coins, saying they were settled.
Agent 4 separately paid Agent 5 four coins plus one fiber in advance for a
place in shelter 4, but the structure remained one stone short and no access
was delivered. In seed 41, critically injured Agent 2 promised four coins plus
four fiber if Agent 3 yielded a storm shelter position; Agent 3 stepped off,
Agent 2 entered and paid, then died the next tick from accumulated damage.
These are materially different from unconditional aid. The event ledger
correctly records the primitive actions, but a metric that equates `gift` with
noncommercial generosity and only recognizes formal access fees will miss
negotiated service purchases, advances, and default-like outcomes.
Evidence:
`runs/benchmarks/claude-opus-4-8-participant-v6-seeds11-41-20260729-155748`.

## 2026-07-29 — Opus 4.7 spontaneously formed a two-stage food supply chain

**Without an assigned commercial objective, Opus 4.7 produced a ledger-backed
producer-to-intermediary-to-consumer chain: farm owner Agent 1 sold five food
to Agent 6 at tick 45, and Agent 6 resold two food to Agent 7 at tick 49 after
the buyer explicitly advertised the deal as "free profit."** Agent 1 had
harvested 13 food from its farm and received four coins plus three fiber for
five food. Agent 6 consumed part of that inventory, then received three fiber
for two food; at frozen book values, its acquisition cost on those two units
was four and its resale proceeds were six. These were separate settled trades,
not gifts or conversational promises. The chain was short-lived and driven by
winter scarcity rather than a formal firm—there were no contracts, access
fees, or dividends—but it demonstrates emergent inventory intermediation and
resale under the organic economy.
Evidence:
`runs/benchmarks/claude-opus-4-7-participant-v6-seeds11-41-20260729-072905/opus-seed-41`.

## 2026-07-29 — Opus 4.6 deliberated far less than Sonnet 4.6 and built a weaker society

**Under the same Participant v6 medium-effort envelope, Opus 4.6 used about
216 estimated reasoning tokens per decision versus Sonnet 4.6's 1,765, then
finished substantially behind Sonnet in competence (47.3 versus 71.6),
entrepreneurship (0.0 versus 53.6), survival (14/20 versus 17/20), and capital
formation (four finished structures versus 14).** Opus was not socially inert:
it created the campaign's ForestAlliance, organized three cooperative builds,
issued 15 access grants, and executed 12 gifts. But its formal organization
did not become a productive institution, and none of its 28 trade offers
settled. The provider reports clean model decisions and estimates Claude
reasoning because the CLI does not expose thinking-token usage directly, so
the absolute token counts are less certain than the behavioral ledger. The
within-provider comparison nevertheless uses the same estimator and envelope.
This is therefore evidence that the nominally larger Claude model allocated
less adaptive deliberation on this task, not evidence that Opus was artificially
given a smaller configured budget.
Evidence:
`runs/benchmarks/claude-opus-4-6-gpt-5-6-luna-participant-v6-certified-seeds11-41-20260729-033735`,
`runs/benchmarks/claude-haiku-4-5-claude-sonnet-4-6-gpt-5-4-participant-v6-certified-seeds11-41-20260729-004549`.

## 2026-07-28 — The planning gap inside Claude is portfolio selection, not willingness to invest

**Haiku 4.5 and Sonnet 4.6 both formed capital aggressively, but Sonnet
allocated it to winter survival and shared access: Sonnet completed 14 assets,
including five shelters, organized seven cooperative builds, issued 24 access
grants, and kept 17/20 agents alive; Haiku completed nine assets, built no
shelter, and lost 20/20.** This is not a simple activity or generosity gap.
Haiku even produced a genuinely co-financed storage structure, while Sonnet's
commercial market remained inefficient (three accepted trades from 46 offers).
The decisive difference was institutional planning: Sonnet began shelter
construction before winter, assigned contributors proportional ownership
shares, opened privately anchored farms and shelters to other agents, and used
targeted gifts to cover immediate food and water shortfalls. Closely related
Claude models therefore displayed similar willingness to build and cooperate
but radically different ability to choose the right capital portfolio and
translate cooperation into survival.
Evidence:
`runs/benchmarks/claude-haiku-4-5-claude-sonnet-4-6-gpt-5-4-participant-v6-certified-seeds11-41-20260729-004549`.

## 2026-07-28 — Capital formation can be actively misleading when the portfolio is wrong

**Haiku 4.5 built nine completed productive assets across its two frontier
worlds—more than Mini and Spark combined, including the campaign's only
genuinely co-financed structure among those three model cohorts—and still lost
all 20 agents because every completed asset was a farm or storage rather than
winter shelter.** Seed 11
produced two farms and a storage co-built by agents 4 and 9 (ownership shares
87.5%/12.5%); seed 41 produced five farms and a storage. Yet the farms yielded
only 8 accounting units across both worlds, upkeep was missed 26 times, no
shelter was completed, and both populations reached zero before tick 44. By
contrast, Mini retained 4/20 agents and Spark 1/10 despite completing no
structures. The model plainly understood the seasonal vocabulary—it repeatedly
described farms and shelters as winter preparation—but optimized the visible
spring production opportunity, treated storage as protection, and deferred the
actual exposure countermeasure until seed 11's first shelter attempt at tick 37;
its owner died that same tick. Capital quantity is therefore not a proxy for
planning horizon: locally sensible investment can accelerate commitment to the
wrong strategy.
Evidence:
`runs/benchmarks/claude-haiku-4-5-claude-sonnet-4-6-gpt-5-4-participant-v6-certified-seeds11-41-20260729-004549`,
`runs/benchmarks/gpt-5-3-codex-spark-gpt-5-4-mini-participant-v6-certified-seeds11-41-20260728-200141`.

## 2026-07-28 — OpenAI's deliberation spend falls monotonically across model generations

**On identical benchmark decisions at the same effort setting, reasoning
tokens per decision fall strictly with model recency: Spark ~5,011 >
GPT-5.4-mini ~1,260 > GPT-5.4 ~785 > GPT-5.5 ~32.** This tracks OpenAI's
public token-efficiency push — GPT-5.5's launch materials emphasized
efficiency — and looks like its tradeoff surface: each generation buys its
efficiency by trusting its own judgment about when thinking is unnecessary,
and 5.5 overshoots on this task (see the misallocation entry below). Newer ≠
more deliberate; the frontier is moving toward thinking less, not more.
Evidence: participant-v5 leaderboard Reasoning/decision column
(provider-reported figures).

## 2026-07-28 — Claude reasons without limit unless capped, and Anthropic ships no token cap at all

**Stock Claude Code drives adaptive thinking purely from the effort dial with
no token ceiling — uncapped, Sonnet 4.6 at medium spent 5,129 output tokens
on a single small puzzle — and the token cap that does exist
(`MAX_THINKING_TOKENS`) is deprecated in the CLI in favor of effort.** The
labs have diverged on control surfaces: OpenAI exposes discrete effort levels
that newer models increasingly interpret as "barely think" (see the
monotonic-efficiency entry above), while Anthropic exposes effort levels that
scale an uncapped adaptive budget. Practical consequences: (1) no
cross-provider effort label means the same spend; (2) a benchmark that
uncapped Claude would let it outspend every current-generation OpenAI model
by an order of magnitude — participant-v5 caps the envelope at 2,048 tokens
for this reason; (3) measuring Claude's spend requires estimation, because
the CLI reports no thinking-token split and its streamed thinking blocks are
display summaries whose length is unrelated to billed tokens (measured: 4,527
summary chars against ~5,000 billed thinking tokens).
Evidence: `claude` CLI 2.1.201 stream-json probes 2026-07-28; binary string
"takes precedence over the deprecated maxThinkingTokens"; calibration in
`agent_world/claude_brain.py`.

## 2026-07-28 — GPT-5.5 is smart but misallocates deliberation: at medium effort it simply doesn't think

**GPT-5.5 spent ~0 reasoning tokens on 92% of its benchmark decisions at
`model_reasoning_effort=medium` — and lost to its own predecessor because of
it.** The knob demonstrably binds: on a small math prompt 5.5@medium reasons
like 5.4@medium (43 vs 40 tokens), and on the actual sim prompt 5.5@high
spends ~516 tokens. But at medium on the big structured decision prompt, 5.5
adaptively judges the task easy and answers cold every time, while 5.4 at the
identical setting deliberates ~1,000 tokens. The failure profile matches
rushing, not weakness: 29–32 action-point budget overruns per run vs 2 for
5.4. Participant v6 reproduced and widened the inversion: 5.4 spent 799
reasoning tokens per decision and scored 88.5 execution / 58.4 competence /
20.8 entrepreneurship with 12/20 survivors and 11 completed structures; 5.5
spent 19 and scored 84.6 / 34.7 / 0.0 with 7/20 survivors and 3 structures.
Effort labels are promises about *ceilings*, not spend, and their semantics
shift between model generations of the same family.
Evidence: `runs/benchmarks/gpt-5-5-participant-v4-certified-seeds11-41-20260728-132823`
(reasoning/decision 31–34 vs 760–811 for GPT-5.4), controlled probes 2026-07-28,
`runs/benchmarks/gpt-5-5-participant-v6-certified-seeds11-41-20260729-005319`,
`runs/benchmarks/claude-haiku-4-5-claude-sonnet-4-6-gpt-5-4-participant-v6-certified-seeds11-41-20260729-004549`.

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

## 2026-07-28 — The frontier world separates models by planning horizon, exactly as designed

**On the first participant-v6 runs, the seasonal world split the field
cleanly along survival planning: GPT-5.6 Sol kept 10/10 agents alive through
winter (7 farms plus 2 shelters built before the cold, net value created
213.25, entrepreneurship 74.5 — the first nonzero score since the metric was
introduced), while GPT-5.4-mini kept 2/10 alive and GPT-5.3-codex-spark
1/10, both with zero completed structures.** The v4/v5 worlds had compressed
these models into a ~15-point competence band; v6 spreads the same models
across 78.8 vs 26.6 vs 19.9. The discriminating skill appears to be acting
on forecastable future state (winter is announced in the rulebook and the
season payload every tick) rather than reacting to present scarcity — the
small models farmed competently in autumn and then starved in a winter they
had been told was coming. Sol also broke the models-don't-trade pattern
(1 trade, 9 gifts, enterprise supply 26.0 per 100 agent-ticks vs the 0.6–1.8
historical band). A low floor was accepted deliberately (ARC-AGI-3 style):
small-model collapse is signal, not failure.
Evidence: `runs/benchmarks/leaderboard-v6-20260728.md`,
`runs/benchmarks/gpt-5-6-sol-participant-v6-provisional-seed11-20260728-195329`,
`runs/benchmarks/gpt-5-3-codex-spark-gpt-5-4-mini-participant-v6-certified-seeds11-41-20260728-200141`.
