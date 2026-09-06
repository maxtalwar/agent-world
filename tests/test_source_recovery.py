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
