# 勤怠管理エージェント 実装計画

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** PC稼働状況を監視し、社内勤怠システムへの打刻漏れを自動防止するLangGraphエージェントを構築する。

**Architecture:** LangGraphのステートマシンで6ノード（WorkingState → CalendarCheck → TimeGate → Stamp → SlackNotify → StateUpdate）を順次実行。各ノードはservices層の実処理を呼び出す。外部サービス（Slack/Google Calendar/勤怠システム）はインターフェース化し、フォールバック実装を持つ。APSchedulerで5分間隔の定期実行。

**Tech Stack:** Python 3.10, LangGraph, pynput, Playwright, APScheduler, PyYAML, python-dotenv, slack-sdk, google-api-python-client, jpholiday, pytest

**仕様書:** `attendance_agent_spec.md` を必ず参照のこと

---

## Task 0: プロジェクト初期化

**Files:**
- Create: `attendance-agent/pyproject.toml`
- Create: `attendance-agent/config.yaml`
- Create: `attendance-agent/.env.example`
- Create: `attendance-agent/.gitignore`
- Create: `attendance-agent/main.py` (空エントリーポイント)
- Create: `attendance-agent/graph/__init__.py`
- Create: `attendance-agent/graph/nodes/__init__.py`
- Create: `attendance-agent/services/__init__.py`
- Create: `attendance-agent/schedulers/__init__.py`
- Create: `attendance-agent/tests/__init__.py`

**Step 1: Gitリポジトリ初期化**

```bash
cd /c/AI/勤怠エージェント
git init
```

**Step 2: pyproject.toml作成**

```toml
[project]
name = "attendance-agent"
version = "0.1.0"
description = "PC稼働監視 + 自動打刻 LangGraphエージェント"
requires-python = ">=3.10"
dependencies = [
    "langgraph>=0.2.0",
    "pynput>=1.7.6",
    "playwright>=1.40.0",
    "apscheduler>=3.10.0",
    "pyyaml>=6.0",
    "python-dotenv>=1.0.0",
    "slack-sdk>=3.27.0",
    "google-api-python-client>=2.100.0",
    "google-auth-oauthlib>=1.2.0",
    "jpholiday>=0.1.8",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23.0",
    "pytest-mock>=3.12.0",
]

[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.backends._legacy:_Backend"
```

**Step 3: config.yaml作成**

仕様書セクション7の通り:

```yaml
scheduler:
  check_interval_minutes: 5

working_state:
  window_minutes: 15
  min_event_count: 2

time_rules:
  clock_out_time: "18:00"
  cutoff_time: "22:00"

browser:
  headless: true
  retry_count: 3
  session_storage_path: ".session"
  # 社内システム固有のセレクタ設定
  selectors:
    login_url: "https://your-system.example.com/login"
    username_field: "#username"
    password_field: "#password"
    login_button: "#login-btn"
    clock_in_button: "#clock-in"
    clock_out_button: "#clock-out"
    success_message: ".success-msg"

slack:
  enabled: true
  notify_channel: "DXXXXXXXX"
  fallback: "console"  # "console" or "toast"

calendar:
  enabled: true
  fallback: "jpholiday"  # "jpholiday" でローカル祝日判定
  holiday_calendar_id: "ja.japanese#holiday@group.v.calendar.google.com"
  vacation_keywords:
    - "有給"
    - "年休"
    - "休暇"
```

**Step 4: .env.example作成**

```
# 勤怠システム
ATTENDANCE_URL=https://your-system.example.com
ATTENDANCE_USER=your_user_id
ATTENDANCE_PASS=your_password

# Slack
SLACK_BOT_TOKEN=xoxb-...
SLACK_NOTIFY_CHANNEL=DXXXXXXXX

# Google Calendar
GOOGLE_CREDENTIALS_PATH=credentials.json
GOOGLE_TOKEN_PATH=token.json
HOLIDAY_CALENDAR_ID=ja.japanese#holiday@group.v.calendar.google.com
```

**Step 5: .gitignore作成**

```
__pycache__/
*.pyc
.env
.session/
token.json
credentials.json
*.egg-info/
dist/
.venv/
```

**Step 6: ディレクトリ構造作成**

```bash
mkdir -p attendance-agent/{graph/nodes,services,schedulers,tests}
touch attendance-agent/graph/__init__.py
touch attendance-agent/graph/nodes/__init__.py
touch attendance-agent/services/__init__.py
touch attendance-agent/schedulers/__init__.py
touch attendance-agent/tests/__init__.py
touch attendance-agent/main.py
```

**Step 7: 依存関係インストール**

```bash
cd attendance-agent
pip install -e ".[dev]"
playwright install chromium
```

**Step 8: 初回コミット**

```bash
git add -A
git commit -m "chore: プロジェクト初期化 - ディレクトリ構造・設定ファイル"
```

---

## Task 1: AgentState型定義

**Files:**
- Create: `attendance-agent/graph/state.py`
- Test: `attendance-agent/tests/test_state.py`

**Step 1: テスト作成**

```python
# tests/test_state.py
from graph.state import AttendanceState
from datetime import datetime


def test_attendance_state_creation():
    """AttendanceStateが正しいキーで生成できること"""
    state: AttendanceState = {
        "today": "2026-02-22",
        "is_holiday": False,
        "holiday_reason": None,
        "clock_in_done": False,
        "clock_in_time": None,
        "last_clock_out_time": None,
        "is_working": False,
        "operation_log": [],
        "action_taken": None,
        "error_message": None,
        "extra": {},
    }
    assert state["today"] == "2026-02-22"
    assert state["is_holiday"] is False
    assert state["operation_log"] == []


def test_attendance_state_with_data():
    """操作ログ付きのStateが正しく動作すること"""
    now = datetime.now()
    state: AttendanceState = {
        "today": "2026-02-22",
        "is_holiday": False,
        "holiday_reason": None,
        "clock_in_done": True,
        "clock_in_time": "09:00",
        "last_clock_out_time": None,
        "is_working": True,
        "operation_log": [now],
        "action_taken": "clock_in",
        "error_message": None,
        "extra": {},
    }
    assert state["clock_in_done"] is True
    assert state["clock_in_time"] == "09:00"
    assert len(state["operation_log"]) == 1
```

**Step 2: テスト実行して失敗確認**

```bash
cd attendance-agent
python -m pytest tests/test_state.py -v
```
Expected: FAIL - `ModuleNotFoundError: No module named 'graph.state'`

**Step 3: 実装**

