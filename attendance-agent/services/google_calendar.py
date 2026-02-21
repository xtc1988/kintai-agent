# services/google_calendar.py
from datetime import date, datetime
from typing import Optional
import jpholiday


class LocalCalendarService:
    """ローカル祝日データ(jpholiday)による判定サービス"""

    def __init__(self, vacation_keywords: list[str] = None):
        self._vacation_keywords = vacation_keywords or ["有給", "年休", "休暇"]
        self._cache: dict[date, tuple[bool, str]] = {}

    def is_holiday(self, target_date: date = None) -> tuple[bool, str]:
        """指定日が祝日かどうかを判定する"""
        if target_date is None:
            target_date = date.today()

        if target_date in self._cache:
            return self._cache[target_date]

        # 土日チェック
        if target_date.weekday() >= 5:
            day_name = "土曜日" if target_date.weekday() == 5 else "日曜日"
            result = (True, day_name)
            self._cache[target_date] = result
            return result

        # 祝日チェック
        holiday_name = jpholiday.is_holiday_name(target_date)
        if holiday_name:
            result = (True, holiday_name)
            self._cache[target_date] = result
            return result

        result = (False, "")
        self._cache[target_date] = result
        return result

    def get_today_events(self) -> list[dict]:
        return []


class GoogleCalendarService:
    """Google Calendar APIによる祝日・有給判定サービス（フォールバック付き）"""

    def __init__(
        self,
        credentials_path: str = "credentials.json",
        token_path: str = "token.json",
        holiday_calendar_id: str = "",
        vacation_keywords: list[str] = None,
    ):
        self._credentials_path = credentials_path
        self._token_path = token_path
        self._holiday_calendar_id = holiday_calendar_id
        self._vacation_keywords = vacation_keywords or ["有給", "年休", "休暇"]
        self._cache: dict[date, tuple[bool, str]] = {}
        self._service = None
        self._fallback = LocalCalendarService(self._vacation_keywords)
        self._init_api()

    def _init_api(self):
        """Google Calendar APIを初期化（失敗時はフォールバックモード）"""
        try:
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from google.auth.transport.requests import Request
            from googleapiclient.discovery import build
            import os

            SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
            creds = None

            if os.path.exists(self._token_path):
                creds = Credentials.from_authorized_user_file(self._token_path, SCOPES)

            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    if not os.path.exists(self._credentials_path):
                        return  # フォールバックモード
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self._credentials_path, SCOPES
                    )
                    creds = flow.run_local_server(port=0)

                with open(self._token_path, "w") as token:
                    token.write(creds.to_json())

            self._service = build("calendar", "v3", credentials=creds)
        except Exception:
            self._service = None  # フォールバックモード

    def is_holiday(self, target_date: date = None) -> tuple[bool, str]:
        """祝日・有給判定（API失敗時はローカルフォールバック）"""
        if target_date is None:
            target_date = date.today()

        if target_date in self._cache:
            return self._cache[target_date]

        # まずローカル祝日チェック
        local_result = self._fallback.is_holiday(target_date)
        if local_result[0]:
            self._cache[target_date] = local_result
            return local_result

        # Google Calendar APIで有給チェック
        if self._service:
            try:
                result = self._check_google_calendar(target_date)
                if result[0]:
                    self._cache[target_date] = result
                    return result
            except Exception:
                pass

        result = (False, "")
        self._cache[target_date] = result
        return result

    def _check_google_calendar(self, target_date: date) -> tuple[bool, str]:
        """Google Calendar APIで個人カレンダーの有給イベントをチェック"""
        start = datetime.combine(target_date, datetime.min.time()).isoformat() + "Z"
        end = datetime.combine(target_date, datetime.max.time()).isoformat() + "Z"

        events_result = (
            self._service.events()
            .list(calendarId="primary", timeMin=start, timeMax=end, singleEvents=True)
            .execute()
        )

        for event in events_result.get("items", []):
            summary = event.get("summary", "")
            for keyword in self._vacation_keywords:
                if keyword in summary:
                    return (True, summary)

        return (False, "")

    def get_today_events(self) -> list[dict]:
        if not self._service:
            return []
        try:
            target = date.today()
            start = datetime.combine(target, datetime.min.time()).isoformat() + "Z"
            end = datetime.combine(target, datetime.max.time()).isoformat() + "Z"
            result = (
                self._service.events()
                .list(calendarId="primary", timeMin=start, timeMax=end, singleEvents=True)
                .execute()
            )
            return result.get("items", [])
        except Exception:
            return []
