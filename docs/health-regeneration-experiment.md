# Conditional health regeneration pilot — 2026-09-07

Question: do surviving agents recover when they establish sustainable access to
food, water and rest, and does this distinguish population recovery potential?

Treatment: 2 health per tick, capped at 100, after two consecutive damage-free
ticks with all three reserves at least half their configured maximum **after
passive decay**. Shortage or damage resets the streak; dead agents never heal.
Automatic recovery costs no action points. The prompt explains the rule only
when enabled. Rate zero is the legacy default. Agent streak state is checkpointed.
Private health_recovery events record actual restored health; health_recovery_check
records eligibility including full-health/no-healing ticks, excluded from agent
observation so telemetry does not displace their useful recent history.

Gemini 3.7 Flash via Antigravity and GPT-5.6 Sol via Codex each run seeds 11 and
41, ten agents, sixty ticks, medium effort, fresh-conversation connector-v3.
Configs in configs/run-configs/regen2-*-20260907.json inherit participant-v8-revised
world defaults. These are diagnostic experiments, not a changed benchmark.
Existing web-gemini-3-7-flash-medium-1ae63d77303d and
gpt-5-6-sol-v8-revised-20260906 provide the off baseline. No off runs are relaunched.

Source is based on a886e7e, the completed Gemini connector recovery revision;
original recipe and scoring are retained. Changes are regeneration mechanics,
its neutral rule disclosure, and the previously verified Gemini pricing rates.

Tests cover stable recovery, passive-decay thresholds, interruption, death, health
cap, pickle/checkpoint continuity, disabled prompt/events, and validation. Scripted
stable/alternating-shortage scenarios sweep rates 1/2/4: stable agents starting at
10 health finish sixty ticks at 69/100/100; alternating shortages never heal.
The chosen rate 2 permits substantial recovery without the rapid forgiveness of 4.

At completion compare per-tick original-population health, final survival, timing
of deaths, eligibility, restored health, production, and accepted/attempted token
costs. Do not interpret rank changes as a general model ordering. The agents may
change strategy in response to the newly disclosed mechanic; this is intended.
