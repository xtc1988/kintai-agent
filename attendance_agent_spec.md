# 勤怠管理エージェント 仕様書

## 1. プロジェクト概要

PC稼働状況を監視し、社内勤怠システムへの打刻漏れを自動防止するLangGraphエージェント。  
Slackで結果通知、Googleカレンダーで祝日・有給判定を行う。

### 設計方針
- **拡張性重視**: 各機能をサービス層・ノード層に分離し、将来的な機能追加を容易にする
- **設定の外部化**: ハードコードを避け、config.yamlで動作を制御可能にする
- **障害耐性**: 打刻失敗時のリトライ・エラー通知を標準装備

---

## 2. システム構成

### 技術スタック

| 役割 | ライブラリ / サービス |
|------|----------------------|
| エージェントフレームワーク | LangGraph |
| PC操作監視 | pynput |
| ブラウザ自動操作 | Playwright (Python) |
| Slack通知 | slack-bolt / slack-sdk |
| カレンダー取得 | google-api-python-client |
| スケジューラ | APScheduler |
| 設定管理 | PyYAML + python-dotenv |

### ディレクトリ構成

```
attendance-agent/
├── main.py                      # エントリーポイント・起動処理
├── config.yaml                  # 動作設定（タイミング・閾値など）
├── .env                         # 認証情報（Gitignore対象）
│
├── graph/
│   ├── graph.py                 # LangGraphグラフ定義・エッジ設定
│   ├── state.py                 # AgentState型定義
│   └── nodes/                   # 各ノードの実装
│       ├── __init__.py
│       ├── working_state_node.py
│       ├── calendar_check_node.py
│       ├── time_gate_node.py
│       ├── stamp_node.py
│       ├── slack_notify_node.py
│       └── state_update_node.py
│
├── services/                    # ノードから呼び出される実処理層
│   ├── __init__.py
│   ├── pc_monitor.py            # pynputによるPC操作監視
│   ├── attendance_browser.py    # Playwrightによる打刻処理
│   ├── google_calendar.py       # Google Calendar API
│   └── slack_client.py          # Slack送受信
│
├── schedulers/
│   └── scheduler.py             # APSchedulerによる定期実行管理
│
└── tests/
    ├── test_working_state.py
    ├── test_calendar_check.py
    └── test_stamp.py
```

---

## 3. LangGraph 状態定義

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
    
    # 拡張用（将来的な週次工数チェックなどに使用）
    extra: dict                         # 任意の追加データ
```

---

## 4. LangGraphグラフ構成

### ノード一覧とフロー

```
[WorkingStateNode]
    ↓ is_working=True
[CalendarCheckNode]
    ↓ is_holiday=False
[TimeGateNode]
    ↓ 時間帯・打刻種別を判定
[StampNode]
    ↓ 打刻実行（Playwright）
[SlackNotifyNode]
    ↓ 結果をSlackに投稿
[StateUpdateNode]
    ↓ 状態を更新してループへ

※ 各ノードでFalse/エラーになった場合はSlackNotifyNodeへジャンプしてログ
```

### エッジ定義（条件分岐）

```python
# graph/graph.py（概要）

def route_after_working_check(state: AttendanceState) -> str:
    if not state["is_working"]:
        return "skip"  # ENDへ
    return "calendar_check"

def route_after_calendar_check(state: AttendanceState) -> str:
    if state["is_holiday"]:
        return "skip"  # ENDへ（通知なし）
    return "time_gate"

def route_after_time_gate(state: AttendanceState) -> str:
    if state["action_taken"] == "skipped":
        return "end"
    return "stamp"
```

---

## 5. 各ノード仕様

### WorkingStateNode
**役割**: PC操作ログを分析し「作業中」かを判定する

**判定ロジック**:
- 直近15分以内のイベントが2回以上 → `is_working = True`
- pc_monitor.pyが別スレッドで常時イベントをキューに蓄積
- 古いイベント（15分超）は自動パージ

**拡張ポイント**: 判定閾値（15分・2回）はconfig.yamlで変更可能

---

### CalendarCheckNode
**役割**: 今日が打刻対象日かをGoogle Calendarで確認する

**チェック内容**:
1. Googleの日本の祝日カレンダー（`ja.japanese#holiday@group.v.calendar.google.com`）
2. 個人カレンダーのイベントタイトルに「有給」「年休」「休暇」が含まれるか

**キャッシュ**: 当日の判定結果はメモリにキャッシュし、APIコールを最小化

---

### TimeGateNode
**役割**: 時刻に応じて打刻種別（出勤/退勤/スキップ）を決定する

**ルール表**:

| 時間帯 | 出勤打刻済み | 判定 |
|--------|-------------|------|
| 22:00以降 | - | スキップ（打刻禁止） |
| 〜18:00 | False | 出勤打刻 |
| 〜18:00 | True | スキップ（退勤まだ） |
| 18:00〜22:00 | True | 退勤打刻（上書きOK） |
| 18:00〜22:00 | False | 出勤+退勤打刻（両方） |

