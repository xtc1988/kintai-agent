from graph.state import AttendanceState
from datetime import datetime


def test_attendance_state_creation():
    """AttendanceStateが正しいキーで生成できること"""
    state: AttendanceState = {
        "today": "2026-02-22",
        "is_holiday": False,
        "holiday_reason": None,
        "clock_in_done": False,
        "clock_in_time": None,
        "last_clock_out_time": None,
        "is_working": False,
        "operation_log": [],
        "action_taken": None,
        "error_message": None,
        "extra": {},
    }
    assert state["today"] == "2026-02-22"
    assert state["is_holiday"] is False
    assert state["operation_log"] == []


def test_attendance_state_with_data():
    """操作ログ付きのStateが正しく動作すること"""
    now = datetime.now()
    state: AttendanceState = {
        "today": "2026-02-22",
        "is_holiday": False,
        "holiday_reason": None,
        "clock_in_done": True,
        "clock_in_time": "09:00",
        "last_clock_out_time": None,
        "is_working": True,
        "operation_log": [now],
        "action_taken": "clock_in",
        "error_message": None,
        "extra": {},
    }
    assert state["clock_in_done"] is True
    assert state["clock_in_time"] == "09:00"
    assert len(state["operation_log"]) == 1
