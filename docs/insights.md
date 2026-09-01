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

## 2026-09-01 — ZCode's environment model override bypassed its saved Coding Plan credential

**A ZCode 0.16.5 process could pass login preflight yet fail every GLM-5.3
decision before inference because setting `ZCODE_MODEL` selected an
environment-configured provider without carrying over the saved Coding Plan
credential.** The first frontier-generalists smoke cells ended in about 1.3
seconds with zero tokens and an ambiguous `Turn execution failed` boundary.
The matching local ZCode trace located the failure in `processing_input`, with
`AiSdkModelAdapterError: Model provider is missing an API key: zai`; this was
a harness configuration failure, not model behavior.

ZCode's login-generated local catalog also initially contained only GLM-5.1
and GLM-4.7 despite the installed 3.10.2 application and current GLM-5.3 Coding
Plan documentation. After enabling GLM-5.3 locally and bridging only the saved
provider credential and base URL into the child process, the clean pinned smoke
completed one real decision: 11,087 input tokens, 2,587 output tokens, a
1,000,000-token context window, three valid actions, and zero decision or
invalid-action failures. Evidence:
`runs/experiments/glm-5-3-zcode-frontier-smoke-20260901-163341`;
commits `c832da8` and `ea50444`.
## 2026-08-30 — Ordinary effort scaling did not make stateless agents discover the ledger

**Raising GPT-5.6 Luna from medium to max and GPT-5.6 Sol from medium to high
did not produce spontaneous town-ledger adoption under the original rules-only
prompt: both new matched cells authored zero notes and never mentioned the
ledger in 200 response payloads.** The seed-11 diagnostic used the same
10-agent, 10-tick, specialist frontier world, one-AP ledger, four-action output,
neutral objective, and stateless-v3 boundary as the prior medium controls.
Luna moved from 0/100 notes at medium to 0/100 at max; Sol moved from 1/100 at
medium to 0/100 at high. Both new cells completed 100/100 exact-model decisions
with zero model-output failures and full usage capture. Luna max spent 399,060
reasoning-output tokens and Sol high spent 47,265, so this is not a trivial
failure to allocate more inference.

This narrows rather than universalizes the planning limitation. OpenAI's 2026
Hugging Face incident report says persistent cyber agents using extraordinary
reasoning discovered and rebuilt unsanctioned boards; METR reports many
trajectories ran to millions of tokens. The local null result therefore applies
to ordinary per-decision effort inside a neutral, stateless tick loop. Persistent
identity, cumulative context, extreme task pressure, population scale, or
training for multi-agent collaboration may be the actual threshold variables.
Evidence: `runs/experiments/ledger-effort-threshold-20260831-024354/`, especially
`{luna-max-legacy-r2,sol-high-legacy-r2}`; contextual comparison:
`https://openai.com/index/hugging-face-incident-and-the-road-ahead/` and
`https://metr.org/blog/2026-08-26-openai-hugging-face-incident-investigation/`.

## 2026-08-30 — Agents mistook private familiarity for public knowledge until the prompt supplied a decision trigger

**The town ledger's zero-use failure was not mechanical or a model-capability
limit: agents omitted the optional institution from planning and, when forced
to evaluate it, usually called their private local facts “not novel” even
though the public ledger was empty.** Before intervention, 27 preserved organic
reports spanning Luna, Sol, Grok 4.5/4.6, and DeepSeek variants contained 8,684
decisions and zero authored ledger notes. In a matched eight-cell Luna screen,
salience, zero AP cost, a collective objective, generic social proof, realistic
peer examples, charging local speech, and the combined salience/free/seeded
treatment all remained at zero; a mandated positive control produced 25 notes,
proving the action and model capability were intact.

The decisive diagnostic asked agents to begin their intent with LEDGER POST or
LEDGER SKIP while leaving posting optional. At tick 0, nine of ten said they
had no novel nonlocal information despite an empty board and private
specialty/resource observations. Reflection alone produced 9 notes from 7
authors; explaining private discovery/trade value produced 19 from all 10;
defining novelty operationally against recent public notes produced 23 from all
10. Perspective documentation by itself still produced 0/100 whether posting
cost one AP or zero: the knowledge had to be coupled to a decision condition.
Under the original four-action, one-AP mechanics, the rule produced 24/100 Luna
notes from all 10 authors versus 0 in the exact-shape control.

This generalized to the stronger model and unlocked a second institution. A
matched Sol baseline produced 1 note by 1 author and no contract events; the
rule produced 29 notes by all 10, 6 contracts proposed, 4 accepted, and 3
settled. Notes carried moving/depleted fishing sites, a retracted false water
coordinate, farm and artisan needs, offers, and live contract status. A longer
20-agent Luna cell sustained 141 notes from all 20 over 500 decisions and 23 of
25 ticks (130 unique author/title pairs), while compact production wording
produced 18 notes from all 10 agents for both Luna and Sol with zero decision
failures. The implemented fix keeps the original mechanics, adds an exact
public-novelty decision rule to the default organic prompt, preserves the old
behavior as `legacy`, and remains within the static-context budget at 7,678
characters. This causally refines the 2026-08-02 “failure is in the affordance”
entry below: that conclusion was directionally right, but action count and
protocol complexity were not the primary mechanism.
Evidence: `docs/ledger-affordance-causal-study.md` and
`runs/experiments/ledger-affordance-causal-20260830-221534/`.

## 2026-08-26 — Strict terminal validation separated Grok 4.5's tool-seeking from harness contamination

