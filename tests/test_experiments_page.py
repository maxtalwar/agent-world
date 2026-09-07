import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from datetime import datetime, timezone
from agent_world.leaderboard import LeaderboardStore

class ExperimentsPageTests(unittest.TestCase):
    def test_experiment_progress_never_enters_rankings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);folder=root/'runs/jobs/experiment';folder.mkdir(parents=True)
            output=root/'runs/managed/experiment/seed-11';output.mkdir(parents=True)
            manifest=output/'run-manifest.json';manifest.write_text(json.dumps({'status':'running'}))
            (output/'run-report.json').write_text('{}')
            job={'run_id':'experiment','kind':'experiment','question':'Regeneration?',
                 'recipe':'participant-v8-revised','config':{'model':{'id':'gpt-5.6-sol','brain':'codex'}},
                 'cells':[{'id':'seed-11','seed':11,'run_manifest':str(manifest),'output_dir':str(output),'target_ticks':60}]}
            (folder/'job.json').write_text(json.dumps(job))
            (folder/'controller-heartbeat.json').write_text(json.dumps({'checked_at_utc':datetime.now(timezone.utc).isoformat(),
                'cells':[{'id':'seed-11','controller_state':'running','tick':12,'attention':'not_started'}]}))
            store=LeaderboardStore(root)
            with patch.object(store,'canonical_boards',return_value=[]),patch('agent_world.leaderboard.accepted_report',side_effect=AssertionError('No experiment certification')):
                data=store.build()
            self.assertEqual(len(data['experiments']),1)
            self.assertEqual(data['boards'],[])
            run=data['experiments'][0]
            self.assertEqual(run['question'],'Regeneration?')
            self.assertEqual(run['cells'][0]['tick'],12)
            self.assertIsNone(run['cells'][0]['attention'])
            self.assertFalse(run['ranked'])
