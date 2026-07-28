# Agent World model benchmarks

Agent World Participant v4 is the current standardized model benchmark suite.
It keeps the deterministic protocol and evidence safeguards from v3 while
correcting four construct-validity failures:

- an all-`wait` policy can no longer receive a perfect execution score, and
  neither can an all-`publish_rule` policy built from zero-cost actions;
- internal transfers and structure input cost no longer count as value created;
- entrepreneurial agency is no longer a restatement of terminal wealth: it
  scores enterprise supply, which sees a member selling to same-model peers;
- benchmark accounting units conserve value across every production chain, so
  no recipe can mint measured wealth through rounding.

Participant v1, v2, and v3 reports remain historical artifacts. They are not
silently rescored or mixed into a v4 leaderboard.

The [Participant v4 retrospective rescore](participant-v4-retrospective-rescore.md)
applies the v4 formulas to every preserved Spark and GPT-5.4 ledger without
re-running a simulation. The GPT-5.4 seed-11/41 pair is certified and the Spark
seed-11 trial is provisional on that evidence, both under audited declared
deviations; the remaining rescored runs are diagnostic.

Preserved examples include the
[GPT-5.4 v2 report](gpt-5-4-benchmark.md), the
[Spark v1/v2 diagnostic](gpt-5-3-codex-spark-benchmark.md), and the
[Spark v3 provisional report](gpt-5-3-codex-spark-v3-benchmark.md).

## Result tiers

- **Diagnostic:** any run, including mixed populations, stopped runs, degraded
  runs, historical protocols, and nonstandard seeds.
- **Provisional:** one integrity-clean, complete v4 run on predeclared seed 11.
  A trial run under an earlier protocol may qualify the same way certification
  does, and is labelled *provisional with declared deviation*.
- **Replicated certified:** one integrity-clean, complete v4 run on each
  required seed: 11 and 41. A trial run under an earlier protocol may qualify
  only through an audited entry in `BENCHMARK_ACCEPTED_PRIOR_TRIALS`, and is
  then labelled *certified with declared deviation*.

Certification pools raw numerators and denominators from seeds 11 and 41 for
the official score. The aggregate also retains both replication scores and
reports their range and absolute difference. Two worlds are not enough to
justify a formal confidence interval, so the benchmark does not report one.
Seeds 73, 101, and 137 may be run as optional extended evidence when budget
allows; they are displayed separately and never change or block the official
certified score.

Duplicate copies of a required seed are not certified evidence. Repeated-seed
studies remain useful diagnostics for model sampling variance, but they must
not overweight one world in the standardized pooled result.

## Frozen trial

Every benchmark run uses:

| Setting | Required value |
|---|---|
| Certification seeds | 11, 41 |
| Optional extended seeds | 73, 101, 137 |
| Population | 10 copies of one model |
| Horizon | 50 ticks |
| Diagnostic checkpoints | ticks 30 and 40 |
| Official endpoint | tick 50 |
| World | `organic-generalists` |
| Objective | neutral |
| Reasoning effort | medium |
| Decisions | raw |
| Action feedback | baseline |
| Resolution | simultaneous |
| Global/provider workers | 4 |
| Connector | `stateless-v3` |
| Provider conversation | stateless |
| Private agent I/O | enabled |

Launch the provisional seed:

```bash
python3 -m agent_world.cli run \
  --benchmark-protocol participant-v4 \
  --brain codex --model gpt-5.6-luna \
  --seed 11 \
  --out runs/benchmarks/luna-v4/seed-11/run.jsonl \
  --snapshot runs/benchmarks/luna-v4/seed-11/run-snapshot.json \
  --progress
```

Run the same command with seed 41 for certification, using a separate output
directory. Aggregate the two reports with:

```bash
python3 -m agent_world.cli benchmark \
  runs/benchmarks/luna-v4/seed-11/run-report.json \
  runs/benchmarks/luna-v4/seed-41/run-report.json \
  --out runs/benchmarks/luna-v4/leaderboard
```

If budget allows, add reports for seeds 73, 101, and 137 to the same aggregate
command. They appear as optional extended evidence without changing the
official two-seed score.

The benchmark flag locks every other setting. A conflicting option fails
before a model call.

## Scores

Higher is better. Effective execution and sustained competence range from 0
to 100. Entrepreneurial agency and its economic-productivity diagnostic start
at zero and have no maximum; 100 is a frozen reference target, not a ceiling.

### 1. Effective execution

This score replaces v3's planning-execution label:

```text
action feasibility =
  valid submitted proposals / submitted proposals excluding contention

purposeful activity =
  decision opportunities with at least one successful meaningful action
  / decision opportunities

effective execution =
  geometric mean(action feasibility, purposeful activity)
```

Same-tick contention is excluded from feasibility. Independently confirmed
model-output contract violations are invalid proposals. Provider, quota,
adapter, harness, and ambiguous-boundary failures invalidate the trial rather
than becoming model mistakes.

