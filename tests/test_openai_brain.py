from __future__ import annotations

import os
import tempfile
import unittest

from agent_world.env import load_dotenv
from agent_world.openai_brain import OpenAIBrain, extract_output_text


class OpenAIBrainTests(unittest.TestCase):
    def test_extract_output_text_from_output_text(self) -> None:
        response = {"output_text": '{"intent":"wait","actions":[],"messages":[],"memory_updates":[]}'}
        self.assertIn('"intent"', extract_output_text(response))

    def test_extract_output_text_from_nested_response_content(self) -> None:
        response = {
            "output": [
                {
                    "content": [
                        {
                            "type": "output_text",
                            "text": '{"intent":"wait","actions":[],"messages":[],"memory_updates":[]}',
                        }
                    ]
                }
            ]
        }
        self.assertIn('"actions"', extract_output_text(response))

    def test_dotenv_loader_sets_missing_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, ".env")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("AGENT_WORLD_TEST_ENV=loaded\n")
            os.environ.pop("AGENT_WORLD_TEST_ENV", None)
            load_dotenv(path)
            self.assertEqual(os.environ["AGENT_WORLD_TEST_ENV"], "loaded")

    def test_openai_brain_requires_key(self) -> None:
        old_key = os.environ.pop("OPENAI_API_KEY", None)
        try:
            with self.assertRaises(ValueError):
                OpenAIBrain()
        finally:
            if old_key is not None:
                os.environ["OPENAI_API_KEY"] = old_key


if __name__ == "__main__":
    unittest.main()
