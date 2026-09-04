"""Offline infrastructure audit probe; synthetic data, no model calls.

Run from the repository root with PYTHONPATH=. python3 reports/infrastructure-audit-2026-09-04/probe_timing.py
Results describe the audited revision; later fixes should change them.
"""

import json, time, threading, tempfile, subprocess, sys, statistics
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from agent_world.openrouter_brain import OpenRouterBrain
from agent_world.codex_brain import _read_app_server_response
from agent_world.models import WorldConfig, Event, DeliveryContract
from agent_world.world import WorldEngine
from agent_world.interface import build_observation, build_dynamic_observation
from agent_world.observer import load_observer_state
from agent_world.run_controller import _latest_control_event
from collections import Counter
results={}
class Slow(BaseHTTPRequestHandler):
 def do_POST(self):
  body=b'{"answer": "abcdef"}'
  self.send_response(200);self.send_header('Content-Length',str(len(body)));self.end_headers()
  try:
   for b in body:self.wfile.write(bytes([b]));self.wfile.flush();time.sleep(.025)
  except BrokenPipeError:pass
 def log_message(self,*args):pass
server=ThreadingHTTPServer(('127.0.0.1',0),Slow)
thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
brain=OpenRouterBrain(api_key='synthetic',base_url=f'http://127.0.0.1:{server.server_port}',timeout_seconds=.08,hard_deadline_grace_seconds=.02,min_request_interval_seconds=0,max_retries=0)
start=time.perf_counter()
try:brain._post_json('/chat/completions',{});error=None
except Exception as exc:error=type(exc).__name__
results['drip_http']={'configured_total_deadline_seconds':.1,'actual_seconds':round(time.perf_counter()-start,3),'error':error}
server.shutdown();server.server_close()
code="import sys,time;sys.stdout.write('{');sys.stdout.flush();time.sleep(.35);print(chr(34)+'id'+chr(34)+':1,'+chr(34)+'result'+chr(34)+':{}}',flush=True)"
p=subprocess.Popen([sys.executable,'-c',code],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
start=time.monotonic()
try:result=_read_app_server_response(p,1,start+.05);error=None
except Exception as exc:error=type(exc).__name__
results['partial_stdout']={'deadline_seconds':.05,'actual_seconds':round(time.monotonic()-start,3),'error':error}
p.wait(timeout=2)
def timed(fn,n=5):
 vals=[]
 for _ in range(n):
  start=time.perf_counter();fn();vals.append((time.perf_counter()-start)*1000)
 return round(statistics.median(vals),3)
with tempfile.TemporaryDirectory(prefix='aw-audit-perf-') as d:
 root=Path(d);event_path=root/'events.jsonl';snapshot_path=root/'snapshot.json'
 results['history_scaling']=[]
 for count in [0,1000,10000,100000]:
  e=WorldEngine.create(WorldConfig(seed=11,economy_mode='organic'),agent_names=['A','B'])
  e.state.events += [Event(tick=i//100,type='synthetic_history',scope='public',message='synthetic history') for i in range(count)]
  event_path.write_text(''.join(json.dumps(x.to_dict())+'\n' for x in e.state.events))
  snapshot_path.write_text(json.dumps(e.snapshot()))
  results['history_scaling'].append({'synthetic_events':count,'observation_ms':timed(lambda:build_observation(e.state,'agent-1')),'snapshot_ms':timed(e.snapshot),'control_event_scan_ms':timed(lambda:_latest_control_event(event_path)),'observer_state_ms':timed(lambda:load_observer_state(snapshot_path,event_path),3),'event_file_bytes':event_path.stat().st_size})
 e=WorldEngine.create(WorldConfig(seed=11,economy_mode='organic'),agent_names=['A','B'])
 def chars():
  return len(json.dumps(build_dynamic_observation(build_observation(e.state,'agent-1')),sort_keys=True,separators=(',',':')))
 before=chars()
 for i in range(1000):
  e.state.contracts[str(i)]=DeliveryContract(id=str(i),proposer_id='agent-1',counterparty_id='agent-2',give=Counter(food=1),receive=Counter(wood=1),collateral=Counter(),created_tick=0,deadline_tick=1,proposal_expires_tick=1,status='fulfilled')
 results['finished_contract_prompt_growth']={'before_chars':before,'after_1000_finished_contracts_chars':chars()}
print(json.dumps(results,indent=2))