Purposeful activity counts at most once per agent-tick. Successful movement,
resource work, consumption, crafting, construction, ownership, exchange,
contracts, gifts, storage, and maintenance count. `wait`, `inspect`, and
communication-only ticks do not.

Neither do zero-action-point bookkeeping actions: `create_group`, `join_group`,
`leave_group`, `invite_member`, `publish_rule`, `record_agreement`,
`grant_access`, `revoke_access`, `reject_trade`, and `set_access_fee`. Counting
them would replace the all-`wait` exploit with an equally free
all-`publish_rule` one, since a model could emit one per tick at no cost. Free
actions that do move goods - `accept_trade`, `accept_contract`,
`repay_contract`, `claim_dividend` - still count. The rule is that purposeful
activity must cost something or move something.

This term prevents action spam from gaining extra activity credit and prevents
an all-`wait` policy from scoring 100. Waiting can still be strategically
correct; a model is not required to act on every tick. The rate simply makes
the amount of exercised agency visible alongside proposal accuracy.

### 2. Sustained competence

```text
geometric mean(
  effective execution,
  survival continuity,
  living-accessible material outcome
)
```

- **Survival exposure** is completed decision opportunities divided by the
  full target horizon.
- **Endpoint population health** includes dead agents as zero and living
  agents by remaining health.
- **Survival continuity** is the geometric mean of exposure and endpoint
  health.
- **Living-accessible material outcome** is living cohort value relative to
  three times starting endowment, capped at 100.

The material term stays bounded so extreme inventories cannot compensate for
collapse or ineffective execution. Uncapped economic output is reported
separately.

### 3. Entrepreneurial agency

```text
geometric mean(enterprise supply score, net value creation score)
```

Both halves are required, matching the two halves of the plain-language idea:
you built something that serves others, and the economy actually grew.

**Net value created** is the money-making half:

```text
max(0, living-accessible terminal value - starting endowment)
```

normalized per 100 possible agent-ticks, reaching 100 at 20 value per 100
agent-ticks and uncapped above it.

**Enterprise supply** is the business-building half. A cohort balance sheet
cannot show one member selling to another, but that is a limitation of the
instrument, not evidence that intra-cohort commerce is worthless. A farmer who
builds a plot and supplies nine neighbours is an entrepreneur even when every
neighbour runs the same model. Enterprise supply measures directional flow
rather than net worth, so it sees exactly that:

- **net goods supplied to others** - for each agent and each good, outflows to
  other agents minus inflows of the same good, counting only the positive
  remainder;
- **net service income** - access fees and contract premiums received, minus
  those paid.

**Own capital output** - goods produced from improved land the cohort built -
is reported alongside these but is deliberately *not* scored as supply. Those
goods stay in cohort inventory, so net value creation already counts them.
Scoring them here as well would count the same harvest events in both halves
of the geometric mean and re-couple the two axes, which is the defect this
construct exists to avoid. A cohort that builds producing capital is still
rewarded - through the value term, once.

Coin is excluded from the goods term. It is the medium of exchange, so paying
for food must not read as supplying it. Coin still counts as wealth in terminal
value.

Netting is per agent across all counterparties, not per trading pair, so value
that returns to its origin scores nothing:

- a straight round trip between two agents cancels exactly;
- a circular A->B->C->A flow also cancels, which per-pair netting would miss;
- reciprocal access fees between members cancel;
- completing a structure converts inputs into a same-value asset, so building
  alone scores nothing until the structure produces.

Only a persistent directional surplus - goods produced beyond what the producer
consumed, then supplied to others - can score. The component reaches 100 at 20
supply units per 100 possible agent-ticks and is uncapped.

The 20-per-100 anchor is mechanics-based, not fitted to observed behavior.
Accepting a trade costs no action points, so over a 500 agent-tick trial the
target is roughly one accepted trade per agent per twenty ticks - clearly
reachable.

Measured behavior is nowhere near it. Across the three complete 50-tick runs on
record, 22 trade offers produced **three** accepted trades in total, giving
enterprise supply rates of 0.6 to 1.0 per 100 agent-ticks. Current models
essentially do not trade. The benchmark reports that as a low score rather than
lowering the anchor to flatter it: an anchor fitted to whichever models happen
to be on the leaderboard would stop measuring anything. Expect enterprise
supply to behave as a near-binary "does this model trade at all" signal until
models improve.

**Venture initiatives are a diagnostic, not a scored component.** They count
attempts, and several qualifying actions - `set_access_fee` among them - cost
zero action points, so the initiative rate is too cheap to saturate to gate the
score. Enterprise supply subsumes the honest part of the signal: commerce that
happened rather than commerce that was proposed. Initiatives remain in every
report as evidence of intent.

Two consequences worth stating plainly:

- a pure foraging cohort accumulates value but supplies nobody, so it scores
  zero;
- a wash-trading cohort supplies nobody in net terms, so it also scores zero.

What the score still does not capture is pure arbitrage. A middleman who buys
low from one cohort member and sells high to another has zero net supply, and
their gain is a transfer from peers rather than new value. Measuring that
fairly would need heterogeneous preferences, external counterparties, or a
validated utility counterfactual that the current simulation does not provide.

