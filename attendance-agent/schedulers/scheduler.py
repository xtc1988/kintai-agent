# schedulers/scheduler.py
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from typing import Callable


class AttendanceScheduler:
    """APSchedulerによる定期実行管理"""

    def __init__(self, interval_minutes: int, job_func: Callable):
        self._interval = interval_minutes
        self._job_func = job_func
        self._scheduler = BackgroundScheduler()
        self._scheduler.add_job(
            self._job_func,
            trigger=IntervalTrigger(minutes=self._interval),
            id="attendance_check",
            replace_existing=True,
        )

    def start(self):
        """スケジューラ開始"""
        self._scheduler.start()

    def stop(self):
        """スケジューラ停止"""
        self._scheduler.shutdown(wait=False)
