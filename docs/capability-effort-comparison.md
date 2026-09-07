# Capability effort comparison

Matched seed 11, 60 ticks, ten agents; diagnostic experiments versus historical medium baselines.
All four completed with clean integrity, 100% decision usage coverage, zero output/provider/harness
failures and no discarded or unaccounted attempts. Requested model identity is retained;
the CLI does not independently return serving model or observed effort. All use Codex CLI 0.147.0.
World configs and static prompt hashes match. Both high runs and 5.5 medium pin 39232e4.
Mini medium pins 783341a; the only intervening package change is managed-launch PATH capture
and preflight validation, not engine, prompt, parser, connector or scoring changes.
High runs are diagnostic_only; benchmark fingerprint/effort flags do not invalidate this
deliberately non-benchmark comparison. Do not add them to the medium leaderboard.

| Model | Effort | Capability | Execution | Production | Survivors | Reasoning/call | Seconds/decision | API-equivalent $/world |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 5.5 | medium | 57.64 | 82.43 | 119.17 | 4/10 | 81 | 8.60 | 16.95 |
| 5.5 | high | 74.49 | 86.84 | 173.83 | 9/10 | 385 | 12.49 | 25.55 |
| 5.4 Mini | medium | 55.28 | 89.19 | 82.00 | 3/10 | 1377 | 23.88 | 3.80 |
| 5.4 Mini | high | 66.28 | 88.50 | 116.00 | 7/10 | 3464 | 52.16 | 9.51 |

Costs use each frozen report's September 5 rate card, not current prices or subscription charges.
Longer survival increases decision count, so full-world cost changes also reflect more decisions.

## Behavioral diagnostics

### 5.5 medium

- Season mean health: 98.08, 86.69, 61.34, 28.67, 13.43.
- Completed structures: {'farm_plot': 2, 'storage': 1}. Production by source: {'chop': 54.0, 'craft_value_added': 3.0, 'fish': 18.0, 'gather': 484.0, 'harvest': 152.0, 'mine': 4.0}.
- Damage cause occurrences (causes can overlap): {'thirst': 78, 'hunger': 71, 'storm_exposure': 10, 'winter_exposure': 86}.
- Zero-reasoning calls: 79.55%; successful actions per decision: 3.00.
- Accepted trades: 0; gifts: 1; groups: 0.
- Evidence: [gpt-5-5-v8-revised-20260906](../runs/managed/gpt-5-5-v8-revised-20260906/seed-11/run-report.json).

### 5.5 high

- Season mean health: 99.75, 94.21, 81.56, 58.48, 38.44.
- Completed structures: {'farm_plot': 7, 'storage': 1}. Production by source: {'chop': 180.0, 'fish': 22.0, 'gather': 547.0, 'harvest': 262.0, 'mine': 32.0}.
- Damage cause occurrences (causes can overlap): {'thirst': 44, 'hunger': 10, 'storm_exposure': 10, 'winter_exposure': 118}.
- Zero-reasoning calls: 25.26%; successful actions per decision: 3.03.
- Accepted trades: 0; gifts: 1; groups: 0.
- Evidence: [gpt-5-5-v81-high-capability-probe-20260906](../runs/managed/gpt-5-5-v81-high-capability-probe-20260906/seed-11/run-report.json).

### 5.4 Mini medium

- Season mean health: 98.88, 84.23, 51.22, 28.49, 13.58.
- Completed structures: {}. Production by source: {'chop': 48.0, 'fish': 16.0, 'gather': 360.0, 'mine': 68.0}.
- Damage cause occurrences (causes can overlap): {'thirst': 111, 'hunger': 44, 'exhaustion': 6, 'storm_exposure': 10, 'winter_exposure': 63}.
- Zero-reasoning calls: 0.00%; successful actions per decision: 1.87.
- Accepted trades: 0; gifts: 0; groups: 0.
- Evidence: [gpt-5-4-mini-v8-revised-20260905](../runs/managed/gpt-5-4-mini-v8-revised-20260905/seed-11/run-report.json).

### 5.4 Mini high

- Season mean health: 100.00, 87.82, 68.35, 48.73, 26.52.
- Completed structures: {'farm_plot': 2, 'storage': 1}. Production by source: {'chop': 99.0, 'fish': 26.0, 'gather': 441.0, 'harvest': 62.0, 'mine': 68.0}.
- Damage cause occurrences (causes can overlap): {'thirst': 64, 'hunger': 40, 'exhaustion': 1, 'storm_exposure': 10, 'winter_exposure': 96}.
- Zero-reasoning calls: 0.00%; successful actions per decision: 2.21.
- Accepted trades: 4; gifts: 0; groups: 0.
- Evidence: [gpt-5-4-mini-v81-high-capability-probe-20260906](../runs/managed/gpt-5-4-mini-v81-high-capability-probe-20260906/seed-11/run-report.json).

## Interpretation and limits

5.5 gains 16.85 Capability points; Mini gains 11.01. The gap widens from 2.36 to
8.20, a 5.84-point difference in observed effort gains. Production rises 45.87%
for 5.5 and 41.46% for Mini. Most health separation emerges after the first season.
Both models improve in Capability and Production. 5.5 gains more Capability, while Mini's
Execution slightly decreases despite substantially better survival and output. Thus a higher
valid-action fraction alone does not explain improvement. This supports preserving Execution
as a separate narrow metric rather than using it to predetermine Capability.
The same fixed Capability formula already distinguishes the high-effort outcomes; a score
redesign is not required to reveal this gap. Healing remains a separate world-design question.
Both models allocate more reasoning. 5.5 remains much more token-frugal even at high.
This strengthens the under-deliberation hypothesis, but does not establish that every score
difference is caused by reasoning tokens. There is one world per condition and historical
rather than randomized repeated baselines; ten interacting agents are not ten independent
replications. Do not compare high seed 11 against pooled medium seeds 11/41.
High is a promising experimental setting, not grounds on its own to change the baseline
for every provider. No new world mechanics or scoring changes were made.

Reproduce: python3 scripts/compare-capability-effort.py. Exact numerators, derived metrics,
per-tick trajectories, provenance and evidence hashes are in capability-effort-comparison.json.
