# Agent World benchmark: agent-world-participant-v4

| Model | Seeds | Execution | Competence | Entrepreneurship | Invalid proposals | Status |
|---|---:|---:|---:|---:|---:|---|
| gpt-5.4 | 11,41 | 86.8 | 71.9 | 23.8 | 406 (12.3%) | certified with declared deviation |

## Per-replication scores

| Model | Seed | Role | Execution | Competence | Entrepreneurship |
|---|---:|---|---:|---:|---:|
| gpt-5.4 | 11 | certification | 85.3 | 72.1 | 25.2 |
| gpt-5.4 | 41 | certification | 88.3 | 70.8 | 21.7 |

Descriptive spread:

- gpt-5.4: official competence range 70.8–72.1, absolute seed difference 1.3.

## Declared deviations

- **gpt-5.4** (seed 11, 41) ran under `participant-v3`, accepted as v4 evidence after audit.
  - Deviation: static_context_mechanics_text: ore was described as a 'high-value raw material' rather than as smeltable into an ingot. One line of a 6,430-character static context.
  - Audit: The other two differences introduced with v4 were checked against these ledgers and do not bind. No structure in any run had more than one contributor, so the construction contributor-share change is inert. Engine-declared trade values never reached agents: market history was already filtered to give/receive bundles and event rendering never exposed event data. Trial settings, horizon, integrity, and usage coverage all match v4 exactly.