```python
# graph/state.py
from typing import TypedDict, Optional
from datetime import datetime


class AttendanceState(TypedDict):
    # 日付
    today: str                          # YYYY-MM-DD

    # カレンダー判定
    is_holiday: bool                    # 祝日・有給フラグ
    holiday_reason: Optional[str]       # 理由（例: "山の日", "有給"）

    # 打刻状態
    clock_in_done: bool                 # 出勤打刻済み
    clock_in_time: Optional[str]        # 出勤打刻時刻 HH:MM
    last_clock_out_time: Optional[str]  # 最終退勤打刻時刻 HH:MM

    # PC稼働状態
    is_working: bool                    # 現在作業中か
    operation_log: list[datetime]       # 直近の操作イベントリスト

    # 実行結果
    action_taken: Optional[str]         # "clock_in" / "clock_out" / "skipped" / "error"
    error_message: Optional[str]        # エラー詳細

    # 拡張用
    extra: dict                         # 任意の追加データ
```

**Step 4: テスト実行してパス確認**

```bash
python -m pytest tests/test_state.py -v
```
Expected: 2 passed

**Step 5: コミット**

```bash
git add graph/state.py tests/test_state.py
git commit -m "feat: AttendanceState型定義を追加"
```

---

## Task 2: PC操作監視サービス (pc_monitor.py)

**Files:**
- Create: `attendance-agent/services/pc_monitor.py`
- Test: `attendance-agent/tests/test_pc_monitor.py`

**Step 1: テスト作成**

```python
# tests/test_pc_monitor.py
import time
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from services.pc_monitor import PCMonitor


def test_initial_state():
    """初期状態ではイベントが空であること"""
    monitor = PCMonitor()
    assert monitor.get_recent_events(15) == []
    assert monitor.is_working(threshold_minutes=15, min_count=2) is False


def test_record_event():
    """イベント記録後に取得できること"""
    monitor = PCMonitor()
    monitor._record_event()
    events = monitor.get_recent_events(15)
    assert len(events) == 1


def test_is_working_true():
    """閾値以上のイベントでis_working=Trueになること"""
    monitor = PCMonitor()
    monitor._record_event()
    monitor._record_event()
    monitor._record_event()
    assert monitor.is_working(threshold_minutes=15, min_count=2) is True


def test_is_working_false_too_few_events():
    """イベント数が閾値未満でis_working=Falseになること"""
    monitor = PCMonitor()
    monitor._record_event()
    assert monitor.is_working(threshold_minutes=15, min_count=2) is False


def test_old_events_purged():
    """古いイベントがパージされること"""
    monitor = PCMonitor()
    old_time = datetime.now() - timedelta(minutes=20)
    monitor._events.append(old_time)
    monitor._record_event()  # 現在のイベント追加
    events = monitor.get_recent_events(15)
    assert len(events) == 1  # 古いものはフィルタされる


def test_start_stop():
    """start/stopでリスナーが開始・停止されること"""
    monitor = PCMonitor()
    with patch("services.pc_monitor.mouse_listener_cls") as mock_mouse, \
         patch("services.pc_monitor.keyboard_listener_cls") as mock_kb:
        mock_mouse_inst = MagicMock()
        mock_kb_inst = MagicMock()
        mock_mouse.return_value = mock_mouse_inst
        mock_kb.return_value = mock_kb_inst

        monitor.start()
        mock_mouse_inst.start.assert_called_once()
        mock_kb_inst.start.assert_called_once()

        monitor.stop()
        mock_mouse_inst.stop.assert_called_once()
        mock_kb_inst.stop.assert_called_once()
```

**Step 2: テスト失敗確認**

```bash
python -m pytest tests/test_pc_monitor.py -v
```
Expected: FAIL

**Step 3: 実装**

```python
# services/pc_monitor.py
import threading
from datetime import datetime, timedelta
from pynput import mouse, keyboard

# テスト時にモック差し替え可能にするためモジュールレベルで参照
mouse_listener_cls = mouse.Listener
keyboard_listener_cls = keyboard.Listener


class PCMonitor:
    """PC操作（マウス・キーボード）を監視し、稼働状態を判定する"""

    def __init__(self):
        self._events: list[datetime] = []
        self._lock = threading.Lock()
        self._mouse_listener = None
        self._keyboard_listener = None

    def _record_event(self):
        """操作イベントを記録する（重複防止: 1秒以内の連続イベントは無視）"""
        now = datetime.now()
        with self._lock:
            if self._events and (now - self._events[-1]).total_seconds() < 1:
                return
            self._events.append(now)

    def _on_mouse_move(self, x, y):
        self._record_event()

    def _on_key_press(self, key):
        self._record_event()

    def get_recent_events(self, minutes: int) -> list[datetime]:
        """直近N分以内の操作イベントを返す"""
        cutoff = datetime.now() - timedelta(minutes=minutes)
        with self._lock:
            return [e for e in self._events if e > cutoff]

    def is_working(self, threshold_minutes: int, min_count: int) -> bool:
        """直近threshold_minutes分以内にmin_count回以上の操作があれば作業中と判定"""
        recent = self.get_recent_events(threshold_minutes)
        return len(recent) >= min_count

    def purge_old_events(self, minutes: int = 30):
        """古いイベントを削除してメモリを節約"""
        cutoff = datetime.now() - timedelta(minutes=minutes)
        with self._lock:
            self._events = [e for e in self._events if e > cutoff]

    def start(self):
        """マウス・キーボード監視を開始"""
        self._mouse_listener = mouse_listener_cls(on_move=self._on_mouse_move)
        self._keyboard_listener = keyboard_listener_cls(on_press=self._on_key_press)
        self._mouse_listener.start()
        self._keyboard_listener.start()

    def stop(self):
        """監視を停止"""
        if self._mouse_listener:
            self._mouse_listener.stop()
        if self._keyboard_listener:
            self._keyboard_listener.stop()
```

**Step 4: テスト実行**

```bash
python -m pytest tests/test_pc_monitor.py -v
```
Expected: 6 passed

**Step 5: コミット**

```bash
git add services/pc_monitor.py tests/test_pc_monitor.py
git commit -m "feat: PC操作監視サービス(PCMonitor)を追加"
```

---

## Task 3: 設定ローダー

**Files:**
- Create: `attendance-agent/services/config_loader.py`
- Test: `attendance-agent/tests/test_config_loader.py`

**Step 1: テスト作成**

