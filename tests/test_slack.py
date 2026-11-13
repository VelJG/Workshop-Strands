import json
from unittest.mock import patch
import unittest

from workshop.slack import SlackNotificationError, send_ticket


class SlackNotificationTest(unittest.TestCase):
    def test_posts_ticket_summary_to_webhook(self):
        ticket = {"ticket_ref": "IT-00001", "title": "Lỗi đăng nhập VPN",
                  "priority": "normal", "category": "network"}
        with patch("workshop.slack.urlopen") as open_url:
            open_url.return_value.__enter__.return_value.status = 200
            send_ticket("https://hooks.slack.com/services/T/B/test", ticket)
        request = open_url.call_args.args[0]
        self.assertEqual(request.full_url, "https://hooks.slack.com/services/T/B/test")
        self.assertEqual(open_url.call_args.kwargs["timeout"], 5)
        self.assertEqual(request.get_header("Content-type"), "application/json")
        message = json.loads(request.data)["text"]
        for value in ticket.values():
            self.assertIn(value, message)

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
                             "priority": "normal", "category": "network"})
