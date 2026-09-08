# Final Gemini/Sol regeneration comparison ? 2026-09-07

Batch: health-regeneration-20260907. Source/handoff: .worktrees/health-regeneration/docs/health-regeneration-experiment.md. Treatment source remains 9f296668f779fa281e269da98f73c1683e45b467. Diagnostic only; no leaderboard admission. This completed comparison supersedes the partial Gemini discussion in regeneration-expanded-results.md.

Both models and both seeds completed 60 ticks. All eight treatment/control reports have clean integrity and 100% usage coverage. Gemini finalization audited once: completed manifests, reports, snapshots, usage and checkpoints present. Returned Gemini identity is requested-only in the usage ledger; do not mistake the configured model label for independently verified provider identity. Transfers use the existing self-declared policy. World-config differences are exclusively regeneration settings; disclosure, stochastic decisions and nonconcurrent controls limit causal claims.

| Model | Seed | Health off ? on | Final health off ? on | Survivors off ? on | Production off ? on | Eligible ticks / restored HP |
|---|---:|---:|---:|---:|---:|---:|
| Gemini | 11 | 90.06 ? 91.84 | 71.80 ? 77.10 | 9 ? 10 | 152.83 ? 183.33 | 333 / 151 |
| Gemini | 41 | 75.26 ? 85.26 | 33.60 ? 64.80 | 8 ? 10 | 190.17 ? 166.33 | 287 / 206 |
| Sol | 11 | 73.95 ? 86.22 | 36.50 ? 65.50 | 10 ? 9 | 180.67 ? 160.83 | 374 / 168 |
| Sol | 41 | 81.26 ? 85.66 | 47.00 ? 71.70 | 10 ? 10 | 223.83 ? 167.83 | 373 / 214 |

Health uses all original agents, dead slots zero. Pooled raw health: Gemini 82.6583 ? 88.5458; Sol 77.6050 ? 85.9392. Gemini-minus-Sol narrows 5.0533 ? 2.6067 points. Endpoint health: Gemini 52.70 ? 70.95%, Sol 41.75 ? 68.60%. Gemini survival improves 17 ? 20; Sol changes 20 ? 19. Gemini therefore retains a small aggregate health lead while preserving more survivors in this treatment. This resolves the pending endpoint question for these seeds, not a general model ordering.

Baseline Gemini deaths occur at ticks 51 (seed 11), 52 and 56 (seed 41); treatment has none. Sol treatment loses agent-6 at tick 58 in seed 11; its controls have no deaths. Gemini restores 357 HP versus Sol 382: more healing alone does not determine the final ordering.

## Token accounting

API-list-equivalent USD, using the local rate card; not subscription charges. Accepted estimates select the last usage row per logical tick/agent; recorded attempts include all ledger rows. Provider calls without reported usage cannot be priced. Historical Gemini baseline report attempted-cost zero is stale and is not used as a price estimate.

| Model | Setting | Seed | Accepted estimate | Recorded attempts |
|---|---|---:|---:|---:|
| Gemini | off | 11 | 5.504338 | 5.504338 |
| Gemini | off | 41 | 6.166416 | 6.166416 |
| Gemini | on | 11 | 6.240231 | 6.240231 |
| Gemini | on | 41 | 6.446909 | 6.479098 |
| Sol | off | 11 | 25.576183 | 25.576183 |
| Sol | off | 41 | 25.262936 | 25.262936 |
| Sol | on | 11 | 25.050329 | 25.050329 |
| Sol | on | 41 | 25.950778 | 25.950778 |

[Detailed evidence](health-regeneration-final-comparison.json) preserves per-tick original-population health, raw metrics, diagnostic scores, deaths, recovery eligibility, cost fields, exact report paths and manifest provenance. Eligibility is unavailable for off controls because disabled regeneration emits no checks.

Validation: all eight event-reconstructed health trajectories exactly match frozen report health-point-tick numerators; terminal/coverage/artifact and config-difference assertions pass. Baseline database verify: 87 runs, integrity ok, no foreign-key errors. No simulation, checkpoint or source was modified.
