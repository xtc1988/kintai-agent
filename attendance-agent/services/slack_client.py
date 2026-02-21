from typing import Optional
import sys


class ConsoleNotifier:
    """コンソール出力による通知（フォールバック用）"""

    def send(self, message: str) -> bool:
        print(f"[勤怠通知] {message}", file=sys.stdout)
        return True

    def send_error(self, error: str) -> bool:
        print(f"[勤怠エラー] {error}", file=sys.stderr)
        return True


class SlackNotifier:
    """Slack APIによる通知サービス"""

    def __init__(self, token: str, channel: str):
        self._channel = channel
        self._client = None
        self._fallback = ConsoleNotifier()

        if token:
            try:
                from slack_sdk import WebClient
                self._client = WebClient(token=token)
            except Exception:
                pass

    def send(self, message: str) -> bool:
        """メッセージ送信（失敗時はフォールバック）"""
        if self._client is None:
            return self._fallback.send(message)

        try:
            self._client.chat_postMessage(channel=self._channel, text=message)
            return True
        except Exception:
            return False

    def send_error(self, error: str) -> bool:
        """エラー通知"""
        message = f"❌ 打刻に失敗しました。手動確認をお願いします（エラー: {error}）"
        return self.send(message)
