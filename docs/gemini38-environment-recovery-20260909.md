# Gemini 3.8 execution recovery — 2026-09-09

Run `web-gemini-3-8-flash-medium-1113fb6ad885`, seed 11, stopped at tick25;
seed41 was already complete60. Resume attempts5/6 failed before provider calls
because the installed Antigravity binary changed. Python remained3.12.3 and
the executable path remained ~/.local/bin/agy, but SHA-256 changed from
93eb2118b778a4005700b54cdd7e08b896fbe665d5ff338e38e9e53da9a091ea to
a8793092fbe6eea0b8228fc20582ec306f7f7698d1151be526902b1556a76f3a.

The retained old executable matches the original hash exactly. Recovery uses
that executable through a job-scoped PATH. The checkpoint explicitly records
its relocated executable path, preserving original evidence in a full archive.
No source/model/world change or decision resampling is authorized. Nine pending
decisions and original usage/ledger bytes were verified before managed resume.
The first post-recovery provider request targets only unresolved agent3.

The old controller mistook a deterministic startup guard for an interrupted
supervisor and repeatedly scheduled retries. The repaired launcher records the
current attempt's log offset; the controller inspects a bounded tail only from
that attempt and routes an execution-environment ValueError to
execution_environment_mismatch attention. It clears pending auto-resume times.
Old failure text cannot poison a subsequent launch. Existing integrity checks
are retained. This job runs the repaired controller with its original pinned
simulation source d1e088e065324aede8a957371b83763511922311.

Validation:38 managed-run/controller/routing tests pass. Runtime recovery and
completed-seed hashes are recorded locally under the job's
environment-recovery-20260909/recovery.json. The completed seed41 finalization
signature is retained so controller replacement does not repeat finalization.
Fable runs are outside this recovery and were not resumed.
