"""Exercise Strands graph construction and safe Tavily result shaping without provider calls."""
import importlib.util
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from workshop.policy import TicketDraft
from workshop.tools import ProviderUnavailable, RouteDecision, _tavily_hits, live_agents, route_for_message


@unittest.skipUnless(all(importlib.util.find_spec(name) for name in ("faiss", "strands", "tavily")),
                     "install requirements-live.txt for the live adapter test")
class LiveAdapterTest(unittest.TestCase):
    def setUp(self):
        loader = patch("workshop.tools.load_policy_pdf", return_value=[
            {"source": "Information Technology Procedure - Passwords, page 1",
             "text": "Password rules from PDF"},
        ])
        loader.start()
        self.addCleanup(loader.stop)

    @staticmethod
    def _embed_documents(texts):
        return [[1.0, 0.0] if index % 2 == 0 else [0.0, 1.0]
                for index, _ in enumerate(texts)]

    @patch("langchain_openai.OpenAIEmbeddings")
    def test_builds_a_real_strands_graph_with_three_specialists(self, embedding_type):
        embedding_type.return_value.embed_documents.side_effect = self._embed_documents
        agents = live_agents(chat_model="test-chat", embedding_model="test-embed", api_key="test-key",
                             tavily_key="test-tavily-key")
        self.assertGreaterEqual(embedding_type.call_args.kwargs["request_timeout"], 45)
        self.assertEqual(embedding_type.call_args.kwargs["max_retries"], 1)
        graph = agents.build_graph()
        self.assertEqual(set(graph.nodes), {"router", "qa", "ticket", "research"})
        self.assertEqual(len(graph.edges), 3)
        self.assertEqual(graph.nodes["router"].executor.__class__.__name__, "Agent")
        embedded = embedding_type.return_value.embed_documents.call_args.args[0]
        self.assertIn("Password rules from PDF", embedded)
        self.assertEqual(embedded, ["Password rules from PDF"])

    @patch("langchain_openai.OpenAIEmbeddings")
    def test_indexing_error_reports_safe_exception_type(self, embedding_type):
        from openai import OpenAIError
        embedding_type.return_value.embed_documents.side_effect = OpenAIError("private details")
        with self.assertRaisesRegex(RuntimeError, "OpenAIError") as caught:
            live_agents(chat_model="test-chat", embedding_model="test-embed", api_key="test-key",
                        tavily_key="test-tavily-key")
        self.assertNotIn("private details", str(caught.exception))

    def test_tavily_results_are_bounded_and_only_https(self):
        hits = _tavily_hits({"results": [
            {"title": "Good", "url": "https://example.com/vpn", "content": "A" * 900},
            {"title": "Bad", "url": "http://example.com", "content": "unsafe"},
            {"title": "Duplicate", "url": "https://example.com/vpn", "content": "same"},
        ]})
        self.assertEqual(len(hits), 1)
        self.assertEqual(len(hits[0]["content"]), 700)

    def test_troubleshoot_keyword_routes_to_research_but_ticket_stays_ticket(self):
        self.assertEqual(route_for_message(RouteDecision(route="qa"), "Troubleshoot VPN"), "research")
        self.assertEqual(route_for_message(RouteDecision(route="qa"), "troubleshooting login"), "research")
        self.assertEqual(route_for_message(RouteDecision(route="ticket"),
                                           "Tạo phiếu để troubleshoot VPN"), "ticket")
        self.assertEqual(route_for_message(RouteDecision(route="qa"),
                                           "Tạo phiếu để troubleshoot VPN"), "ticket")
        self.assertEqual(route_for_message(RouteDecision(route="qa"), "VPN là gì?"), "qa")

    @patch("langchain_openai.OpenAIEmbeddings")
    def test_troubleshoot_uses_research_edge_and_result_even_if_router_says_qa(self, embedding_type):
        from strands.multiagent.base import Status
        embedding_type.return_value.embed_documents.side_effect = self._embed_documents
        agents = live_agents(chat_model="test-chat", embedding_model="test-embed", api_key="test-key",
                             tavily_key="test-tavily-key")
        message = "Troubleshoot VPN login"
        graph = agents.build_graph({"message": message})
        state = SimpleNamespace(results={
            "router": SimpleNamespace(result=SimpleNamespace(structured_output=RouteDecision(route="qa"))),
        })
        selected = [edge.to_node.node_id for edge in graph.edges if edge.condition(state)]
        self.assertEqual(selected, ["research"])

        class Final:
            stop_reason = "end_turn"

            def __str__(self):
                return "Hướng dẫn VPN"

        def fake_build(capture):
            capture["citations"] = [{"url": "https://example.com", "title": "VPN guidance"}]
            capture["search_count"] = 1
            result = SimpleNamespace(status=Status.COMPLETED, results={
                "router": state.results["router"],
                "research": SimpleNamespace(status=Status.COMPLETED,
                                            result=Final()),
            })
            return lambda _message: result

        with patch.object(agents, "build_graph", side_effect=fake_build):
            answer = agents.run(message)
        self.assertEqual(answer["agent"], "research")
        self.assertEqual(answer["answer"], "Hướng dẫn VPN")

    @patch("langchain_openai.OpenAIEmbeddings")
    def test_strands_graph_result_preserves_ticket_approval_boundary(self, embedding_type):
        from strands.multiagent.base import Status
        embedding_type.return_value.embed_documents.side_effect = self._embed_documents
        agents = live_agents(chat_model="test-chat", embedding_model="test-embed", api_key="test-key",
                             tavily_key="test-tavily-key")

        class Final:
            stop_reason = "end_turn"

            def __str__(self):
                return "Bản nháp đã sẵn sàng"

        def fake_build(capture):
            capture["draft"] = TicketDraft(content="Lỗi VPN")
            result = SimpleNamespace(status=Status.COMPLETED, results={
                "router": SimpleNamespace(result=SimpleNamespace(structured_output=RouteDecision(route="ticket"))),
                "ticket": SimpleNamespace(status=Status.COMPLETED, result=Final()),
            })
            return lambda message: result

        with patch.object(agents, "build_graph", side_effect=fake_build):
            reply = agents.run("Tạo phiếu hỗ trợ cho lỗi VPN")
        self.assertEqual(reply["agent"], "ticket")
        self.assertEqual(reply["draft"].content, "Lỗi VPN")
        self.assertNotIn("ticket_id", reply)

    @patch("langchain_openai.OpenAIEmbeddings")
    def test_missing_tool_result_fails_closed(self, embedding_type):
        from strands.multiagent.base import Status
        embedding_type.return_value.embed_documents.side_effect = self._embed_documents
        agents = live_agents(chat_model="test-chat", embedding_model="test-embed", api_key="test-key",
                             tavily_key="test-tavily-key")
        result = SimpleNamespace(status=Status.COMPLETED, results={
            "router": SimpleNamespace(result=SimpleNamespace(structured_output=RouteDecision(route="qa"))),
            "qa": SimpleNamespace(status=Status.COMPLETED,
                                  result=SimpleNamespace(stop_reason="end_turn")),
        })
        with patch.object(agents, "build_graph", return_value=lambda message: result):
            with self.assertRaises(ProviderUnavailable):
                agents.run("VPN là gì?")