**After the connector began accepting only `end_turn`, a matched seed-11
diagnostic found 20/50 Grok 4.5 Build decisions still diverted into hidden
coding tools while Grok 4.6 Build completed 50/50 decisions without one tool
event.** Both five-tick cells used Grok CLI 1.0.5, the same pinned commit,
frontier-generalists world, medium reasoning, stateless-v3 connector, four
workers, and an expanded denylist covering every documented tool plus the
aliases found in earlier traces. Grok 4.5 nevertheless attempted `use_tool`
(9), `write` (4), `workflow` (3), `monitor` (2), and `enter_plan_mode` (2).
Its raw sessions ended 31 completed and 19 cancelled; the repaired adapter
fenced all non-success terminal states, yielding 19 ambiguous-boundary failures
plus one independent output-contract violation and correctly failing the 20%
startup-health gate at a 40% decision-failure rate. Grok 4.6's 50 raw sessions
all ended completed, with zero tool events and zero decision failures.

The failure is therefore not primarily excessive reasoning or an inability to
emit JSON: several cancelled Grok 4.5 envelopes contained plausible JSON, but
the model chose a coding-agent tool turn first. It is also not fully removable
with Grok CLI 1.0.5's documented tool filter: an unknown-only `--tools`
allowlist still exposed default/internal tools, and expanding the denylist made
4.5 shift to new internal names. The reliable harness boundary is terminal
validation plus an isolated empty provider workspace; the denylist is only
defense in depth. Grok 4.6 paid for its clean adherence with much heavier
deliberation in this diagnostic: median latency was 70.62 seconds and mean
reasoning 2,501 tokens/call versus 18.80 seconds and 707 tokens/call for 4.5.
Evidence:
`runs/experiments/grok-tool-boundary-side-by-side-v3-20260827-030634`;
retained Grok sessions under `~/.grok/sessions`; commits `f7eada1`, `ec547e2`.

## 2026-08-26 — Grok 4.5 Build exposed a model/tool-boundary failure that the integrity audit undercounted

**Grok 4.5 Build attempted coding tools in 77 of its first 100 Agent World
decisions despite an explicit no-tools system prompt, and the connector
mistakenly admitted 44 of those cancelled turns as decisions; Grok 4.6 attempted
tools in 0 of 992 preserved calls through the same CLI version and command.** A
trace audit of both Participant-v7 Grok 4.5 cells found only 23/100 turns with a
normal completed outcome. Thirty-two turns called list_dir (31 also called
grep) and ended max_turns_reached at the one-turn limit; these are the 32
max-turn cancellations among the 33 ambiguous-boundary failures recorded in the
usage ledgers. Another 45 turns attempted run_terminal_command and ended
permission_cancelled. The adapter rejected one of those but accepted 44
because it checked the CLI exit/error envelope and payload shape without
requiring a successful terminal stopReason. Those admitted payloads included
invented actions such as idle, list_dir, give, grep, drink, ask, forage, and
look, so the worlds were already behaviorally contaminated before the startup
gate stopped them at tick 5.

The model-facing system prompt was not missing: each retained session starts
with “Do not inspect files, run commands, browse, call tools, or delegate” and
contains the full Agent World action list. The connector command was also the
same one used by the clean Grok 4.6 Build study, and both studies used Grok CLI
1.0.5. The model difference is therefore real evidence about coding-harness
instruction adherence, but two harness defects amplified and obscured it:
passing an empty --tools allowlist leaves Grok Build's default tools available,
and the adapter does not reject every non-success terminal reason. This entry
corrects the 2026-08-25 interpretation below that all cancelled completions were
fenced out; only the max-turn subset was consistently fenced out.
Evidence:
runs/benchmarks/grok-4-5-grok-cli-participant-v7-seeds11-41-20260825-231433;
retained Grok sessions under ~/.grok/sessions;
runs/benchmarks/grok-4-6-grok-cli-participant-v6-fixed-seeds11-41-20260823-161608;
agent_world/grok_brain.py; Grok CLI 1.0.5 README.md tool-filtering semantics.

## 2026-08-25 — Grok 4.5 failed differently across Grok Build and Cursor

**Grok Build was roughly four times faster than Cursor for Grok 4.5, but its
direct boundary cancelled enough valid-looking startup responses to stop both
worlds at tick 5; Cursor began cleanly and failed later through a concentrated
loop-detector pathology.** In the Participant-v7 Grok Build cells, 20/50 seed-11
decisions and 13/50 seed-41 decisions were ambiguous-boundary extraction
failures. Every failed envelope carried `stopReason=cancelled`, yet 30 of the 33
still contained syntactically parseable JSON text. The integrity fence correctly
refused to score cancelled completions, and both cells stopped at the startup
gate. Their median decision latencies were 10.04 and 10.98 seconds. The older
Participant-v6 Cursor seed-11 diagnostic had zero failures in its first 50
decisions and reached tick 50, but ended with 43/485 failures: 35 Cursor
`Agent Looping Detected` boundary errors and 8 confirmed output-contract
violations, concentrated mainly in Agents 10, 4, and 5. Its median latency was
45.56 seconds. This is a harness-compatibility result, not a clean model
comparison: protocol version, worker count (20 versus 4), run date/backend,
response identity, and seed coverage also differ. It shows that a provider
wrapper can trade speed for a much worse failure shape without establishing
that the underlying model became less capable.
Evidence:
`runs/benchmarks/grok-4-5-grok-cli-participant-v7-seeds11-41-20260825-231433/{grok-4-5-build-v7-seed11,grok-4-5-build-v7-seed41}`;
`runs/benchmarks/cursor-grok-4-5-participant-v6-provisional-seed11-20260729-181433/grok45-v6-seed11`.
## 2026-08-24 -- Codex process count was not the desktop's limiting resource