### Economic productivity diagnostic

The uncapped value-creation component is also reported on its own. It shows
whether a cohort created living-accessible material value regardless of
whether it used entrepreneurial institutions. This keeps wealth information
visible without allowing it to overwhelm sustained competence.

## Recipe-consistent benchmark accounting units

V3 used the offline metrics table directly, which made some productive
transformations look like wealth destruction. V4 starts with that accounting
table and raises each single-output recipe's result to exactly its input total
divided by the output quantity.

Units are fractional by design. Rounding the per-unit value up would multiply
the rounding error by the output quantity, so minting eight coins from one
ingot would manufacture accounting value on every cycle - the same defect as
wash trading, relocated into the crafting layer. Exact division makes every
transformation conserve units.

| Resource | V4 accounting units |
|---|---:|
| coin | 2.375 |
| water | 1 |
| food | 2 |
| fiber | 2 |
| wood | 3 |
| stone | 4 |
| ore | 8 |
| ingot | 19 |
| tool | 12 |
| advanced tool | 43 |

Consequently, smelting two ore plus one wood into an ingot preserves exactly
19 accounting units, minting one ingot into eight coins preserves exactly 19,
and crafting an advanced tool preserves its 43-unit input bundle. No production
chain gains or loses measured wealth through the accounting itself. These units
exist only in offline metrics and benchmark scoring. The world engine does not
use or expose them as prices: agents choose trade bundles, and accepted bundles
are the only observed market terms.

## Integrity and versioning

A run is diagnostic-only when a required setting differs, the run stops early,
the population is mixed, external or harness integrity fails, usage coverage
is incomplete, or its fingerprint differs.

The run records a SHA-256 fingerprint of scoring code plus behavior-defining
provider, world, rule, map, model, interface, runner, and session sources.
Changing a formula, target, world, or harness requires a new suite version.
A narrow telemetry correction may use a scoring revision only when preserved
raw evidence can reproduce it without changing trial behavior.

V4 has no blanket compatibility exception for v3 reports: the old aggregates
do not contain the purposeful-activity construct and the economic formula
changed materially. A v3 *report* is never rescored as v4.

A v3 *trial* is a different matter. The event ledger and terminal snapshot are
the primary evidence, and every v4 metric derives from them, so a trial run
under an earlier protocol can be re-derived exactly. What it cannot do is
prove the model faced the same world. `BENCHMARK_ACCEPTED_PRIOR_TRIALS` is a
named allowlist for trials where that question has been audited and answered:
each entry stores the exact source fingerprint, the protocol it ran under, the
surviving deviation, and the audit that examined every other difference. A
fingerprint is only accepted under the protocol it was audited against, and
unknown fingerprints are never accepted.

Accepted trials are certified, not silently absorbed. Their status reads
`certified with declared deviation`, and the leaderboard prints the deviation
and its audit in full. Anything the audit cannot dismiss - a different horizon,
a real mechanical change, an unexamined difference - keeps the trial
diagnostic.

One entry exists today, covering the GPT-5.4 seed-11/41 pair. It ran under
`participant-v3` and differs from v4 in one line of static context: ore was
described as a "high-value raw material" rather than as smeltable into an
ingot. The audit checked the two other v4-era changes against the ledgers and
found neither binds. No structure in either run had more than one contributor,
so the construction contributor-share change is inert. Engine-declared trade
values never reached agents, because market history was already filtered to
give/receive bundles and event rendering never exposed event data at all.

The Spark seed-11 trial is accepted as provisional under two declared
deviations: the same static-context difference, plus an entry in
`BENCHMARK_ACCEPTED_ATTRIBUTION_OVERRIDES`.

That second list is the one place the suite trades a bright-line integrity
check for a judgment call, and it is deliberately awkward to use. An override
covers unverifiable model-output attribution only, matches on model, seed,
source fingerprint, and the exact count of unverifiable failures, and must
record both the measured sensitivity and who accepted it. A rescore yielding a
different count stops matching and the flag returns. It is an allowlist, never
a relaxation of the rule: any cohort outside it still fails on
`unverified_model_output_attribution`. The full audit is in the
[retrospective rescore](participant-v4-retrospective-rescore.md).

## Reporting standard

Human-facing reports put these scores first:

1. effective execution;
2. sustained competence;
3. entrepreneurial agency.

Supporting evidence must include proposal failures with denominators,
contention, action-point overruns, purposeful agent-ticks, survival, endpoint
health, living value, net value created, initiatives, decision/provider
failures, usage, result tier, and seed coverage.

Certified aggregate reports also include both required seeds' scores, range,
and absolute difference. Optional extended seeds are labeled separately.
Tick-30 and tick-40 trajectories remain diagnostics; only tick 50 is the
official endpoint.

Communication, prosocial behavior, leadership, deception, and antisocial
behavior remain unscored. Frequency alone is not a validated measure of their
quality or intent.
