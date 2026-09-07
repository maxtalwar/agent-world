import pickle
import unittest
from agent_world.models import WorldConfig, Needs
from agent_world.world import WorldEngine
from agent_world.interface import build_observation, build_agent_prompt

class RegenerationTests(unittest.TestCase):
    def make(self, **kw):
        e = WorldEngine.create(config=WorldConfig(health_regen_rate=kw.pop("rate", 2), **kw), agent_names=["A"])
        a = e.state.agents["agent-1"]
        a.health = 10
        a.needs = Needs(20,20,30)
        return e,a

    def test_stability_cap_and_prompt(self):
        e,a = self.make()
        e._apply_survival(); self.assertEqual(a.health,10)
        e._apply_survival(); self.assertEqual(a.health,12)
        a.health=99
        e._apply_survival(); self.assertEqual(a.health,100)
        event=e.state.events[-1]
        self.assertEqual(event.data["restored"],1)
        self.assertIn("HEALTH RECOVERY",build_agent_prompt(build_observation(e.state,a.id),compact=True))

    def test_threshold_is_after_decay_and_shortage_resets(self):
        e,a=self.make()
        e._apply_survival()
        a.needs.water=11 # after decay 9, below half
        e._apply_survival(); self.assertEqual(a.health_regen_streak,0)
        a.needs=Needs(20,20,30)
        e._apply_survival(); self.assertEqual(a.health,10)
        e._apply_survival(); self.assertEqual(a.health,12)

    def test_damage_and_death_never_heal(self):
        e,a=self.make()
        e._apply_survival()
        a.needs=Needs(0,0,0)
        e._apply_survival()
        self.assertLess(a.health,10); self.assertEqual(a.health_regen_streak,0)
        a.health=0; a.alive=False; a.needs=Needs(20,20,30)
        e._apply_survival(); self.assertEqual(a.health,0)

    def test_checkpoint_streak(self):
        e,a=self.make();e._apply_survival()
        restored=pickle.loads(pickle.dumps(e))
        e._apply_survival();restored._apply_survival()
        self.assertEqual(e.state.agents[a.id].health,restored.state.agents[a.id].health)
        self.assertEqual(restored.state.agents[a.id].health,12)

    def test_disabled_unchanged_and_validation(self):
        e,a=self.make(rate=0)
        e._apply_survival();e._apply_survival()
        self.assertEqual(a.health,10)
        self.assertFalse(any(x.type.startswith("health_recovery") for x in e.state.events))
        self.assertNotIn("HEALTH RECOVERY",build_agent_prompt(build_observation(e.state,a.id),compact=True))
        for kw in [dict(health_regen_rate=-1),dict(health_regen_stable_ticks=0),dict(health_regen_reserve_fraction=1.1)]:
            with self.assertRaises(ValueError): WorldConfig(**kw)

    def test_scripted_rate_sweep(self):
        # Ten injured survivors can recover; dead population slots remain zero.
        for rate in (1,2,4):
            e,a=self.make(rate=rate)
            health=[]
            for tick in range(60):
                a.needs=Needs(20,20,30)
                e._apply_survival();health.append(a.health)
            self.assertEqual(health[-1],min(100,10+59*rate))
            self.assertGreater(sum(health)/60,10)
            # Repeated shortages never qualify for recovery.
            e,a=self.make(rate=rate)
            for tick in range(10):
                a.needs=Needs(20,20,30) if tick%2==0 else Needs(9,9,14)
                e._apply_survival()
            self.assertEqual(a.health,10)
