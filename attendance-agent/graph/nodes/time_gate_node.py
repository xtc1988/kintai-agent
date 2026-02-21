# graph/nodes/time_gate_node.py
from datetime import datetime, time
from graph.state import AttendanceState


def _now() -> datetime:
    """テスト時にモック可能な現在時刻取得"""
    return datetime.now()


def _parse_time(time_str: str) -> time:
    """HH:MM形式の文字列をtimeオブジェクトに変換"""
    h, m = map(int, time_str.split(":"))
    return time(h, m)


def time_gate_node(state: AttendanceState, config: dict = None) -> dict:
    """時刻に応じて打刻種別（出勤/退勤/スキップ）を決定するノード"""
    if config is None:
        config = {"time_rules": {"clock_out_time": "18:00", "cutoff_time": "22:00"}}

    rules = config["time_rules"]
    clock_out_time = _parse_time(rules["clock_out_time"])
    cutoff_time = _parse_time(rules["cutoff_time"])

    now = _now()
    current_time = now.time()

    # 22:00以降 → スキップ（打刻禁止）
    if current_time >= cutoff_time:
        return {"action_taken": "skipped"}

    clock_in_done = state["clock_in_done"]

    # 18:00〜22:00
    if current_time >= clock_out_time:
        if clock_in_done:
            return {"action_taken": "clock_out"}
        else:
            return {"action_taken": "clock_in_and_out"}

    # 〜18:00
    if not clock_in_done:
        return {"action_taken": "clock_in"}
    else:
        return {"action_taken": "skipped"}
