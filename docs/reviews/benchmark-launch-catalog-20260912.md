# Benchmark launch catalog repair — 2026-09-12

The launch page became empty because recipe discovery ran execution verification
before returning recipe metadata, then silently discarded each failed recipe.
The existing pricing and Devin preflight changes in commits 212de24 and 29be9f5
no longer matched the reviewed implementation hashes for usage.py and
devin_brain.py. No recipe definition changed. The cached Claude warning was
unrelated and did not establish a current subscription quota block.

Recipe discovery now retains metadata and model choices for blocked recipes,
exposes a concise launch blocker, and continues to reject launch previews.
Other discovery errors are logged and surfaced instead of yielding an apparently
healthy empty catalog. The browser explicitly selects the first recipe when
there is no matching leaderboard and displays an error if no recipes load.
Cached optional Claude discovery failures no longer claim a current rate limit.
Daily saved-catalog refresh behavior is unchanged.

Validation: 48 Python launch/catalog tests and the browser picker regression
script pass. Coverage includes retained blocked recipes, rejection of their
launch previews, empty-catalog errors, and stale-warning wording.

The compatibility-lock update is a separate pending action requiring explicit
owner approval from automatic approval review. Until it is applied and verified,
launches remain blocked. Read-only review found only help-parser preflight and
pricing changes; 35 connector, pricing, historical-v6, and v6.1 compatibility
tests passed. The prepared update changes only the two expected hashes and adds
the imported pricing constants module to the guarded file set.
