# Participant v8 design notes

Status: design in progress; no recipe registered and no new runs launched.

## Agreed direction

- Build the next leaderboard on a new v8 recipe; preserve v6/v7 evidence.
- Omit the message board.
- Retain explicit gift/payment/barter intent declarations; economic credit
  should be grounded in demonstrated outcomes, not a label alone.
- Keep the main table compact: Model, Competence, Execution, Enterprise,
  Cost/run, and Mean time/decision. Component metrics belong in detailed results.
- Latency is mean end-to-end decision-call duration, not tick duration or
  total run elapsed time divided by decisions. Preserve retry accounting;
  exclude between-call quota sleeps and machine downtime. Disclose provider
  and harness overhead and retain latency tails in detailed evidence.
- Audit candidate scores against retained evidence and constructed edge cases
  before freezing new formulas. Existing runs remain historical diagnostics
  under their original recipes when used to evaluate candidate scoring.

## Still unresolved

Reasoning effort is not selected. The user prefers exploring whether low or
maximum supported effort provides a clearer cross-model policy than an
intermediate label. Endpoint policies reduce mapping ambiguity; they do not
equalize computation. Maximum supported effort is a reproducible configuration
choice, not proof of a model's best achievable score or unlimited deliberation.
The exact model/connector setting and any output/time ceiling must be frozen.

Medium remains a possible budget/quality compromise, not a more standardized
setting. No maximum-effort study is authorized by this discussion. Follow
AGENTS.md's provider-specific experiment replication and usage policy.

Competence and enterprise formulas are not frozen. Proposed directions are
to separate execution from outcome scores, consider health/capacity over time,
and evaluate realized productive output/useful exchange without double
counting, circular-trade rewards, or automatic enterprise erasure from negative
terminal living wealth. The exact treatment of subsistence, charitable supply,
productive investment, and collapse needs explicit examples and agreement.

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
