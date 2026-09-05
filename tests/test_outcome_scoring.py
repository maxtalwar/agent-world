import copy
import unittest

from agent_world.outcome_scoring import (
    ScoringEvidenceError, derive_outcome_counts, score_outcome_counts,
)


def world(health=(100, 100, 100, 100), invalid_ticks=(), contention_ticks=(), actions=None):
    events = []
    for t in range(len(health)):
        hp = 100 if t == 0 else health[t - 1]
        if hp <= 0:
            continue
        events += [
            {"type": "agent_observation", "tick": t, "actor_id": "a",
             "data": {"observation": {"self": {"health": hp}}}},
            {"type": "agent_response", "tick": t, "actor_id": "a", "message": "Rest.",
             "data": {"actions": actions or [{"type": "wait"}], "messages": []}},
        ]
        if t in invalid_ticks:
            events.append({"type": "invalid_action", "tick": t, "actor_id": "a"})
        if t in contention_ticks:
            events.append({"type": "contention_failure", "tick": t, "actor_id": "a"})
        if health[t] == 0:
            events.append({"type": "death", "tick": t, "actor_id": "a"})
    events.append({"type": "run_completed", "tick": len(health)})
    snapshot = {"tick": len(health), "agents": {"a": {
        "alive": health[-1] > 0, "health": health[-1],
    }}}
    return events, snapshot


def counts(events, snapshot):
    return derive_outcome_counts(events, snapshot, member_ids=["a"],
                                 target_ticks=snapshot["tick"], tail_ticks=2)


class OutcomeScoringTests(unittest.TestCase):
    def test_perfect_health_and_valid_rest_are_perfect(self):
        result = score_outcome_counts(counts(*world()))
        self.assertEqual(result["execution"]["score"], 100)
        self.assertEqual(result["capability"]["score"], 100)

    def test_valid_bad_strategy_can_execute_perfectly_and_collapse(self):
        result = score_outcome_counts(counts(*world((50, 0, 0, 0))))
        self.assertEqual(result["execution"]["score"], 100)
        self.assertEqual(result["capability"]["score"], 0)

    def test_capability_is_independent_of_execution_and_economics(self):
        a = counts(*world((90, 80, 70, 60)))
        b = counts(*world((90, 80, 70, 60), invalid_ticks=(0, 1, 2)))
        b.update(enterprise_supply_value=999999, living_terminal_economic_value=999999)
        self.assertEqual(score_outcome_counts(a)["capability"], score_outcome_counts(b)["capability"])
        self.assertNotEqual(score_outcome_counts(a)["execution"], score_outcome_counts(b)["execution"])

    def test_one_invalid_item_fails_plan_and_valid_padding_does_not_repair_it(self):
        a = counts(*world(invalid_ticks=(1,)))
        b = counts(*world(invalid_ticks=(1,), actions=[{"type": "wait"}] * 4))
        self.assertEqual(score_outcome_counts(a)["execution"]["score"], 75)
        self.assertEqual(score_outcome_counts(a)["execution"], score_outcome_counts(b)["execution"])

    def test_contention_does_not_count_as_invalid_execution(self):
        self.assertEqual(score_outcome_counts(counts(*world(contention_ticks=(0, 1))))["execution"]["score"], 100)

    def test_health_monotonicity_and_late_resilience(self):
        rising = score_outcome_counts(counts(*world((40, 60, 80, 100))))["capability"]["score"]
        falling = score_outcome_counts(counts(*world((100, 80, 60, 40))))["capability"]["score"]
        improved = score_outcome_counts(counts(*world((100, 90, 70, 50))))["capability"]["score"]
        self.assertGreater(rising, falling)
        self.assertGreater(improved, falling)

    def test_deaths_remain_in_denominator_and_initial_health_is_excluded(self):
        c = counts(*world((50, 0, 0, 0)))
        self.assertEqual(c["health_point_ticks"], 50)
        self.assertEqual(c["health_point_tick_capacity"], 400)
        self.assertEqual(c["tail_health_point_tick_capacity"], 200)

    def test_pooling_raw_counts_is_replication_invariant(self):
        c = counts(*world((90, 80, 70, 60), invalid_ticks=(1,)))
        doubled = {k: v * 2 for k, v in c.items()}
        for score in ("execution", "capability"):
            self.assertEqual(score_outcome_counts(c)[score]["score"], score_outcome_counts(doubled)[score]["score"])

    def test_missing_living_evidence_is_not_imputed_as_death(self):
        events, snapshot = world()
        events = [e for e in events if not (e["type"] == "agent_observation" and e["tick"] == 2)]
        with self.assertRaises(ScoringEvidenceError):
            counts(events, snapshot)

    def test_duplicate_resolved_decisions_are_rejected(self):
        events, snapshot = world()
        events.append(copy.deepcopy(next(e for e in events if e["type"] == "agent_response")))
        with self.assertRaises(ScoringEvidenceError):
            counts(events, snapshot)

    def test_model_output_failure_scores_zero_for_that_decision(self):
        events, snapshot = world()
        next(e for e in events if e["type"] == "agent_response")["message"] = (
            "Codex model output contract failed: invalid JSON"
        )
        self.assertEqual(score_outcome_counts(counts(events, snapshot))["execution"]["score"], 75)

    def test_provider_refusal_is_not_scored_as_model_execution(self):
        events, snapshot = world()
        next(e for e in events if e["type"] == "agent_response")["message"] = (
            "Grok quota unavailable: usage balance exhausted"
        )
        with self.assertRaises(ScoringEvidenceError):
            counts(events, snapshot)

    def test_missing_invalid_and_nonfinite_counts_are_unavailable(self):
        c = counts(*world())
        for bad in ({}, {**c, "execution_decisions": 0}, {**c, "health_point_ticks": float("nan")}):
            with self.assertRaises(ScoringEvidenceError):
                score_outcome_counts(bad)

    def test_uncompleted_run_cannot_be_scored(self):
        events, snapshot = world()
        events.pop()
        with self.assertRaises(ScoringEvidenceError):
            counts(events, snapshot)


if __name__ == "__main__":
    unittest.main()