---

### StampNode
**役割**: Playwrightで社内勤怠システムにアクセスし打刻する

**処理フロー**:
1. ブラウザ起動（headless or headful は設定で切替可）
2. ログイン状態確認（セッションクッキー保存で再利用）
3. 未ログインならID/パスワードでログイン
4. 打刻ボタンをクリック
5. 成功確認（画面上の確認メッセージ等をアサート）
6. 失敗時はリトライ（最大3回、設定変更可）

**認証情報**: `.env`から読み込み（`ATTENDANCE_USER`, `ATTENDANCE_PASS`）

**拡張ポイント**: 社内システム変更時は`attendance_browser.py`のセレクタのみ修正で対応可

---

### SlackNotifyNode
**役割**: 打刻結果をSlackに投稿する

**通知メッセージ例**:

| アクション | メッセージ |
|-----------|-----------|
| 出勤打刻成功 | `✅ 出勤打刻しました（09:12）` |
| 退勤打刻更新 | `🕐 退勤打刻を更新しました（18:00）` |
| 作業停止→最終退勤 | `🏁 作業停止を検知。最終退勤打刻しました（20:03）` |
| 打刻失敗 | `❌ 打刻に失敗しました。手動確認をお願いします（エラー: XXX）` |
| 祝日スキップ | （通知なし） |

**送信先**: 設定でDM or チャンネル指定（`SLACK_NOTIFY_CHANNEL`）

---

### StateUpdateNode
**役割**: 打刻後の状態をメモリ上で更新し、日付跨ぎでリセットする

- `clock_in_done`, `last_clock_out_time`を更新
- 日付が変わったら全状態をリセット

---

## 6. 各サービス層の仕様

### pc_monitor.py
```python
class PCMonitor:
    def start() -> None          # 監視スレッド開始
    def stop() -> None           # 監視停止
    def get_recent_events(minutes: int) -> list[datetime]  # 直近N分のイベント取得
    def is_working(threshold_minutes: int, min_count: int) -> bool  # 作業中判定
```

### attendance_browser.py
```python
class AttendanceBrowser:
    def ensure_logged_in() -> bool       # ログイン確認・必要なら実行
    def clock_in() -> StampResult        # 出勤打刻
    def clock_out() -> StampResult       # 退勤打刻
    def get_today_status() -> dict       # 今日の打刻状況取得（拡張用）

class StampResult:
    success: bool
    timestamp: str
    error: Optional[str]
```

### google_calendar.py
```python
class GoogleCalendarService:
    def is_holiday_today() -> tuple[bool, str]   # (判定結果, 理由)
    def get_today_events() -> list[dict]          # 今日のイベント一覧（拡張用）
```

### slack_client.py
```python
class SlackNotifier:
    def send(message: str) -> bool                # メッセージ送信
    def send_error(error: str) -> bool            # エラー通知
    # 将来: Slackからのコマンド受付（有給登録など）も追加可
```

---

## 7. スケジューラ設定

```yaml
# config.yaml
scheduler:
  check_interval_minutes: 5     # 稼働チェック間隔

working_state:
  window_minutes: 15            # 操作イベントの監視窓
  min_event_count: 2            # 作業中判定の最小イベント数

time_rules:
  clock_out_time: "18:00"       # 退勤打刻開始時刻
  cutoff_time: "22:00"          # 打刻禁止時刻

browser:
  headless: true                # headlessモード
  retry_count: 3                # 打刻失敗時のリトライ数
  session_storage_path: ".session"  # クッキー保存先

slack:
  notify_channel: "DXXXXXXXX"   # 通知先（DMのユーザーIDかチャンネルID）
```

---

## 8. 将来の拡張ポイント

| 機能 | 追加方法 |
|------|---------|
| 週次工数チェック | 新ノード`WeeklyWorkCheckNode`を追加、金曜にスケジュール |
| Slackからの有給登録 | `slack_client.py`にイベントハンドラ追加 |
| 複数社内システム対応 | `attendance_browser.py`をインターフェース化して実装を差し替え |
| 打刻ログの永続化 | `StateUpdateNode`にDB/スプレッドシート書き込みを追加 |
| 複数人対応 | Stateにuser_idを追加しグラフをマルチユーザー対応に |

---

## 9. 環境変数一覧（.env）

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

---

## 10. 実装優先順位（推奨）

1. `pc_monitor.py` + `working_state_node.py` — PC監視の基盤
2. `attendance_browser.py` + `stamp_node.py` — 打刻処理（社内システムのURL・セレクタ確認後）
3. `google_calendar.py` + `calendar_check_node.py` — 祝日・有給判定
4. `graph.py` でグラフ組み立て + `scheduler.py` で定期実行
5. `slack_client.py` + `slack_notify_node.py` — 通知
6. テスト・設定の外部化

---

*作成日: 2026-02-22*
