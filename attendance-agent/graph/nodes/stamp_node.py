from graph.state import AttendanceState
from services.stamper_interface import StamperInterface


async def stamp_node(state: AttendanceState, browser: StamperInterface = None) -> dict:
    """Playwrightで打刻を実行するノード"""
    action = state["action_taken"]

    if action == "clock_in":
        result = await browser.clock_in()
        if result.success:
            return {
                "clock_in_done": True,
                "clock_in_time": result.timestamp,
                "action_taken": "clock_in",
                "error_message": None,
            }
        else:
            return {"action_taken": "error", "error_message": result.error}

    elif action == "clock_out":
        result = await browser.clock_out()
        if result.success:
            return {
                "last_clock_out_time": result.timestamp,
                "action_taken": "clock_out",
                "error_message": None,
            }
        else:
            return {"action_taken": "error", "error_message": result.error}

    elif action == "clock_in_and_out":
        in_result = await browser.clock_in()
        if not in_result.success:
            return {
                "action_taken": "error",
                "error_message": f"出勤打刻失敗: {in_result.error}",
            }

        out_result = await browser.clock_out()
        if not out_result.success:
            return {
                "clock_in_done": True,
                "clock_in_time": in_result.timestamp,
                "action_taken": "error",
                "error_message": f"退勤打刻失敗: {out_result.error}",
            }

        return {
            "clock_in_done": True,
            "clock_in_time": in_result.timestamp,
            "last_clock_out_time": out_result.timestamp,
            "action_taken": "clock_in_and_out",
            "error_message": None,
        }

    return {"action_taken": "skipped"}