**Four simultaneous Codex cells sustained an aggregate 99 observed child
processes without swapping, while the 40-worker cell remained the fastest
setting tested.** Matched 40-agent, five-tick cells at 10, 20, 30, and 40
workers finished in 372.5, 241.5, 218.4, and 168.4 seconds respectively. All
800 decisions succeeded with clean harness integrity. The 40-worker cell's
median call slowed to 22.9 seconds from 16.2 at 10 workers, showing contention,
but eliminating scheduling waves still delivered 2.21x whole-run throughput.
During the four-way overlap WSL retained at least 12,273 MiB available memory
and recorded zero swap use, page-ins, or page-outs. This is a harness/host
capacity result, not model behavior: on this desktop 40 is a tested-safe Codex
ceiling and the actual ceiling lies above the tested range.
Evidence: `runs/experiments/desktop-worker-ramp-20260824/analysis.md`;
`runs/experiments/desktop-worker-ramp-20260824/host-resource-samples.csv`;
per-cell manifests and usage ledgers in that experiment directory.

## 2026-08-24 — A provider ceiling is not an effective worker default

**Raising a provider semaphore alone did not increase concurrency because the
upstream global pool remained the binding limit.** Commit `58dc3b8` initially
raised only `codex_cli`'s provider ceiling; `BrainSpec.resolve` still fell back
to one global worker, and the isolated-cohort launcher did not inject a
different value. The original ramp manifests confirm that every measured cell
explicitly passed both `--max-workers` and `--codex-max-workers`. Ordinary
provider-backed runs now default to a four-thread global pool. Inside a larger
pool, provider defaults are 40 for Codex, 20 for Claude Code and Grok Build,
and 4 for the remaining harnesses, with every provider value clamped to the
global pool. The Codex value is supported by the desktop ramp; the Claude and
Grok values are conservative inferences, not measured results. Because the
current benchmark population has ten agents, all three larger configured
limits still mean at most ten simultaneous decisions in that protocol.
Evidence: commit `58dc3b8`; `agent_world/brain_factory.py`;
`agent_world/cli.py`; `runs/experiments/worker-ramp-20260802/*/run-manifest.json`.


---

## 2026-08-24 — Grok Build's cost telemetry is not an API-list-price estimate

**Grok Build's subscription telemetry reported $4.213683 for the completed
seed-11 run, while the same 8.451M input tokens and 1.972M output tokens cost
$24.786370 at xAI's public Grok 4.6 API rates—a 5.88x difference—and a connector
normalization bug initially hid most cache reads.** The CLI exposes uncached
input (`inputTokens`) and cache reads (`cacheReadInputTokens`) as disjoint
counts, whereas Agent World's common usage contract defines cached tokens as a
subset of inclusive prompt tokens. The old connector copied only the uncached
field into `prompt_tokens`; the generic cost calculator then capped 2,631,168
reported cache-read tokens down to 455,064 because many individual cache counts
exceeded the incorrectly narrow prompt count. This is entirely a harness and
billing-basis artifact, not model behavior. The connector now writes inclusive
prompt totals, the report loader deterministically upgrades historical Grok
records from their preserved `grok_model_usage`, and reports retain the $4.21
subscription figure separately from the comparable $24.79 API equivalent.
Evidence:
`runs/benchmarks/grok-4-6-grok-cli-participant-v6-fixed-seeds11-41-20260823-161608/grok-4-6-build-v6-seed11/run-usage.jsonl`,
`runs/benchmarks/grok-4-6-grok-cli-participant-v6-fixed-seeds11-41-20260823-161608/grok-4-6-build-v6-seed11/run-report.json`,
`agent_world/grok_brain.py`, `agent_world/run_report.py`,
`agent_world/usage.py`, and `tests/test_usage.py`.

## 2026-08-25 — Grok repeatedly improvised shelter economies but failed at basic survival logistics

**Across both clean seeds, Grok 4.6 Build improvised contributor shares,
discretionary shelter access, and upkeep-for-roof exchanges without forming a
single group, contract, or formal access-fee policy—then lost three agents to
zero food or water.** In seed 11, Agents 6 and 10 completed shelter 14 with
62.5%/37.5% contributor shares. Agent 6 admitted Agents 10, 7, 9, and 1 while
messages explicitly negotiated food, coins, help, and winter access; the frozen
classifier credited five commercial gifts worth 22.5 accounting units as
service income. Agent 6 nevertheless died at tick 49 with water 0. Seed 41
reproduced the same informal institution in a different form: Agent 9 made
shelter 13 public, admitted Agents 1, 6, 8, and 7, and received one fiber from
Agent 1 explicitly "for shelter upkeep." That was the run's only classified
service payment. Meanwhile Agents 3 and 10 died at ticks 44 and 46 with both
food and water at 0. The two frozen ledgers pool to 91.45 execution, 82.41
competence, and 92.60 entrepreneurship, with 17/20 survivors and zero model,
provider, quota, ambiguous-boundary, or harness failures. This is model
behavior, not a harness artifact: Grok can invent working micro-property and
reciprocity arrangements, but its high-level coordination does not reliably
close individual subsistence loops.
Evidence:
`runs/benchmarks/grok-4-6-grok-cli-participant-v6-fixed-seeds11-41-20260823-161608/grok-4-6-build-v6-seed11/run.jsonl`,
`runs/benchmarks/grok-4-6-grok-cli-participant-v6-fixed-seeds11-41-20260823-161608/grok-4-6-build-v6-seed41/run.jsonl`,
both `run-report.json` and `gift-classifications.json` artifacts in those seed
directories,
`runs/benchmarks/grok-4-6-grok-cli-participant-v6-fixed-seeds11-41-20260823-161608/study-manifest.json`.

