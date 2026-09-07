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
