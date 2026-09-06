# Leaderboard model discovery

Model identities come from current connectors, never historical runs. Results
and activity only determine the recipe-specific "To benchmark next" shortlist.

Claude SDK initialization returns a short recommended menu. Other live connector
catalogs supply additional explicit Claude version candidates. Each candidate
must pass Claude Code's built-in `/model EXACT_ID` command with an exact-version
selection and zero model turns in a disposable, nonpersistent session. Checks
are cached for ten minutes, keyed by executable version. This verifies selection,
not inference or remaining quota; normal runtime identity guards still apply.

ZCode reads the same `provider.zai.models` or `providers.zai.models` catalog as
benchmark preflight, respecting `ZCODE_CONFIG_PATH` and otherwise using
`~/.zcode/cli/config.json`. Only IDs and names are returned, never credentials.

Native connectors win equivalent-model deduplication. The default browse view
shows native models without results or studies in the selected recipe. All models
and search retain access to the full catalog. Lab filters apply to both views.

## Decision-model eligibility

Discovery is not sufficient for inclusion. OpenRouter models must explicitly
advertise text input and exclusively text output. Image/audio/video inputs are
allowed; generated image/audio/video outputs are not. Missing modality metadata
is excluded rather than assumed compatible. Across all connectors, explicitly
named image generators, speech generators/transcribers, embedding and reranking
endpoints are excluded, including when a connector supplies no modality metadata.
This filters the benchmark picker; it does not restrict general laboratory runs.

## Muse tiers and study identity

Standard and Contributor use the same version identity for shortlist history and
active-launch duplicate checks. Their exact execution IDs remain unchanged in
requests and run evidence. Active Muse versions are omitted from all picker views,
including searches, and the server rejects duplicate tier launches from stale pages.

As checked on 2026-09-06, Meta's authenticated Muse Code subscription documentation
(<https://dev.meta.ai/docs/muse-code/subscriptions>) describes plan usage separately
from per-token API pricing. It does not establish a Contributor multiplier for
subscription allowance. Lower API pricing alone is insufficient to switch the
benchmark default or hide the tier's distinct data-use terms. Standard remains
unchanged pending documented subscription savings.
