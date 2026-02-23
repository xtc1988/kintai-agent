from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class StampResult:
    success: bool
    timestamp: str
    error: Optional[str]


class StamperInterface(ABC):
    """打刻サービスの抽象インターフェース"""

    @abstractmethod
    async def clock_in(self) -> StampResult:
        """出勤打刻"""
        ...

    @abstractmethod
    async def clock_out(self) -> StampResult:
        """退勤打刻"""
        ...

    @abstractmethod
    async def close(self) -> None:
        """リソース解放"""
        ...
