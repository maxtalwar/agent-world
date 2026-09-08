import copy
import json
from pathlib import Path
import tempfile
import unittest

from agent_world.capability_reanalysis import health_counts, rescore, score_counts, season_ticks, validate_policy


POLICY = {"id": "test-v1", "source_recipe": "participant-test", "source_recipe_digest": "abc",
          "horizon": 60, "season_length_ticks": 12, "season_index": 3, "season_name": "winter",
          "season_damage_multiplier": 1.3, "required_seeds": [11, 41]}


def fixture(seed=11, death=None):
    curve = [100 if t <= 36 else 50 if t <= 48 else 20 for t in range(1, 61)]
    if death is not None:
        curve = [v if i < death else 0 for i, v in enumerate(curve)]
    events = [{"type": "agent_observation", "tick": t, "actor_id": "a", "data": {"observation": {"self": {"health": 100 if t == 0 else curve[t - 1]}}}} for t in range(60) if death is None or t <= death]
    if death is not None:
        events.append({"type": "death", "tick": death, "actor_id": "a", "data": {}})
    report = {"run": {"completed": True, "target_ticks": 60}, "config": {"seed": seed, "season_length_ticks": 12},
              "benchmarks": {"protocol": {"id": "participant-test", "recipe_fingerprint_sha256": "abc"},
                             "cohorts": {"one": {"agents": ["a"], "model": "test", "raw": {"health_point_ticks": sum(curve), "endpoint_health_points": curve[-1]}}}}}
    snapshot = {"agents": {"a": {"alive": death is None, "health": curve[-1]}}}
    return report, snapshot, events


class CapabilityReanalysisTests(unittest.TestCase):
    def test_winter_uses_post_action_states_not_pre_winter_or_final_spring(self):
        self.assertEqual(season_ticks(POLICY), list(range(37, 49)))
        c = health_counts(*fixture(), POLICY)
        result = score_counts(c, POLICY)
        self.assertEqual(result["winter_damage"], 50)
        self.assertEqual(result["endpoint"], 20)
        self.assertEqual(result["score"], 5)

    def test_pre_winter_damage_does_not_receive_winter_surcharge(self):
        report, snapshot, events = fixture()
        for e in events:
            if 25 <= e["tick"] <= 36:
                e["data"]["observation"]["self"]["health"] = 50
        report["benchmarks"]["cohorts"]["one"]["raw"]["health_point_ticks"] -= 12 * 50
        result = score_counts(health_counts(report, snapshot, events, POLICY), POLICY)
        self.assertEqual(result["winter_damage"], 0)
        self.assertEqual(result["score"], 20)

    def test_winter_death_cannot_produce_negative_capability(self):
        result = score_counts(health_counts(*fixture(death=40), POLICY), POLICY)
        self.assertEqual(result["score"], 0)
        self.assertTrue(result["floor_applied"])
        self.assertEqual(result["winter_damage"], 100)

    def test_dead_original_population_slots_remain_zero(self):
        c = health_counts(*fixture(death=10), POLICY)
        self.assertEqual(c["endpoint_capacity"], 100)
        self.assertEqual(c["season_damage_points"], 0)
        self.assertEqual(score_counts(c, POLICY)["score"], 0)

    def test_missing_evidence_and_different_recipe_are_rejected(self):
        r, s, e = fixture()
        with self.assertRaisesRegex(ValueError, "Missing living"):
            health_counts(r, s, [x for x in e if x["tick"] != 40], POLICY)
        r["benchmarks"]["protocol"]["recipe_fingerprint_sha256"] = "different"
        with self.assertRaisesRegex(ValueError, "identity"):
            health_counts(r, s, e, POLICY)

    def test_report_reconciliation_catches_inconsistent_health(self):
        r, s, e = fixture()
        r["benchmarks"]["cohorts"]["one"]["raw"]["health_point_ticks"] += 1
        with self.assertRaisesRegex(ValueError, "frozen report"):
            health_counts(r, s, e, POLICY)

    def test_invalid_weights_and_incomplete_season_rejected(self):
        for override in ({"season_damage_multiplier": float("nan")}, {"season_damage_multiplier": .8}, {"horizon": 40}):
            with self.assertRaises(ValueError):
                validate_policy({**POLICY, **override})

    def test_required_seeds_pool_raw_counts_and_preserve_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = []
            originals = {}
            for seed in [11, 41]:
                folder = root / str(seed)
                folder.mkdir()
                r, s, e = fixture(seed, death=10 if seed == 41 else None)
                for name, content in (("run-report.json", json.dumps(r)), ("run-snapshot.json", json.dumps(s)), ("run.jsonl", "\n".join(json.dumps(x) for x in e))):
                    path = folder / name
                    path.write_text(content)
                    originals[path] = content
                paths.append(folder / "run-report.json")
            result = rescore(root, paths, POLICY)
            self.assertEqual(result["capability"]["score"], 2.5)
            with self.assertRaisesRegex(ValueError, "exactly"):
                rescore(root, [paths[0], paths[0]], POLICY)
            for path, content in originals.items():
                self.assertEqual(path.read_text(), content)


if __name__ == "__main__":
    unittest.main()
