# tests/test_state_update_node.py
from unittest.mock import patch
from datetime import datetime
from graph.nodes.state_update_node import state_update_node


def _make_state(**overrides):
    base = {
        "today": "2026-02-22",
        "is_holiday": False,
        "holiday_reason": None,
        "clock_in_done": True,
        "clock_in_time": "09:00",
        "last_clock_out_time": "18:00",
        "is_working": True,
        "operation_log": [],
        "action_taken": "clock_out",
        "error_message": None,
        "extra": {},
    }
    base.update(overrides)
    return base


def test_state_update_same_day():
    """同日中は状態を維持すること"""
    with patch("graph.nodes.state_update_node._today_str", return_value="2026-02-22"):
        state = _make_state()
        result = state_update_node(state)
    assert result["clock_in_done"] is True
    assert result["today"] == "2026-02-22"


def test_state_update_day_change():
    """日付が変わったら状態リセットすること"""
    with patch("graph.nodes.state_update_node._today_str", return_value="2026-02-23"):
        state = _make_state(today="2026-02-22")
        result = state_update_node(state)
    assert result["clock_in_done"] is False
    assert result["clock_in_time"] is None
    assert result["last_clock_out_time"] is None
    assert result["today"] == "2026-02-23"
    assert result["action_taken"] is None
    assert result["is_holiday"] is False


def test_state_update_clears_error():
    """正常完了後にエラーをクリアすること"""
    with patch("graph.nodes.state_update_node._today_str", return_value="2026-02-22"):
        state = _make_state(error_message="前回エラー", action_taken="clock_in")
        result = state_update_node(state)
    assert result["error_message"] is None
