from graph.state import AttendanceState
from services.pc_monitor import PCMonitor


def working_state_node(
    state: AttendanceState,
    monitor: PCMonitor = None,
    config: dict = None,
) -> dict:
    """PC操作ログを分析し、作業中かどうかを判定するノード"""
    if config is None:
        config = {"working_state": {"window_minutes": 15, "min_event_count": 2}}

    ws_config = config["working_state"]
    window = ws_config["window_minutes"]
    min_count = ws_config["min_event_count"]

    is_working = monitor.is_working(threshold_minutes=window, min_count=min_count)
    recent_events = monitor.get_recent_events(window)

    return {
        "is_working": is_working,
        "operation_log": recent_events,
    }
