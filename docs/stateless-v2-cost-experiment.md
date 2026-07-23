# Stateless v2 cost experiment

This paired experiment isolates connector-profile overhead for Codex and Cursor agents.

Experiment root:

`runs/experiments/stateless-v1-v2-cost-30a-50t-seed41-20260723-041213`

Both cells use world seed 41, stratified assignment seed 117, the `organic-generalists` preset, medium reasoning effort, baseline action feedback, raw decisions, and 50 target ticks. Each civilization contains seven Sol, seven Terra, eight Luna, and eight Grok 4.5 agents. The control uses `stateless-v1` plus `stateless`; the treatment uses `stateless-v2` plus `stateless`. `bounded-session-v1` is excluded.

The only intended treatment differences are the stable empty workspaces used by Codex and Cursor and the disabled irrelevant Codex skills in `stateless-v2`. Both profiles use the same newest installed Codex CLI so model availability and CLI version are not confounds.

Primary Codex outcomes are exact simulation credits, prompt tokens, cached tokens, output and reasoning tokens, successful decision coverage, and credits per successful call. Normalize total run cost for deaths and provider failures before interpreting it. Cursor does not expose comparable plan-window consumption; the user reported approximately 34% of the weekly Cursor limit used before launch preparation, followed by three bounded Cursor smoke calls. Cursor analysis should therefore emphasize successful calls, provider token telemetry, cache behavior, latency when available, and the user's post-run usage reading.

Both cells retain the automatic tick-5 model-health gate. Any partial tick discarded for provider or quota failure belongs only in its separate partial-usage audit ledger.
