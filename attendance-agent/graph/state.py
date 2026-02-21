from typing import TypedDict, Optional
from datetime import datetime


class AttendanceState(TypedDict):
    today: str                          # YYYY-MM-DD
    is_holiday: bool                    # 祝日・有給フラグ
    holiday_reason: Optional[str]       # 理由
    clock_in_done: bool                 # 出勤打刻済み
    clock_in_time: Optional[str]        # 出勤打刻時刻 HH:MM
    last_clock_out_time: Optional[str]  # 最終退勤打刻時刻 HH:MM
    is_working: bool                    # 現在作業中か
    operation_log: list[datetime]       # 直近の操作イベントリスト
    action_taken: Optional[str]         # "clock_in" / "clock_out" / "skipped" / "error"
    error_message: Optional[str]        # エラー詳細
    extra: dict                         # 任意の追加データ
