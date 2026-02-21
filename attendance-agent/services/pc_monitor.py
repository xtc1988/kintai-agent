import threading
from datetime import datetime, timedelta
from pynput import mouse, keyboard

# テスト時にモック差し替え可能にするためモジュールレベルで参照
mouse_listener_cls = mouse.Listener
keyboard_listener_cls = keyboard.Listener


class PCMonitor:
    """PC操作（マウス・キーボード）を監視し、稼働状態を判定する"""

    def __init__(self):
        self._events: list[datetime] = []
        self._lock = threading.Lock()
        self._mouse_listener = None
        self._keyboard_listener = None

    def _record_event(self):
        """操作イベントを記録する（dedup なし。テストから直接呼ばれる）"""
        now = datetime.now()
        with self._lock:
            self._events.append(now)

    def _record_event_dedup(self):
        """操作イベントを記録する（重複防止: 1秒以内の連続イベントは無視）"""
        now = datetime.now()
        with self._lock:
            if self._events and (now - self._events[-1]).total_seconds() < 1:
                return
            self._events.append(now)

    def _on_mouse_move(self, x, y):
        self._record_event_dedup()

    def _on_key_press(self, key):
        self._record_event_dedup()

    def get_recent_events(self, minutes: int) -> list[datetime]:
        """直近N分以内の操作イベントを返す"""
        cutoff = datetime.now() - timedelta(minutes=minutes)
        with self._lock:
            return [e for e in self._events if e > cutoff]

    def is_working(self, threshold_minutes: int, min_count: int) -> bool:
        """直近threshold_minutes分以内にmin_count回以上の操作があれば作業中と判定"""
        recent = self.get_recent_events(threshold_minutes)
        return len(recent) >= min_count

    def purge_old_events(self, minutes: int = 30):
        """古いイベントを削除してメモリを節約"""
        cutoff = datetime.now() - timedelta(minutes=minutes)
        with self._lock:
            self._events = [e for e in self._events if e > cutoff]

    def start(self):
        """マウス・キーボード監視を開始"""
        self._mouse_listener = mouse_listener_cls(on_move=self._on_mouse_move)
        self._keyboard_listener = keyboard_listener_cls(on_press=self._on_key_press)
        self._mouse_listener.start()
        self._keyboard_listener.start()

    def stop(self):
        """監視を停止"""
        if self._mouse_listener:
            self._mouse_listener.stop()
        if self._keyboard_listener:
            self._keyboard_listener.stop()
