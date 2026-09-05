# Participant v8 design notes

Status: design in progress; no recipe registered and no new runs launched.

## Agreed direction

- Build the next leaderboard on a new v8 recipe; preserve v6/v7 evidence.
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
- Audit candidate scores against retained evidence and constructed edge cases
  before freezing new formulas. Existing runs remain historical diagnostics
  under their original recipes when used to evaluate candidate scoring.

## Still unresolved

The user proposed extending the horizon from 50 to 60 completed ticks; this
remains a proposal, not an approved recipe change or run launch. At twelve
ticks per season, 50 ticks includes spring, summer, autumn, winter, and two
ticks of the next spring. Sixty ticks completes that second spring: five
season blocks, not five annual cycles.

A longer horizon gives stored supplies and productive investments more time
to affect observed health. It does not eliminate the terminal-stockpile
blind spot: two societies with identical health trajectories still receive
equal capability even if one has more useful reserves at the cutoff.
Raw inventory value is not automatically a measure of future survival.

The horizon also changes the phase emphasized by the current twelve-tick
tail: at 50 it covers ten winter ticks and two spring ticks; at 60 it covers
a complete spring. Sixty is a candidate for assessing post-winter recovery,
not merely a longer version of the same scoring window. More ticks increase
potential decisions; cost and elapsed time will also depend on survival,
context length, and reasoning. Follow AGENTS.md's provider-specific experiment
replication and usage policy. No new study is authorized by this discussion.

Capability and execution components are implemented in
agent_world/outcome_scoring.py and reviewed in v8-capability-execution.md.
Capability is independent of execution and economic scoring; it combines
full-horizon and final-season population health. Execution is the fraction
of decisions free from output-contract violations and invalid action/message
proposals, with contention excluded. Neither is a generic intelligence score.

Enterprise remains undecided. The final v8 recipe is intentionally not
registered until enterprise and the remaining protocol decisions are complete.
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