## 2026-08-23 — Grok reported an exhausted balance as a successful process carrying an error envelope

**Grok Build returned HTTP 402 quota exhaustion inside a JSON `type=error`
envelope while the CLI process exited successfully, so the connector treated a
provider refusal as an ambiguous payload-extraction failure and bypassed the
benchmark's quota-wait policy.** Two independent Participant v6 cells reached
the same account boundary after 210 and 200 successful decisions respectively.
At seed 11 tick 21 and seed 41 tick 20, all ten attempted decisions preserved
the exact message `Grok Build usage balance exhausted`; both worlds stopped at
clean checkpoints with `decisions_unusable` instead of entering the configured
12-hour wait. This was a harness artifact, not model behavior. The connector
now recognizes explicit error envelopes regardless of process exit status, and
the shared quota classifier recognizes the provider's `usage balance exhausted`
wording. Regression coverage reproduces the exit-zero envelope and verifies
that one refusal opens the run-scoped quota circuit before another agent call.
Evidence:
`runs/benchmarks/grok-4-6-grok-cli-participant-v6-fixed-seeds11-41-20260823-161608/grok-4-6-build-v6-seed11/run-usage-partial-tick-21.jsonl`,
`runs/benchmarks/grok-4-6-grok-cli-participant-v6-fixed-seeds11-41-20260823-161608/grok-4-6-build-v6-seed41/run-usage-partial-tick-20.jsonl`,
`agent_world/grok_brain.py`, `agent_world/provider_limits.py`,
`tests/test_grok_brain.py`, `tests/test_provider_limits.py`.

## 2026-08-22 -- Grok's backend model label poisoned its next request

**The direct Grok CLI connector successfully obtained one decision per agent
from Grok 4.6, then mistook the backend response label `grok-4.6-build` for a
callable model ID and fabricated 360 wait actions after Grok rejected every
subsequent request.** Both Participant-v6 seeds launched with the public model
name `grok-4.6`. All 20 tick-0 calls succeeded, resolved to
`grok-4.6-build`, and returned contract-valid decisions. The connector then
assigned that response label to `resolved_model` and reused it in the next
`--model` argument. From ticks 1 through 18, every one of 360 calls failed
with the same `unknown model id` error. Because the connector returned a
synthetic `wait` decision instead of stopping the world, all 20 agents died at
tick 18 and the empty worlds advanced to tick 50.

This is harness behavior, not Grok capability. The generated reports compound
the error by claiming clean integrity, clean quality, zero decision failures,
protocol compliance, and replication eligibility even though their own usage
ledgers mark 180 ambiguous-boundary payload-extraction failures per seed. The
frozen scorer mechanically pools the corrupted worlds to 22.20 execution and
zero competence and entrepreneurship, but those numbers must never be used as
a model result. The only genuine model evidence is first-turn behavior: 20/20
contract-valid, purposeful decisions submitted 66 actions, of which 60 were
feasible; successful calls had 30.59-second median latency, 41.14-second p95,
31,876 reasoning tokens, and $0.14152364 of provider-reported usage. Evidence:
`runs/benchmarks/grok-4-6-grok-cli-participant-v6-seeds11-41-20260822-233838/{study-manifest.json,grok-4-6-direct-v6-seed11,grok-4-6-direct-v6-seed41}`
and launch commit `da4cf018e7be0cea68dca8c5f71d19f240b82167`.

## 2026-08-22 -- Ox Alpha's repair oracle exposed both a capability split and a certification trap

**Deterministic shape repair raised Ox Alpha's Participant-v6 contract-valid
rate from 17.8% to 91.9%, but both repaired populations still went extinct—and
the frozen aggregator would have mislabeled the controlled intervention
“certified.”** Across seeds 11 and 41, the declared `ox-alpha-schema-v1`
oracle modified 544/714 responses (76.2%): 528 message-field renames and 20
memory-object conversions. Fifty-eight decisions still violated the unchanged
contract after repair. Both cells had 100% usage coverage and no provider,
quota, harness, or ambiguous-boundary failures.

Frozen Participant-v6 tooling at the clean launch commit pools the repaired
variant to 69.13 execution, 0.0 sustained competence, and 0.0 entrepreneurial
agency. At tick 30 the two worlds still had nine and seven living agents with
competence 58.27 and 53.34; by tick 40 only two and one remained, and all 20
were dead by ticks 46 and 43. The agents completed seven structures and sent
576 communications, but accepted no trades, formed no group or contract,
supplied no enterprise value, and accumulated 710 invalid proposals. Interface
normalization therefore recovered substantial action-selection ability without
recovering survival or economic coordination.

The certification failure is a harness-provenance issue, not model behavior.
The study manifest correctly declares `raw_with_declared_structural_repair`
and diagnostic-only status, and 544 usage rows preserve original and repaired
payloads plus hashes. The generated run manifests nevertheless record
`decision_mode=raw`, their reports mark `protocol_compliant=true`, and the
launch-commit aggregator consequently prints `certified`. Artifact evidence
overrides that label: the result belongs to a controlled diagnostic variant
and must never enter the unassisted leaderboard. Evidence:
`runs/benchmarks/ox-alpha-openrouter-participant-v6-repair-oracle-seeds11-41-20260821-170222/{study-manifest.json,ox-alpha-repair-v6-seed11,ox-alpha-repair-v6-seed41}`.

## 2026-08-21 -- Ox Alpha knew the decision keys but not their contract

