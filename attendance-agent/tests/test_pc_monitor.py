import time
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from services.pc_monitor import PCMonitor


def test_initial_state():
    """初期状態ではイベントが空であること"""
    monitor = PCMonitor()
    assert monitor.get_recent_events(15) == []
    assert monitor.is_working(threshold_minutes=15, min_count=2) is False


def test_record_event():
    """イベント記録後に取得できること"""
    monitor = PCMonitor()
    monitor._record_event()
    events = monitor.get_recent_events(15)
    assert len(events) == 1


def test_is_working_true():
    """閾値以上のイベントでis_working=Trueになること"""
    monitor = PCMonitor()
    monitor._record_event()
    monitor._record_event()
    monitor._record_event()
    assert monitor.is_working(threshold_minutes=15, min_count=2) is True


def test_is_working_false_too_few_events():
    """イベント数が閾値未満でis_working=Falseになること"""
    monitor = PCMonitor()
    monitor._record_event()
    assert monitor.is_working(threshold_minutes=15, min_count=2) is False


def test_old_events_purged():
    """古いイベントがフィルタされること"""
    monitor = PCMonitor()
    old_time = datetime.now() - timedelta(minutes=20)
    monitor._events.append(old_time)
    monitor._record_event()  # 現在のイベント追加
    events = monitor.get_recent_events(15)
    assert len(events) == 1  # 古いものはフィルタされる


def test_start_stop():
    """start/stopでリスナーが開始・停止されること"""
    monitor = PCMonitor()
    with patch("services.pc_monitor.mouse_listener_cls") as mock_mouse, \
         patch("services.pc_monitor.keyboard_listener_cls") as mock_kb:
        mock_mouse_inst = MagicMock()
        mock_kb_inst = MagicMock()
        mock_mouse.return_value = mock_mouse_inst
        mock_kb.return_value = mock_kb_inst

        monitor.start()
        mock_mouse_inst.start.assert_called_once()
        mock_kb_inst.start.assert_called_once()

        monitor.stop()
        mock_mouse_inst.stop.assert_called_once()
        mock_kb_inst.stop.assert_called_once()
