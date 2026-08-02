from __future__ import annotations

import hashlib
import json
import unittest
from collections import Counter

from agent_world.interface import build_dynamic_observation, build_observation, build_static_context
from agent_world.models import AgentDecision, Position, WorldConfig
from agent_world.world import WorldEngine


def _organic_engine(names: list[str] | None = None, **overrides) -> WorldEngine:
    config = dict(
        seed=1,
        economy_mode="organic",
        geography_mode="dispersed",
        survival_food_decay=0,
        survival_water_decay=0,
        survival_energy_decay=0,
        carried_food_spoil_interval=0,
    )
    config.update(overrides)
    engine = WorldEngine.create(WorldConfig(**config), agent_names=names or ["Seller", "Buyer"])
    for agent in engine.state.agents.values():
        agent.carry_capacity = 100
    return engine


def _proposal(deadline_tick: int, **overrides) -> dict:
    action = {
        "type": "propose_contract",
        "counterparty": "agent-2",
        "give": {"food": 2},
        "receive": {"coin": 3},
        "deadline_tick": deadline_tick,
        "collateral": {"tool": 1},
    }
    action.update(overrides)
    return action


class DeliveryContractEngineTests(unittest.TestCase):
    def test_full_lifecycle_escrows_and_settles_atomically(self) -> None:
        engine = _organic_engine()
        seller, buyer = engine.state.agents.values()
        seller.inventory = Counter({"food": 2, "tool": 1})
        buyer.inventory = Counter({"coin": 3})

        engine.tick({seller.id: AgentDecision(actions=[_proposal(3)])})
        contract = engine.state.contracts["contract-1"]
        self.assertEqual(contract.status, "proposed")
        self.assertEqual(seller.inventory, Counter({"food": 2, "tool": 1}))

        engine.tick({buyer.id: AgentDecision(actions=[{"type": "accept_contract", "contract_id": contract.id}])})
        self.assertEqual(contract.status, "active")
        self.assertEqual(buyer.inventory["coin"], 0)
        self.assertEqual(seller.inventory["tool"], 0)

        engine.tick({seller.id: AgentDecision(actions=[{"type": "deliver_contract", "contract_id": contract.id}])})
        self.assertEqual(contract.status, "settled")
        self.assertEqual(buyer.inventory["food"], 2)
        self.assertEqual(seller.inventory["coin"], 3)
        self.assertEqual(seller.inventory["tool"], 1)
        self.assertEqual(
            [event.type for event in engine.state.events if event.type.startswith("contract_")],
            ["contract_proposed", "contract_accepted", "contract_settled"],
        )
        self.assertNotIn("value", next(event for event in engine.state.events if event.type == "contract_settled").data)

    def test_deadline_default_returns_payment_and_forfeits_collateral(self) -> None:
        engine = _organic_engine()
        seller, buyer = engine.state.agents.values()
        seller.inventory = Counter({"tool": 1})
        buyer.inventory = Counter({"coin": 3})
        engine.tick({seller.id: AgentDecision(actions=[_proposal(2)])})
        engine.tick({buyer.id: AgentDecision(actions=[{"type": "accept_contract", "contract_id": "contract-1"}])})
        engine.tick({})

        self.assertEqual(engine.state.contracts["contract-1"].status, "defaulted")
        self.assertEqual(buyer.inventory["coin"], 3)
        self.assertEqual(buyer.inventory["tool"], 1)
        event = next(event for event in engine.state.events if event.type == "contract_defaulted")
        self.assertFalse(event.data["flow"]["enterprise_supply_eligible"])

    def test_acceptance_failures_move_nothing(self) -> None:
        for buyer_items, seller_items, expected in (
            ({}, {"tool": 1}, "Acceptor lacks"),
            ({"coin": 3}, {}, "Proposer lacks"),
        ):
            with self.subTest(expected=expected):
                engine = _organic_engine()
                seller, buyer = engine.state.agents.values()
                seller.inventory = Counter(seller_items)
                buyer.inventory = Counter(buyer_items)
                engine.tick({seller.id: AgentDecision(actions=[_proposal(3)])})
                before = (Counter(seller.inventory), Counter(buyer.inventory))
                events = engine.tick(
                    {buyer.id: AgentDecision(actions=[{"type": "accept_contract", "contract_id": "contract-1"}])}
                )
                self.assertEqual((seller.inventory, buyer.inventory), before)
                self.assertEqual(engine.state.contracts["contract-1"].status, "proposed")
                self.assertIn(expected, next(event.message for event in events if event.type == "invalid_action"))

    def test_cancel_and_unaccepted_expiry(self) -> None:
        cancelled = _organic_engine()
        cancelled.tick({"agent-1": AgentDecision(actions=[_proposal(10)])})
        cancelled.tick(
            {"agent-1": AgentDecision(actions=[{"type": "cancel_contract", "contract_id": "contract-1"}])}
        )
        self.assertEqual(cancelled.state.contracts["contract-1"].status, "cancelled")

        expired = _organic_engine()
        expired.tick({"agent-1": AgentDecision(actions=[_proposal(10)])})
        for _ in range(5):
            expired.tick({})
        self.assertEqual(expired.state.contracts["contract-1"].status, "expired")
        self.assertTrue(any(event.type == "contract_expired" for event in expired.state.events))

    def test_proposal_cap_and_deadline_bounds(self) -> None:
        engine = _organic_engine(action_points_per_tick=5)
        actions = [_proposal(10, give={"food": 1}, receive={"coin": 1}) for _ in range(4)]
        events = engine.tick({"agent-1": AgentDecision(actions=actions)})
        self.assertEqual(sum(contract.status == "proposed" for contract in engine.state.contracts.values()), 3)
        self.assertIn("maximum of 3", next(event.message for event in events if event.type == "invalid_action"))

        bounds = _organic_engine()
        for offset in (0, 21):
            deadline = bounds.state.tick + offset
            events = bounds.tick({"agent-1": AgentDecision(actions=[_proposal(deadline)])})
            self.assertTrue(any("at least 1 and at most 20" in event.message for event in events))

    def test_active_cap_counts_either_party(self) -> None:
        engine = _organic_engine(action_points_per_tick=4)
        seller, buyer = engine.state.agents.values()
        buyer.inventory = Counter({"coin": 6})
        for batch_size in (3, 2):
            proposals = [
                _proposal(engine.state.tick + 20, give={"food": 1}, receive={"coin": 1}, collateral={})
                for _ in range(batch_size)
            ]
            engine.tick({seller.id: AgentDecision(actions=proposals)})
            open_ids = [cid for cid, contract in engine.state.contracts.items() if contract.status == "proposed"]
            engine.tick(
                {buyer.id: AgentDecision(actions=[{"type": "accept_contract", "contract_id": cid} for cid in open_ids])}
            )
        engine.tick(
            {seller.id: AgentDecision(actions=[_proposal(engine.state.tick + 20, give={"food": 1}, receive={"coin": 1}, collateral={})])}
        )
        events = engine.tick(
            {buyer.id: AgentDecision(actions=[{"type": "accept_contract", "contract_id": "contract-6"}])}
        )
        self.assertEqual(engine.state.contracts["contract-6"].status, "proposed")
        self.assertIn("maximum of 5", next(event.message for event in events if event.type == "invalid_action"))

    def test_same_seed_and_decisions_produce_identical_events(self) -> None:
        def run() -> str:
            engine = _organic_engine()
            engine.state.agents["agent-1"].inventory = Counter({"food": 2})
            engine.state.agents["agent-2"].inventory = Counter({"coin": 3})
            decisions = [
                {"agent-1": AgentDecision(actions=[_proposal(3, collateral={})])},
                {"agent-2": AgentDecision(actions=[{"type": "accept_contract", "contract_id": "contract-1"}])},
                {"agent-1": AgentDecision(actions=[{"type": "deliver_contract", "contract_id": "contract-1"}])},
            ]
            for decision in decisions:
                engine.tick(decision)
            return engine.export_events_jsonl()

        self.assertEqual(run(), run())


