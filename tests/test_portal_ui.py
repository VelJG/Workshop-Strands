import unittest
from pathlib import Path


STATIC = Path(__file__).resolve().parents[1] / "workshop" / "static"


class PortalUiTest(unittest.TestCase):
    def test_portal_copy_and_existing_interaction_hooks(self):
        page = (STATIC / "index.html").read_text(encoding="utf-8")
        script = (STATIC / "ui.js").read_text(encoding="utf-8")

        for expected in (
            "Cổng hỗ trợ CNTT",
            "Trợ lý CNTT nội bộ",
            "Tra cứu chính sách",
            "Tạo yêu cầu hỗ trợ",
            "Tìm kiếm web",
            'id="messages"',
            'id="chat-form"',
            'id="message"',
            'id="send"',
            'id="service-status"',
            'src="/ui.js"',
        ):
            self.assertIn(expected, page)

        for demo_copy in ("Workshop Strands", "Hướng dẫn demo", "Chỉ dùng dữ liệu giả lập", "1. Hỏi về"):
            self.assertNotIn(demo_copy, page)

        for contract in ('post("/chat"', 'post(`/approvals/', 'fetch("/health")', 'data-message'):
            self.assertIn(contract, script if contract != "data-message" else page)
        self.assertNotIn("AI thật · local", script)
        self.assertIn("Phiếu hỗ trợ đã được tạo và đang chờ xử lý.", script)
        self.assertNotIn("${result.ticket_id}", script)


if __name__ == "__main__":
    unittest.main()