```python
# tests/test_config_loader.py
import os
import tempfile
from services.config_loader import load_config


def test_load_config_defaults():
    """デフォルト設定が正しくロードされること"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("scheduler:\n  check_interval_minutes: 10\n")
        f.flush()
        config = load_config(f.name)
    os.unlink(f.name)
    assert config["scheduler"]["check_interval_minutes"] == 10


def test_load_config_nested():
    """ネストされた設定が正しく取得できること"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(
            "working_state:\n"
            "  window_minutes: 15\n"
            "  min_event_count: 2\n"
        )
        f.flush()
        config = load_config(f.name)
    os.unlink(f.name)
    assert config["working_state"]["window_minutes"] == 15
    assert config["working_state"]["min_event_count"] == 2


def test_load_config_file_not_found():
    """存在しないファイルの場合デフォルト設定を返すこと"""
    config = load_config("nonexistent.yaml")
    assert "scheduler" in config
    assert config["scheduler"]["check_interval_minutes"] == 5
```

**Step 2: テスト失敗確認**

```bash
python -m pytest tests/test_config_loader.py -v
```

**Step 3: 実装**

```python
# services/config_loader.py
import yaml
from pathlib import Path

DEFAULT_CONFIG = {
    "scheduler": {
        "check_interval_minutes": 5,
    },
    "working_state": {
        "window_minutes": 15,
        "min_event_count": 2,
    },
    "time_rules": {
        "clock_out_time": "18:00",
        "cutoff_time": "22:00",
    },
    "browser": {
        "headless": True,
        "retry_count": 3,
        "session_storage_path": ".session",
        "selectors": {
            "login_url": "",
            "username_field": "#username",
            "password_field": "#password",
            "login_button": "#login-btn",
            "clock_in_button": "#clock-in",
            "clock_out_button": "#clock-out",
            "success_message": ".success-msg",
        },
    },
    "slack": {
        "enabled": True,
        "notify_channel": "",
        "fallback": "console",
    },
    "calendar": {
        "enabled": True,
        "fallback": "jpholiday",
        "holiday_calendar_id": "ja.japanese#holiday@group.v.calendar.google.com",
        "vacation_keywords": ["有給", "年休", "休暇"],
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    """ベース設定にオーバーライドをマージする"""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(path: str = "config.yaml") -> dict:
    """YAML設定ファイルをロードし、デフォルト設定とマージして返す"""
    config_path = Path(path)
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            user_config = yaml.safe_load(f) or {}
        return _deep_merge(DEFAULT_CONFIG, user_config)
    return DEFAULT_CONFIG.copy()
```

**Step 4: テストパス確認**

```bash
python -m pytest tests/test_config_loader.py -v
```
Expected: 3 passed

**Step 5: コミット**

```bash
git add services/config_loader.py tests/test_config_loader.py
git commit -m "feat: 設定ローダー(config_loader)を追加"
```

---

## Task 4: WorkingStateNode

**Files:**
- Create: `attendance-agent/graph/nodes/working_state_node.py`
- Test: `attendance-agent/tests/test_working_state.py`

**Step 1: テスト作成**

```python
# tests/test_working_state.py
from datetime import datetime, timedelta
from unittest.mock import MagicMock
from graph.nodes.working_state_node import working_state_node


def _make_state(**overrides):
    base = {
        "today": "2026-02-22",
        "is_holiday": False,
        "holiday_reason": None,
        "clock_in_done": False,
        "clock_in_time": None,
        "last_clock_out_time": None,
        "is_working": False,
        "operation_log": [],
        "action_taken": None,
        "error_message": None,
        "extra": {},
    }
    base.update(overrides)
    return base


def test_working_state_node_active():
    """PC操作が十分にある場合、is_working=Trueになること"""
    mock_monitor = MagicMock()
    now = datetime.now()
    mock_monitor.is_working.return_value = True
    mock_monitor.get_recent_events.return_value = [now, now]

    state = _make_state()
    result = working_state_node(state, monitor=mock_monitor, config={
        "working_state": {"window_minutes": 15, "min_event_count": 2}
    })
    assert result["is_working"] is True
    assert len(result["operation_log"]) == 2


def test_working_state_node_inactive():
    """PC操作がない場合、is_working=Falseになること"""
    mock_monitor = MagicMock()
    mock_monitor.is_working.return_value = False
    mock_monitor.get_recent_events.return_value = []

    state = _make_state()
    result = working_state_node(state, monitor=mock_monitor, config={
        "working_state": {"window_minutes": 15, "min_event_count": 2}
    })
    assert result["is_working"] is False
```

**Step 2: テスト失敗確認**

```bash
python -m pytest tests/test_working_state.py -v
```

**Step 3: 実装**

```python
# graph/nodes/working_state_node.py
from graph.state import AttendanceState
from services.pc_monitor import PCMonitor


def working_state_node(
    state: AttendanceState,
    monitor: PCMonitor = None,
    config: dict = None,
) -> dict:
    """PC操作ログを分析し、作業中かどうかを判定するノード"""
    if config is None:
        config = {"working_state": {"window_minutes": 15, "min_event_count": 2}}

    ws_config = config["working_state"]
    window = ws_config["window_minutes"]
    min_count = ws_config["min_event_count"]

    is_working = monitor.is_working(threshold_minutes=window, min_count=min_count)
    recent_events = monitor.get_recent_events(window)

    return {
        "is_working": is_working,
        "operation_log": recent_events,
    }
```

**Step 4: テストパス確認**

```bash
python -m pytest tests/test_working_state.py -v
```
Expected: 2 passed

**Step 5: コミット**

```bash
git add graph/nodes/working_state_node.py tests/test_working_state.py
git commit -m "feat: WorkingStateNodeを追加"
```

---

## Task 5: カレンダーサービス (google_calendar.py)

**Files:**
- Create: `attendance-agent/services/google_calendar.py`
- Test: `attendance-agent/tests/test_calendar_check.py`

**Step 1: テスト作成**

```python
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
    # 2026-02-23は月曜日（平日）
    is_holiday, reason = service.is_holiday(date(2026, 2, 23))
    assert is_holiday is False
    assert reason == ""


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
```

**Step 2: テスト失敗確認**

```bash
python -m pytest tests/test_calendar_check.py -v
```

**Step 3: 実装**

```python
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
```

**Step 4: テストパス確認**

```bash
python -m pytest tests/test_calendar_check.py -v
```
Expected: 4 passed

**Step 5: コミット**

```bash
git add services/google_calendar.py tests/test_calendar_check.py
git commit -m "feat: カレンダーサービス(Google Calendar + jpholidayフォールバック)を追加"
```

---

## Task 6: CalendarCheckNode

**Files:**
- Create: `attendance-agent/graph/nodes/calendar_check_node.py`
- Test: `attendance-agent/tests/test_calendar_check_node.py`

