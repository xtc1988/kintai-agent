from datetime import datetime
from unittest.mock import MagicMock
from graph.nodes.working_state_node import working_state_node


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


def test_working_state_node_active():
    """PC操作が十分にある場合、is_working=Trueになること"""
    mock_monitor = MagicMock()
    now = datetime.now()
    mock_monitor.is_working.return_value = True
    mock_monitor.get_recent_events.return_value = [now, now]

    state = _make_state()
    result = working_state_node(state, monitor=mock_monitor, config={
        "working_state": {"window_minutes": 15, "min_event_count": 2}
    })
    assert result["is_working"] is True
    assert len(result["operation_log"]) == 2


def test_working_state_node_inactive():
    """PC操作がない場合、is_working=Falseになること"""
    mock_monitor = MagicMock()
    mock_monitor.is_working.return_value = False
    mock_monitor.get_recent_events.return_value = []

    state = _make_state()
    result = working_state_node(state, monitor=mock_monitor, config={
        "working_state": {"window_minutes": 15, "min_event_count": 2}
    })
    assert result["is_working"] is False
