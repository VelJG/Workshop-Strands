import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from workshop.__main__ import load_live_settings, load_local_env, research_timeout_seconds, http_timeout_seconds


class ConfigTest(unittest.TestCase):
    def test_http_demo_timeout_covers_two_agent_calls(self):
        self.assertEqual(http_timeout_seconds({}), 180)
        self.assertEqual(http_timeout_seconds({"WORKSHOP_HTTP_TIMEOUT_SECONDS": "240"}), 240)
        with self.assertRaisesRegex(ValueError, "WORKSHOP_HTTP_TIMEOUT_SECONDS"):
            http_timeout_seconds({"WORKSHOP_HTTP_TIMEOUT_SECONDS": "0"})

    def test_research_timeout_is_configurable_and_bounded(self):
        self.assertEqual(research_timeout_seconds({}), 120)
        self.assertEqual(research_timeout_seconds({"WORKSHOP_RESEARCH_TIMEOUT_SECONDS": "180"}), 180)
        for value in ("0", "301", "invalid"):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "WORKSHOP_RESEARCH_TIMEOUT_SECONDS"):
                research_timeout_seconds({"WORKSHOP_RESEARCH_TIMEOUT_SECONDS": value})

    def test_live_configuration_requires_key_and_both_model_names(self):
        with self.assertRaisesRegex(ValueError, "OPENAI_API_KEY.*WORKSHOP_CHAT_MODEL.*WORKSHOP_EMBEDDING_MODEL.*TAVILY_API_KEY"):
            load_live_settings({})
        with self.assertRaisesRegex(ValueError, "WORKSHOP_CHAT_MODEL"):
            load_live_settings({
                "OPENAI_API_KEY": "example-test-only",
                "WORKSHOP_CHAT_MODEL": "   ",
                "WORKSHOP_EMBEDDING_MODEL": "test-embed",
                "TAVILY_API_KEY": "test-tavily-key",
            })
        settings = load_live_settings({
            "OPENAI_API_KEY": "example-test-only",
            "WORKSHOP_CHAT_MODEL": "test-chat",
            "WORKSHOP_EMBEDDING_MODEL": "test-embed",
            "TAVILY_API_KEY": "test-tavily-key",
        })
        self.assertEqual(settings, {
            "api_key": "example-test-only",
            "chat_model": "test-chat",
            "embedding_model": "test-embed",
            "tavily_key": "test-tavily-key",
        })

    def test_loads_local_file_without_overwriting_process_environment(self):
        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder) / ".env"
            config.write_text("OPENAI_API_KEY=file-test-key\n", encoding="utf-8")
            with patch.dict(os.environ, {"OPENAI_API_KEY": "process-test-key"}, clear=True):
                load_local_env(config)
                self.assertEqual(os.environ["OPENAI_API_KEY"], "process-test-key")
