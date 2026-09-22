"""Bounded Codex prompt-layout diagnostic; no simulation is advanced."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_world.codex_brain import CodexBrain, _plan_auth_environment, build_codex_prompt, parse_codex_jsonl, parse_codex_session_id, _codex_subtract_inherited_usage
from agent_world.interface import build_static_context, build_observation, dynamic_observation_json
from agent_world.models import WorldConfig
from agent_world.world import WorldEngine


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--live', action='store_true', help='Spend the bounded native Luna calls described by the generated config.')
    parser.add_argument('--fork', action='store_true', help='Test three native ephemeral forks of a static-only template.')
    args = parser.parse_args()
    if args.live and (args.output / 'results.jsonl').exists():
        parser.error('Use a new output directory; existing diagnostic evidence is never appended or overwritten.')
    brain = CodexBrain(connector_profile='connector-v3', model='gpt-5.6-luna', reasoning_effort='low')
    world = WorldEngine.create(WorldConfig(seed=11), agent_names=['Cache Probe'])
    observation = build_observation(world.state, 'agent-1')
    static = build_static_context(observation['world'])
    prefix = build_codex_prompt(static, '').removesuffix('The current private observation follows as JSON:\n')
    args.output.mkdir(parents=True, exist_ok=True)
    instruction_file = args.output.resolve() / 'instructions.txt'
    instruction_file.write_text(prefix)
    config = {'model': brain.model, 'effort': brain.reasoning_effort, 'seed': 11,
        'question': 'Can a native static instruction file extend caching past the CLI preamble?',
        'cli_version': brain.cli_version, 'static_sha256': hashlib.sha256(prefix.encode()).hexdigest(),
        'treatments': ['baseline', 'static-instructions'], 'calls_per_treatment': 3,
        'simulation_advanced': False}
    if args.fork:
        config['treatments'] = ['static-template', 'native-fork']
        config['question'] = 'Do native ephemeral forks reuse the static rulebook cache without sharing private observations?'
    config['call_counts'] = {t: 1 if t == 'static-template' else 3 for t in config['treatments']}
    config.pop('calls_per_treatment')
    (args.output / 'config.json').write_text(json.dumps(config, indent=2) + '\n')
    if not args.live:
        print(json.dumps(config))
        return
    with (args.output / 'results.jsonl').open('a') as output:
        seed_id = None
        seed_usage = {}
        for treatment in config['treatments']:
            for index in range(1 if treatment == 'static-template' else 3):
                observation['tick'] = index
                dynamic = dynamic_observation_json(observation)
                prompt = build_codex_prompt(static, dynamic)
                command = brain._command(brain._stable_schema_path)
                if treatment == 'static-instructions':
                    command[-1:-1] = ['-c', 'model_instructions_file=' + json.dumps(str(instruction_file))]
                    prompt = 'The current private observation follows as JSON:\n' + dynamic
                elif treatment == 'static-template':
                    command.remove('--ephemeral')
                    prompt = prefix + '\nThis initializes the shared rulebook only. No agent observation has been supplied. Return exactly {"intent":"ready","actions":[],"messages":[],"memory_updates":[]}. The next user message will supply the private observation.'
                elif treatment == 'native-fork':
                    command[2:2] = ['fork']
                    pos = command.index('--sandbox')
                    del command[pos:pos+2]
                    command[-1:-1] = [seed_id]
                    prompt = 'The current private observation follows as JSON:\n' + dynamic
                started = time.monotonic()
                result = subprocess.run(command, cwd=brain._stable_work_dir, input=prompt,
                    text=True, capture_output=True, env=_plan_auth_environment(), timeout=120)
                record = {'treatment': treatment, 'index': index, 'exit': result.returncode,
                    'duration_seconds': round(time.monotonic() - started, 3),
                    'stdout': result.stdout, 'stderr': result.stderr}
                if result.returncode == 0:
                    response, usage = parse_codex_jsonl(result.stdout)
                    record['raw_cli_usage'] = dict(usage)
                    if treatment == 'native-fork':
                        response, usage = parse_codex_jsonl(_codex_subtract_inherited_usage(result, seed_usage).stdout)
                    record.update(response=json.loads(response), usage=usage)
                    if treatment == 'static-template':
                        seed_id = parse_codex_session_id(result.stdout)
                        seed_usage = dict(usage)
                        record['template_session_id'] = seed_id
                output.write(json.dumps(record) + '\n')
                output.flush()
                print(json.dumps({k: v for k, v in record.items() if k not in {'stdout', 'stderr', 'response'}}), flush=True)
                if result.returncode:
                    raise SystemExit('Diagnostic stopped on provider failure; see retained output.')


if __name__ == '__main__':
    main()
