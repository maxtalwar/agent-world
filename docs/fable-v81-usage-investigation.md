# Fable 5 v8.1 usage investigation — 2026-09-07

The observed quota exhaustion followed a substantial parallel workload, with no
evidence of runaway retries or a large increase in per-decision token usage.
The initial apparent Max-to-Pro plan difference was subsequently traced to stale
CLI metadata: a fresh sign-in changed the reported tier to Max. Whether stale
metadata affected server-side quota enforcement remains unresolved; token
telemetry does not measure percentage of a subscription quota.

## Evidence

Current run: `claude-fable-5-v81-20260907`, source
`d1e088e065324aede8a957371b83763511922311`, native `claude-fable-5`, medium.
Artifacts: `runs/managed/claude-fable-5-v81-20260907/seed-{11,41}/`.
Historical study: `runs/benchmarks/claude-fable-5-participant-v6-provisional-seed11-20260729-220002/`.

The historical `study-manifest.json` provider_compatibility records
`subscription_type: max`. The current installed Claude CLI's `auth status`
reported `subscriptionType: pro` at launch and during this investigation.
Historical evidence does not identify Max 5x versus 20x. Current metadata is not
an invoice or authoritative live billing entitlement.

Between 19:00:43 and 19:09:05 PDT on September 7, the current run recorded:

| Measure | Value |
|---|---:|
| Successful model decisions | 134 |
| Seed 11 / seed 41 decisions | 90 / 44 |
| Input tokens, including cache reads and writes | 863,295 |
| Cache-read tokens (subset of input) | 584,776 (67.7%) |
| Cache-write tokens (subset of input) | 278,251 |
| Output tokens, including estimated thinking | 119,702 |
| Estimated thinking tokens (subset of output) | 26,283 |
| Started requests / quota refusals | 140 / 6 |

All 134 successful records have distinct (run, tick, agent) identities and return
`claude-fable-5`. There are no other provider failure events. Six requests received
session-limit refusals around the cutoff; both cells then entered quota sleep.
No successful decisions were duplicated. Request-start events are telemetry,
not extra model calls in addition to usage records.

Seed 41 started at 19:05:20 after the startup gate. Four workers per cell permit
eight simultaneous calls across the two cells. Historical v6 had four workers
per cell too, but seed 11 finished at 22:57 UTC July 29 and seed 41 first returned
at 23:30 UTC, so those seeds did not overlap. Concurrency compresses usage into
less elapsed time; it does not itself multiply tokens per decision.

## Comparable early decisions

Compare the first 90 seed-11 decisions, avoiding v6's later, larger contexts:

| Measure | v6 | v8.1 | Change |
|---|---:|---:|---:|
| Input tokens | 554,225 | 593,501 | +7.1% |
| Output tokens | 82,904 | 83,646 | +0.9% |
| Cache-read tokens | 355,696 | 385,366 | +8.3% |
| Estimated thinking tokens | 18,406 | 19,448 | +5.7% |

Both use fresh/stateless decisions at medium effort. This is not a transition
from retained conversations to full-context requests. Historical cache-write
telemetry is absent; its missing field must not be interpreted as zero writes.
V6 seed 11 completed 500 decisions in about 56 minutes on the recorded Max plan.

## Subscription limits and uncertainty

[Anthropic's Max overview](https://support.claude.com/en/articles/11049741-what-is-the-max-plan)
describes 5x/20x usage tiers relative to Pro. This describes potential tier differences, but the successful authentication
refresh below means the initial Pro label is not evidence of a real downgrade
in current entitlement. The exact historical allowance remains unknown.
[The current Fable policy](https://support.claude.com/en/articles/15424964-claude-fable-models-on-your-plan)
says Fable draws on Max limits and uses usage credits on Pro. That conflicts with
combining this CLI's Pro metadata and the observed session-limit refusal into a
simple entitlement conclusion. Billing settings would be needed to resolve it.

The user reported approximately 8% weekly Fable usage; no prelaunch or postlaunch
account quota snapshot was captured. We cannot assign that entire percentage to
this job, infer exact quota token weights, or prove a provider limit reduction.
Claude and Claude Code share subscription usage according to
[Anthropic](https://support.claude.com/en/articles/11145838-use-claude-code-with-your-pro-or-max-plan).
The ledger's zero dollar cost is a subscription accounting marker, not proof of
zero token consumption or an independently verified invoice charge.

## Runtime disposition

Both worlds are frozen at completed ticks 9 and 4, with the four successful
seed-41 partial-tick decisions retained. Their `run_quota_wait` events specify
September 7 at 23:50 PDT (September 8 06:50 UTC) as the reset and automatic retry
time, including the manager's retry margin. No provider probes occurred during
the observed quota sleep. No run settings or pinned source were changed.
Reducing workers would spread consumption over time; it would not eliminate the
remaining benchmark workload. No extra usage, plan upgrade, or model substitution
was requested or enabled by this investigation.

## Correction: paid Max and successful authentication refresh

The user clarified that they paid for one month of Max and immediately scheduled
a downgrade to Pro for the following billing cycle. They explicitly authorized
publishing this clarification in the repository.
[Anthropic's pricing FAQ](https://claude.com/pricing) says downgrades take effect
at the end of the current billing period. The initial Pro CLI label therefore
was not sufficient evidence that their paid Max entitlement had ended.

On September 7, `claude update` found version 2.1.263 already current, and
`claude auth status` still reported Pro. A fresh `claude auth login --claudeai`
was then completed through the user's existing browser sign-in. The CLI returned
`Login successful`; a subsequent `claude auth status` reported authenticated
first-party subscription access with `subscriptionType: max`.

This verifies that the prior CLI plan metadata was stale. It does not establish
that scheduling the downgrade caused it, that the server enforced Pro limits,
or that refreshing the login restored any quota allowance. No subscription
change, purchase, extra-usage enablement, or model request was made to test that
hypothesis. The benchmark retained its checkpoint and recorded quota wait;
Run Monitoring received the verified authentication result.
