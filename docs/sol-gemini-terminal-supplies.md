# Sol and Gemini 3.7: terminal supplies and late health

2026-09-07. Matched, accepted v8.1 no-healing runs: seeds 11 and 41, ten original agents per world, 60 ticks, medium effort. These are two independent worlds per model; twenty agents are not twenty independent replications. The differences below are descriptive, not a claim of statistical significance.

**Sol ends with much more food and more working farms. Gemini ends with better hydration and more remaining health, despite losing three agents during the final spring.** A health-only score does not capture all of these differences.

| At tick 60, combined across two worlds | GPT-5.6 Sol | Gemini 3.7 Flash |
|---|---:|---:|
| Survivors / original agents | 20 / 20 | 17 / 20 |
| Final health per original agent | 41.75 | 52.70 |
| Food carried by living agents | 57 | 10 |
| Food in active storage | 104 | 0 |
| Carried food per survivor | 2.85 | 0.59 |
| Carried + stored water | 18 | 18 |
| Mean food reserve per survivor, max 20 | 14.20 | 12.71 |
| Mean water reserve per survivor, max 20 | 11.00 | 14.24 |
| Mean energy per survivor, max 30 | 26.20 | 21.76 |
| Active farms | 8 | 2 |
| Active shelters | 4 | 7 |
| Active storage buildings | 4 | 0 |

Food reserve is the agent's internal reserve, distinct from carried or stored inventory. Per-survivor averages exclude dead agents and must not be mistaken for original-population health scores. Both models have zero active wells at the endpoint; counting all structures ever built would overstate usable infrastructure.

## Is the food advantage concentrated?

Yes. Sol carries 24 and 33 food in seeds 11 and 41; Gemini carries 3 and 7. Thus Sol's carried-food advantage appears in both matched worlds. All 104 units of Sol's stored food, however, occur in seed 41: 57 in agent-4's private store and 47 in agent-1's private store. Both owners are alive. These stores are not automatically available to every agent, and this one-world stockpile dominates the combined 161-versus-10 food comparison. Sol also has four active farms in each world; Gemini has zero and two.

Gemini is not uniformly exhausted. Its living agents have higher water reserves; neither world has a surviving agent at zero food, water or energy, although two survivors have only 2/20 food reserve. Sol has one survivor at zero water. Stored food alone does not establish future survival: ownership/access, maintenance, production and future actions matter.

## Winter versus the final spring

| Phase, health points lost per original agent | Sol | Gemini 3.7 |
|---|---:|---:|
| Last winter, action ticks 36–47 | 38.45 | 24.15 |
| Final spring, action ticks 48–59 | 2.75 | 8.30 |

Sol loses more health during winter, but stabilizes afterward. Gemini's three deaths all occur in the final spring, and it loses about three times as much population health as Sol in that phase. At winter's end, Gemini's mean food reserve is 2.5/20 in seed 11 and 7.3/20 in seed 41, versus Sol's 11.5 and 11.8. Its food reserve recovers among survivors by the endpoint.

This supports the narrower observation that Sol has a stronger food buffer and a more stable final health trajectory. It does not prove Gemini would fail in an extended run, or Sol would outperform it: we have not simulated that continuation. Extra winter weighting favors Gemini because its actual winter health loss is smaller. Endpoint health, winter resilience, and preparedness beyond the endpoint are distinct measurements.

## Sources

The [extracted evidence](sol-gemini-terminal-supplies.json) records snapshots, hashes, agent reserves, active structures, storage ownership and phase observations. Original source runs:

- `runs/managed/gpt-5-6-sol-v8-revised-20260906/seed-{11,41}/`
- `runs/managed/web-gemini-3-7-flash-medium-1ae63d77303d/seed-{11,41}/`

Each contains `run-report.json`, `run-snapshot.json` and `run.jsonl`. See the [rescoring report](v81-endpoint-winter-rescoring.md) for original versus revised capability scores and original-population health curves. Gemini's existing owner-accepted provenance exception remains unchanged.
