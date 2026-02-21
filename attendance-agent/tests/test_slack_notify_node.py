from unittest.mock import MagicMock
from graph.nodes.slack_notify_node import slack_notify_node


def _make_state(**overrides):
    base = {
        "today": "2026-02-22",
        "is_holiday": False,
        "holiday_reason": None,
        "clock_in_done": False,
        "clock_in_time": None,
        "last_clock_out_time": None,
        "is_working": True,
        "operation_log": [],
        "action_taken": None,
        "error_message": None,
        "extra": {},
    }
    base.update(overrides)
    return base


def test_notify_clock_in():
    """出勤打刻成功の通知"""
    mock_notifier = MagicMock()
    mock_notifier.send.return_value = True

    state = _make_state(action_taken="clock_in", clock_in_time="09:12")
    result = slack_notify_node(state, notifier=mock_notifier)

    mock_notifier.send.assert_called_once()
    call_msg = mock_notifier.send.call_args[0][0]
    assert "出勤" in call_msg
    assert "09:12" in call_msg


def test_notify_clock_out():
    """退勤打刻成功の通知"""
    mock_notifier = MagicMock()
    mock_notifier.send.return_value = True

    state = _make_state(action_taken="clock_out", last_clock_out_time="18:00")
    result = slack_notify_node(state, notifier=mock_notifier)

    call_msg = mock_notifier.send.call_args[0][0]
    assert "退勤" in call_msg
    assert "18:00" in call_msg


def test_notify_error():
    """エラー通知"""
    mock_notifier = MagicMock()
    mock_notifier.send_error.return_value = True

    state = _make_state(action_taken="error", error_message="タイムアウト")
    result = slack_notify_node(state, notifier=mock_notifier)

    mock_notifier.send_error.assert_called_once_with("タイムアウト")


def test_notify_skipped_no_message():
    """スキップ時は通知しない"""
    mock_notifier = MagicMock()

    state = _make_state(action_taken="skipped")
    result = slack_notify_node(state, notifier=mock_notifier)

    mock_notifier.send.assert_not_called()
    mock_notifier.send_error.assert_not_called()
