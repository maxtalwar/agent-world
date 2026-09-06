"""Offline audit of the first v8 model ranking; never edits run evidence."""
import collections
import hashlib
import json
import math
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_world.outcome_scoring import derive_outcome_counts, score_outcome_counts

MODELS = ['gpt-5.4-mini', 'gpt-5.5', 'gpt-5.6-luna', 'gpt-5.6-terra']
catalog = json.loads(Path('data/run-sources.json').read_text())
result = {'evidence_class': 'offline_scoring_audit', 'studies': {}}
for model in MODELS:
    for suite in ['participant-v6', 'participant-v8']:
        entries = [m for m in catalog['models'] if m.get('model_id', m['model_key']) == model
                   and m.get('suite', catalog['suite']) == suite and m.get('leaderboard_eligible', True)]
        if not entries:
            continue
        entry = entries[0]
        cells = []
        pooled = collections.Counter()
        for spec in entry['runs']:
            if spec.get('included_in_model_result') is False:
                continue
            p = Path(spec['report_path'])
            report = json.loads(p.read_text())
            cohort = next(iter(report['benchmarks']['cohorts'].values()))
            events_path = p.with_name('run.jsonl')
            events = [json.loads(line) for line in events_path.open()]
            snapshot = json.loads(p.with_name('run-snapshot.json').read_text())
            manifest = json.loads(p.with_name('run-manifest.json').read_text())
            assert report['reliability']['benchmark_integrity_status'] == 'clean'
            horizon = report['run']['target_ticks']
            raw = derive_outcome_counts(events, snapshot, member_ids=cohort['agents'],
                                        target_ticks=horizon, tail_ticks=12)
            scores = score_outcome_counts(raw)
            if suite == 'participant-v8':
                for k in ['capability', 'execution']:
                    assert scores[k]['score'] == cohort['scores'][k]['score']
            pooled.update(raw)
            observations = {(e['tick'],e['actor_id']):e['data']['observation']['self']
                            for e in events if e['type']=='agent_observation'}
            # Independent population-health trajectory, excluding initial health.
            health = {t: sum(v['health'] for (tick,actor),v in observations.items() if tick==t)/10
                      for t in range(1,horizon)}
            health[horizon] = sum(a['health'] for a in snapshot['agents'].values() if a['alive'])/10
            assert abs(sum(health.values())*10 - raw['health_point_ticks']) < 1e-6
            decisions = [e for e in events if e['type']=='agent_response']
            invalid = [e for e in events if e['type']=='invalid_action']
            invalid_keys = {(e['tick'],e['actor_id']) for e in invalid}
            length = collections.defaultdict(lambda: [0,0])
            for e in decisions:
                n=len(e['data'].get('actions',[]))
                length[n][0]+=1
                length[n][1]+=int((e['tick'],e['actor_id']) in invalid_keys)
            usage=[json.loads(line) for line in p.with_name('run-usage.jsonl').open()]
            capacity_errors = [e for e in invalid if e['message'] in
                               [f"No {item} is available." for item in
                                ['water','food','wood','ore','stone','fiber']]]
            assert all(int(e['data']['action'].get('quantity',1)) > 0 for e in capacity_errors)
            c = {
                'misleading_capacity_errors':len(capacity_errors),
                'report': str(p), 'seed':spec['seed'], 'horizon':horizon,
                'hashes': {f.name:hashlib.sha256(f.read_bytes()).hexdigest()
                           for f in [p,events_path,p.with_name('run-snapshot.json'),p.with_name('run-manifest.json')]},
                'source':manifest['provenance']['git_sha'],
                'config':report['config'], 'agent_boundary':manifest['agent_boundary'],
                'original_scores':{k:v['score'] for k,v in cohort['scores'].items()},
                'outcome_raw':raw, 'outcome_scores':scores,
                'health_by_tick':health,
                'health_at_48':health[48],
                'capability_at_48':math.sqrt(sum(health[t] for t in range(1,49))/48*
                                             sum(health[t] for t in range(37,49))/12),
                'capability_at_50':math.sqrt(sum(health[t] for t in range(1,51))/50*
                                             sum(health[t] for t in range(39,51))/12),
                'living':report['survival']['living'],
                'structures':report['structures']['complete'],
                'actions':collections.Counter(a['type'] for e in decisions for a in e['data'].get('actions',[])),
                'plans_by_action_count':dict(length),
                'invalid_by_action':collections.Counter(e['data']['action'].get('type') for e in invalid),
                'invalid_messages':dict(collections.Counter(e['message'] for e in invalid).most_common(10)),
                'diagnostic_raw':cohort['raw'],
                'reasoning_tokens_per_call':report['usage']['efficiency'].get('mean_reasoning_tokens_per_call'),
                'static_prompt_hashes':sorted(set(u.get('static_prompt_sha256','missing') for u in usage)),
                'requested_efforts':sorted(set(u.get('reasoning_effort','missing') for u in usage)),
            }
            cells.append(c)
        if cells:
            result['studies'][model+' '+suite]={'cells':cells,'pooled_outcome_scores':score_outcome_counts(dict(pooled))}
out=Path(sys.argv[1])
out.write_text(json.dumps(result,indent=2)+'\n')
for name,study in result['studies'].items():
    print(name,'pooled', {k:v['score'] for k,v in study['pooled_outcome_scores'].items()})
    for c in study['cells']:
        r=c['diagnostic_raw']
        d=c['outcome_raw']['execution_decisions']
        print(c['seed'],'health',c['outcome_scores']['capability']['components'],
              'cap',c['outcome_scores']['capability']['score'],'cap50',round(c['capability_at_50'],2),
              'living',c['living'],'actions/decision',round(r.get('submitted_actions',0)/d,2),
              'plans',c['plans_by_action_count'],'reasoning',c['reasoning_tokens_per_call'])
