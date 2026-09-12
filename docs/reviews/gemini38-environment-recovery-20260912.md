# Gemini 3.8 recovery evidence decision ? 2026-09-12

Restored exact saved wrapper routing and verified progress beyond tick 25, but its payload self-updated despite AGY_CLI_DISABLE_AUTO_UPDATE=1 from 93eb2118 to 38f130cd before recovered calls. Stopped seed and controller; owner must decide whether to retain continuation as changed-condition evidence before any further resume or admission.

Resume 10 lacked the saved job-local executable directory in PATH. Resume 11 restored it through the managed interface; the wrapper and payload hashes matched before launch. Safe pickle disassembly confirmed the saved wrapper identity. The pinned simulation worktree was clean and the original 1,799,821-byte event prefix remains identical. No checkpoint or simulation source was edited.

Continuation reached tick 26, but verification then found that the original CLI payload had replaced itself at 01:59 UTC. Its backup still matches the original hash; the wrapper hash is unchanged. Thus the wrapper fingerprint alone failed to detect a changed executable payload. Native quota showed 99% remaining. The affected controller and seed were stopped and process absence verified. All checkpoint, usage and event evidence is retained; no decisions were discarded or relabelled. Seed 41 remains complete at tick 60. No pooled admission or comparison is appropriate while this study is incomplete and changed conditions are unresolved.

The owner must decide whether the recovered continuation may be retained as changed-condition evidence; standard-condition certification has not been granted. Exact hashes and retained artifact locations are in the adjacent JSON.

## Owner-approved continuation

On 2026-09-12T18:41:17.481609+00:00, the user approved continuing seed 11 from tick 27 with the CLI update recorded. The existing checkpoint, accepted decisions, recipe and pinned simulation source are retained. This approval covers continuation with a declared harness-version change; it does not silently grant unchanged-condition certification. Seed 41 remains complete.

The approved migration updated only `extra.brain_states.<agent>.cli_version` from 1.1.27 to 1.2.1 for the ten agents. A recursive comparison after restoring those fields verified all other checkpoint values, including world and RNG state, unchanged. The original checkpoint was archived with its SHA256. Two initial restart attempts stopped before inference: one because a wrapper search path was relative, and one because the explicit version migration had not yet been applied. The final managed launcher uses the absolute saved wrapper directory.

The run then advanced to tick 28, but the CLI replaced itself a second time. That payload was archived, all accepted progress was retained, and the approved 1.2.1 payload was restored. A filesystem immutable flag now protects this job-local executable; `--version` succeeds and its SHA256 remains the approved value. The flag can be removed with `chattr -i` for later maintenance. This is a run-local reproducibility control, not a change to simulation mechanics or account configuration.

Completing the previously interrupted tick replayed nine accepted decisions and restored their historical CLI-version metadata. After reaching tick 28, that runtime metadata was migrated again to the approved version, with a second archived checkpoint and recursive equality check. No decisions were regenerated or removed. The new checkpoint now has consistent 1.2.1 runtime metadata for all ten agents.

Verified successful continuation at tick 29 with a running controller and the approved payload hash unchanged. The entire pre-approval event prefix remains byte-identical. Seed 41 remains complete at tick 60.
