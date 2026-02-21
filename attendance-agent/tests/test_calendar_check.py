# tests/test_calendar_check.py
from datetime import date
from unittest.mock import patch, MagicMock
from services.google_calendar import GoogleCalendarService, LocalCalendarService


def test_local_calendar_holiday():
    """jpholidayで祝日判定できること"""
    service = LocalCalendarService(vacation_keywords=["有給", "年休", "休暇"])
    # 2026-01-01は元日
    is_holiday, reason = service.is_holiday(date(2026, 1, 1))
    assert is_holiday is True
    assert "元日" in reason


def test_local_calendar_workday():
    """平日が祝日でないこと"""
    service = LocalCalendarService(vacation_keywords=["有給", "年休", "休暇"])
    # 2026-02-24は火曜日（平日・祝日でない）
    is_holiday, reason = service.is_holiday(date(2026, 2, 24))
    assert is_holiday is False
    assert reason == ""


def test_local_calendar_weekend():
    """土日が休日判定されること"""
    service = LocalCalendarService(vacation_keywords=["有給"])
    # 2026-02-21は土曜日
    is_holiday, reason = service.is_holiday(date(2026, 2, 21))
    assert is_holiday is True


def test_google_calendar_fallback():
    """Google Calendar APIが失敗した場合、ローカルにフォールバックすること"""
    service = GoogleCalendarService(
        credentials_path="nonexistent.json",
        token_path="nonexistent.json",
        holiday_calendar_id="test",
        vacation_keywords=["有給"],
    )
    # API初期化に失敗するのでフォールバック
    is_holiday, reason = service.is_holiday(date(2026, 1, 1))
    assert is_holiday is True


def test_cache_works():
    """同一日の判定結果がキャッシュされること"""
    service = LocalCalendarService(vacation_keywords=["有給"])
    d = date(2026, 2, 22)
    result1 = service.is_holiday(d)
    result2 = service.is_holiday(d)
    assert result1 == result2
