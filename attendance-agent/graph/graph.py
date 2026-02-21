# graph/graph.py
from langgraph.graph import StateGraph, END
from graph.state import AttendanceState


def route_after_working_check(state: AttendanceState) -> str:
    if not state["is_working"]:
        return "end"
    return "calendar_check"


def route_after_calendar_check(state: AttendanceState) -> str:
    if state["is_holiday"]:
        return "end"
    return "time_gate"


def route_after_time_gate(state: AttendanceState) -> str:
    if state["action_taken"] == "skipped":
        return "end"
    return "stamp"


def build_graph(
    monitor=None,
    calendar_service=None,
    browser=None,
    notifier=None,
    config=None,
):
    """LangGraphのグラフを構築して返す

    各ノード関数はサービス依存を持つため、functools.partialでラップして
    LangGraphが期待する (state) -> dict シグネチャに合わせる。
    引数を省略した場合はプレースホルダーラッパーを使用する（テスト用）。
    """
    from functools import partial
    from graph.nodes.working_state_node import working_state_node
    from graph.nodes.calendar_check_node import calendar_check_node
    from graph.nodes.time_gate_node import time_gate_node
    from graph.nodes.stamp_node import stamp_node
    from graph.nodes.slack_notify_node import slack_notify_node
    from graph.nodes.state_update_node import state_update_node

    # ノード関数をLangGraph互換の (state) -> dict にラップ
    working_state_wrapped = partial(
        working_state_node, monitor=monitor, config=config
    )
    calendar_check_wrapped = partial(
        calendar_check_node, calendar_service=calendar_service
    )
    time_gate_wrapped = partial(time_gate_node, config=config)
    stamp_wrapped = partial(stamp_node, browser=browser)
    slack_notify_wrapped = partial(slack_notify_node, notifier=notifier)

    workflow = StateGraph(AttendanceState)

    workflow.add_node("working_state", working_state_wrapped)
    workflow.add_node("calendar_check", calendar_check_wrapped)
    workflow.add_node("time_gate", time_gate_wrapped)
    workflow.add_node("stamp", stamp_wrapped)
    workflow.add_node("slack_notify", slack_notify_wrapped)
    workflow.add_node("state_update", state_update_node)

    workflow.set_entry_point("working_state")

    workflow.add_conditional_edges(
        "working_state",
        route_after_working_check,
        {"calendar_check": "calendar_check", "end": END},
    )
    workflow.add_conditional_edges(
        "calendar_check",
        route_after_calendar_check,
        {"time_gate": "time_gate", "end": END},
    )
    workflow.add_conditional_edges(
        "time_gate",
        route_after_time_gate,
        {"stamp": "stamp", "end": END},
    )

    workflow.add_edge("stamp", "slack_notify")
    workflow.add_edge("slack_notify", "state_update")
    workflow.add_edge("state_update", END)

    return workflow.compile()
