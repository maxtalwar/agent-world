import collections
import hashlib
import json
import re
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNS = ['sol-v61-ledger-comparison-20260908', 'web-gpt-6-astra-1dafc66aaaea']
PATTERNS = {
    'resource': r'\b(food|water|wood|timber|stone|ore|fiber|supplies)\b',
    'need': r'\b(need|needs|needed|seeking|seek|request|requests|urgently)\b',
    'offer': r'\b(offer|offers|offering|supply|supplier|suppliers|trade|pay|sell|selling)\b',
    'coordination': r'\b(shelter|well|farm|storage|access|contribut\w*|deliver\w*|shared|coordinat\w*|upkeep)\b',
}
result = {'batch_id': 'v6-restoration-ledger-20260908',
          'handoff': 'docs/benchmark-recipe-restoration-20260908.md',
          'method': 'Counts use successful ledger events. Agent-ticks use report observed_agent_ticks. Exact repetition normalizes body case/whitespace within each seed. Near repetition counts bodies with SequenceMatcher ratio >= .85 to an earlier body in that seed. Categories are overlapping lexical screens, not semantic judgements. Temporal follow-up does not establish causality.',
          'patterns': PATTERNS, 'cells': []}
for run in RUNS:
    job_path = ROOT / 'runs/jobs' / run / 'job.json'
    job = json.loads(job_path.read_text())
    assert job['analysis_readiness']['status'] == 'ready'
    for cell in job['cells']:
        directory = Path(cell['output_dir'])
        paths = [directory / f for f in ['run.jsonl', 'run-report.json', 'run-manifest.json', 'run-usage.jsonl', 'gift-classifications.json']]
        events = [json.loads(line) for line in paths[0].read_text().splitlines()]
        report = json.loads(paths[1].read_text())
        cohort = next(iter(report['benchmarks']['cohorts'].values()))
        raw = cohort['raw']
        assert raw['decisions'] == sum(e['type'] == 'agent_response' for e in events)
        assert any(e['type'] == 'run_completed' for e in events)
        notes = []
        bodies = []
        for line, event in enumerate(events, 1):
            if event['type'] != 'ledger_note':
                continue
            body = ' '.join(event['data']['body'].lower().split())
            labels = [key for key, pattern in PATTERNS.items() if re.search(pattern, body)]
            notes.append({'line': line, 'tick': event['tick'], 'agent': event['actor_id'],
                          'title': event['data']['title'], 'body': event['data']['body'],
                          'labels': labels, 'exact_repeat': body in bodies,
                          'near_repeat': any(SequenceMatcher(None, body, earlier).ratio() >= .85 for earlier in bodies)})
            bodies.append(body)
        counts = collections.Counter(e['type'] for e in events)
        data = {'run': run, 'seed': cell['seed'], 'launch_commit': job['launch_commit'],
                'recipe_digest': job.get('recipe_fingerprint_sha256'),
                'readiness': job['analysis_readiness'],
                'sources': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
                'agent_ticks': raw['observed_agent_ticks'], 'notes': len(notes),
                'notes_per_agent_tick': len(notes) / raw['observed_agent_ticks'],
                'unique_bodies': len(set(bodies)), 'near_repeats': sum(n['near_repeat'] for n in notes),
                'categories': {k: sum(k in n['labels'] for n in notes) for k in PATTERNS},
                'posting_by_agent': dict(collections.Counter(n['agent'] for n in notes)),
                'posting_by_ten_ticks': [sum(lo <= n['tick'] < lo + 10 for n in notes) for lo in range(0, 50, 10)],
                'events': dict(counts), 'raw': raw,
                'scores': {k: v['score'] for k, v in cohort['scores'].items()},
                'note_evidence': notes,
                'economic_events': [{'line': i, **e} for i,e in enumerate(events,1) if e['type'] in ['build','contribute','accept_trade','contract_proposed','contract_accepted','contract_defaulted','contract_completed','gift']]}
        result['cells'].append(data)
out = ROOT / 'docs/v61-ledger-comparison-20260908.json'
out.write_text(json.dumps(result, indent=2) + '\n')
for c in result['cells']:
    print(c['run'], c['seed'], {k: c[k] for k in ['notes','agent_ticks','unique_bodies','near_repeats','categories','posting_by_ten_ticks','posting_by_agent','scores']})
