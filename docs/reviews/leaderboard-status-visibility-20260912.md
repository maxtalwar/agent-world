# Leaderboard status and pending-run visibility — 2026-09-12

The model-name subtext now suppresses routine Certified, Replicated, and Reviewed
recovery statuses. Provisional single-seed results and controlled variants remain
marked. Admission notes and underlying provenance records are unchanged. Gemini
3.8's recovery note describes the owner-approved Antigravity CLI update; it does
not need a special operational label on the ranking table.

Pending runs from all evidence groups in the selected recipe now appear in the
visible Study activity panel, deduplicated by run ID. Previously a catalog fallback
could put a pending run under the collapsed Additional studies disclosure. That
section now holds results only. The previous source-routing repair restored the
normal projection; this fixes visibility during future fallback as well.

The live Opus 5 benchmark web-claude-opus-5-1m-680839180c53 recorded 377 calls for
seed 11 and 339 for seed 41 before the shared Claude session limit. Completed
checkpoints are ticks 37 and 33. Its quota event says "You've hit your session
limit · resets 5:30pm (America/Los_Angeles)" with reset 2026-09-13T00:30:00Z and
retry at 00:31Z. Controllers are alive and the existing run processes are waiting;
no new benchmark, restart, or extra quota probe was launched during this repair.
These records establish benchmark consumption, not an exact attribution of the
account's quota percentage; other Claude applications share the subscription.

Validation covers whole-page rendering, routine/meaningful subtitles, a pending
Claude run in a secondary group, duplicate prevention, and the live payload's
full model inventory, Gemini costs, and visibility of every pending study.
