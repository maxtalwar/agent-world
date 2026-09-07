import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from agent_world.source_recovery import validate_recovery_record

class RecoveryTests(unittest.TestCase):
    def test_record_binds_source_recipe_provider_checkpoint_and_archive(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); archive=root/"before.pkl"; archive.write_bytes(b"original")
            checkpoint=root/"run.pkl"; checkpoint.write_bytes(b"current")
            record={"schema_version":1,"to_commit":"fixed","from_commit":"original",
                "protocol":"participant-v8-revised","from_fingerprint":"old-fingerprint",
                "providers":["antigravity_cli"],"checkpoint":str(checkpoint.resolve()),
                "checkpoint_archive":str(archive),"checkpoint_sha256":hashlib.sha256(b"original").hexdigest(),
                "certification":"requires_source_migration_review","reason":"audited finish event correction"}
            path=root/"recovery.json"
            with patch("agent_world.source_recovery.subprocess.check_output",return_value="fixed\n"):
                path.write_text(json.dumps(record))
                validate_recovery_record(path,checkpoint,"participant-v8-revised","old-fingerprint",["antigravity_cli"])
                for key in ["to_commit","protocol","from_fingerprint","providers","checkpoint","certification","checkpoint_sha256"]:
                    altered={**record,key:"wrong"};path.write_text(json.dumps(altered))
                    with self.subTest(key=key),self.assertRaises(ValueError):
                        validate_recovery_record(path,checkpoint,"participant-v8-revised","old-fingerprint",["antigravity_cli"])


import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from agent_world.source_recovery import validate_recovery_record

class SourceRecoveryTests(unittest.TestCase):
    def test_nonempty_pending_journal_is_preserved_and_blocks_migration(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); checkpoint=root/"run-checkpoint.pkl"; archive=root/"archive.pkl"
            archive.write_bytes(b"original")
            pending=root/"run-pending-tick.json"
            pending.write_text(json.dumps({"decisions":{"agent-1":{"decision":{"intent":"accepted"}}}}))
            before=pending.read_bytes()
            record={"schema_version":1,"to_commit":"new","from_commit":"old",
                    "protocol":"recipe","from_fingerprint":"fingerprint","providers":["claude_cli"],
                    "checkpoint":str(checkpoint.resolve()),"checkpoint_archive":str(archive),
                    "checkpoint_sha256":hashlib.sha256(archive.read_bytes()).hexdigest(),
                    "certification":"requires_source_migration_review","reason":"quota repair"}
            path=root/"recovery.json"; path.write_text(json.dumps(record))
            with patch("agent_world.source_recovery.subprocess.check_output",return_value="new"):
                with self.assertRaisesRegex(ValueError,"accepted pending decisions"):
                    validate_recovery_record(path,checkpoint,"recipe","fingerprint",["claude_cli"])
            self.assertEqual(pending.read_bytes(),before)
