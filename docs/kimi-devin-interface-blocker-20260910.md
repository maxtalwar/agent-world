# Kimi K2.7: verified Devin interface incompatibility

The existing job `web-kimi-k2-7-42c16fa9d5bb` is preserved at seed 11 tick 0; seed 41 remains gated. This is not a quota wait. No inference or simulation resume was attempted in this investigation, and no checkpoint, model, source or seed was changed.

## Exact failure

The pinned connector launches:

```
devin --respect-workspace-trust false --agent-config CONFIG.json acp --model kimi-k2-7
```

Its configuration supplies the benchmark system instructions, `allowed_tools: []`, and empty permission lists. Native help-only parser checks reject `--agent-config` with exit 2 in every retained version: 3000.4.25, 3000.6.14 and 3000.10.21. The error is “unexpected argument '--agent-config' found”. The suggestion to put it after `--` means literal prompt text, not a supported configuration flag, and is not a repair.

Current binary SHA256: `ba1956450c0e0bf95f477ccd442a0b45b14765402b2377d6737ae758126d70cd`.

The installed documentation under `~/.local/share/devin/cli/_versions/3000.10.21/share/devin/docs/` confirms:

- Global `--config PATH` selects a user settings file. Its documented schema has permissions and model settings, but no system-instruction replacement or `allowed_tools` field. Renaming the flag is not a verified equivalent.
- `devin acp --agent-type` permits only `summarizer` or `review`. Summarizer has no tools but substitutes its own system prompt and persists its result through a post-iteration callback. Review exposes read and shell tools.
- Custom subagent profiles support system prompts and tools, but are invoked by a parent agent. They are not a supported top-level ACP agent type and would add a different model-call path.
- Default ACP initialization/session creation succeeds with the authenticated account and explicitly reports current model `kimi-k2-7`. Configuration exposes mode/model, not custom instructions or an empty tool list. Ask mode alone does not mean no tools.

Thus none of the locally verified interfaces is equivalent to the pinned custom-agent boundary. Existing evidence cannot support a repaired continuation or quota-wait claim.

## Available alternative and decision required

The existing Devin installation accepts `acp --agent-type summarizer --model kimi-k2-7` and opens an ACP session without an inference call. This is an available tool-less candidate for a separately declared connector variation. The summarizer session did not echo a model option, so actual response model and output-contract compatibility still require a bounded validation before any benchmark continuation. Do not silently treat it as the original connector or claim it is already validated. A default-agent permission-denial setup would likewise retain a different system prompt and exposed tools.

Native Kimi CLI and OpenCode were not installed at the checked standard local paths; no independently authenticated alternative connector was established. The viable next step is an explicitly approved same-model connector variation and its validation, or a provider interface that supports the original custom-agent configuration.

## Prevent recurrence

The repair branch adds a help-only preflight of the exact connector command. Authentication/model availability can no longer be mistaken for custom-agent compatibility; unsupported versions stop with a precise provider-unavailable message before inference. All 13 Devin adapter/ACP tests pass. This guard is for future launch-source integration; it has not been injected into the pinned study.

Preserved artifact SHA256 values:

```json
{
  "run-checkpoint.pkl": "8077c9617fd4e7bb094be768b833c11fa0c89e6c8e6c10f296f278c1bebf979f",
  "run.jsonl": "df4b0c8bf6ceb0885f6bcbf4763058f3b97ffb4c0adaf9a9543075cb96eb7673",
  "run-usage.jsonl": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
}
```

## Authorized alternative validation and catalog removal

The user approved testing the summarizer variation and requested removal of Kimi K2.7 from the launch catalog. A first setup attempt timed out fetching team settings; one bounded retry returned the requested diagnostic JSON with zero tool calls. ACP described its model only as “Summarizer”. A read-only query of that diagnostic session (`candle-nutmeg`) in the native session store revealed `model=swe-2-high`, `backend_type=windsurf`, despite `--model kimi-k2-7`. Therefore this built-in variant does not validate Kimi and must not resume the Kimi study. The existing checkpoint is unchanged.

The catalog now excludes `devin:kimi-k2-7` during discovery, including subsequent refreshes. Historical runs remain visible. Validation evidence is saved in the existing job's `connector-validation-20260910/` directory. The catalog and Devin tests pass (23 tests).