**Step 1: テスト作成**

```python
# tests/test_calendar_check_node.py
from unittest.mock import MagicMock
from graph.nodes.calendar_check_node import calendar_check_node


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
        "action_taken": None,
        "error_message": None,
        "extra": {},
    }
    base.update(overrides)
    return base


def test_calendar_check_holiday():
    """祝日の場合is_holiday=Trueになること"""
    mock_cal = MagicMock()
    mock_cal.is_holiday.return_value = (True, "建国記念の日")

    state = _make_state()
    result = calendar_check_node(state, calendar_service=mock_cal)
    assert result["is_holiday"] is True
    assert result["holiday_reason"] == "建国記念の日"


def test_calendar_check_workday():
    """平日の場合is_holiday=Falseになること"""
    mock_cal = MagicMock()
    mock_cal.is_holiday.return_value = (False, "")

    state = _make_state()
    result = calendar_check_node(state, calendar_service=mock_cal)
    assert result["is_holiday"] is False
    assert result["holiday_reason"] is None
```

**Step 2: テスト失敗確認**

```bash
python -m pytest tests/test_calendar_check_node.py -v
```

**Step 3: 実装**

```python
# graph/nodes/calendar_check_node.py
from datetime import date
from graph.state import AttendanceState


def calendar_check_node(
    state: AttendanceState,
    calendar_service=None,
) -> dict:
    """今日が打刻対象日かをカレンダーで確認するノード"""
    today = date.fromisoformat(state["today"])
    is_holiday, reason = calendar_service.is_holiday(today)

    return {
        "is_holiday": is_holiday,
        "holiday_reason": reason if is_holiday else None,
    }
```

**Step 4: テストパス確認**

```bash
python -m pytest tests/test_calendar_check_node.py -v
```
Expected: 2 passed

**Step 5: コミット**

```bash
git add graph/nodes/calendar_check_node.py tests/test_calendar_check_node.py
git commit -m "feat: CalendarCheckNodeを追加"
```

---

## Task 7: TimeGateNode

**Files:**
- Create: `attendance-agent/graph/nodes/time_gate_node.py`
- Test: `attendance-agent/tests/test_time_gate.py`

**Step 1: テスト作成**

```python
# tests/test_time_gate.py
from unittest.mock import patch
from graph.nodes.time_gate_node import time_gate_node

DEFAULT_CONFIG = {
    "time_rules": {"clock_out_time": "18:00", "cutoff_time": "22:00"}
}


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
        "action_taken": None,
        "error_message": None,
        "extra": {},
    }
    base.update(overrides)
    return base


def _mock_time(hour, minute=0):
    """指定時刻をモックするデコレータ用ヘルパー"""
    from datetime import datetime
    return datetime(2026, 2, 22, hour, minute, 0)


def test_morning_clock_in():
    """朝・未打刻 → 出勤打刻"""
    with patch("graph.nodes.time_gate_node._now", return_value=_mock_time(9, 0)):
        state = _make_state(clock_in_done=False)
        result = time_gate_node(state, config=DEFAULT_CONFIG)
    assert result["action_taken"] == "clock_in"


def test_morning_already_clocked_in():
    """朝・打刻済み → スキップ"""
    with patch("graph.nodes.time_gate_node._now", return_value=_mock_time(10, 0)):
        state = _make_state(clock_in_done=True, clock_in_time="09:00")
        result = time_gate_node(state, config=DEFAULT_CONFIG)
    assert result["action_taken"] == "skipped"


def test_evening_clock_out():
    """18時以降・出勤済み → 退勤打刻"""
    with patch("graph.nodes.time_gate_node._now", return_value=_mock_time(18, 30)):
        state = _make_state(clock_in_done=True, clock_in_time="09:00")
        result = time_gate_node(state, config=DEFAULT_CONFIG)
    assert result["action_taken"] == "clock_out"


def test_evening_no_clock_in():
    """18時以降・出勤未済 → 出勤+退勤"""
    with patch("graph.nodes.time_gate_node._now", return_value=_mock_time(19, 0)):
        state = _make_state(clock_in_done=False)
        result = time_gate_node(state, config=DEFAULT_CONFIG)
    assert result["action_taken"] == "clock_in_and_out"


def test_after_cutoff():
    """22時以降 → スキップ"""
    with patch("graph.nodes.time_gate_node._now", return_value=_mock_time(22, 30)):
        state = _make_state(clock_in_done=False)
        result = time_gate_node(state, config=DEFAULT_CONFIG)
    assert result["action_taken"] == "skipped"
```

**Step 2: テスト失敗確認**

```bash
python -m pytest tests/test_time_gate.py -v
```

**Step 3: 実装**

```python
# graph/nodes/time_gate_node.py
from datetime import datetime, time
from graph.state import AttendanceState


def _now() -> datetime:
    """テスト時にモック可能な現在時刻取得"""
    return datetime.now()


def _parse_time(time_str: str) -> time:
    """HH:MM形式の文字列をtimeオブジェクトに変換"""
    h, m = map(int, time_str.split(":"))
    return time(h, m)


def time_gate_node(state: AttendanceState, config: dict = None) -> dict:
    """時刻に応じて打刻種別（出勤/退勤/スキップ）を決定するノード"""
    if config is None:
        config = {"time_rules": {"clock_out_time": "18:00", "cutoff_time": "22:00"}}

    rules = config["time_rules"]
    clock_out_time = _parse_time(rules["clock_out_time"])
    cutoff_time = _parse_time(rules["cutoff_time"])

    now = _now()
    current_time = now.time()

    # 22:00以降 → スキップ（打刻禁止）
    if current_time >= cutoff_time:
        return {"action_taken": "skipped"}

    clock_in_done = state["clock_in_done"]

    # 18:00〜22:00
    if current_time >= clock_out_time:
        if clock_in_done:
            return {"action_taken": "clock_out"}
        else:
            return {"action_taken": "clock_in_and_out"}

    # 〜18:00
    if not clock_in_done:
        return {"action_taken": "clock_in"}
    else:
        return {"action_taken": "skipped"}
```

**Step 4: テストパス確認**

```bash
python -m pytest tests/test_time_gate.py -v
```
Expected: 5 passed

**Step 5: コミット**

```bash
git add graph/nodes/time_gate_node.py tests/test_time_gate.py
git commit -m "feat: TimeGateNodeを追加"
```

---

## Task 8: 打刻サービス (attendance_browser.py)

**Files:**
- Create: `attendance-agent/services/attendance_browser.py`
- Test: `attendance-agent/tests/test_stamp.py`

