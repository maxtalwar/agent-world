# Grok startup authentication recovery — 2026-09-12

Run: web-grok-4-5-6f85c90bf7d7, participant-v8-revised, Grok 4.5 medium,
seeds 11 and 41; original source 3a0867cfaf6c598ce506485a93fbcaa660ddab0c.

Seed 11 stopped at tick zero during native model preflight. Seed 41 correctly
remained behind the startup gate. The event monitor did handle the incident,
but merely repeated the stored "not logged in" message and recorded an external
blocker without running a native authentication check. The UI still said that
monitoring follow-up was pending, which did not describe the completed review.

The existing Grok CLI's `grok models` check returned exit zero, confirmed the
saved grok.com login, and listed both grok-4.5 and grok-4.6. No new sign-in,
credential replacement, model substitution, or connector migration was needed.
The managed resume used the original checkpoint/source and produced completed
world ticks beyond the stopped tick. At verification, seed 11 reached tick 6,
the normal startup gate passed, and seed 41 reached tick 1. No frozen execution
source was edited.

The old preflight mapped every nonzero model-catalog result to "not logged in".
It did not preserve the original catalog error, so the exact initial native
failure cannot be reconstructed. The repair retries the native lookup once,
requires explicit authentication markers to report authentication failure, and
keeps catalog/network and quota failures distinct. This performs no model calls.

Execution compatibility review: only GrokBrain.preflight changed; prompts,
model/effort selection, decision execution, parsing, accounting, world mechanics,
and recipe files are unchanged. The execution lock's grok_brain.py hash was
updated after targeted adapter/recipe tests; no guard was removed or bypassed.
Existing pinned runs retain their original source and fingerprint.

The monitor now must perform a native check before recording a Grok sign-in
blocker. A valid login/model refuses that acknowledgment and instructs recovery.
The worker prompt and benchmark operating skill describe the same procedure.
The UI shows a completed external-blocker review truthfully and labels both
failed/gated seeds "Startup blocked" when they share the startup fault.
Opus's [1M] suffix is removed in shared display-name formatting; its exact native
model identifier remains unchanged.
