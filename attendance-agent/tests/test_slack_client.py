from unittest.mock import MagicMock, patch
from services.slack_client import SlackNotifier, ConsoleNotifier


def test_console_notifier_send():
    """ConsoleNotifierがメッセージを出力すること"""
    notifier = ConsoleNotifier()
    with patch("builtins.print") as mock_print:
        result = notifier.send("テストメッセージ")
    assert result is True
    mock_print.assert_called_once()


def test_console_notifier_send_error():
    """ConsoleNotifierがエラーメッセージを出力すること"""
    notifier = ConsoleNotifier()
    with patch("builtins.print") as mock_print:
        result = notifier.send_error("エラー内容")
    assert result is True


def test_slack_notifier_send_success():
    """SlackNotifierがメッセージ送信に成功すること"""
    mock_client = MagicMock()
    mock_client.chat_postMessage.return_value = {"ok": True}

    notifier = SlackNotifier(token="xoxb-test", channel="C12345")
    notifier._client = mock_client

    result = notifier.send("テスト通知")
    assert result is True
    mock_client.chat_postMessage.assert_called_once_with(
        channel="C12345", text="テスト通知"
    )


def test_slack_notifier_send_failure():
    """Slack API失敗時にFalseを返すこと"""
    mock_client = MagicMock()
    mock_client.chat_postMessage.side_effect = Exception("API Error")

    notifier = SlackNotifier(token="xoxb-test", channel="C12345")
    notifier._client = mock_client

    result = notifier.send("テスト通知")
    assert result is False


def test_slack_notifier_fallback():
    """Slack初期化失敗時にフォールバックすること"""
    notifier = SlackNotifier(token="", channel="")
    with patch("builtins.print") as mock_print:
        result = notifier.send("フォールバックテスト")
    assert result is True
