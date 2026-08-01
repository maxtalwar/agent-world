from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from agent_world.checkpoint_recovery import recover_completed_tick_checkpoint
from agent_world.models import AgentDecision, WorldConfig
from agent_world.persistence import IncrementalRunWriter, load_run_checkpoint
from agent_world.world import WorldEngine


class CheckpointRecoveryTests(unittest.TestCase):
    def test_replays_paid_decisions_and_preserves_source_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source"
            source.mkdir()
            events_path = source / "run.jsonl"
            snapshot_path = source / "run-snapshot.json"
            checkpoint_path = source / "run-checkpoint.pkl"
            engine = WorldEngine.create(
                WorldConfig(seed=7), agent_names=["A1", "A2"]
            )
            engine.log_event("run_started", scope="public")
            decisions: dict[int, dict[str, AgentDecision]] = {}
            for tick in range(4):
                tick_decisions = {
                    agent_id: AgentDecision(
                        intent=f"wait at {tick}", actions=[{"type": "wait"}]
                    )
                    for agent_id, agent in engine.state.agents.items()
                    if agent.alive
                }
                decisions[tick] = tick_decisions
                for agent_id in tick_decisions:
                    engine.log_event(
                        "agent_observation", actor_id=agent_id, scope="private"
                    )
                    engine.log_event("agent_prompt", actor_id=agent_id, scope="private")
                engine.tick(tick_decisions)
                if engine.state.tick == 2:
                    engine.log_event("benchmark_checkpoint", scope="private")

            writer = IncrementalRunWriter(
                events_path,
                snapshot_path,
                checkpoint_path=checkpoint_path,
                fsync=False,
            )
            writer.flush(
                engine,
                checkpoint_extra={
                    "run": {
                        "target_ticks": 4,
                        "events_path": str(events_path),
                        "snapshot_path": str(snapshot_path),
                    },
                    "brain_states": {"agent-1": {"stale": True}},
                },
            )
            usage_path = source / "run-usage.jsonl"
            usage_path.write_text(
                "".join(
                    json.dumps({"tick": tick, "agent_id": agent_id}) + "\n"
                    for tick in range(4)
                    for agent_id in ("agent-1", "agent-2")
                ),
                encoding="utf-8",
            )
            source_hashes = {
                path: hashlib.sha256(path.read_bytes()).hexdigest()
                for path in (checkpoint_path, events_path, usage_path)
            }

            result = recover_completed_tick_checkpoint(
                checkpoint_path,
                resume_tick=2,
                output_dir=root / "recovered",
            )

            recovered, extra = load_run_checkpoint(result.checkpoint_path)
            expected = WorldEngine.create(
                WorldConfig(seed=7), agent_names=["A1", "A2"]
            )
            expected.tick(decisions[0])
            expected.tick(decisions[1])
            self.assertEqual(recovered.state.tick, 2)
            self.assertEqual(recovered.snapshot(), expected.snapshot())
            self.assertEqual(recovered.rng.getstate(), expected.rng.getstate())
            self.assertEqual(extra["brain_states"], {})
            self.assertEqual(
                extra["checkpoint_recovery"]["method"],
                "deterministic_decision_replay_with_event_validation",
            )
            self.assertEqual(
                len(result.usage_path.read_text(encoding="utf-8").splitlines()), 4
            )
            self.assertEqual(
                len(
                    result.discarded_usage_path.read_text(
                        encoding="utf-8"
                    ).splitlines()
                ),
                4,
            )
            recovered_types = [event.type for event in recovered.state.events]
            self.assertIn("benchmark_checkpoint", recovered_types)
            self.assertNotIn("run_completed", recovered_types)
            for path, digest in source_hashes.items():
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest)

    def test_refuses_to_replace_existing_recovery_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output = root / "recovered"
            output.mkdir()
            (output / "keep.txt").write_text("do not replace", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "not empty"):
                recover_completed_tick_checkpoint(
                    root / "missing.pkl", resume_tick=2, output_dir=output
                )


if __name__ == "__main__":
    unittest.main()