**Step 1: テスト作成**

```python
# tests/test_stamp.py
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
```

**Step 2: テスト失敗確認**

```bash
python -m pytest tests/test_stamp.py -v
```

**Step 3: 実装**

```python
# services/attendance_browser.py
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

            # ログインページにリダイレクトされたかチェック
            if "login" in page.url.lower():
                await page.fill(self._selectors["username_field"], self._user)
                await page.fill(self._selectors["password_field"], self._password)
                await page.click(self._selectors["login_button"])
                await page.wait_for_load_state("networkidle")
                await self._save_session()

            return True
        except Exception as e:
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

                # 成功確認
                success_el = await page.query_selector(
                    self._selectors["success_message"]
                )
                if success_el:
                    timestamp = datetime.now().strftime("%H:%M")
                    await self._save_session()
                    return StampResult(
                        success=True, timestamp=timestamp, error=None
                    )
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
```

**Step 4: テストパス確認**

```bash
python -m pytest tests/test_stamp.py -v
```
Expected: 4 passed

**Step 5: コミット**

```bash
git add services/attendance_browser.py tests/test_stamp.py
git commit -m "feat: 打刻サービス(AttendanceBrowser)を追加"
```

---

## Task 9: StampNode

**Files:**
- Create: `attendance-agent/graph/nodes/stamp_node.py`
- Test: `attendance-agent/tests/test_stamp_node.py`

**Step 1: テスト作成**

```python
# tests/test_stamp_node.py
import pytest
from unittest.mock import AsyncMock
from services.attendance_browser import StampResult
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
```

**Step 2: テスト失敗確認**

```bash
python -m pytest tests/test_stamp_node.py -v
```

**Step 3: 実装**

```python
# graph/nodes/stamp_node.py
from graph.state import AttendanceState
from services.attendance_browser import AttendanceBrowser


async def stamp_node(state: AttendanceState, browser: AttendanceBrowser = None) -> dict:
    """Playwrightで打刻を実行するノード"""
    action = state["action_taken"]

    if action == "clock_in":
        result = await browser.clock_in()
        if result.success:
            return {
                "clock_in_done": True,
                "clock_in_time": result.timestamp,
                "action_taken": "clock_in",
                "error_message": None,
            }
        else:
            return {
                "action_taken": "error",
                "error_message": result.error,
            }

    elif action == "clock_out":
        result = await browser.clock_out()
        if result.success:
            return {
                "last_clock_out_time": result.timestamp,
                "action_taken": "clock_out",
                "error_message": None,
            }
        else:
            return {
                "action_taken": "error",
                "error_message": result.error,
            }

    elif action == "clock_in_and_out":
        in_result = await browser.clock_in()
        if not in_result.success:
            return {
                "action_taken": "error",
                "error_message": f"出勤打刻失敗: {in_result.error}",
            }

        out_result = await browser.clock_out()
        if not out_result.success:
            return {
                "clock_in_done": True,
                "clock_in_time": in_result.timestamp,
                "action_taken": "error",
                "error_message": f"退勤打刻失敗: {out_result.error}",
            }

        return {
            "clock_in_done": True,
            "clock_in_time": in_result.timestamp,
            "last_clock_out_time": out_result.timestamp,
            "action_taken": "clock_in_and_out",
            "error_message": None,
        }

    return {"action_taken": "skipped"}
```

**Step 4: テストパス確認**

```bash
python -m pytest tests/test_stamp_node.py -v
```
Expected: 4 passed

**Step 5: コミット**

```bash
git add graph/nodes/stamp_node.py tests/test_stamp_node.py
git commit -m "feat: StampNodeを追加"
```

---

## Task 10: Slack通知サービス (slack_client.py)

**Files:**
- Create: `attendance-agent/services/slack_client.py`
- Test: `attendance-agent/tests/test_slack_client.py`

**Step 1: テスト作成**

```python
# tests/test_slack_client.py
from unittest.mock import MagicMock, patch
from services.slack_client import SlackNotifier, ConsoleNotifier


def test_console_notifier_send():
    """ConsoleNotifierがメッセージを出力すること"""
    notifier = ConsoleNotifier()
    with patch("builtins.print") as mock_print:
        result = notifier.send("テストメッセージ")
    assert result is True
    mock_print.assert_called_once()


def test_console_notifier_send_error():
    """ConsoleNotifierがエラーメッセージを出力すること"""
    notifier = ConsoleNotifier()
    with patch("builtins.print") as mock_print:
        result = notifier.send_error("エラー内容")
    assert result is True


def test_slack_notifier_send_success():
    """SlackNotifierがメッセージ送信に成功すること"""
    mock_client = MagicMock()
    mock_client.chat_postMessage.return_value = {"ok": True}

    notifier = SlackNotifier(token="xoxb-test", channel="C12345")
    notifier._client = mock_client

    result = notifier.send("テスト通知")
    assert result is True
    mock_client.chat_postMessage.assert_called_once_with(
        channel="C12345", text="テスト通知"
    )


def test_slack_notifier_send_failure():
    """Slack API失敗時にFalseを返すこと"""
    mock_client = MagicMock()
    mock_client.chat_postMessage.side_effect = Exception("API Error")

    notifier = SlackNotifier(token="xoxb-test", channel="C12345")
    notifier._client = mock_client

    result = notifier.send("テスト通知")
    assert result is False


def test_slack_notifier_fallback():
    """Slack初期化失敗時にフォールバックすること"""
    notifier = SlackNotifier(token="", channel="")
    # トークンが空の場合、_clientはNone
    with patch("builtins.print") as mock_print:
        result = notifier.send("フォールバックテスト")
    assert result is True  # ConsoleNotifierにフォールバック
```

**Step 2: テスト失敗確認**

```bash
python -m pytest tests/test_slack_client.py -v
```

**Step 3: 実装**

```python
# services/slack_client.py
from typing import Optional
import sys


class ConsoleNotifier:
    """コンソール出力による通知（フォールバック用）"""

    def send(self, message: str) -> bool:
        print(f"[勤怠通知] {message}", file=sys.stdout)
        return True

    def send_error(self, error: str) -> bool:
        print(f"[勤怠エラー] {error}", file=sys.stderr)
        return True


class SlackNotifier:
    """Slack APIによる通知サービス"""

    def __init__(self, token: str, channel: str):
        self._channel = channel
        self._client = None
        self._fallback = ConsoleNotifier()

        if token:
            try:
                from slack_sdk import WebClient
                self._client = WebClient(token=token)
            except Exception:
                pass

    def send(self, message: str) -> bool:
        """メッセージ送信（失敗時はフォールバック）"""
        if self._client is None:
            return self._fallback.send(message)

        try:
            self._client.chat_postMessage(channel=self._channel, text=message)
            return True
        except Exception:
            return self._fallback.send(message)

    def send_error(self, error: str) -> bool:
        """エラー通知"""
        message = f"❌ 打刻に失敗しました。手動確認をお願いします（エラー: {error}）"
        return self.send(message)
```