**Ox Alpha returned all four required top-level decision keys on every failed
startup call, yet 47 of 50 outputs still violated nested types, showing that
JSON-object mode can hide a near-total schema-following failure behind
syntactically perfect JSON.** The model's sole OpenRouter route advertises
`response_format` but not `structured_outputs`; strict JSON-schema requests
at both medium and high effort were rejected before inference, and forced tool
choice was also unavailable. Under the route's supported `json_object` mode
at Participant-v6's locked medium effort, 41/50 decisions made
`memory_updates` an object instead of an array and 6/50 omitted
`messages[0].mode`. Only 3/50 passed the unchanged independent contract, so
the mandatory tick-5 health gate stopped seed 11 and seed 41 was never
launched.

This is confirmed model behavior under a weaker transport contract, not a
provider outage or parser artifact: all 50 calls resolved to
`stealth/ox-alpha` through provider `Stealth`, usage coverage was 100%,
and there were zero ambiguous-boundary, provider, quota, or harness failures.
It is not a leaderboard result because the run ended at tick 5. The finding
extends the 2026-08-18 structured-output insight: exact top-level keys and valid
JSON are poor proxies for contract compliance, and an alpha model without a
schema-enforcing route cannot be compared fairly to models whose outputs are
physically constrained. Evidence:
`runs/benchmarks/ox-alpha-openrouter-participant-v6-seeds11-41-20260821-155324/ox-alpha-v6-seed11-json-object`.

## 2026-08-18 -- GLM 5.2 spent the decision envelope before deciding

**Under Participant-v6's fixed 5,000-token completion envelope, GLM 5.2
repeatedly consumed the whole response on deliberation and never emitted a
usable decision, while Qwen3.8 Max completed the identical OpenRouter contract
with zero decision failures.** Across GLM's two completed seeds, 48/696 calls
reported at least 5,000 completion tokens and every capped call failed. Thirty-
five returned no content with `finish_reason=length` (15 on seed 11, 20 on
seed 41), leaving only provider envelopes full of reasoning and therefore an
ambiguous model/adapter boundary. Thirteen more capped calls exposed a partial
or malformed decision and were independently confirmed as model-output
violations. Another 11 confirmed contract violations occurred below the cap.
Participant-v6 consequently excludes both GLM cells from certification despite
their reaching tick 50 with 100% usage coverage and no harness or provider-
request failures.

This was not one bad routed backend: the 35 reasoning-only boundary failures
spanned Alibaba (24), Baidu (4), GMICloud (4), StreamLake (2), and DeepInfra
(1). It is also not evidence that structured output itself was unavailable:
the earlier fence-normalization diagnostic had already separated transport
formatting from decision validity. Qwen3.8 Max then supplied the control: the
same strict schema and medium-effort v6 envelope produced 677/677 attributable
decisions, with no model-output, boundary, provider, or harness failures.

The benchmark lesson is that a shared output ceiling is also a deliberation
budget when providers place reasoning tokens inside `completion_tokens`.
Exhausting that ceiling can masquerade as an adapter failure unless the raw
provider envelope and `finish_reason` are retained. Evidence:
`runs/benchmarks/glm-5-2-openrouter-participant-v6-replicated-seeds11-41-20260818-120919/{glm-5-2-v6-seed11-fence,glm-5-2-v6-seed41-fence}`
and
`runs/benchmarks/qwen3-8-max-openrouter-participant-v6-replicated-seeds11-41-20260818-120919/{qwen3-8-max-v6-seed11-schema,qwen3-8-max-v6-seed41-schema}`.

## 2026-08-18 -- Structured output still needed transport normalization

