from contextlib import contextmanager
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
import unittest

from fastapi.testclient import TestClient

from workshop.agent_runtime import create_app
from workshop.observability import init_langfuse


class LangfuseTest(unittest.TestCase):
    def test_disabled_without_keys_and_partial_keys_fail_clearly(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(init_langfuse())
            os.environ["LANGFUSE_PUBLIC_KEY"] = "test-public"
            with self.assertRaisesRegex(ValueError, "LANGFUSE_SECRET_KEY"):
                init_langfuse()

    def test_configured_keys_initialize_client(self):
        client = object()
        get_client = Mock(return_value=client)
        with patch.dict(os.environ, {"LANGFUSE_PUBLIC_KEY": "test-public",
                                     "LANGFUSE_SECRET_KEY": "test-secret"}, clear=True):
            with patch.dict(sys.modules, {"langfuse": SimpleNamespace(get_client=get_client)}):
                self.assertIs(init_langfuse(), client)
        get_client.assert_called_once_with()

    def test_chat_runs_inside_trace_and_flushes_on_shutdown(self):
        class TraceClient:
            def __init__(self):
                self.events = []

            @contextmanager
            def start_as_current_observation(self, **kwargs):
                self.events.append(("start", kwargs))
                yield
                self.events.append(("end", None))

            def flush(self):
                self.events.append(("flush", None))

        tracer = TraceClient()

        def run(_message):
            self.assertEqual(tracer.events[0][0], "start")
            return {"agent": "qa", "answer": "OK", "sources": []}

        with tempfile.TemporaryDirectory() as folder:
            app = create_app(Path(folder) / "test.db",
                             agents_factory=lambda: SimpleNamespace(run=run), trace_client=tracer)
            with TestClient(app) as client:
                response = client.post("/chat", json={"message": "Test trace"})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(tracer.events[0][1]["name"], "workshop.chat")
                self.assertEqual(tracer.events[0][1]["metadata"]["request_id"],
                                 response.headers["X-Request-ID"])
                self.assertEqual([event for event, _ in tracer.events], ["start", "end"])
            self.assertEqual([event for event, _ in tracer.events], ["start", "end", "flush"])