**Step 4: テストパス確認**

```bash
python -m pytest tests/test_slack_client.py -v
```
Expected: 5 passed

**Step 5: コミット**

```bash
git add services/slack_client.py tests/test_slack_client.py
git commit -m "feat: Slack通知サービス(SlackNotifier + ConsoleNotifierフォールバック)を追加"
```

---

## Task 11: SlackNotifyNode

**Files:**
- Create: `attendance-agent/graph/nodes/slack_notify_node.py`
- Test: `attendance-agent/tests/test_slack_notify_node.py`

**Step 1: テスト作成**

```python
# tests/test_slack_notify_node.py
from unittest.mock import MagicMock
from graph.nodes.slack_notify_node import slack_notify_node


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
        "action_taken": None,
        "error_message": None,
        "extra": {},
    }
    base.update(overrides)
    return base


def test_notify_clock_in():
    """出勤打刻成功の通知"""
    mock_notifier = MagicMock()
    mock_notifier.send.return_value = True

    state = _make_state(action_taken="clock_in", clock_in_time="09:12")
    result = slack_notify_node(state, notifier=mock_notifier)

    mock_notifier.send.assert_called_once()
    call_msg = mock_notifier.send.call_args[0][0]
    assert "出勤" in call_msg
    assert "09:12" in call_msg


def test_notify_clock_out():
    """退勤打刻成功の通知"""
    mock_notifier = MagicMock()
    mock_notifier.send.return_value = True

    state = _make_state(action_taken="clock_out", last_clock_out_time="18:00")
    result = slack_notify_node(state, notifier=mock_notifier)

    call_msg = mock_notifier.send.call_args[0][0]
    assert "退勤" in call_msg
    assert "18:00" in call_msg


def test_notify_error():
    """エラー通知"""
    mock_notifier = MagicMock()
    mock_notifier.send_error.return_value = True

    state = _make_state(action_taken="error", error_message="タイムアウト")
    result = slack_notify_node(state, notifier=mock_notifier)

    mock_notifier.send_error.assert_called_once_with("タイムアウト")


def test_notify_skipped_no_message():
    """スキップ時は通知しない"""
    mock_notifier = MagicMock()

    state = _make_state(action_taken="skipped")
    result = slack_notify_node(state, notifier=mock_notifier)

    mock_notifier.send.assert_not_called()
    mock_notifier.send_error.assert_not_called()
```

**Step 2: テスト失敗確認**

```bash
python -m pytest tests/test_slack_notify_node.py -v
```

**Step 3: 実装**

```python
# graph/nodes/slack_notify_node.py
from graph.state import AttendanceState


MESSAGES = {
    "clock_in": "✅ 出勤打刻しました（{time}）",
    "clock_out": "🕐 退勤打刻を更新しました（{time}）",
    "clock_in_and_out": "✅ 出勤（{in_time}）・退勤（{out_time}）を打刻しました",
}


def slack_notify_node(state: AttendanceState, notifier=None) -> dict:
    """打刻結果をSlackに通知するノード"""
    action = state["action_taken"]

    if action == "error":
        notifier.send_error(state["error_message"])
        return {}

    if action == "skipped":
        return {}

    if action == "clock_in":
        msg = MESSAGES["clock_in"].format(time=state["clock_in_time"])
        notifier.send(msg)
    elif action == "clock_out":
        msg = MESSAGES["clock_out"].format(time=state["last_clock_out_time"])
        notifier.send(msg)
    elif action == "clock_in_and_out":
        msg = MESSAGES["clock_in_and_out"].format(
            in_time=state["clock_in_time"],
            out_time=state["last_clock_out_time"],
        )
        notifier.send(msg)

    return {}
```

**Step 4: テストパス確認**

```bash
python -m pytest tests/test_slack_notify_node.py -v
```
Expected: 4 passed

**Step 5: コミット**

```bash
git add graph/nodes/slack_notify_node.py tests/test_slack_notify_node.py
git commit -m "feat: SlackNotifyNodeを追加"
```

---

## Task 12: StateUpdateNode

**Files:**
- Create: `attendance-agent/graph/nodes/state_update_node.py`
- Test: `attendance-agent/tests/test_state_update_node.py`

**Step 1: テスト作成**

```python
# tests/test_state_update_node.py
from unittest.mock import patch
from datetime import datetime
from graph.nodes.state_update_node import state_update_node


def _make_state(**overrides):
    base = {
        "today": "2026-02-22",
        "is_holiday": False,
        "holiday_reason": None,
        "clock_in_done": True,
        "clock_in_time": "09:00",
        "last_clock_out_time": "18:00",
        "is_working": True,
        "operation_log": [],
        "action_taken": "clock_out",
        "error_message": None,
        "extra": {},
    }
    base.update(overrides)
    return base


def test_state_update_same_day():
    """同日中は状態を維持すること"""
    with patch("graph.nodes.state_update_node._today_str", return_value="2026-02-22"):
        state = _make_state()
        result = state_update_node(state)
    assert result["clock_in_done"] is True
    assert result["today"] == "2026-02-22"


def test_state_update_day_change():
    """日付が変わったら状態リセットすること"""
    with patch("graph.nodes.state_update_node._today_str", return_value="2026-02-23"):
        state = _make_state(today="2026-02-22")
        result = state_update_node(state)
    assert result["clock_in_done"] is False
    assert result["clock_in_time"] is None
    assert result["last_clock_out_time"] is None
    assert result["today"] == "2026-02-23"
    assert result["action_taken"] is None
    assert result["is_holiday"] is False


def test_state_update_clears_error():
    """正常完了後にエラーをクリアすること"""
    with patch("graph.nodes.state_update_node._today_str", return_value="2026-02-22"):
        state = _make_state(error_message="前回エラー", action_taken="clock_in")
        result = state_update_node(state)
    assert result["error_message"] is None
```

**Step 2: テスト失敗確認**

```bash
python -m pytest tests/test_state_update_node.py -v
```

**Step 3: 実装**

