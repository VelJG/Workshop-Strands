import unittest
from pathlib import Path
import re


STATIC = Path(__file__).resolve().parents[1] / "workshop" / "static"


class PortalUiTest(unittest.TestCase):
    def test_portal_copy_and_existing_interaction_hooks(self):
        page = (STATIC / "index.html").read_text(encoding="utf-8")
        script = (STATIC / "ui.js").read_text(encoding="utf-8")

        for expected in (
            "Cổng hỗ trợ CNTT",
            "Trợ lý IT",
            "Tra cứu chính sách",
            'data-message="Theo quy trình mật khẩu, có được dùng lại mật khẩu trong sáu lần đổi liên tiếp không? Trích dẫn trang liên quan."',
            'data-message="Tạo phiếu hỗ trợ: Tôi không đăng nhập được VPN từ sáng nay dù đã đổi mật khẩu; cần IT kiểm tra."',
            'data-message="Troubleshoot tại sao Outlook của tôi bị sập"',
            "Tạo yêu cầu hỗ trợ",
            "Tìm kiếm web",
            'id="messages"',
            'id="chat-form"',
            'id="message"',
            'id="send"',
            'src="/ui.js"',
        ):
            self.assertIn(expected, page)

        for demo_copy in ("Workshop Strands", "Hướng dẫn demo", "Chỉ dùng dữ liệu giả lập", "1. Hỏi về"):
            self.assertNotIn(demo_copy, page)
        self.assertNotIn('data-message="Phiếu hỗ trợ mới có trạng thái gì?"', page)

        for contract in ('post("/chat"', 'post(`/approvals/', 'data-message'):
            self.assertIn(contract, script if contract != "data-message" else page)
        self.assertNotIn("AI thật · local", script)
        self.assertIn("Phiếu hỗ trợ đã được tạo.", script)
        self.assertIn('id="recent-tickets"', page)
        self.assertIn('fetch("/tickets")', script)
        self.assertNotIn("${result.ticket_id}", script)

    def test_sidebar_shortcuts_and_recent_tickets_are_collapsed_and_status_badge_is_gone(self):
        page = (STATIC / "index.html").read_text(encoding="utf-8")
        script = (STATIC / "ui.js").read_text(encoding="utf-8")
        shortcuts = re.search(r'<details class="sidebar-section shortcuts">(.*?)</details>', page, re.S)
        tickets = re.search(r'<details class="sidebar-section ticket-list">(.*?)</details>', page, re.S)
        self.assertIsNotNone(shortcuts)
        self.assertIsNotNone(tickets)
        self.assertIn("<summary>Dịch vụ hỗ trợ</summary>", shortcuts.group(1))
        self.assertEqual(shortcuts.group(1).count('class="example"'), 3)
        self.assertIn("<summary>Phiếu gần đây</summary>", tickets.group(1))
        self.assertIn('id="recent-tickets"', tickets.group(1))
        self.assertNotIn('id="service-status"', page)
        self.assertNotIn('querySelector("#service-status")', script)
        self.assertNotIn('fetch("/health")', script)


if __name__ == "__main__":
    unittest.main()
