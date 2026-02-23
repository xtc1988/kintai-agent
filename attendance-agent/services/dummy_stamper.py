from datetime import datetime
from services.stamper_interface import StamperInterface, StampResult


class DummyStamper(StamperInterface):
    """ダミー打刻（ログ出力のみ）。Playwright実装が準備できるまでの仮実装。"""

    async def clock_in(self) -> StampResult:
        timestamp = datetime.now().strftime("%H:%M")
        print(f"[DummyStamper] 出勤打刻（シミュレーション）: {timestamp}")
        return StampResult(success=True, timestamp=timestamp, error=None)

    async def clock_out(self) -> StampResult:
        timestamp = datetime.now().strftime("%H:%M")
        print(f"[DummyStamper] 退勤打刻（シミュレーション）: {timestamp}")
        return StampResult(success=True, timestamp=timestamp, error=None)

    async def close(self) -> None:
        pass