```python
# graph/nodes/state_update_node.py
from datetime import date
from graph.state import AttendanceState


def _today_str() -> str:
    """テスト時にモック可能"""
    return date.today().isoformat()


def state_update_node(state: AttendanceState) -> dict:
    """打刻後の状態を更新し、日付跨ぎでリセットするノード"""
    today = _today_str()

    # 日付が変わったらリセット
    if state["today"] != today:
        return {
            "today": today,
            "is_holiday": False,
            "holiday_reason": None,
            "clock_in_done": False,
            "clock_in_time": None,
            "last_clock_out_time": None,
            "is_working": False,
            "operation_log": [],
            "action_taken": None,
            "error_message": None,
        }

    # 同日: エラーをクリアして状態を維持
    return {
        "today": today,
        "clock_in_done": state["clock_in_done"],
        "clock_in_time": state["clock_in_time"],
        "last_clock_out_time": state["last_clock_out_time"],
        "error_message": None,
    }
```

**Step 4: テストパス確認**

```bash
python -m pytest tests/test_state_update_node.py -v
```
Expected: 3 passed

**Step 5: コミット**

```bash
git add graph/nodes/state_update_node.py tests/test_state_update_node.py
git commit -m "feat: StateUpdateNodeを追加"
```

---

## Task 13: LangGraphグラフ定義

**Files:**
- Create: `attendance-agent/graph/graph.py`
- Test: `attendance-agent/tests/test_graph.py`

**Step 1: テスト作成**

```python
# tests/test_graph.py
from graph.graph import (
    route_after_working_check,
    route_after_calendar_check,
    route_after_time_gate,
    build_graph,
)


def _make_state(**overrides):
    base = {
        "today": "2026-02-22",
        "is_holiday": False,
        "holiday_reason": None,
        "clock_in_done": False,
        "clock_in_time": None,
        "last_clock_out_time": None,
        "is_working": False,
        "operation_log": [],
        "action_taken": None,
        "error_message": None,
        "extra": {},
    }
    base.update(overrides)
    return base


def test_route_working_check_not_working():
    """作業中でない場合skipへ"""
    state = _make_state(is_working=False)
    assert route_after_working_check(state) == "end"


def test_route_working_check_working():
    """作業中の場合calendar_checkへ"""
    state = _make_state(is_working=True)
    assert route_after_working_check(state) == "calendar_check"


def test_route_calendar_holiday():
    """祝日の場合endへ"""
    state = _make_state(is_holiday=True)
    assert route_after_calendar_check(state) == "end"


def test_route_calendar_workday():
    """平日の場合time_gateへ"""
    state = _make_state(is_holiday=False)
    assert route_after_calendar_check(state) == "time_gate"


def test_route_time_gate_skipped():
    """スキップの場合endへ"""
    state = _make_state(action_taken="skipped")
    assert route_after_time_gate(state) == "end"


def test_route_time_gate_stamp():
    """打刻が必要な場合stampへ"""
    state = _make_state(action_taken="clock_in")
    assert route_after_time_gate(state) == "stamp"


def test_build_graph():
    """グラフが正常にビルドできること"""
    graph = build_graph()
    assert graph is not None
```

**Step 2: テスト失敗確認**

```bash
python -m pytest tests/test_graph.py -v
```

**Step 3: 実装**

```python
# graph/graph.py
from langgraph.graph import StateGraph, END
from graph.state import AttendanceState


def route_after_working_check(state: AttendanceState) -> str:
    if not state["is_working"]:
        return "end"
    return "calendar_check"


def route_after_calendar_check(state: AttendanceState) -> str:
    if state["is_holiday"]:
        return "end"
    return "time_gate"


def route_after_time_gate(state: AttendanceState) -> str:
    if state["action_taken"] == "skipped":
        return "end"
    return "stamp"


def build_graph() -> StateGraph:
    """LangGraphのグラフを構築して返す"""
    from graph.nodes.working_state_node import working_state_node
    from graph.nodes.calendar_check_node import calendar_check_node
    from graph.nodes.time_gate_node import time_gate_node
    from graph.nodes.stamp_node import stamp_node
    from graph.nodes.slack_notify_node import slack_notify_node
    from graph.nodes.state_update_node import state_update_node

    workflow = StateGraph(AttendanceState)

    # ノード追加（実際のサービス注入はmain.pyで行う）
    workflow.add_node("working_state", working_state_node)
    workflow.add_node("calendar_check", calendar_check_node)
    workflow.add_node("time_gate", time_gate_node)
    workflow.add_node("stamp", stamp_node)
    workflow.add_node("slack_notify", slack_notify_node)
    workflow.add_node("state_update", state_update_node)

    # エントリーポイント
    workflow.set_entry_point("working_state")

    # 条件分岐エッジ
    workflow.add_conditional_edges(
        "working_state",
        route_after_working_check,
        {"calendar_check": "calendar_check", "end": END},
    )
    workflow.add_conditional_edges(
        "calendar_check",
        route_after_calendar_check,
        {"time_gate": "time_gate", "end": END},
    )
    workflow.add_conditional_edges(
        "time_gate",
        route_after_time_gate,
        {"stamp": "stamp", "end": END},
    )

    # 通常エッジ
    workflow.add_edge("stamp", "slack_notify")
    workflow.add_edge("slack_notify", "state_update")
    workflow.add_edge("state_update", END)

    return workflow.compile()
```

**Step 4: テストパス確認**

```bash
python -m pytest tests/test_graph.py -v
```
Expected: 7 passed

**Step 5: コミット**

```bash
git add graph/graph.py tests/test_graph.py
git commit -m "feat: LangGraphグラフ定義を追加"
```

---

## Task 14: スケジューラ

**Files:**
- Create: `attendance-agent/schedulers/scheduler.py`
- Test: `attendance-agent/tests/test_scheduler.py`

**Step 1: テスト作成**

```python
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
```

**Step 2: テスト失敗確認**

```bash
python -m pytest tests/test_scheduler.py -v
```

**Step 3: 実装**

```python
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
```

**Step 4: テストパス確認**

```bash
python -m pytest tests/test_scheduler.py -v
```
Expected: 2 passed

**Step 5: コミット**

```bash
git add schedulers/scheduler.py tests/test_scheduler.py
git commit -m "feat: APSchedulerによるスケジューラを追加"
```

---

## Task 15: main.py エントリーポイント

**Files:**
- Create: `attendance-agent/main.py`

**Step 1: 実装**

