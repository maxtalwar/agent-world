# Participant v8 design notes

Status: 60-tick world configuration implemented; enterprise scoring and the
final benchmark recipe remain in design. No new runs launched.

## Agreed direction

- Build the next leaderboard on a new v8 recipe; preserve v6/v7 evidence.
- Run each benchmark world for 60 completed ticks with ten agents and
  twelve-tick seasons. Keep required benchmark seeds 11 and 41.
- Omit the message board.
- Use medium reasoning effort as the practical budget/quality baseline. Freeze
  the exact model/connector mapping and output/time ceilings; medium does not
  imply equal computation across providers. Document unsupported-setting
  exceptions explicitly rather than silently relabelling another setting.
- Retain explicit gift/payment/barter intent declarations; economic credit
  should be grounded in demonstrated outcomes, not a label alone.
- Keep the main table compact: Model, Capability, Execution, Enterprise,
  Cost/run, and Mean time/decision. Component metrics belong in detailed results.
- Latency is mean end-to-end decision-call duration, not tick duration or
  total run elapsed time divided by decisions. Preserve retry accounting;
  exclude between-call quota sleeps and machine downtime. Disclose provider
  and harness overhead and retain latency tails in detailed evidence.
- Do not add an inventory bonus to capability. Whether useful reserves or
  productive assets should count in enterprise remains a separate decision.
- Audit candidate scores against retained evidence and constructed edge cases
  before freezing new formulas. Existing runs remain historical diagnostics
  under their original recipes when used to evaluate candidate scoring.

## Implemented horizon and world template

[configs/run-configs/v8-world.example.json](../configs/run-configs/v8-world.example.json)
encodes the agreed world: 60 ticks, ten generalists, medium effort, no board,
self-declared commerce intent, and twelve-tick seasons. It is a managed
experiment template until enterprise scoring and the final recipe are ready.
It does not borrow v6/v7 recipe identity or claim v8 benchmark certification.
Replace its run ID and placeholder model/connector before an authorized launch.
Its single seed 11 follows the experiment usage policy; the eventual benchmark
recipe retains both seeds 11 and 41. Worker count is operational.

At twelve ticks per season, 60 ticks completes spring, summer, autumn, winter,
and the next spring: five complete season blocks. Capability uses all sixty
completed ticks and the final twelve completed ticks (49 through 60) as its
tail. Those final twelve outcomes result from the second spring's decisions.
The terminal state at tick 60 is the boundary before summer decisions begin.

The longer horizon gives stored supplies and productive investments more time
to affect observed health. It does not eliminate the terminal-stockpile
blind spot: identical health trajectories still receive equal capability
even if one society has more useful reserves at the cutoff. No inventory
bonus is included.

The old 50-tick horizon's final twelve outcomes span ten winter ticks and two
spring ticks. At sixty they cover a complete spring, emphasizing post-winter
recovery. More ticks increase potential decisions; cost and elapsed time also
depend on survival, context length, and reasoning. Historical 50-tick evidence
retains its original horizon and is not promoted to a 60-tick result.

## Scoring and remaining work

Capability and execution components are implemented in
agent_world/outcome_scoring.py and reviewed in v8-capability-execution.md.
Capability is independent of execution and economic scoring; it combines
full-horizon and final-season population health. Execution is the fraction
of decisions free from output-contract violations and invalid action/message
proposals, with contention excluded. Neither is a generic intelligence score.

Enterprise remains undecided. The final v8 recipe is intentionally not
registered until enterprise and the remaining protocol decisions are complete.
Its world defaults must use the approved 60-tick horizon; its final checkpoint
must also be tick 60.
The component scorer and offline review are usable now; historical recipes,
reports, and leaderboard rankings retain their original formulas.

## Cost evidence relevant to effort choice

The completed Luna board-off experiment had average per-world API-equivalent
cost $0.394544 at low and $0.8747855 at high; mean decision latency was 10.31s
and 24.68s. Output tokens including reasoning account for 48.5% and 73.5% of
total API-equivalent cost respectively. High is about 2.22 times the total cost,
but populations and decision counts also differ. This is not a max-effort
forecast or a measure of subscription allowance consumption.

OpenAI bills reasoning tokens as output tokens:
https://developers.openai.com/api/docs/guides/reasoning
Anthropic documents model-specific effort behavior and potential overthinking
at maximum effort:
https://platform.claude.com/docs/en/build-with-claude/effort

Local evidence: docs/luna-ledger-factorial-evidence-2026-09-05.json and the
eight usage ledgers referenced there. Input-token volume alone is insufficient
to infer cost dominance, particularly with cached prefixes.
