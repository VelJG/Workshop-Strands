"""Send approved ticket announcements to one configured Slack channel."""
from datetime import datetime, tzinfo
import json
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


class SlackNotificationError(Exception):
    pass


CATEGORIES = {"access": "Tài khoản", "network": "Mạng/VPN", "software": "Phần mềm",
              "hardware": "Thiết bị", "other": "Khác"}
PRIORITIES = {"low": "Thấp", "normal": "Bình thường", "high": "Cao"}


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def send_ticket(webhook_url: str, ticket: dict, *, tz: tzinfo | None = None) -> None:
    target = urlsplit(webhook_url)
    if (target.scheme != "https" or target.netloc != "hooks.slack.com"
            or not target.path.startswith("/services/") or target.query or target.fragment):
        raise ValueError("SLACK_WEBHOOK_URL must be a Slack incoming webhook URL.")

    created_at = datetime.fromtimestamp(ticket["created_at"], tz=tz).strftime("%H:%M:%S %d/%m/%Y")
    message = (f"Mã phiếu: {ticket['ticket_ref']}\n"
               f"Tiêu đề: {_escape(ticket['title'])}\n"
               f"Loại: {CATEGORIES.get(ticket['category'], CATEGORIES['other'])}\n"
               f"Ưu tiên: {PRIORITIES.get(ticket['priority'], PRIORITIES['normal'])}\n"
               f"Mô tả: {_escape(ticket['content'])}\n"
               f"Trạng thái: Chờ xử lý\n"
               f"Tạo lúc: {created_at}")
    request = Request(webhook_url, data=json.dumps({"text": message}).encode("utf-8"),
                      headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(request, timeout=5) as response:
            if response.status != 200:
                raise SlackNotificationError("Slack webhook returned an error.")
    except (URLError, OSError):
        raise SlackNotificationError("Slack webhook request failed.") from None
