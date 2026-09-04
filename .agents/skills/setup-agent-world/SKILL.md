---
name: setup-agent-world
description: Prepare a newly cloned Agent World repository for local use. Inspect the host, configure machine-local worker recommendations, verify Python and model harnesses, and guide required installation or sign-in. Use for first-time setup, migration to a new machine, or recalibrating local concurrency; not for launching runs or interpreting results.
---

# Set Up Agent World

Make a clone ready for reliable local runs without committing machine-specific
state or credentials.

## Inspect before changing

- Read `AGENTS.md` and the README quick start.
- Check the effective execution environment: operating system, Python version,
  logical CPUs, visible RAM, and whether the process is inside WSL. In WSL,
  visible RAM is the usable limit even when Windows has more installed.
- Inspect which connector CLIs are already available. Do not infer login state
  merely from an executable being present, and never print credential files,
  tokens, or populated environment values.

## Generate the host profile

Run:

```bash
python3 -m agent_world.cli setup --write-profile
```

This writes the default user-level profile reported by the command so shared
checkouts and isolated run worktrees use the same recommendations. Respect
`AGENT_WORLD_HOST_PROFILE` when the user needs a different location.

The recommendations are operational starting points:

- Codex uses the repository's measured CPU and subprocess-memory scaling.
- Claude Code, Grok Build, and ZCode begin at a conservative fraction of the
  host ceiling until that harness is calibrated.
- Other providers retain the ordinary low-concurrency default.
- Explicit run flags override the profile.

If WSL exposes materially less memory than the Windows host, explain the
relevant WSL memory configuration and that changing it requires shutting down
WSL. Do not edit host-level configuration without the user's authorization.

## Verify the software boundary

- Confirm the supported Python version and run the local unit tests before
  diagnosing provider setup.
- For each harness the user intends to use, follow that connector's repository
  documentation and source-level preflight. Install missing external software
  only with authorization.
- Start native sign-in flows when needed and pause at the point where the user
  must authenticate. Verify success without exposing secrets.
- A harness executable and a valid login do not prove a model is callable.
  Perform a paid or quota-consuming probe only when the user explicitly asks.

## Finish

Report the profile path, detected CPU and RAM, estimated global and
per-provider ceilings, installed/missing harnesses, authentication work still
needed, and validation results. Keep the host profile and credentials outside
Git. Use `$run-agent-world-experiment` only if the user asks for a smoke test or
calibration run.
