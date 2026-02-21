import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from pathlib import Path


@dataclass
class StampResult:
    success: bool
    timestamp: str
    error: Optional[str]


class AttendanceBrowser:
    """Playwrightで社内勤怠システムにアクセスし打刻する"""

    def __init__(self, url: str, user: str, password: str, config: dict):
        self._url = url
        self._user = user
        self._password = password
        self._config = config["browser"]
        self._selectors = self._config["selectors"]
        self._playwright = None
        self._browser = None
        self._context = None

    async def _get_page(self):
        """ブラウザページを取得（セッション再利用）"""
        if self._browser is None:
            from playwright.async_api import async_playwright

            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=self._config["headless"]
            )

            storage_path = Path(self._config["session_storage_path"])
            if storage_path.exists():
                self._context = await self._browser.new_context(
                    storage_state=str(storage_path)
                )
            else:
                self._context = await self._browser.new_context()

        page = await self._context.new_page()
        return page

    async def _save_session(self):
        """セッション状態を保存"""
        if self._context:
            storage_path = self._config["session_storage_path"]
            Path(storage_path).parent.mkdir(parents=True, exist_ok=True)
            await self._context.storage_state(path=storage_path)

    async def ensure_logged_in(self, page) -> bool:
        """ログイン状態を確認し、必要ならログインする"""
        try:
            await page.goto(self._url)
            await page.wait_for_load_state("networkidle")
            if "login" in page.url.lower():
                await page.fill(self._selectors["username_field"], self._user)
                await page.fill(self._selectors["password_field"], self._password)
                await page.click(self._selectors["login_button"])
                await page.wait_for_load_state("networkidle")
                await self._save_session()
            return True
        except Exception:
            return False

    async def clock_in(self) -> StampResult:
        """出勤打刻"""
        return await self._stamp(self._selectors["clock_in_button"], "clock_in")

    async def clock_out(self) -> StampResult:
        """退勤打刻"""
        return await self._stamp(self._selectors["clock_out_button"], "clock_out")

    async def _stamp(self, button_selector: str, action: str) -> StampResult:
        """打刻実行（リトライ付き）"""
        retry_count = self._config["retry_count"]
        last_error = None

        for attempt in range(retry_count):
            page = None
            try:
                page = await self._get_page()
                await self.ensure_logged_in(page)
                await page.click(button_selector)
                await page.wait_for_load_state("networkidle")

                success_el = await page.query_selector(
                    self._selectors["success_message"]
                )
                if success_el:
                    timestamp = datetime.now().strftime("%H:%M")
                    await self._save_session()
                    return StampResult(success=True, timestamp=timestamp, error=None)
                else:
                    last_error = "打刻確認メッセージが見つかりません"
            except Exception as e:
                last_error = str(e)
            finally:
                if page:
                    await page.close()

        return StampResult(success=False, timestamp="", error=last_error)

    async def close(self):
        """ブラウザを閉じる"""
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
