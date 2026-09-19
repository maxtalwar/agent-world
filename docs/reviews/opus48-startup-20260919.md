# Opus 4.8 startup and monitoring review — 2026-09-19

Run: `web-anthropic-claude-opus-4-8-2f56ee8bf651`, Participant v8.1,
OpenRouter `anthropic/claude-opus-4.8`, medium effort, seeds 11 and 41.
Launch source: `7a240d628660837340b03b96745ac2f3bea4a005`.

The monitor did review the September 16 startup failure and acknowledged an
`evidence_decision` at 06:56 UTC. The dashboard handled that resolution only
for completed runs awaiting provenance review, so the incomplete study
incorrectly displayed “Monitoring follow-up is pending.” The UI now displays
completed review, the required decision, and its reason outside collapsed details.

## Independent evidence check

Seed 11 stopped at the recipe's tick-5 startup health gate: 41/50 responses
failed independent validation (82%, against a 20% ceiling). Of those, 27 used
objects instead of strings for memory entries and 14 omitted message mode.
Nine passed. Seed 41 was never launched. Usage exists for all 50 requests.

The original monitor attributed the malformed outputs to model behavior without
checking whether the model received the contract. That conclusion was too strong.
The pinned `OpenRouterBrain._chat_payload` sends `response_format=json_object`
and the rulebook, but does not send `AGENT_DECISION_SCHEMA`. The rulebook names
`memory_updates` without its nested type and does not specify message `mode`.
Reconstructing the system prompt from the saved checkpoint using the pinned
source yields SHA-256
`b0bd9f0d40224a72f93e4be099e65f75a2b44298106121c7f417ab84dabe0a4d`,
matching all 50 recorded `static_prompt_sha256` values. This verifies a contract
communication gap; it does not prove that adding the schema will fix every response.

Evidence: `runs/managed/web-anthropic-claude-opus-4-8-2f56ee8bf651/seed-11/`
contains the checkpoint, usage ledger with failed raw responses, and `run.jsonl`
with the `run_health_check` event. Monitor event:
`.local/leaderboard-launches/events/1789541674293149876/`.

## Disposition

Keep the original checkpoint, accepted decisions, failed responses, source and
recipe unchanged. The managed resume path deliberately does not resume a
`startup_health_check_failed` cell. Do not bypass that gate or substitute successful
responses retrospectively. The original study remains stopped and seed 41 gated.

Proposed next scope: a separately identified, single-seed (11) diagnostic using
the same model and effort, with the complete existing decision schema supplied
in the prompt and unchanged output validation. Start with the five-tick health
check before authorizing a longer study. This changes the request conditions;
it must not be admitted as an unchanged Participant v8.1 benchmark. No diagnostic
or new model call was launched in this repair.
