# Desktop Codex worker-ramp analysis

Date: 2026-08-24

## Question

How much Codex CLI decision concurrency can the new desktop sustain? Four
matched cells were run simultaneously with worker ceilings of 10, 20, 30, and
40. This is a deliberately adversarial host-load test: the four cells requested
an aggregate ceiling of 100 Codex processes, so the results include
cross-cell interference rather than estimating four isolated runs.

## Protocol

- Launch commit: `ff18504`
- Harness/model: Codex CLI, `gpt-5.6-luna`, medium reasoning
- World: `frontier-generalists`, 40 agents, 5 ticks, seed 11, 32x32
- Connector: `stateless-v3`; conversation mode: `stateless`
- Each cell set both the global and Codex provider ceilings to its named value.
- All cells used distinct `scripts/run-isolated-cohort` worktrees.
- Per-tick wall time is reconstructed as the span from the earliest call start
  (`time - duration_seconds`) to the latest call finish in each usage ledger.

## Results

| Workers | Observed peak calls | Run wall | Mean tick wall | Median tick wall | Call median | Call p95 | Calls/run-second |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 10 | 10 | 372.5 s | 73.5 s | 80.3 s | 16.2 s | 24.5 s | 0.537 |
| 20 | 20 | 241.5 s | 47.6 s | 48.3 s | 21.1 s | 26.6 s | 0.828 |
| 30 | 30 | 218.4 s | 43.1 s | 44.7 s | 20.8 s | 27.9 s | 0.916 |
| 40 | 40 | 168.4 s | 33.0 s | 31.4 s | 22.9 s | 30.0 s | 1.188 |

Relative to the 10-worker cell, whole-run throughput improved 1.54x at 20,
1.71x at 30, and 2.21x at 40. Individual calls slowed under contention--the
median rose from 16.2 seconds at 10 workers to 22.9 seconds at 40--but removing
the extra scheduling waves more than compensated. The 40-worker cell was 23%
faster than 30 workers and 30% faster than 20 workers by whole-run wall time.

Every cell completed 200/200 decisions with 100% usage coverage, zero LLM,
provider, quota, or harness failures, and clean benchmark-integrity status.
The four cells sent nearly identical prompt volume (2.425-2.431 million tokens),
so workload-size variation does not explain the ordering.

## Host observations

The WSL VM exposed 12 logical CPUs (Ryzen 5 3600), 15 GiB RAM, and 4 GiB swap.
During the sampled overlap it reached 99 simultaneous Codex child processes,
load average 31.63, and 88.4% sampled CPU. Minimum available memory was
12,273 MiB; swap usage, page-ins, and page-outs all remained zero. Summed
per-process RSS peaked at 10,907 MiB, but this double-counts shared pages and
must not be interpreted as physical consumption. `MemAvailable` and swap are
the meaningful pressure indicators.

The resource sampler began after the cells had started, but while all four
were still active; it captured 47 five-second samples through final completion.
Consequently, it proves a clean 99-process overlap with substantial memory
headroom but may not contain the experiment's absolute CPU peak.

The RTX 3070 does not accelerate this workload: Codex CLI inference is remote,
and local work consists of process orchestration, JSON handling, and simulation
updates.

## Recommendation

Use 40 as the desktop's tested-safe Codex ceiling for large runs. It was the
fastest tested setting, completed cleanly during a much harsher aggregate
100-worker overlap, and showed no memory or swap pressure. This experiment
establishes that the machine can handle **at least** 40 workers per run; it does
not locate the true maximum because no single-cell setting above 40 was tested.
The former 24-worker Codex benchmark default was conservative and is now 40.
For the ten-agent Participant benchmark, any ceiling above ten still has no
effect because only ten decisions exist in a tick.

The evidence for each cell is its `run-manifest.json`, `run-report.json`, and
`run-usage.jsonl`; host samples are in `host-resource-samples.csv`.
