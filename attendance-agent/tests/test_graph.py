# tests/test_graph.py
from graph.graph import (
    route_after_working_check,
    route_after_calendar_check,
    route_after_time_gate,
    build_graph,
)


def _make_state(**overrides):
    base = {
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
    base.update(overrides)
    return base


def test_route_working_check_not_working():
    """作業中でない場合endへ"""
    state = _make_state(is_working=False)
    assert route_after_working_check(state) == "end"


def test_route_working_check_working():
    """作業中の場合calendar_checkへ"""
    state = _make_state(is_working=True)
    assert route_after_working_check(state) == "calendar_check"


def test_route_calendar_holiday():
    """祝日の場合endへ"""
    state = _make_state(is_holiday=True)
    assert route_after_calendar_check(state) == "end"


def test_route_calendar_workday():
    """平日の場合time_gateへ"""
    state = _make_state(is_holiday=False)
    assert route_after_calendar_check(state) == "time_gate"


def test_route_time_gate_skipped():
    """スキップの場合endへ"""
    state = _make_state(action_taken="skipped")
    assert route_after_time_gate(state) == "end"


def test_route_time_gate_stamp():
    """打刻が必要な場合stampへ"""
    state = _make_state(action_taken="clock_in")
    assert route_after_time_gate(state) == "stamp"


def test_build_graph():
    """グラフが正常にビルドできること"""
    graph = build_graph()
    assert graph is not None
