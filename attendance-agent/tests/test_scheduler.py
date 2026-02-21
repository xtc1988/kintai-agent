# tests/test_scheduler.py
from unittest.mock import MagicMock, patch
from schedulers.scheduler import AttendanceScheduler


def test_scheduler_creation():
    """スケジューラが正しく生成されること"""
    scheduler = AttendanceScheduler(
        interval_minutes=5,
        job_func=MagicMock(),
    )
    assert scheduler._interval == 5


def test_scheduler_start_stop():
    """スケジューラの開始・停止"""
    mock_func = MagicMock()
    scheduler = AttendanceScheduler(interval_minutes=5, job_func=mock_func)

    with patch.object(scheduler._scheduler, "start") as mock_start:
        scheduler.start()
        mock_start.assert_called_once()

    with patch.object(scheduler._scheduler, "shutdown") as mock_shutdown:
        scheduler.stop()
        mock_shutdown.assert_called_once()
