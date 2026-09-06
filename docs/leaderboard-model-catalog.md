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
