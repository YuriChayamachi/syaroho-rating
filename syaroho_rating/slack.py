from slackweb import Slack

from syaroho_rating.consts import SLACK_WEBHOOK_URL


class SlackNotifier(object):
    def __init__(
        self,
        url: str = SLACK_WEBHOOK_URL,
        username: str = "syaroho-rating",
        icon_emoji: str = ":gurusyaro:",
    ):
        self.slack = Slack(url=url)
        self.username = username
        self.icon_emoji = icon_emoji

    def notify_success(self, title: str, text: str) -> None:
        attachment = {
            "color": "#30d158",
            "title": ":smile: " + title,
            "text": text,
        }
        self.slack.notify(
            attachments=[attachment], username=self.username, icon_emoji=self.icon_emoji
        )
        return

    def notify_failed(self, title: str, text: str) -> None:
        attachment = {
            "color": "#ff453a",
            "title": ":cry: " + title,
            "text": text,
        }
        self.slack.notify(
            attachments=[attachment], username=self.username, icon_emoji=self.icon_emoji
        )
        return

    def notify_info(self, title: str, text: str) -> None:
        attachment = {
            "color": "#0a84ff",
            "title": ":simple_smile: " + title,
            "text": text,
        }
        self.slack.notify(
            attachments=[attachment], username=self.username, icon_emoji=self.icon_emoji
        )
        return