class TownLedgerTests(unittest.TestCase):
    def test_posting_cap_and_length_validation(self) -> None:
        engine = _organic_engine(names=["A1"])
        events = engine.tick(
            {
                "agent-1": AgentDecision(
                    actions=[
                        {"type": "post_ledger_note", "title": "Prices", "body": "Food is 2 coin."},
                        {"type": "post_ledger_note", "title": "Again", "body": "No."},
                    ]
                )
            }
        )
        note = next(event for event in events if event.type == "ledger_note")
        self.assertEqual(note.scope, "public")
        self.assertEqual(note.data["author"], "agent-1")
        self.assertTrue(any("only one" in event.message for event in events if event.type == "invalid_action"))

        for title, body, phrase in (("x" * 61, "ok", "60"), ("ok", "x" * 401, "400")):
            events = engine.tick(
                {"agent-1": AgentDecision(actions=[{"type": "post_ledger_note", "title": title, "body": body}])}
            )
            self.assertIn(phrase, next(event.message for event in events if event.type == "invalid_action"))

    def test_observation_shows_latest_eight_and_total(self) -> None:
        engine = _organic_engine(names=["A1"])
        for index in range(9):
            engine.tick(
                {
                    "agent-1": AgentDecision(
                        actions=[{"type": "post_ledger_note", "title": f"N{index}", "body": f"Body {index}"}]
                    )
                }
            )
        ledger = build_dynamic_observation(build_observation(engine.state, "agent-1"))["town_ledger"]
        self.assertEqual(ledger["total_count"], 9)
        self.assertEqual([note["title"] for note in ledger["recent_notes"]], [f"N{i}" for i in range(1, 9)])


