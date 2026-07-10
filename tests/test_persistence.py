from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from agent_world.models import WorldConfig
from agent_world.persistence import IncrementalRunWriter, load_run_checkpoint
from agent_world.world import WorldEngine


class IncrementalRunWriterTests(unittest.TestCase):
    def test_events_are_appended_once_and_snapshot_is_replaced(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            events_path = root / "run.jsonl"
            snapshot_path = root / "snapshot.json"
            engine = WorldEngine.create(WorldConfig(seed=3), agent_names=["A1"])
            writer = IncrementalRunWriter(events_path, snapshot_path, fsync=False)

            writer.flush(engine)
            first_lines = events_path.read_text(encoding="utf-8").splitlines()
            engine.log_event("test_event", message="once")
            writer.flush(engine)
            writer.flush(engine)

            lines = events_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), len(first_lines) + 1)
            self.assertEqual(sum(json.loads(line)["type"] == "test_event" for line in lines), 1)
            self.assertEqual(json.loads(snapshot_path.read_text(encoding="utf-8"))["tick"], 0)

    def test_checkpoint_round_trip_and_resume_rebases_event_log(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            events_path = root / "run.jsonl"
            snapshot_path = root / "snapshot.json"
            checkpoint_path = root / "run-checkpoint.pkl"
            engine = WorldEngine.create(WorldConfig(seed=7), agent_names=["A1"])
            engine.log_event("before_crash", message="durable")
            writer = IncrementalRunWriter(
                events_path,
                snapshot_path,
                checkpoint_path=checkpoint_path,
                fsync=False,
            )
            writer.flush(engine, checkpoint_extra={"run": {"target_ticks": 5}})

            restored, extra = load_run_checkpoint(checkpoint_path)
            self.assertEqual(restored.state.tick, engine.state.tick)
            self.assertEqual(extra["run"]["target_ticks"], 5)
            self.assertEqual(restored.rng.getstate(), engine.rng.getstate())

            resumed_writer = IncrementalRunWriter(
                events_path,
                snapshot_path,
                checkpoint_path=checkpoint_path,
                fsync=False,
                truncate_events=False,
            )
            resumed_writer.rebase(restored)
            restored.log_event("after_resume", message="once")
            resumed_writer.flush(restored)
            event_types = [
                json.loads(line)["type"]
                for line in events_path.read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(event_types.count("before_crash"), 1)
            self.assertEqual(event_types.count("after_resume"), 1)

    def test_checkpoint_size_does_not_copy_the_event_history(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            events_path = root / "run.jsonl"
            checkpoint_path = root / "run-checkpoint.pkl"
            engine = WorldEngine.create(WorldConfig(seed=9), agent_names=["A1"])
            writer = IncrementalRunWriter(
                events_path,
                None,
                checkpoint_path=checkpoint_path,
                fsync=False,
            )
            writer.flush(engine)
            initial_checkpoint_size = checkpoint_path.stat().st_size

            for index in range(50):
                engine.log_event("large_audit_event", data={"payload": "x" * 2_000, "index": index})
            writer.flush(engine)

            self.assertGreater(events_path.stat().st_size, 100_000)
            self.assertLess(checkpoint_path.stat().st_size, initial_checkpoint_size + 2_000)


if __name__ == "__main__":
    unittest.main()
