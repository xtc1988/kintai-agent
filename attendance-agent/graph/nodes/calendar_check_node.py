# graph/nodes/calendar_check_node.py
from datetime import date
from graph.state import AttendanceState


def calendar_check_node(
    state: AttendanceState,
    calendar_service=None,
) -> dict:
    """今日が打刻対象日かをカレンダーで確認するノード"""
    today = date.fromisoformat(state["today"])
    is_holiday, reason = calendar_service.is_holiday(today)

    return {
        "is_holiday": is_holiday,
        "holiday_reason": reason if is_holiday else None,
    }
