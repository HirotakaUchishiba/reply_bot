"""
Unit tests for gmail_poller handler
"""
from unittest.mock import MagicMock, patch

from src.app.gmail_poller import handler


def _mock_message(msg_id: str, subject: str, sender: str, body: str) -> dict:
    return {
        "id": msg_id,
        "payload": {
            "headers": [
                {"name": "Subject", "value": subject},
                {"name": "From", "value": sender},
            ],
            "parts": [
                {
                    "mimeType": "text/plain",
                    "body": {
                        # urlsafe base64-encoded "body"
                        "data": __import__("base64")
                        .urlsafe_b64encode(body.encode("utf-8"))
                        .decode("ascii"),
                    },
                }
            ],
        },
    }


class _MockGmailService:
    def __init__(self, messages):
        self._messages = messages

    def users(self):
        return self

    def messages(self):
        return self

    def list(self, userId: str, q: str, maxResults: int):  # noqa: N802
        class _Exec:
            def execute(inner_self):
                return {"messages": [{"id": m["id"]} for m in self._messages]}

        return _Exec()

    def get(self, userId: str, id: str, format: str):  # noqa: A003,N802
        class _Exec:
            def execute(inner_self):
                for m in self._messages:
                    if m["id"] == id:
                        return m
                return {}

        return _Exec()


class TestGmailPoller:
    def test_processes_unread_and_posts_slack(self) -> None:
        messages = [
            _mock_message("m1", "S1", "a@example.com", "Hello 1"),
            _mock_message("m2", "S2", "b@example.com", "Hello 2"),
        ]

        with (
            patch("src.app.gmail_poller.load_config") as mock_cfg,
            patch("src.app.gmail_poller.clear_secrets_cache"),
            patch("src.app.gmail_poller.resolve_gmail_oauth") as mock_oauth,
            patch("src.app.gmail_poller._get_gmail_service") as mock_gmail,
            patch("src.app.gmail_poller.get_context_item") as mock_get,
            patch("src.app.gmail_poller.put_context_item") as mock_put,
            patch(
                "common.secrets.resolve_slack_credentials"
            ) as mock_resolve_slack,
            patch("src.app.gmail_poller.SlackClient") as mock_slack,
            patch("src.app.gmail_poller.redact_and_map") as mock_redact,
        ):
            mock_cfg.return_value = MagicMock(
                gmail_oauth_secret_arn="arn:aws:secretsmanager:region:acct:secret:x",
                slack_signing_secret_arn="arn:aws:secretsmanager:region:acct:secret:y",
                slack_app_secret_arn="arn:aws:secretsmanager:region:acct:secret:z",
                slack_channel_id="C123",
            )
            mock_oauth.return_value = {
                "client_id": "id",
                "client_secret": "secret",
                "refresh_token": "rt",
            }
            mock_gmail.return_value = _MockGmailService(messages)
            mock_get.return_value = None
            mock_resolve_slack.return_value = {
                "bot_token": "xoxb-test",
                "signing_secret": "s",
            }
            mock_slack_instance = MagicMock()
            mock_slack.return_value = mock_slack_instance
            # passthrough redaction
            mock_redact.side_effect = lambda x: (x, {})

            response = handler({}, None)

            assert response["statusCode"] == 200
            # two items saved
            assert mock_put.call_count == 2
            # two Slack notifications
            assert mock_slack_instance.post_message.call_count == 2

    def test_deduplicates_existing_messages(self) -> None:
        messages = [
            _mock_message("dup", "S", "a@example.com", "Hello"),
            _mock_message("new", "S2", "b@example.com", "Hello2"),
        ]

        with (
            patch("src.app.gmail_poller.load_config") as mock_cfg,
            patch("src.app.gmail_poller.clear_secrets_cache"),
            patch("src.app.gmail_poller.resolve_gmail_oauth") as mock_oauth,
            patch("src.app.gmail_poller._get_gmail_service") as mock_gmail,
            patch("src.app.gmail_poller.get_context_item") as mock_get,
            patch("src.app.gmail_poller.put_context_item") as mock_put,
            patch(
                "common.secrets.resolve_slack_credentials"
            ) as mock_resolve_slack,
            patch("src.app.gmail_poller.SlackClient") as mock_slack,
            patch("src.app.gmail_poller.redact_and_map") as mock_redact,
        ):
            mock_cfg.return_value = MagicMock(
                gmail_oauth_secret_arn="arn:aws:secretsmanager:region:acct:secret:x",
                slack_signing_secret_arn="arn:aws:secretsmanager:region:acct:secret:y",
                slack_app_secret_arn="arn:aws:secretsmanager:region:acct:secret:z",
                slack_channel_id="C123",
            )
            mock_oauth.return_value = {
                "client_id": "id",
                "client_secret": "secret",
                "refresh_token": "rt",
            }
            mock_gmail.return_value = _MockGmailService(messages)
            # first id exists, second does not
            def _get(cid):
                return {"context_id": cid} if cid == "dup" else None

            mock_get.side_effect = _get
            mock_resolve_slack.return_value = {
                "bot_token": "xoxb-test",
                "signing_secret": "s",
            }
            mock_slack.return_value = MagicMock()
            mock_redact.side_effect = lambda x: (x, {})

            response = handler({}, None)

            assert response["statusCode"] == 200
            # only new message saved
            assert mock_put.call_count == 1

    def test_handles_gmail_error(self) -> None:
        with (
            patch("src.app.gmail_poller.load_config") as mock_cfg,
            patch("src.app.gmail_poller.clear_secrets_cache"),
            patch("src.app.gmail_poller.resolve_gmail_oauth") as mock_oauth,
            patch("src.app.gmail_poller._get_gmail_service") as mock_gmail,
        ):
            mock_cfg.return_value = MagicMock(
                gmail_oauth_secret_arn="arn:aws:secretsmanager:region:acct:secret:x",
            )
            mock_oauth.return_value = {
                "client_id": "id",
                "client_secret": "secret",
                "refresh_token": "rt",
            }
            mock_gmail.side_effect = RuntimeError("boom")

            response = handler({}, None)

            assert response["statusCode"] == 500


