"""Send approved ticket announcements to one configured Slack channel."""
import json
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


class SlackNotificationError(Exception):
    pass


def send_ticket(webhook_url: str, ticket: dict) -> None:
    target = urlsplit(webhook_url)
    if (target.scheme != "https" or target.netloc != "hooks.slack.com"
            or not target.path.startswith("/services/") or target.query or target.fragment):
        raise ValueError("SLACK_WEBHOOK_URL must be a Slack incoming webhook URL.")

    title = ticket["title"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    message = (f"Phiếu CNTT mới: {ticket['ticket_ref']}\n"
               f"Tiêu đề: {title}\n"
               f"Mức ưu tiên: {ticket['priority']} | Loại: {ticket['category']}")
    request = Request(webhook_url, data=json.dumps({"text": message}).encode("utf-8"),
                      headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(request, timeout=5) as response:
            if response.status != 200:
                raise SlackNotificationError("Slack webhook returned an error.")
    except (URLError, OSError):
        raise SlackNotificationError("Slack webhook request failed.") from None
