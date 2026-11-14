import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import unittest

from workshop.slack import SlackNotificationError, send_ticket


class SlackNotificationTest(unittest.TestCase):
    def test_posts_full_ticket_details_to_webhook(self):
        vietnam_time = timezone(timedelta(hours=7))
        ticket = {"ticket_ref": "IT-00001", "title": "Lỗi đăng nhập VPN",
                  "priority": "normal", "category": "network",
                  "content": "Người dùng không thể đăng nhập VPN.",
                  "created_at": datetime(2026, 11, 14, 8, 50, 26, tzinfo=vietnam_time).timestamp()}
        with patch("workshop.slack.urlopen") as open_url:
            open_url.return_value.__enter__.return_value.status = 200
            send_ticket("https://hooks.slack.com/services/T/B/test", ticket, tz=vietnam_time)
        request = open_url.call_args.args[0]
        self.assertEqual(request.full_url, "https://hooks.slack.com/services/T/B/test")
        self.assertEqual(open_url.call_args.kwargs["timeout"], 5)
        self.assertEqual(request.get_header("Content-type"), "application/json")
        message = json.loads(request.data)["text"]
        self.assertEqual(message, "Mã phiếu: IT-00001\nTiêu đề: Lỗi đăng nhập VPN\n"
                         "Loại: Mạng/VPN\nƯu tiên: Bình thường\n"
                         "Mô tả: Người dùng không thể đăng nhập VPN.\n"
                         "Trạng thái: Chờ xử lý\nTạo lúc: 08:50:26 14/11/2026")

    def test_escapes_user_text_before_sending_to_slack(self):
        ticket = {"ticket_ref": "IT-00001", "title": "VPN <@U123>", "priority": "low",
                  "category": "other", "content": "Lỗi <script> & cần hỗ trợ",
                  "created_at": 0}
        with patch("workshop.slack.urlopen") as open_url:
            open_url.return_value.__enter__.return_value.status = 200
            send_ticket("https://hooks.slack.com/services/T/B/test", ticket)
        message = json.loads(open_url.call_args.args[0].data)["text"]
        self.assertIn("VPN &lt;@U123&gt;", message)
        self.assertIn("Lỗi &lt;script&gt; &amp; cần hỗ trợ", message)

    def test_rejects_non_slack_or_insecure_webhook(self):
        with patch("workshop.slack.urlopen") as open_url:
            for url in ("http://hooks.slack.com/services/T/B/test",
                        "https://hooks.slack.com.evil.test/services/T/B/test",
                        "https://hooks.slack.com/other"):
                with self.subTest(url=url), self.assertRaises(ValueError):
                    send_ticket(url, {"ticket_ref": "IT-00001"})
            open_url.assert_not_called()

    def test_non_success_response_raises(self):
        with patch("workshop.slack.urlopen") as open_url:
            open_url.return_value.__enter__.return_value.status = 500
            with self.assertRaises(SlackNotificationError):
                send_ticket("https://hooks.slack.com/services/T/B/test",
                            {"ticket_ref": "IT-00001", "title": "VPN",
                             "priority": "normal", "category": "network",
                             "content": "VPN issue", "created_at": 0})
