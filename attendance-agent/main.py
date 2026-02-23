"""勤怠管理エージェント - エントリーポイント"""
import asyncio
import signal
import sys
import time
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
import os

from services.config_loader import load_config
from services.pc_monitor import PCMonitor
from services.google_calendar import GoogleCalendarService, LocalCalendarService
from services.slack_client import SlackNotifier, ConsoleNotifier
from graph.nodes.working_state_node import working_state_node
from graph.nodes.calendar_check_node import calendar_check_node
from graph.nodes.time_gate_node import time_gate_node
from graph.nodes.stamp_node import stamp_node
from graph.nodes.slack_notify_node import slack_notify_node
from graph.nodes.state_update_node import state_update_node
from schedulers.scheduler import AttendanceScheduler


# グローバル状態保持用
_state_store = {
    "clock_in_done": False,
    "clock_in_time": None,
    "last_clock_out_time": None,
    "last_date": "",
}


def create_services(config: dict):
    """設定に基づいてサービスインスタンスを生成"""
    load_dotenv()

    # PC監視
    monitor = PCMonitor()

    # カレンダーサービス
    cal_config = config["calendar"]
    if cal_config["enabled"] and cal_config.get("fallback") != "jpholiday":
        calendar_service = GoogleCalendarService(
            credentials_path=os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json"),
            token_path=os.getenv("GOOGLE_TOKEN_PATH", "token.json"),
            holiday_calendar_id=os.getenv(
                "HOLIDAY_CALENDAR_ID", cal_config["holiday_calendar_id"]
            ),
            vacation_keywords=cal_config["vacation_keywords"],
        )
    else:
        calendar_service = LocalCalendarService(
            vacation_keywords=cal_config["vacation_keywords"]
        )

    # Slack通知
    slack_config = config["slack"]
    slack_token = os.getenv("SLACK_BOT_TOKEN", "")
    slack_channel = os.getenv("SLACK_NOTIFY_CHANNEL", slack_config.get("notify_channel", ""))
    if slack_config["enabled"] and slack_token:
        notifier = SlackNotifier(token=slack_token, channel=slack_channel)
    else:
        notifier = ConsoleNotifier()

    # 打刻サービス
    browser_config = config["browser"]
    stamper_type = browser_config.get("stamper", "dummy")

    if stamper_type == "playwright":
        from services.attendance_browser import AttendanceBrowser
        stamper = AttendanceBrowser(
            url=os.getenv("ATTENDANCE_URL", ""),
            user=os.getenv("ATTENDANCE_USER", ""),
            password=os.getenv("ATTENDANCE_PASS", ""),
            config=config,
        )
    else:
        from services.dummy_stamper import DummyStamper
        stamper = DummyStamper()

    return monitor, calendar_service, notifier, stamper


def run_check(monitor, calendar_service, notifier, stamper, config):
    """1回分のチェックを実行"""
    today_str = date.today().isoformat()

    # 日付リセット
    if today_str != _state_store["last_date"]:
        _state_store["clock_in_done"] = False
        _state_store["clock_in_time"] = None
        _state_store["last_clock_out_time"] = None
        _state_store["last_date"] = today_str

    # 初期状態
    state = {
        "today": today_str,
        "is_holiday": False,
        "holiday_reason": None,
        "clock_in_done": _state_store["clock_in_done"],
        "clock_in_time": _state_store["clock_in_time"],
        "last_clock_out_time": _state_store["last_clock_out_time"],
        "is_working": False,
        "operation_log": [],
        "action_taken": None,
        "error_message": None,
        "extra": {},
    }

    # 1. WorkingState
    ws_result = working_state_node(state, monitor=monitor, config=config)
    state.update(ws_result)

    if not state["is_working"]:
        return

    # 2. CalendarCheck
    cal_result = calendar_check_node(state, calendar_service=calendar_service)
    state.update(cal_result)

    if state["is_holiday"]:
        return

    # 3. TimeGate
    tg_result = time_gate_node(state, config=config)
    state.update(tg_result)

    if state["action_taken"] == "skipped":
        return

    # 4. Stamp
    stamp_result = asyncio.run(stamp_node(state, browser=stamper))
    state.update(stamp_result)

    # 5. SlackNotify
    slack_notify_node(state, notifier=notifier)

    # 6. StateUpdate
    su_result = state_update_node(state)
    state.update(su_result)

    # 状態保持
    _state_store["clock_in_done"] = state.get("clock_in_done", False)
    _state_store["clock_in_time"] = state.get("clock_in_time")
    _state_store["last_clock_out_time"] = state.get("last_clock_out_time")


def main():
    """メイン起動処理"""
    config = load_config("config.yaml")
    monitor, calendar_service, notifier, stamper = create_services(config)

    # PC監視開始
    monitor.start()
    print("[勤怠エージェント] PC監視を開始しました")

    # スケジューラ設定
    interval = config["scheduler"]["check_interval_minutes"]

    def check_job():
        try:
            run_check(monitor, calendar_service, notifier, stamper, config)
        except Exception as e:
            print(f"[勤怠エージェント] チェック中にエラー: {e}")
            notifier.send_error(str(e))

    scheduler = AttendanceScheduler(interval_minutes=interval, job_func=check_job)
    scheduler.start()
    print(f"[勤怠エージェント] {interval}分間隔でチェックを開始します")

    # シグナルハンドリング
    def shutdown(signum, frame):
        print("\n[勤怠エージェント] 停止中...")
        scheduler.stop()
        monitor.stop()
        asyncio.run(stamper.close())
        print("[勤怠エージェント] 停止しました")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # メインループ
    print("[勤怠エージェント] Ctrl+Cで停止します")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        shutdown(None, None)


if __name__ == "__main__":
    main()
