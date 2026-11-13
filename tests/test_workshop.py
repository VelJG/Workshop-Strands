from concurrent.futures import ThreadPoolExecutor
import tempfile
from unittest.mock import patch
import unittest
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from workshop.agent_runtime import architecture_mermaid, create_app, save_graph_visualization
from workshop.policy import TicketDraft


def fake_agents_factory():
    def run(message):
        normalized = message.lower()
        if "tạo phiếu" in normalized or "create ticket" in normalized:
            return {"agent": "ticket", "draft": TicketDraft(content="Lỗi đăng nhập VPN")}
        if "web" in normalized:
            return {"agent": "research", "answer": "Kết quả web", "sources": [],
                    "citations": [{"title": "Nguồn mẫu", "url": "https://example.com"}]}
        return {"agent": "qa", "answer": "Phiếu hỗ trợ mới có trạng thái Pending." if "phiếu" in normalized else "Chưa rõ.",
                "sources": ["ticket-policy"] if "phiếu" in normalized else []}

    return SimpleNamespace(run=run)


class WorkshopTest(unittest.TestCase):
    def test_architecture_diagram_names_strands_agents_and_tools(self):
        diagram = architecture_mermaid()
        for name in ("Strands", "router", "qa_agent", "ticket_agent", "research_agent", "Tavily"):
            self.assertIn(name, diagram)

    def test_graph_png_export_does_not_call_provider(self):
        output = Path(self.temp.name) / "graph_visualization.png"
        with patch("workshop.agent_runtime.draw_mermaid_png", return_value=b"\x89PNG\r\n\x1a\n") as draw:
            self.assertEqual(save_graph_visualization(output), output)
            draw.assert_called_once()
        self.assertEqual(output.read_bytes(), b"\x89PNG\r\n\x1a\n")

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "test.db"

    def client(self, **kwargs):
        return TestClient(create_app(self.db, agents_factory=fake_agents_factory, **kwargs))

    def propose(self, client):
        response = client.post("/chat", json={"message": "Tạo phiếu hỗ trợ cho lỗi đăng nhập VPN"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["kind"], "approval_required")
        return response.json()["approval_id"]

    def test_grounded_answer_and_health(self):
        with self.client() as client:
            self.assertEqual(client.get("/health").json(), {"status": "ok"})
            reply = client.post("/chat", json={"message": "Phiếu hỗ trợ mới có trạng thái gì?"})
            self.assertIn("Pending", reply.json()["answer"])
            self.assertIn("ticket-policy", reply.json()["sources"])
            self.assertTrue(reply.headers["X-Request-ID"])
            unknown = client.post("/chat", json={"message": "Who won Wimbledon?"})
            self.assertEqual(unknown.json()["sources"], [])

    def test_research_route_returns_citation(self):
        with self.client() as client:
            result = client.post("/chat", json={"message": "Research web về VPN"}).json()
            self.assertEqual(result["agent"], "research")
            self.assertEqual(result["citations"][0]["url"], "https://example.com")

    def test_local_chat_page_and_script(self):
        with self.client() as client:
            page = client.get("/")
            self.assertEqual(page.status_code, 200)
            self.assertIn("text/html", page.headers["content-type"])
            self.assertIn("Trợ lý CNTT nội bộ", page.text)
            self.assertIn('src="/ui.js"', page.text)
            script = client.get("/ui.js")
            self.assertEqual(script.status_code, 200)
            source = script.content.decode("utf-8")
            self.assertIn('post("/chat"', source)
            self.assertIn('/approvals/', source)
            self.assertIn("Hệ thống sẵn sàng", source)
            self.assertNotIn("Chế độ diễn tập", source)

    def test_hosted_mode_does_not_expose_local_chat_page(self):
        with self.client(hosted=True, token="temporary-test-token") as client:
            self.assertEqual(client.get("/").status_code, 404)
            self.assertEqual(client.get("/ui.js").status_code, 404)
        with self.client(token="temporary-test-token") as client:
            self.assertEqual(client.get("/").status_code, 404)

    def test_only_approval_creates_a_ticket_and_replay_returns_same_ticket(self):
        with self.client() as client:
            approval = self.propose(client)
            self.assertEqual(client.get(f"/tickets/{approval}").status_code, 404)
        with self.client() as client:
            first = client.post(f"/approvals/{approval}", json={"approve": True})
            self.assertEqual(first.status_code, 200, first.text)
            second = client.post(f"/approvals/{approval}", json={"approve": True})
            self.assertEqual(first.json(), second.json())
            ticket = client.get(f"/tickets/{first.json()['ticket_id']}")
            self.assertEqual(ticket.json()["status"], "Pending")

    def test_concurrent_approval_replays_same_ticket(self):
        with self.client() as client:
            approval = self.propose(client)
            path = f"/approvals/{approval}"
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(lambda _: client.post(path, json={"approve": True}), range(2)))
            self.assertEqual([r.status_code for r in results], [200, 200])
            self.assertEqual(results[0].json(), results[1].json())

    def test_expired_approval_cannot_write(self):
        with self.client() as client:
            with patch("workshop.memory.time", return_value=0):
                approval = self.propose(client)
            self.assertEqual(client.post(f"/approvals/{approval}", json={"approve": True}).status_code, 409)
            self.assertEqual(client.get(f"/tickets/{approval}").status_code, 404)

    def test_denial_is_final(self):
        with self.client() as client:
            approval = self.propose(client)
            self.assertEqual(client.post(f"/approvals/{approval}", json={"approve": False}).json(),
                             {"status": "denied"})
            self.assertEqual(client.post(f"/approvals/{approval}", json={"approve": True}).status_code, 409)
            self.assertEqual(client.get(f"/tickets/{approval}").status_code, 404)

    def test_hosted_requires_token(self):
        with self.assertRaises(ValueError):
            self.client(hosted=True)
        with self.client(token="temporary-test-token", hosted=True) as client:
            self.assertEqual(client.get("/health").status_code, 200)
            self.assertEqual(client.post("/chat", json={"message": "VPN"}).status_code, 401)
            self.assertEqual(client.post("/chat", json={"message": "VPN"},
                             headers={"Authorization": "Bearer temporary-test-token"}).status_code, 200)

    def test_request_bounds_and_strict_approval(self):
        with self.client() as client:
            self.assertEqual(client.post("/chat", json={"message": "x" * 9000}).status_code, 413)
            self.assertEqual(client.post("/chat", json={"message": " "}).status_code, 422)
            approval = self.propose(client)
            self.assertEqual(client.post(f"/approvals/{approval}", json={"approve": "yes"}).status_code, 422)

    def test_provider_failure_is_returned_without_demo_fallback(self):
        from workshop.tools import ProviderUnavailable

        def unavailable():
            def turn(_message):
                raise ProviderUnavailable()
            return turn

        with TestClient(create_app(self.db, agents_factory=lambda: SimpleNamespace(
                run=unavailable()))) as client:
            response = client.post("/chat", json={"message": "VPN bị lỗi"})
            self.assertEqual(response.status_code, 503)
            self.assertIn("AI or search provider unavailable", response.text)
            self.assertNotIn("demo mode", response.text.lower())