class OrganicInterfaceGatingTests(unittest.TestCase):
    def test_organic_rulebook_and_fields_are_gated(self) -> None:
        organic = _organic_engine(names=["A1"])
        observation = build_observation(organic.state, "agent-1")
        static = build_static_context(observation["world"])
        actions = {action["type"] for action in observation["valid_actions"]}
        self.assertIn("DELIVERY CONTRACTS:", static)
        self.assertIn("TOWN LEDGER:", static)
        self.assertIn("propose_contract", actions)
        self.assertIn("accept_contract", actions)
        self.assertIn("town_ledger", observation)

        for mode in ("baseline", "commerce"):
            engine = WorldEngine.create(WorldConfig(economy_mode=mode), agent_names=["A1"])
            observation = build_observation(engine.state, "agent-1")
            static = build_static_context(observation["world"])
            actions = {action["type"] for action in observation["valid_actions"]}
            self.assertNotIn("DELIVERY CONTRACTS:", static)
            self.assertNotIn("TOWN LEDGER:", static)
            self.assertNotIn("propose_contract", actions)
            self.assertNotIn("town_ledger", observation)

    def test_baseline_and_commerce_worlds_match_pre_feature_bytes(self) -> None:
        expected = {
            "baseline": "93cc0c8d7271840e5beea576a4221f6190e612c18b63667a1a72946c94adf2d1",
            "commerce": "ec6089853a549d44cdcc4219c86e7f2a8c877ed22638fa0ff9c631ca653726f8",
        }
        for mode, digest in expected.items():
            with self.subTest(mode=mode):
                engine = WorldEngine.create(
                    WorldConfig(
                        seed=3,
                        economy_mode=mode,
                        geography_mode="dispersed",
                        survival_food_decay=0,
                        survival_water_decay=0,
                        survival_energy_decay=0,
                        carried_food_spoil_interval=0,
                    ),
                    agent_names=["Seller", "Buyer"],
                )
                seller, buyer = engine.state.agents.values()
                seller.position = buyer.position = Position(8, 8)
                seller.inventory = Counter({"food": 2})
                buyer.inventory = Counter({"water": 2})
                initial = build_observation(engine.state, seller.id)
                engine.tick(
                    {
                        seller.id: AgentDecision(
                            actions=[
                                {
                                    "type": "offer_trade",
                                    "to": buyer.id,
                                    "give": {"food": 1},
                                    "receive": {"water": 1},
                                }
                            ]
                        )
                    }
                )
                engine.tick(
                    {buyer.id: AgentDecision(actions=[{"type": "accept_trade", "trade_id": "trade-1"}])}
                )
                final = build_observation(engine.state, seller.id)
                bundle = {
                    "static": build_static_context(initial["world"]),
                    "initial": initial,
                    "dynamic": build_dynamic_observation(final),
                    "snapshot": engine.snapshot(),
                    "events": [event.to_dict() for event in engine.state.events],
                }
                encoded = json.dumps(bundle, sort_keys=True, separators=(",", ":")).encode()
                self.assertEqual(hashlib.sha256(encoded).hexdigest(), digest)


if __name__ == "__main__":
    unittest.main()