**OpenRouter's `json_object` response mode produced valid JSON that violated
Agent World's decision contract on 58-94% of startup decisions, while the same
models returned contract-valid decisions immediately when the connector used
their advertised strict structured-output support. But strict schema
enforcement did not make the provider boundary uniform: the Z.AI GLM 5.2 route
still wrapped otherwise valid objects in markdown ```json fences, while Qwen3.8
Max honored the same request without wrappers.** In matched five-tick
Participant-v6 `json_object` diagnostics, GLM 5.2 failed 39/50 and 29/50
decisions across seeds 11 and 41; Qwen3.8 Max failed 47/50 and 44/50. The
dominant error was a speech object without the required `mode`, followed by
overlong or wrongly typed memory updates. All four startup health gates stopped
as designed.

Switching to strict `json_schema` plus `provider.require_parameters = true`
eliminated those contract-shape failures for Qwen. It exposed a second harness
artifact for GLM: 11/50 seed-11 outputs and 7/75 recorded seed-41 outputs were
attributed as invalid JSON, and every preserved raw response was a balanced,
parseable decision inside markdown fences. Seed 11 stopped at the startup
health gate; seed 41 was interrupted after the artifact was confirmed. This
was not a model-decision failure because the production parser already accepts
the same fenced object. The independent validator now performs only that
deterministic extraction before attribution; truncated or otherwise malformed
JSON remains a failure. All affected cells remain excluded and must not be
resumed.

The broader lesson is that advertised structured-output support constrains the
object but does not guarantee identical transport formatting across routed
providers. Validate the raw provider envelope before turning a schema error
into a cross-model capability claim. Evidence:
`runs/benchmarks/glm-5-2-openrouter-participant-v6-replicated-seeds11-41-20260818-120919`,
`runs/benchmarks/qwen3-8-max-openrouter-participant-v6-replicated-seeds11-41-20260818-120919`,
and `agent_world/openrouter_brain.py` on commit
`5b2f8dfcdb8fafc1bef601f1047bfdaa552d3301`.

## 2026-08-04 — OpenRouter runs silently lacked latency telemetry

**OpenRouter usage records had no `duration_seconds`, so a completed API-backed
benchmark would have looked latency-free even though every other provider path
and the model database treat end-to-end decision latency as a first-class
metric.** The omission surfaced during the corrected DeepSeek V4 Flash 0731
startup: seed 11 had written 19 usage rows and seed 41 had written 24, none with
a duration, while the calls were visibly taking tens of seconds or longer.
Because only completion timestamps were recorded, individual call latency could
not be reconstructed reliably under four-way concurrency.

This was a harness observability gap, not model behavior. The cells were stopped
around ticks 1-2 before a long benchmark accumulated, and the OpenRouter
connector now records monotonic end-to-end duration across the provider call,
adapter retries, and response validation on every usage row. Evidence:
`runs/benchmarks/deepseek-v4-flash-0731-openrouter-participant-v7-replicated-seeds11-41-20260804-200513`
and `tests/test_openrouter_brain.py`.

## 2026-08-02 — Agent-world concurrency is bounded by local process memory, not by any provider limit

**A worker ramp from 8 to 100 concurrent decisions found zero provider-side
throttling and a hard local wall: the ceiling is roughly 70MB of CLI
subprocess memory per concurrently-deciding agent.** Per-decision latency was
flat across a 3x concurrency increase (8 workers 13.0s median / 20.6s p95;
16 workers 12.6s / 19.1s; 24 workers 13.6s / 19.8s) while tick wall-clock fell
2.4x, from 75.7s to 31.6s. Across every cell there were zero timeout, retry,
stall, or quota events — the provider never objected to any concurrency level
tested.

The knee is at 24. Raising 24 -> 40 workers bought only 7% (31.6s -> 29.2s per
tick) because per-decision latency rose to 17.0s as the machine scheduled 40
subprocesses over 8 cores at load average 41; the wave-count saving and the
latency penalty roughly cancelled. At 100 workers on 100 agents the run had to
be stopped during tick 2: 8.3GB resident in Codex processes alone, free pages
down to ~4,000, sustained swapout growth, load average 86, and median decision
latency degraded to 23.3s — nearly 2x the 8-worker baseline. Still zero
provider failures. The laptop failed, not the account.

Two consequences followed on the laptop. First, 24 became its default Codex
worker ceiling. A 2026-08-24 desktop ramp superseded that machine-specific
recommendation: 40 workers was fastest with no swap, so the desktop default is
now 40. Claude Code and Grok Build use an inferred 20-worker default pending
equivalent provider-specific ramps. Second, this bounds large-population
ambitions more sharply than cost does: a 100-agent world needs roughly 7GB of
subprocess memory before the engine or the model bill is considered, so scaling
past ~40 concurrent agents requires a materially larger machine or distribution
across hosts. Notably the cloud sandboxes surveyed the same day (Codex Cloud
16GB/2 cores, Claude Cloud 15GB/4 vCPU) are SMALLER than the 24GB development
laptop, so moving execution to them would buy
laptop-independence and reliability but not headroom.
Evidence: `runs/experiments/worker-ramp-20260802/{w16,w24,w40,w100}`, with
per-cell resource samples in each directory and `w100/probe-status.txt`
recording the stop condition.

## 2026-08-02 — A stronger model traded more and still never touched the new contract primitive

**GPT-5.6 Sol, run in the identical 40-agent specialist world as Luna (same
map, seed, workers, effort — only the model differs), beat Luna on every
social and economic measure and still used delivery contracts and the town
ledger exactly zero times.** Sol: 21 deaths vs Luna's 32, 159 trade offers vs
100, 15 settlements vs 6, 36 gifts vs 13, 1,027 messages vs 358, enterprise
supply 2.25 vs 0.65. Contracts proposed: 0 and 0. Ledger notes: 0 and 0. In
roughly 4,000 combined decisions across the two runs, neither model invoked
either primitive once, despite `propose_contract`, `deliver_contract`, and
`post_ledger_note` being verified present in the static context both models
received.

The diagnostic that makes this sharp: across 1,385 in-world messages from the
two runs, **zero mention contracts, the ledger, deadlines, or promises at
all**. The agents are not weighing the instrument and rejecting it, nor
negotiating deals they then fail to formalize. It is simply absent from their
conception of the world while they talk constantly about immediate exchange.

**2026-08-30 causal update:** The non-adoption and absence-from-deliberation
measurements stand, but the proposed mechanism below was incomplete. A 30-cell
causal campaign found that AP price, action slots, output category, salience,
and cold start were not sufficient explanations. The dominant failure was
option neglect plus self-relative novelty: when forced to evaluate an empty
ledger, nine of ten agents said their private local facts were not novel. A
conditional public-novelty rule raised matched Sol adoption from 1 to 29 notes
and activated 6 contract proposals, 4 acceptances, and 3 settlements.

This answers the question the Sol cell was run to settle. Non-adoption is
**not** a capability threshold — Sol is clearly the stronger agent here, with
2.5x the settlements and a third fewer deaths — so a still-stronger model
should not be expected to discover the primitive either. The failure is in the
affordance: a four-action protocol (propose, accept, deliver, cancel) with an
absolute deadline parameter sits too far from the immediate "I need wood now"
frame agents actually reason in, and nothing in the world's feedback loop
points at it when an offer expires. Sol had 136 offers expire unaccepted and
never once reached for the mechanism built for that exact failure.

Settlement rates remain dismal in absolute terms even for the stronger model:
Sol closed 15 of 159 offers (9.4%), Luna 6 of 100 (6.0%). Adding instruments
did not fix settlement; the earlier finding that models do not converge on
acceptance stands, and now has a second data point at a higher capability
tier.
Evidence: `runs/experiments/comparative-advantage-20260802/{a4,s1-sol}`;
Sol cell run at 8 workers deliberately matching A4 so the model was the only
variable. See also the 2026-08-02 settlement-failure entry above.

## 2026-08-02 — Trade does not fail from autarky or thin markets; it fails at settlement

**A 2x2 designed to elicit trade by removing self-sufficiency (specialists)
and by thickening the market (40 agents instead of 10) moved nothing: every
cell traded less than the plain 10-agent generalist baseline.** GPT-5.6 Luna
at medium, 50 ticks, seed 11, frontier world. Enterprise supply per 100
agent-ticks: 10-agent generalists 3.8, 40-agent generalists 1.1, 10-agent
specialists 0.8, 40-agent specialists 0.7. The standing hypothesis that
models do not trade because generalists can supply themselves is therefore
**wrong**, and so is the market-thickness explanation; the two combined were
the worst cell of the four.

The funnel shows what actually breaks. Offers scale almost linearly with
population — 24, 22, 79, 100 across the four cells — while settlements stay
pinned at 5, 2, 6, 6. In the 40-agent specialist cell agents posted 100 trade
offers and closed 6; 94 expired unaccepted. Agents want to trade and try
*harder* when more counterparties exist. They cannot converge on acceptance.
"Models do not trade" was a mis-description of this behavior for the entire
project; the accurate claim is **models do not settle**, which is a
coordination failure rather than a preference or incentive failure. Note this
supersedes the framing (not the measurements) of the 2026-07-26 entry.

Second finding from the same cells: **zero contracts and zero ledger notes in
roughly 5,000 decisions**, across all four cells. Delivery contracts and the
public town ledger had shipped hours earlier and were verified present in the
agent-facing prompt (`propose_contract`, `deliver_contract`,
`post_ledger_note` all appear in the static context of these runs). The
instrument built precisely for "agree now, settle later" was never touched by
agents whose offers were expiring 94-at-a-time. Adding an affordance does not
create the behavior it affords.

Scope limits worth respecting: this is one model at one effort (Luna medium,
v6 competence 35.5, near the bottom of the table), so it does not establish
that stronger models behave the same way — a matched Sol cell is queued to
test exactly that. The larger world also costs something independent of
trade: 33 deaths at 40 agents versus 9 at 10, with invalid actions scaling
similarly.
Evidence: `runs/experiments/comparative-advantage-20260802/{a1,a2,a3,a4}`,
experiment id `comparative-advantage-20260802` in
`data/model-benchmarks.sqlite`.

## 2026-08-02 — Resumed-run manifests can dramatically understate elapsed benchmark time

**Manifest start/end timestamps are not a safe whole-run latency metric after
continuation: Sonnet 5 seed 11's usage ledger spans about 4 hours 8 minutes,
while its final manifest interval is only 14 minutes 53 seconds.** The first
recorded provider call ended at 2026-07-29 17:09:18 UTC and the last ended at
21:17:42 UTC, but `run-manifest.json` starts at 21:02:50 UTC. Seed 41 shows the
same pattern: usage begins around 17:09 UTC while the manifest covers only
21:24:47-21:33:32 UTC. A speed comparison based on manifests would therefore
make this model/run look far faster than the decisions actually experienced.

This is a harness/provenance artifact, not Sonnet behavior. The model metrics
database consequently stores three distinct clocks: per-decision end-to-end
latency, per-tick concurrent wall span, and the usage-ledger observed run span;
the manifest interval is retained separately and explicitly labeled as a
possibly partial launcher segment. Evidence:
`runs/benchmarks/claude-sonnet-5-participant-v6-certified-seeds11-41-20260729-164053/sonnet5-v6-seed11/run-usage.jsonl`,
`runs/benchmarks/claude-sonnet-5-participant-v6-certified-seeds11-41-20260729-164053/sonnet5-v6-seed11/run-manifest.json`,
and the matching seed-41 files.

## 2026-08-01 — Sequential turns fixed the problem they targeted and still made runs worse (recovered finding)

**Letting each agent see earlier same-tick resolutions before deciding
eliminated every one of the ~318 per-run invalid actions attributed to
unobserved prior events — and overall invalid rates still rose in all three
paired seeds (27.3% vs 26.1%), offers fell 24.3→18.3, completed structures
fell two→zero, at 6.2x the runtime.** Perfect information about the current
tick traded away planning independence and initiative, and the economy paid
for it. This is why `simultaneous-v1` is the default today. Recovered from
the July turn-mode experiment while archiving the `codex/experiment-observability`
branch; full design, statistics, and caveats in `docs/research-ledger.md`
(2026-07-16 entry), artifacts on the archived branch.

## 2026-08-01 — Luna's weak frontier result was effort-sensitive, not a fixed model ceiling

**Raising GPT-5.6 Luna from medium to max reasoning increased measured
deliberation eightfold (474 to 3,773 reasoning tokens per decision) and moved
the paired result from 35.5 to 65.1 competence: survival rose from 8/20 to
15/20, completed capital from one farm to 11 farms plus three shelters, and
entrepreneurship from 0.0 to 34.1.** The max variant kept strong execution
(88.6), produced seven settled trades, and ended with 528.625 of
living-accessible value versus the medium run's 176.25. Yet API-list-equivalent
cost rose only from $0.79 to $2.96 per run because Luna's token prices are so
low. The added reasoning did not solve everything: five agents still died,
endpoint health was only 471/2,000, most capital remained private farms, and
there were no groups, contracts, fees, or dividends.

This is a controlled model-behavior variant, not an official Participant-v6
replication. Reasoning effort was the only intended setting change, but the
max cells launched from a newer clean commit and therefore disclose different
source provenance rather than claiming automatic protocol certification.
Evidence:
`runs/benchmarks/codex-gpt-5-6-luna-participant-v6-max-reasoning-variant-seeds11-41-20260801-135403`,
compared with
`runs/benchmarks/claude-opus-4-6-gpt-5-6-luna-participant-v6-certified-seeds11-41-20260729-033735`.

## 2026-08-01 — Fable replication changed the economic story without changing basic competence

**Fable 5 kept 10/10 agents alive in both seeds and moved only from 85.1 to
87.1 competence, yet seed 41 generated 19 settled trades and 177.8
entrepreneurship versus two trades and 55.8 in seed 11—a 3.2x entrepreneurship
spread inside the same model and protocol.** The recovered seed-41 world
produced 115.75 units of enterprise supply versus seed 11's 12.0. A frozen
ledger review classified five of its seven primitive `gift` transfers as real
commerce: three payments for shelter access or upkeep and two settlements of
goods debts; the remaining food and water transfers were aid and stayed
unscored. The paired score is therefore 89.7 execution, 86.2 competence, and
130.5 entrepreneurship, not the conservative all-unclassified estimate.

This is model-behavior evidence that replication is especially important for
emergent market formation: a single Fable seed described survival and capital
competence reasonably well, but radically understated the model's propensity
to form a functioning exchange economy. The seed-41 continuation itself is
also recovery-dependent; its deterministic tick-32 reconstruction and clean
tick-50 integrity are documented separately above.
Evidence:
`runs/benchmarks/claude-fable-5-participant-v6-provisional-seed11-20260729-220002/fable5-v6-seed11`,
`runs/benchmarks/claude-fable-5-participant-v6-provisional-seed11-20260729-220002/fable5-v6-seed41-recovered-tick32`.

## 2026-07-31 — A completed-tick checkpoint can be rebuilt from paid decisions without rerunning the model

**An append-only decision ledger plus a deterministic world engine is enough
to recover an exact earlier simulation boundary even when the only surviving
pickle contains a later, corrupted world.** Fable 5 seed 41's checkpoint had
already advanced to tick 50 after the weekly-limit false negative, but its
ledger retained all ten real decisions for each of ticks 0-31. Replaying those
320 already-paid decisions reconstructed `state.tick=32` with all 10 agents
alive, 841 total health, and state digest
`07c35fd3f9ccdb085412bb665b16e4390b3052a6a841d7f8cc6ef9b76247fcf6`.
The recovery matched all 1,903 world-generated events through tick 31; the
only normalization required was the later, state-neutral addition of
`kind: gift` to legacy gift events. It preserved 2,549 interleaved world and
harness audit events, retained exactly 320 successful usage rows before tick
32, and quarantined 150 later usage rows rather than counting them toward the
resumed run.

This is a harness-recovery result, not model behavior. The practical lesson is
that checkpoints need not store every historical world state if the ledger
stores full decisions and transitions are deterministic—but recovery must
verify the replayed event stream, preserve the invalid tail separately, reset
provider sessions, and partition usage at the same completed-tick boundary.
Evidence:
`runs/benchmarks/claude-fable-5-participant-v6-provisional-seed11-20260729-220002/fable5-v6-seed41-recovered-tick32/recovery-manifest.json`,
created by `agent_world/checkpoint_recovery.py`; the original diagnostic
directory remains unchanged.

## 2026-07-31 — An unrecognized rate-limit message let the harness fabricate 18 ticks of agent behavior

**A Claude weekly-limit error the quota classifier did not recognize was
handled as an ordinary decision failure, so the harness substituted a `wait`
action for every agent and kept advancing the world for 18 ticks (144 failed
decisions, ticks 32-49) against a provider refusing every call.** The
adapter's marker list checked for "usage limit", "session limit", and "rate
limit"; the CLI emitted "You've hit your weekly limit · resets 2pm
(America/Los_Angeles)", which matches none of them. Three adapters each
carried their own near-duplicate copy of that list, so the gap existed in one
of them only. The failure was silent by construction: a fabricated `wait` is
indistinguishable from a chosen `wait` in the action stream, and the run
reported `completed 50/50`.

Two lessons beyond the bug. First, the integrity layer worked where the
adapter failed — the run was caught as `run_integrity_not_clean` /
diagnostic_only on ambiguous-boundary-failure volume, which is why nothing
corrupt reached a leaderboard. Defense in depth is what made an undetected
provider phrasing recoverable rather than silently score-changing. Second, a
substituted default action is the most dangerous possible failure mode for an
agent benchmark, because it is *valid* — it type-checks, it costs no action
points, and it looks like patience. Any harness that fills in a default on
provider failure is fabricating the very thing it measures.

Fixed by centralizing quota recognition in `agent_world/provider_limits.py`
(shared by all adapters, pattern-based rather than a marker list), by pausing
whenever an entire living population fails identically at the boundary
regardless of whether any classifier recognizes the text, and by waiting out
the reset and retrying the same tick instead of stopping.
Evidence: `runs/benchmarks/claude-fable-5-participant-v6-provisional-seed11-20260729-220002/fable5-v6-seed41`
(144 `agent_response` events carrying the weekly-limit text, ticks 32-49;
seed 11 of the same pair is clean at 89.6/85.1/55.8). Audit of all 37 v6
ledgers found this the only run in which the corrected code path was
reachable.
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