```python
# main.py
"""勤怠管理エージェント - エントリーポイント"""
import asyncio
import signal
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
import os

from services.config_loader import load_config
from services.pc_monitor import PCMonitor
from services.google_calendar import GoogleCalendarService, LocalCalendarService
from services.slack_client import SlackNotifier, ConsoleNotifier
from services.attendance_browser import AttendanceBrowser
from schedulers.scheduler import AttendanceScheduler


def create_services(config: dict):
    """設定に基づいてサービスインスタンスを生成"""
    load_dotenv()

    # PC監視
    monitor = PCMonitor()

    # カレンダーサービス
    cal_config = config["calendar"]
    if cal_config["enabled"] and cal_config.get("fallback") != "jpholiday":
        calendar_service = GoogleCalendarService(
            credentials_path=os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json"),
            token_path=os.getenv("GOOGLE_TOKEN_PATH", "token.json"),
            holiday_calendar_id=os.getenv(
                "HOLIDAY_CALENDAR_ID", cal_config["holiday_calendar_id"]
            ),
            vacation_keywords=cal_config["vacation_keywords"],
        )
    else:
        calendar_service = LocalCalendarService(
            vacation_keywords=cal_config["vacation_keywords"]
        )

    # Slack通知
    slack_config = config["slack"]
    slack_token = os.getenv("SLACK_BOT_TOKEN", "")
    slack_channel = os.getenv("SLACK_NOTIFY_CHANNEL", slack_config.get("notify_channel", ""))
    if slack_config["enabled"] and slack_token:
        notifier = SlackNotifier(token=slack_token, channel=slack_channel)
    else:
        notifier = ConsoleNotifier()

    # 打刻ブラウザ
    browser = AttendanceBrowser(
        url=os.getenv("ATTENDANCE_URL", ""),
        user=os.getenv("ATTENDANCE_USER", ""),
        password=os.getenv("ATTENDANCE_PASS", ""),
        config=config,
    )

    return monitor, calendar_service, notifier, browser


def run_check(monitor, calendar_service, notifier, browser, config):
    """1回分のチェックを実行"""
    from graph.nodes.working_state_node import working_state_node
    from graph.nodes.calendar_check_node import calendar_check_node
    from graph.nodes.time_gate_node import time_gate_node
    from graph.nodes.stamp_node import stamp_node
    from graph.nodes.slack_notify_node import slack_notify_node
    from graph.nodes.state_update_node import state_update_node

    # 初期状態
    state = {
        "today": date.today().isoformat(),
        "is_holiday": False,
        "holiday_reason": None,
        "clock_in_done": getattr(run_check, "_clock_in_done", False),
        "clock_in_time": getattr(run_check, "_clock_in_time", None),
        "last_clock_out_time": getattr(run_check, "_last_clock_out_time", None),
        "is_working": False,
        "operation_log": [],
        "action_taken": None,
        "error_message": None,
        "extra": {},
    }

    # 日付リセット
    if state["today"] != getattr(run_check, "_last_date", ""):
        state["clock_in_done"] = False
        state["clock_in_time"] = None
        state["last_clock_out_time"] = None
        run_check._last_date = state["today"]

    # ノード順次実行
    # 1. WorkingState
    ws_result = working_state_node(state, monitor=monitor, config=config)
    state.update(ws_result)

    if not state["is_working"]:
        return

    # 2. CalendarCheck
    cal_result = calendar_check_node(state, calendar_service=calendar_service)
    state.update(cal_result)

    if state["is_holiday"]:
        return

    # 3. TimeGate
    tg_result = time_gate_node(state, config=config)
    state.update(tg_result)

    if state["action_taken"] == "skipped":
        return

    # 4. Stamp
    stamp_result = asyncio.run(stamp_node(state, browser=browser))
    state.update(stamp_result)

    # 5. SlackNotify
    slack_notify_node(state, notifier=notifier)

    # 6. StateUpdate
    su_result = state_update_node(state)
    state.update(su_result)

    # 状態保持
    run_check._clock_in_done = state.get("clock_in_done", False)
    run_check._clock_in_time = state.get("clock_in_time")
    run_check._last_clock_out_time = state.get("last_clock_out_time")


def main():
    """メイン起動処理"""
    config = load_config("config.yaml")
    monitor, calendar_service, notifier, browser = create_services(config)

    # PC監視開始
    monitor.start()
    print("[勤怠エージェント] PC監視を開始しました")

    # スケジューラ設定
    interval = config["scheduler"]["check_interval_minutes"]

    def check_job():
        try:
            run_check(monitor, calendar_service, notifier, browser, config)
        except Exception as e:
            print(f"[勤怠エージェント] チェック中にエラー: {e}")
            notifier.send_error(str(e))

    scheduler = AttendanceScheduler(interval_minutes=interval, job_func=check_job)
    scheduler.start()
    print(f"[勤怠エージェント] {interval}分間隔でチェックを開始します")

    # シグナルハンドリング
    def shutdown(signum, frame):
        print("\n[勤怠エージェント] 停止中...")
        scheduler.stop()
        monitor.stop()
        asyncio.run(browser.close())
        print("[勤怠エージェント] 停止しました")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # メインループ（キープアライブ）
    print("[勤怠エージェント] Ctrl+Cで停止します")
    try:
        while True:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        shutdown(None, None)


if __name__ == "__main__":
    main()
```

**Step 2: 動作確認**

```bash
cd attendance-agent
python main.py
```
Expected: PC監視開始のメッセージが表示され、Ctrl+Cで停止可能

**Step 3: コミット**

```bash
git add main.py
git commit -m "feat: main.pyエントリーポイントを追加"
```

---

## Task 16: 全体テスト実行・最終確認

**Step 1: 全テスト実行**

```bash
cd attendance-agent
python -m pytest tests/ -v --tb=short
```
Expected: 全テストパス

**Step 2: 最終コミット**

```bash
git add -A
git commit -m "chore: 全テストパス確認・初期リリース準備完了"
```

---

## 実装完了チェックリスト

- [ ] Task 0: プロジェクト初期化
- [ ] Task 1: AgentState型定義
- [ ] Task 2: PC操作監視サービス
- [ ] Task 3: 設定ローダー
- [ ] Task 4: WorkingStateNode
- [ ] Task 5: カレンダーサービス
- [ ] Task 6: CalendarCheckNode
- [ ] Task 7: TimeGateNode
- [ ] Task 8: 打刻サービス
- [ ] Task 9: StampNode
- [ ] Task 10: Slack通知サービス
- [ ] Task 11: SlackNotifyNode
- [ ] Task 12: StateUpdateNode
- [ ] Task 13: LangGraphグラフ定義
- [ ] Task 14: スケジューラ
- [ ] Task 15: main.py エントリーポイント
- [ ] Task 16: 全体テスト・最終確認
