from graph.state import AttendanceState


MESSAGES = {
    "clock_in": "✅ 出勤打刻しました（{time}）",
    "clock_out": "🕐 退勤打刻を更新しました（{time}）",
    "clock_in_and_out": "✅ 出勤（{in_time}）・退勤（{out_time}）を打刻しました",
}


def slack_notify_node(state: AttendanceState, notifier=None) -> dict:
    """打刻結果をSlackに通知するノード"""
    action = state["action_taken"]

    if action == "error":
        notifier.send_error(state["error_message"])
        return {}

    if action == "skipped":
        return {}

    if action == "clock_in":
        msg = MESSAGES["clock_in"].format(time=state["clock_in_time"])
        notifier.send(msg)
    elif action == "clock_out":
        msg = MESSAGES["clock_out"].format(time=state["last_clock_out_time"])
        notifier.send(msg)
    elif action == "clock_in_and_out":
        msg = MESSAGES["clock_in_and_out"].format(
            in_time=state["clock_in_time"],
            out_time=state["last_clock_out_time"],
        )
        notifier.send(msg)

    return {}
