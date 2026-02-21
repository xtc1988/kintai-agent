import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from services.attendance_browser import AttendanceBrowser, StampResult


def test_stamp_result_success():
    """StampResultが正しく生成できること"""
    result = StampResult(success=True, timestamp="09:00", error=None)
    assert result.success is True
    assert result.timestamp == "09:00"
    assert result.error is None


def test_stamp_result_failure():
    """失敗時のStampResultが正しく生成できること"""
    result = StampResult(success=False, timestamp="", error="タイムアウト")
    assert result.success is False
    assert result.error == "タイムアウト"


@pytest.mark.asyncio
async def test_clock_in_success():
    """出勤打刻が成功すること（モック）"""
    config = {
        "browser": {
            "headless": True,
            "retry_count": 1,
            "session_storage_path": ".session",
            "selectors": {
                "login_url": "https://example.com/login",
                "username_field": "#username",
                "password_field": "#password",
                "login_button": "#login-btn",
                "clock_in_button": "#clock-in",
                "clock_out_button": "#clock-out",
                "success_message": ".success-msg",
            },
        }
    }
    browser = AttendanceBrowser(
        url="https://example.com",
        user="test",
        password="test",
        config=config,
    )

    mock_page = AsyncMock()
    mock_page.query_selector.return_value = MagicMock()  # success element found
    mock_page.inner_text = AsyncMock(return_value="打刻完了")

    with patch.object(browser, "_get_page", return_value=mock_page):
        result = await browser.clock_in()

    assert result.success is True


@pytest.mark.asyncio
async def test_clock_in_retry_on_failure():
    """打刻失敗時にリトライすること"""
    config = {
        "browser": {
            "headless": True,
            "retry_count": 2,
            "session_storage_path": ".session",
            "selectors": {
                "login_url": "https://example.com/login",
                "username_field": "#username",
                "password_field": "#password",
                "login_button": "#login-btn",
                "clock_in_button": "#clock-in",
                "clock_out_button": "#clock-out",
                "success_message": ".success-msg",
            },
        }
    }
    browser = AttendanceBrowser(
        url="https://example.com",
        user="test",
        password="test",
        config=config,
    )

    mock_page = AsyncMock()
    mock_page.query_selector.return_value = None  # success要素なし → 失敗
    mock_page.click = AsyncMock(side_effect=Exception("要素が見つかりません"))

    with patch.object(browser, "_get_page", return_value=mock_page):
        result = await browser.clock_in()

    assert result.success is False
    assert result.error is not None
