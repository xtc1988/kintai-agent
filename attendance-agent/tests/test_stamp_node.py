import pytest
from unittest.mock import AsyncMock
from services.stamper_interface import StampResult
from graph.nodes.stamp_node import stamp_node


def _make_state(**overrides):
    base = {
        "today": "2026-02-22",
        "is_holiday": False,
        "holiday_reason": None,
        "clock_in_done": False,
        "clock_in_time": None,
        "last_clock_out_time": None,
        "is_working": True,
        "operation_log": [],
        "action_taken": "clock_in",
        "error_message": None,
        "extra": {},
    }
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_stamp_clock_in_success():
    """出勤打刻が成功した場合の状態更新"""
    mock_browser = AsyncMock()
    mock_browser.clock_in.return_value = StampResult(
        success=True, timestamp="09:12", error=None
    )

    state = _make_state(action_taken="clock_in")
    result = await stamp_node(state, browser=mock_browser)

    assert result["clock_in_done"] is True
    assert result["clock_in_time"] == "09:12"
    assert result["action_taken"] == "clock_in"
    assert result["error_message"] is None


@pytest.mark.asyncio
async def test_stamp_clock_out_success():
    """退勤打刻が成功した場合の状態更新"""
    mock_browser = AsyncMock()
    mock_browser.clock_out.return_value = StampResult(
        success=True, timestamp="18:05", error=None
    )

    state = _make_state(action_taken="clock_out", clock_in_done=True)
    result = await stamp_node(state, browser=mock_browser)

    assert result["last_clock_out_time"] == "18:05"
    assert result["action_taken"] == "clock_out"


@pytest.mark.asyncio
async def test_stamp_failure():
    """打刻失敗時のエラー状態"""
    mock_browser = AsyncMock()
    mock_browser.clock_in.return_value = StampResult(
        success=False, timestamp="", error="タイムアウト"
    )

    state = _make_state(action_taken="clock_in")
    result = await stamp_node(state, browser=mock_browser)

    assert result["action_taken"] == "error"
    assert result["error_message"] == "タイムアウト"


@pytest.mark.asyncio
async def test_stamp_clock_in_and_out():
    """出勤+退勤の両方を実行"""
    mock_browser = AsyncMock()
    mock_browser.clock_in.return_value = StampResult(
        success=True, timestamp="19:00", error=None
    )
    mock_browser.clock_out.return_value = StampResult(
        success=True, timestamp="19:01", error=None
    )

    state = _make_state(action_taken="clock_in_and_out")
    result = await stamp_node(state, browser=mock_browser)

    assert result["clock_in_done"] is True
    assert result["clock_in_time"] == "19:00"
    assert result["last_clock_out_time"] == "19:01"
