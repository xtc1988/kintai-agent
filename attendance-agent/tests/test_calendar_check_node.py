# tests/test_calendar_check_node.py
from unittest.mock import MagicMock
from graph.nodes.calendar_check_node import calendar_check_node


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


def test_calendar_check_holiday():
    """祝日の場合is_holiday=Trueになること"""
    mock_cal = MagicMock()
    mock_cal.is_holiday.return_value = (True, "建国記念の日")

    state = _make_state()
    result = calendar_check_node(state, calendar_service=mock_cal)
    assert result["is_holiday"] is True
    assert result["holiday_reason"] == "建国記念の日"


def test_calendar_check_workday():
    """平日の場合is_holiday=Falseになること"""
    mock_cal = MagicMock()
    mock_cal.is_holiday.return_value = (False, "")

    state = _make_state()
    result = calendar_check_node(state, calendar_service=mock_cal)
    assert result["is_holiday"] is False
    assert result["holiday_reason"] is None
