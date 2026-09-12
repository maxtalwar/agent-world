# Main harness price coverage — 2026-09-12

The Cost/run column is API-list-price equivalent, not subscription spending. The shared rate card now covers all currently cataloged Codex, Claude Code and Grok models with published API rates, plus published legacy Claude versions. Codex Spark has no published equivalent on the verified API price page and remains explicitly unpriced; it must not inherit GPT-5.3-Codex pricing.

Verified sources:
- https://platform.claude.com/docs/en/about-claude/pricing
- https://developers.openai.com/api/docs/pricing
- https://docs.x.ai/developers/models

Opus 4.5: $5 input, $0.50 cache read, $6.25 five-minute cache write, $25 output per million tokens. Fable 5.1 has a $0.25 cache-read rate, unlike Fable 5's $1. Sol's published promotional standard rates are $4/$0.40/$5/$20. Sonnet 5 remains $2/$0.20/$2.50/$10; the official page explicitly cancels its previously scheduled September 1 increase.

Retained usage is normalized and deduplicated by record ID, including uncommitted attempts, then priced through the shared accounting implementation. Original reports, scores and model identity are not rewritten. The generated metrics database and portal use the current rate-card projection. Tests cover catalog model IDs, dated Claude aliases, context suffixes, the Fable cache distinction, and unavailable Spark pricing.

These token-only comparisons exclude cache storage and optional geographic/fast-mode uplifts. Existing request-specific long-context Astra accounting is retained. Benchmark decisions are far below long-context thresholds; no new claim is made for untested oversized requests.
