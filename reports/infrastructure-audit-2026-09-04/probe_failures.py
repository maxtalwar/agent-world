"""Offline infrastructure audit probe; synthetic data, no model calls.

Run from the repository root with PYTHONPATH=. python3 reports/infrastructure-audit-2026-09-04/probe_failures.py
Results describe the audited revision; later fixes should change them.
"""

import json, tempfile, time, threading
from pathlib import Path
from unittest.mock import patch
from agent_world.models import AgentDecision, WorldConfig
from agent_world.world import WorldEngine
from agent_world.runner import SimulationRunner, PendingTickJournal
from agent_world.interface import build_observation, build_static_context, build_dynamic_observation
from agent_world.session import SimulationSession
from agent_world.brain_factory import BrainSpec
from agent_world.brain_runtime import BrainRuntime
from agent_world.persistence import IncrementalRunWriter, load_run_checkpoint
from agent_world.codex_brain import _write_codex_schema
from agent_world.decision_failure import validate_decision_contract
from agent_world.openrouter_brain import AGENT_DECISION_SCHEMA
class Fixed:
 def __init__(self, value): self.value=value
 def decide(self, observation): return self.value
class Raises:
 def decide(self, observation): raise RuntimeError('synthetic transport crash')
def world(n=2):
 return WorldEngine.create(config=WorldConfig(seed=11),agent_names=[f'A{i}' for i in range(n)])
def decision(intent='ok', actions=None):
 return AgentDecision(intent=intent, actions=actions or [{'type':'wait'}])
results={}
e=world()
r=SimulationRunner(e,{a:Fixed(decision('Avoid unauthorized access to stores.')) for a in e.state.agents},log_agent_io=False)
try:r.step()
except Exception as exc:results['intent_false_auth']={'error':type(exc).__name__,'tick':e.state.tick}
e=world()
r=SimulationRunner(e,{a:Fixed(decision(f'Codex boundary failed: missing payload {a}')) for a in e.state.agents},log_agent_io=False)
r.step()
results['different_boundary_failures']={'tick_advanced_to':e.state.tick,'failures':[v.message for v in e.state.events if v.type=='agent_response']}
for concurrent in [False,True]:
 e=world()
 r=SimulationRunner(e,{a:Raises() for a in e.state.agents},log_agent_io=False,concurrent_decisions=concurrent)
 err=None
 try:r.step()
 except Exception as exc:err=type(exc).__name__
 results[f'exception_concurrent_{concurrent}']={'tick':e.state.tick,'error':err}
with tempfile.TemporaryDirectory(prefix='aw-audit-') as d:
 p=Path(d)
 with patch.dict('os.environ',{'AGENT_WORLD_CODEX_ACTION_MAX_ITEMS':'4'}):
  first=_write_codex_schema(p)
 with patch.dict('os.environ',{'AGENT_WORLD_CODEX_ACTION_MAX_ITEMS':'8'}):
  second=_write_codex_schema(p)
 results['schema_collision']={'same_path':first==second,'first_schema_now_has_maxItems':json.loads(first.read_text())['properties']['actions']['maxItems']}
 e=world()
 a,b=sorted(e.state.agents)
 payload={'intent':'record agreement','actions':[{'type':'record_agreement','text':'pact','parties':None}],'messages':[],'memory_updates':[]}
 valid=validate_decision_contract(payload,AGENT_DECISION_SCHEMA)
 writer=IncrementalRunWriter(p/'events.jsonl',p/'snapshot.json',checkpoint_path=p/'checkpoint.pkl')
 first_decision=decision()
 first_decision.memory_updates=['accepted before tick failure']
 s=SimulationSession(engine=e,brain_spec=BrainSpec.resolve('survival'),runtime=BrainRuntime(),writer=writer,target_ticks=1,brains={a:Fixed(first_decision),b:Fixed(payload)},log_agent_io=False,startup_health_check_tick=None)
 result=s.run()
 restored,_=load_run_checkpoint(p/'checkpoint.pkl')
 results['partial_world_checkpoint']={'contract_valid':valid.valid,'status':result.status,'error':result.error,'tick':restored.state.tick,'memory':restored.state.agents[a].memory,'responses_in_checkpoint':sum(x.type=='agent_response' for x in restored.state.events)}
 # Ledger modifications preserving JSON syntax and line count are accepted by loader.
 ledger=p/'events.jsonl'
 rows=[json.loads(x) for x in ledger.read_text().splitlines()]
 rows[0]['message']='synthetically changed after checkpoint'
 ledger.write_text(''.join(json.dumps(x)+'\n' for x in rows))
 restored,_=load_run_checkpoint(p/'checkpoint.pkl')
 results['ledger_integrity']={'modified_ledger_loaded':restored.state.events[0].message=='synthetically changed after checkpoint'}
 e=world(1); a=next(iter(e.state.agents)); obs={a:build_observation(e.state,a)}
 j=PendingTickJournal(p/'pending.json',tick=0,observations=obs,brains={a:Fixed(decision('old model'))})
 j.record_decision(a,decision('old model'))
 j2=PendingTickJournal(p/'pending.json',tick=0,observations=obs,brains={a:Fixed(decision('new model'))})
 results['journal_execution_identity']={'reused_intent':j2.decisions[a].intent}
runtime=BrainRuntime()
runtime.throttle(.3,'provider-a')
entered=threading.Event()
def hold():
 entered.set()
 runtime.throttle(.3,'provider-a')
t=threading.Thread(target=hold);t.start();entered.wait();time.sleep(.03)
start=time.perf_counter();runtime.quota_message('provider-b');elapsed=time.perf_counter()-start;t.join()
results['cross_provider_lock_seconds']=round(elapsed,3)
for mode in ['baseline','organic']:
 e=WorldEngine.create(config=WorldConfig(seed=11,economy_mode=mode),agent_names=['A','B'])
 obs=build_observation(e.state,'agent-1')
 results['prompt_'+mode]={'static_chars':len(build_static_context(obs['world'])),'dynamic_chars':len(json.dumps(build_dynamic_observation(obs),sort_keys=True,separators=(',',':')))}
print(json.dumps(results,indent=2))
