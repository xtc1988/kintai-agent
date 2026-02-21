# tests/test_time_gate.py
from unittest.mock import patch
from datetime import datetime
from graph.nodes.time_gate_node import time_gate_node

DEFAULT_CONFIG = {
    "time_rules": {"clock_out_time": "18:00", "cutoff_time": "22:00"}
}


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


def _mock_time(hour, minute=0):
    return datetime(2026, 2, 22, hour, minute, 0)


def test_morning_clock_in():
    """朝・未打刻 → 出勤打刻"""
    with patch("graph.nodes.time_gate_node._now", return_value=_mock_time(9, 0)):
        state = _make_state(clock_in_done=False)
        result = time_gate_node(state, config=DEFAULT_CONFIG)
    assert result["action_taken"] == "clock_in"


def test_morning_already_clocked_in():
    """朝・打刻済み → スキップ"""
    with patch("graph.nodes.time_gate_node._now", return_value=_mock_time(10, 0)):
        state = _make_state(clock_in_done=True, clock_in_time="09:00")
        result = time_gate_node(state, config=DEFAULT_CONFIG)
    assert result["action_taken"] == "skipped"


def test_evening_clock_out():
    """18時以降・出勤済み → 退勤打刻"""
    with patch("graph.nodes.time_gate_node._now", return_value=_mock_time(18, 30)):
        state = _make_state(clock_in_done=True, clock_in_time="09:00")
        result = time_gate_node(state, config=DEFAULT_CONFIG)
    assert result["action_taken"] == "clock_out"


def test_evening_no_clock_in():
    """18時以降・出勤未済 → 出勤+退勤"""
    with patch("graph.nodes.time_gate_node._now", return_value=_mock_time(19, 0)):
        state = _make_state(clock_in_done=False)
        result = time_gate_node(state, config=DEFAULT_CONFIG)
    assert result["action_taken"] == "clock_in_and_out"


def test_after_cutoff():
    """22時以降 → スキップ"""
    with patch("graph.nodes.time_gate_node._now", return_value=_mock_time(22, 30)):
        state = _make_state(clock_in_done=False)
        result = time_gate_node(state, config=DEFAULT_CONFIG)
    assert result["action_taken"] == "skipped"
