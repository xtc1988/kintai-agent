# graph/nodes/state_update_node.py
from datetime import date
from graph.state import AttendanceState


def _today_str() -> str:
    """テスト時にモック可能"""
    return date.today().isoformat()


def state_update_node(state: AttendanceState) -> dict:
    """打刻後の状態を更新し、日付跨ぎでリセットするノード"""
    today = _today_str()

    # 日付が変わったらリセット
    if state["today"] != today:
        return {
            "today": today,
            "is_holiday": False,
            "holiday_reason": None,
            "clock_in_done": False,
            "clock_in_time": None,
            "last_clock_out_time": None,
            "is_working": False,
            "operation_log": [],
            "action_taken": None,
            "error_message": None,
        }

    # 同日: エラーをクリアして状態を維持
    return {
        "today": today,
        "clock_in_done": state["clock_in_done"],
        "clock_in_time": state["clock_in_time"],
        "last_clock_out_time": state["last_clock_out_time"],
        "error_message": None,
    }
