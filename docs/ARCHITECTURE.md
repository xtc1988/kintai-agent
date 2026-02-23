# アーキテクチャドキュメント - 勤怠エージェント (kintai-agent)

> 最終更新: 2026-02-23

---

## 目次

1. [システム概要](#1-システム概要)
2. [アーキテクチャ図](#2-アーキテクチャ図)
3. [ディレクトリ構造](#3-ディレクトリ構造)
4. [状態管理 (AttendanceState)](#4-状態管理-attendancestate)
5. [LangGraphステートマシン](#5-langgraphステートマシン)
6. [各ノードの責務と入出力](#6-各ノードの責務と入出力)
7. [サービス層の設計](#7-サービス層の設計)
8. [設定管理](#8-設定管理)
9. [グラフの条件分岐](#9-グラフの条件分岐)
10. [main.py の起動フロー](#10-mainpy-の起動フロー)
11. [テスト戦略](#11-テスト戦略)
12. [拡張ポイント](#12-拡張ポイント)
13. [関連ドキュメント](#13-関連ドキュメント)

---

## 1. システム概要

### 目的

PC操作（マウス移動・キーボード入力）を監視し、ルールベースで社内勤怠システムへの出勤・退勤打刻を自動実行するエージェント。

### 重要な設計思想

- **LLM/AIは一切使用していない。** LangGraphはワークフロー管理フレームワークとしてのみ使用している。状態遷移とノード間のデータフローを宣言的に記述するための仕組みであり、推論・生成・埋め込みなどのAI機能は利用しない。
- **純粋なルールベース判定。** 全ての判定ロジック（稼働状態、祝日、時刻ルール）は決定論的なif/else分岐で実装されている。
- **APSchedulerによる5分間隔の定期実行。** `BackgroundScheduler` で5分ごとに `check_job()` を呼び出し、LangGraphのステートマシンを1回走らせる。
- **Strategy Patternによるサービス差し替え。** 打刻・通知・カレンダーの各サービスはインターフェースを介して実装を切り替え可能。開発/テスト用のダミー実装と本番用実装を `config.yaml` で選択する。

### 技術スタック

| カテゴリ | 技術 | 用途 |
|---------|------|------|
| ワークフロー管理 | LangGraph (`StateGraph`) | ノード間の状態遷移制御 |
| 定期実行 | APScheduler (`BackgroundScheduler`) | 5分間隔のジョブスケジューリング |
| PC監視 | pynput | マウス・キーボードイベントの監視 |
| ブラウザ操作 | Playwright (async API) | 社内勤怠システムへの自動打刻 |
| 通知 | Slack SDK (`WebClient`) | 打刻結果のSlack通知 |
| カレンダー | Google Calendar API / jpholiday | 祝日・有給判定 |
| 設定管理 | PyYAML / python-dotenv | YAML設定ファイルと環境変数 |
| テスト | pytest / pytest-asyncio | ユニットテスト |

---

## 2. アーキテクチャ図

### 全体構成図

```
┌─────────────────────────────────────────────────────────────────────┐
│  main.py  エントリーポイント                                         │
│                                                                     │
│  1. config.yaml 読み込み                                            │
│  2. .env 読み込み                                                   │
│  3. サービスインスタンス生成                                         │
│  4. PCMonitor.start()                                               │
│  5. AttendanceScheduler(5分間隔)                                    │
│  6. SIGINT/SIGTERM ハンドリング                                     │
│  7. while True: sleep(1)                                            │
└──────────────────────────┬──────────────────────────────────────────┘
                           │ check_job() 5分毎に呼び出し
                           ▼
┌──────────────────────────────────────────────────────────────────────┐
│  LangGraph StateGraph (AttendanceState)                              │
│                                                                      │
│  ┌──────────────────┐                                                │
│  │ WorkingStateNode  │ PC稼働判定                                    │
│  │ (is_working判定)  │                                               │
│  └────────┬─────────┘                                                │
│           │                                                          │
│    is_working=False ─────────────────────────────────────▶ END        │
│           │                                                          │
│    is_working=True                                                   │
│           ▼                                                          │
│  ┌──────────────────┐                                                │
│  │ CalendarCheckNode │ 祝日・有給判定                                │
│  │ (is_holiday判定)  │                                               │
│  └────────┬─────────┘                                                │
│           │                                                          │
│    is_holiday=True ──────────────────────────────────────▶ END        │
│           │                                                          │
│    is_holiday=False                                                  │
│           ▼                                                          │
│  ┌──────────────────┐                                                │
│  │ TimeGateNode      │ 時刻ルール判定                                │
│  │ (action_taken決定)│                                               │
│  └────────┬─────────┘                                                │
│           │                                                          │
│    action_taken="skipped" ──────────────────────────────▶ END        │
│           │                                                          │
│    action_taken=clock_in/clock_out/clock_in_and_out                  │
│           ▼                                                          │
│  ┌──────────────────┐                                                │
│  │ StampNode         │ 打刻実行 (async)                              │
│  │ (Playwright/Dummy)│                                               │
│  └────────┬─────────┘                                                │
│           │                                                          │
│           ▼                                                          │
│  ┌──────────────────┐                                                │
│  │ SlackNotifyNode   │ 結果通知                                      │
│  │ (Slack/Console)   │                                               │
│  └────────┬─────────┘                                                │
│           │                                                          │
│           ▼                                                          │
│  ┌──────────────────┐                                                │
│  │ StateUpdateNode   │ 状態更新・日付跨ぎリセット                     │
│  └────────┬─────────┘                                                │
│           │                                                          │
│           ▼                                                          │
│          END                                                         │
└──────────────────────────────────────────────────────────────────────┘

外部サービス:
┌──────────┐  ┌───────────┐  ┌────────────┐  ┌─────────────────┐
│ pynput   │  │ Playwright│  │ Slack SDK  │  │ Google Calendar │
│(PC監視)  │  │(打刻操作)  │  │(通知送信)   │  │(祝日・有給判定)  │
└──────────┘  └───────────┘  └────────────┘  └─────────────────┘
```

### データフロー概要

```
PCMonitor ──操作イベント──▶ WorkingStateNode ──is_working──▶ CalendarCheckNode
                                                              │
                          CalendarService ──is_holiday──────────┘
                                                              │
                                                    TimeGateNode
                                                              │
                                                   action_taken
                                                              │
                                                      StampNode
                                                     ╱        ╲
                                            StampResult   StampResult
                                            (success)     (error)
                                                     ╲        ╱
                                                 SlackNotifyNode
                                                              │
                                                       通知送信
                                                              │
                                                  StateUpdateNode
                                                              │
                                                     状態永続化
```

---

## 3. ディレクトリ構造

```
C:\AI\勤怠エージェント\
├── attendance_agent_spec.md          # 仕様書
├── docs/
│   ├── ARCHITECTURE.md               # 本ドキュメント
│   ├── KNOWN_ISSUES.md               # 既知の問題
│   ├── TROUBLESHOOTING.md            # トラブルシューティング
│   ├── FAQ.md                        # よくある質問
│   └── plans/
│       └── 2026-02-22-attendance-agent.md  # 計画書
│
└── attendance-agent/                 # メインパッケージ
    ├── main.py                       # エントリーポイント
    ├── config.yaml                   # 設定ファイル
    ├── graph/
    │   ├── __init__.py
    │   ├── state.py                  # AttendanceState (TypedDict)
    │   ├── graph.py                  # LangGraph グラフ構築・条件分岐
    │   └── nodes/
    │       ├── __init__.py
    │       ├── working_state_node.py # PC稼働判定ノード
    │       ├── calendar_check_node.py# 祝日・有給判定ノード
    │       ├── time_gate_node.py     # 時刻ルール判定ノード
    │       ├── stamp_node.py         # 打刻実行ノード (async)
    │       ├── slack_notify_node.py  # 結果通知ノード
    │       └── state_update_node.py  # 状態更新ノード
    ├── services/
    │   ├── __init__.py
    │   ├── pc_monitor.py             # PC操作監視 (pynput)
    │   ├── stamper_interface.py      # 打刻ABC + StampResult
    │   ├── dummy_stamper.py          # ダミー打刻 (開発・テスト用)
    │   ├── attendance_browser.py     # Playwright打刻 (本番用)
    │   ├── slack_client.py           # Slack/Console通知
    │   ├── google_calendar.py        # Google Calendar / jpholiday判定
    │   └── config_loader.py          # YAML設定ローダー
    ├── schedulers/
    │   ├── __init__.py
    │   └── scheduler.py              # APScheduler ラッパー
    └── tests/
        ├── __init__.py
        ├── conftest.py               # 共通フィクスチャ (sys.path設定)
        ├── test_state.py             # AttendanceState テスト
        ├── test_working_state.py     # WorkingStateNode テスト
        ├── test_pc_monitor.py        # PCMonitor テスト
        ├── test_calendar_check.py    # カレンダーサービス テスト
        ├── test_calendar_check_node.py # CalendarCheckNode テスト
        ├── test_time_gate.py         # TimeGateNode テスト
        ├── test_stamp.py             # StamperInterface/AttendanceBrowser テスト
        ├── test_stamp_node.py        # StampNode テスト
        ├── test_dummy_stamper.py     # DummyStamper テスト
        ├── test_slack_client.py      # Slack/Console通知 テスト
        ├── test_slack_notify_node.py # SlackNotifyNode テスト
        ├── test_state_update_node.py # StateUpdateNode テスト
        ├── test_graph.py             # グラフ構築・ルーティング テスト
        ├── test_scheduler.py         # スケジューラ テスト
        └── test_config_loader.py     # 設定ローダー テスト
```

---

## 4. 状態管理 (AttendanceState)

### 定義

**ファイル:** `attendance-agent/graph/state.py`

```python
class AttendanceState(TypedDict):
    today: str                          # YYYY-MM-DD 形式の日付文字列
    is_holiday: bool                    # 祝日・有給フラグ
    holiday_reason: Optional[str]       # 休日の理由 (例: "天皇誕生日", "有給休暇")
    clock_in_done: bool                 # 出勤打刻済みフラグ
    clock_in_time: Optional[str]        # 出勤打刻時刻 HH:MM
    last_clock_out_time: Optional[str]  # 最終退勤打刻時刻 HH:MM
    is_working: bool                    # 現在PC操作中か
    operation_log: list[datetime]       # 直近の操作イベントリスト
    action_taken: Optional[str]         # 実行アクション (後述)
    error_message: Optional[str]        # エラー詳細
    extra: dict                         # 拡張用の任意データ
```

### action_taken の取りうる値

| 値 | 意味 | 発生条件 |
|----|------|---------|
| `"clock_in"` | 出勤打刻を実行 | 18:00前 かつ 未出勤 |
| `"clock_out"` | 退勤打刻を実行 | 18:00-22:00 かつ 出勤済み |
| `"clock_in_and_out"` | 出勤+退勤を連続実行 | 18:00-22:00 かつ 未出勤 |
| `"skipped"` | 打刻をスキップ | 22:00以降、または既に出勤済みで18:00前 |
| `"error"` | 打刻失敗 | Playwright操作エラー時 |
| `None` | 未判定 | 初期状態 |

### 状態のライフサイクル

```
起動時:
  clock_in_done=False, clock_in_time=None, last_clock_out_time=None

出勤打刻後:
  clock_in_done=True, clock_in_time="09:05", last_clock_out_time=None

退勤打刻後:
  clock_in_done=True, clock_in_time="09:05", last_clock_out_time="18:02"

日付跨ぎ (翌日):
  clock_in_done=False, clock_in_time=None, last_clock_out_time=None  (リセット)
```

### 状態の永続化

`main.py` 内のグローバル変数 `_state_store` で、スケジューラ呼び出し間の状態を保持する。

```python
_state_store = {
    "clock_in_done": False,      # 出勤済みフラグ
    "clock_in_time": None,       # 出勤時刻
    "last_clock_out_time": None, # 退勤時刻
    "last_date": "",             # 最終チェック日 (日付跨ぎ検出用)
}
```

各 `check_job()` の実行前に `_state_store` から状態を復元し、実行後に更新された状態を書き戻す。日付が変わった場合は全てリセットされる。

---

## 5. LangGraphステートマシン

### グラフ構築

**ファイル:** `attendance-agent/graph/graph.py`

LangGraphの `StateGraph` を使い、6つのノードと3つの条件分岐を定義する。

```python
def build_graph(monitor, calendar_service, browser, notifier, config):
    workflow = StateGraph(AttendanceState)

    # ノード登録
    workflow.add_node("working_state", ...)
    workflow.add_node("calendar_check", ...)
    workflow.add_node("time_gate", ...)
    workflow.add_node("stamp", ...)
    workflow.add_node("slack_notify", ...)
    workflow.add_node("state_update", ...)

    # エントリーポイント
    workflow.set_entry_point("working_state")

    # 条件分岐エッジ
    workflow.add_conditional_edges("working_state", route_after_working_check, ...)
    workflow.add_conditional_edges("calendar_check", route_after_calendar_check, ...)
    workflow.add_conditional_edges("time_gate", route_after_time_gate, ...)

    # 無条件エッジ
    workflow.add_edge("stamp", "slack_notify")
    workflow.add_edge("slack_notify", "state_update")
    workflow.add_edge("state_update", END)

    return workflow.compile()
```

### 依存性注入パターン

各ノード関数はサービスオブジェクトを引数として受け取るが、LangGraphは `(state) -> dict` シグネチャのみ受け付ける。この問題を `functools.partial` で解決している。

```python
from functools import partial

working_state_wrapped = partial(working_state_node, monitor=monitor, config=config)
workflow.add_node("working_state", working_state_wrapped)
```

### main.py での直接呼び出し

`main.py` の `run_check()` 関数では、LangGraphのグラフを介さず各ノード関数を順次呼び出すパターンも使用している。これにより、条件分岐のロジックを明示的に `if` 文で制御し、中間結果に基づいて早期リターンする。

```python
# main.py - run_check() の実行フロー
ws_result = working_state_node(state, monitor=monitor, config=config)
state.update(ws_result)
if not state["is_working"]:
    return  # 早期リターン

cal_result = calendar_check_node(state, calendar_service=calendar_service)
state.update(cal_result)
if state["is_holiday"]:
    return  # 早期リターン

# ... 以下同様
```

---

## 6. 各ノードの責務と入出力

### 6.1 WorkingStateNode

**ファイル:** `attendance-agent/graph/nodes/working_state_node.py`

| 項目 | 内容 |
|------|------|
| **目的** | PCが操作中かどうかを判定する |
| **入力** | `state` (参照のみ), `monitor: PCMonitor`, `config` |
| **処理** | `PCMonitor.is_working(threshold_minutes, min_count)` を呼び出し。直近15分間で2回以上の操作イベントがあれば `is_working=True` |
| **出力** | `{is_working: bool, operation_log: list[datetime]}` |
| **分岐** | `is_working=False` → END (打刻処理をスキップ) |

**設定パラメータ:**
- `working_state.window_minutes`: 判定ウィンドウ幅 (デフォルト: 15分)
- `working_state.min_event_count`: 最小イベント数 (デフォルト: 2回)

### 6.2 CalendarCheckNode

**ファイル:** `attendance-agent/graph/nodes/calendar_check_node.py`

| 項目 | 内容 |
|------|------|
| **目的** | 今日が祝日・有給・休日かを判定する |
| **入力** | `state` (`today` 参照), `calendar_service` |
| **処理** | `calendar_service.is_holiday(target_date)` を呼び出し |
| **出力** | `{is_holiday: bool, holiday_reason: str or None}` |
| **分岐** | `is_holiday=True` → END (打刻不要) |

**判定順序 (GoogleCalendarServiceの場合):**
1. 土日チェック (曜日判定)
2. 日本の祝日チェック (`jpholiday.is_holiday_name()`)
3. Google Calendar APIで有給キーワード検索 (例: "有給", "年休", "休暇")

### 6.3 TimeGateNode

**ファイル:** `attendance-agent/graph/nodes/time_gate_node.py`

| 項目 | 内容 |
|------|------|
| **目的** | 現在時刻と出勤状態から打刻アクションを決定する |
| **入力** | `state` (`clock_in_done` 参照), `config` |
| **処理** | 時刻ルールに基づくif/else分岐 |
| **出力** | `{action_taken: str}` |
| **分岐** | `action_taken="skipped"` → END |

**時刻ルールの判定マトリクス:**

| 時間帯 | 出勤済み (`clock_in_done`) | 未出勤 |
|--------|--------------------------|--------|
| ～18:00 | `skipped` | `clock_in` |
| 18:00～22:00 | `clock_out` | `clock_in_and_out` |
| 22:00以降 | `skipped` | `skipped` |

**設定パラメータ:**
- `time_rules.clock_out_time`: 退勤時刻の境界 (デフォルト: "18:00")
- `time_rules.cutoff_time`: 打刻禁止時刻 (デフォルト: "22:00")

**テスト容易性:** `_now()` 関数をモジュールレベルで定義し、テスト時にモンキーパッチで現在時刻を差し替え可能。

### 6.4 StampNode

**ファイル:** `attendance-agent/graph/nodes/stamp_node.py`

| 項目 | 内容 |
|------|------|
| **目的** | 打刻を実行する (async) |
| **入力** | `state` (`action_taken` 参照), `browser: StamperInterface` |
| **処理** | `action_taken` に応じて `browser.clock_in()` / `browser.clock_out()` を呼び出し |
| **出力** | `{clock_in_done, clock_in_time, last_clock_out_time, action_taken, error_message}` |
| **分岐** | なし (次のノードへ直進) |

**アクション別の処理:**

| action_taken | 処理 |
|-------------|------|
| `clock_in` | `browser.clock_in()` のみ |
| `clock_out` | `browser.clock_out()` のみ |
| `clock_in_and_out` | `browser.clock_in()` → `browser.clock_out()` の順に実行 |

**エラーハンドリング:**
- 打刻失敗時は `action_taken="error"`, `error_message` にエラー詳細を設定
- `clock_in_and_out` で出勤は成功したが退勤が失敗した場合、`clock_in_done=True`, `clock_in_time` は設定された上で `action_taken="error"` となる

### 6.5 SlackNotifyNode

**ファイル:** `attendance-agent/graph/nodes/slack_notify_node.py`

| 項目 | 内容 |
|------|------|
| **目的** | 打刻結果をSlack (またはコンソール) に通知する |
| **入力** | `state` (`action_taken`, `clock_in_time`, `last_clock_out_time`, `error_message` 参照), `notifier` |
| **処理** | アクション種別に応じたメッセージテンプレートを展開し送信 |
| **出力** | `{}` (空dict、状態変更なし) |
| **分岐** | なし |

**メッセージテンプレート:**

| アクション | メッセージ |
|-----------|----------|
| `clock_in` | `"出勤打刻しました（{time}）"` |
| `clock_out` | `"退勤打刻を更新しました（{time}）"` |
| `clock_in_and_out` | `"出勤（{in_time}）・退勤（{out_time}）を打刻しました"` |
| `error` | `"打刻に失敗しました。手動確認をお願いします（エラー: {error}）"` |
| `skipped` | 通知なし |

### 6.6 StateUpdateNode

**ファイル:** `attendance-agent/graph/nodes/state_update_node.py`

| 項目 | 内容 |
|------|------|
| **目的** | 日付跨ぎの検出と状態リセット、エラークリア |
| **入力** | `state` 全体 |
| **処理** | `state["today"]` と現在の日付を比較 |
| **出力** | 更新された状態dict |
| **分岐** | なし (END へ) |

**日付跨ぎ時:** 全ての打刻状態をリセット (`clock_in_done=False`, 各時刻=None)
**同日:** `error_message` をクリアし、打刻状態を維持

---

## 7. サービス層の設計

### 7.1 打刻サービス (Strategy Pattern)

**インターフェース:** `attendance-agent/services/stamper_interface.py`

```python
@dataclass
class StampResult:
    success: bool           # 打刻成功/失敗
    timestamp: str          # 打刻時刻 HH:MM
    error: Optional[str]    # エラー詳細 (失敗時のみ)

class StamperInterface(ABC):
    async def clock_in(self) -> StampResult: ...
    async def clock_out(self) -> StampResult: ...
    async def close(self) -> None: ...
```

**実装クラスの構成:**

```
StamperInterface (ABC)
├── DummyStamper       # ログ出力のみ（開発・テスト用）
└── AttendanceBrowser  # Playwright実装（本番用）
```

#### DummyStamper

**ファイル:** `attendance-agent/services/dummy_stamper.py`

- 実際の打刻は行わず、コンソールにログ出力のみ
- 常に `StampResult(success=True, ...)` を返す
- 開発時やテスト環境での動作確認に使用

#### AttendanceBrowser

**ファイル:** `attendance-agent/services/attendance_browser.py`

- Playwrightの非同期APIで社内勤怠システムのWebページを操作
- セッション状態のファイル永続化 (`storage_state`) でログインを省略可能
- リトライ機能あり (デフォルト3回)
- ログインページ検出時に自動ログイン

**処理フロー:**
```
_get_page() → ブラウザ起動/セッション復元
    ↓
ensure_logged_in() → URL遷移、ログイン判定、自動ログイン
    ↓
_stamp() → ボタンクリック、成功メッセージ確認、リトライ
    ↓
_save_session() → セッション保存
```

**切り替え方法:** `config.yaml` の `browser.stamper` を設定
```yaml
browser:
  stamper: "dummy"       # DummyStamper
  stamper: "playwright"  # AttendanceBrowser
```

### 7.2 通知サービス

**ファイル:** `attendance-agent/services/slack_client.py`

```
SlackNotifier    # Slack SDK による本番通知
ConsoleNotifier  # コンソール出力によるフォールバック
```

#### ConsoleNotifier

- `sys.stdout` / `sys.stderr` に出力するだけのシンプルな実装
- Slack設定が無い場合のフォールバック

#### SlackNotifier

- Slack SDK の `WebClient.chat_postMessage()` でメッセージ送信
- 初期化失敗時 (トークン無効等) は内部的に `ConsoleNotifier` にフォールバック
- `send()` メソッドは例外を握りつぶし、`bool` で成否を返す

**切り替え条件:**
- `SLACK_BOT_TOKEN` 環境変数が未設定 → ConsoleNotifier
- `slack.enabled=false` → ConsoleNotifier
- 上記以外 → SlackNotifier (失敗時は内部でConsoleNotifierにフォールバック)

### 7.3 カレンダーサービス

**ファイル:** `attendance-agent/services/google_calendar.py`

```
GoogleCalendarService   # Google Calendar API + jpholiday (本番)
LocalCalendarService    # jpholiday + 土日判定のみ (フォールバック)
```

#### LocalCalendarService

- `jpholiday` ライブラリで日本の祝日を判定
- `weekday() >= 5` で土日判定
- 結果を `_cache` dict でキャッシュ (同日の再判定を回避)

#### GoogleCalendarService

- ローカル祝日判定 (`LocalCalendarService` を内部に保持) + Google Calendar APIの2段階判定
- Google Calendar APIで個人カレンダーの有給イベントを検索
- `vacation_keywords` (デフォルト: `["有給", "年休", "休暇"]`) でイベントタイトルをマッチング
- API初期化失敗時は自動的にフォールバックモード (ローカル判定のみ)

**切り替え条件:**
- `calendar.fallback="jpholiday"` → LocalCalendarService
- Google API認証情報が未配置 → LocalCalendarService
- 上記以外 → GoogleCalendarService

### 7.4 PC監視サービス

**ファイル:** `attendance-agent/services/pc_monitor.py`

```python
class PCMonitor:
    # pynput mouse.Listener(on_move) + keyboard.Listener(on_press)
    # 1秒デデュプリケーション
    # is_working(threshold_minutes, min_count) → bool
```

**主要メソッド:**

| メソッド | 説明 |
|---------|------|
| `start()` | マウス・キーボードリスナーをバックグラウンドスレッドで開始 |
| `stop()` | リスナーを停止 |
| `_record_event_dedup()` | 1秒以内の連続イベントを除外して記録 |
| `get_recent_events(minutes)` | 直近N分以内の操作イベントリストを返す |
| `is_working(threshold_minutes, min_count)` | 直近N分以内にM回以上の操作があれば `True` |
| `purge_old_events(minutes)` | 古いイベントを削除してメモリを節約 |

**スレッドセーフ:** `threading.Lock` で `_events` リストへのアクセスを保護。

**テスト容易性:** モジュールレベル変数 `mouse_listener_cls`, `keyboard_listener_cls` をテスト時にモック差し替え可能。

---

## 8. 設定管理

### config.yaml

**ファイル:** `attendance-agent/config.yaml`

全ての動作パラメータを定義する。

```yaml
scheduler:
  check_interval_minutes: 5          # チェック間隔 (分)

working_state:
  window_minutes: 15                 # 稼働判定ウィンドウ (分)
  min_event_count: 2                 # 最小イベント数

time_rules:
  clock_out_time: "18:00"            # 退勤時刻の境界
  cutoff_time: "22:00"              # 打刻禁止時刻

browser:
  stamper: "dummy"                   # "dummy" or "playwright"
  headless: true                     # ヘッドレスモード
  retry_count: 3                     # リトライ回数
  session_storage_path: ".session"   # セッション保存パス
  selectors:                         # 社内システムのCSSセレクタ
    login_url: "https://..."
    username_field: "#username"
    password_field: "#password"
    login_button: "#login-btn"
    clock_in_button: "#clock-in"
    clock_out_button: "#clock-out"
    success_message: ".success-msg"

slack:
  enabled: true
  notify_channel: "DXXXXXXXX"        # SlackチャンネルID
  fallback: "console"

calendar:
  enabled: true
  fallback: "jpholiday"
  holiday_calendar_id: "ja.japanese#holiday@group.v.calendar.google.com"
  vacation_keywords:
    - "有給"
    - "年休"
    - "休暇"
```

### .env

認証情報を格納する (Gitには含めない)。

```
SLACK_BOT_TOKEN=xoxb-xxxx
SLACK_NOTIFY_CHANNEL=DXXXXXXXX
GOOGLE_CREDENTIALS_PATH=credentials.json
GOOGLE_TOKEN_PATH=token.json
HOLIDAY_CALENDAR_ID=ja.japanese#holiday@group.v.calendar.google.com
ATTENDANCE_URL=https://your-system.example.com
ATTENDANCE_USER=your-username
ATTENDANCE_PASS=your-password
```

### config_loader.py

**ファイル:** `attendance-agent/services/config_loader.py`

- `DEFAULT_CONFIG` に全デフォルト値を定義
- `load_config(path)` で YAML ファイルを読み込み、`_deep_merge()` でデフォルト値とマージ
- YAML ファイルが存在しない場合はデフォルト設定をそのまま返す
- ディープマージにより、ユーザーは変更したいパラメータのみ `config.yaml` に記載すればよい

---

## 9. グラフの条件分岐

**ファイル:** `attendance-agent/graph/graph.py`

3つの条件分岐関数が、各ノードの出力に基づいて次のノードまたは END を選択する。

### route_after_working_check

```python
def route_after_working_check(state: AttendanceState) -> str:
    if not state["is_working"]:
        return "end"          # → END: PC未操作のためスキップ
    return "calendar_check"   # → CalendarCheckNode へ進む
```

### route_after_calendar_check

```python
def route_after_calendar_check(state: AttendanceState) -> str:
    if state["is_holiday"]:
        return "end"          # → END: 祝日・有給のためスキップ
    return "time_gate"        # → TimeGateNode へ進む
```

### route_after_time_gate

```python
def route_after_time_gate(state: AttendanceState) -> str:
    if state["action_taken"] == "skipped":
        return "end"          # → END: 打刻不要
    return "stamp"            # → StampNode へ進む
```

### 条件分岐の登録

```python
workflow.add_conditional_edges(
    "working_state",
    route_after_working_check,
    {"calendar_check": "calendar_check", "end": END},
)
```

マッピング辞書の左辺がルーティング関数の戻り値、右辺が遷移先のノード名 (または `END`)。

---

## 10. main.py の起動フロー

**ファイル:** `attendance-agent/main.py`

### 起動シーケンス

```
1. load_config("config.yaml")
   └── YAML読み込み + DEFAULT_CONFIGとのディープマージ

2. create_services(config)
   ├── load_dotenv()           # .env読み込み
   ├── PCMonitor()             # PC監視インスタンス
   ├── CalendarService選択     # Google Calendar or jpholiday
   ├── Notifier選択            # Slack or Console
   └── Stamper選択             # Playwright or Dummy

3. monitor.start()
   └── pynputのマウス・キーボードリスナーを開始

4. AttendanceScheduler(interval_minutes=5, job_func=check_job)
   ├── BackgroundSchedulerを構成
   └── scheduler.start()

5. シグナルハンドリング登録
   ├── signal.signal(SIGINT, shutdown)
   └── signal.signal(SIGTERM, shutdown)

6. メインループ
   └── while True: time.sleep(1)
```

### 停止シーケンス (SIGINT/SIGTERM)

```
shutdown(signum, frame)
├── scheduler.stop()       # APSchedulerを停止
├── monitor.stop()         # pynputリスナーを停止
├── stamper.close()        # Playwrightブラウザを閉じる (async)
└── sys.exit(0)
```

### check_job() の実行フロー

各5分間隔で以下が実行される:

```
check_job()
├── 日付リセット判定 (today != last_date → 状態クリア)
├── 初期state構築 (_state_storeから復元)
├── working_state_node()  → is_working判定
│   └── False → return (早期リターン)
├── calendar_check_node() → is_holiday判定
│   └── True → return (早期リターン)
├── time_gate_node()      → action_taken判定
│   └── "skipped" → return (早期リターン)
├── stamp_node()          → 打刻実行 (asyncio.run)
├── slack_notify_node()   → 結果通知
├── state_update_node()   → 状態更新
└── _state_store 書き戻し
```

---

## 11. テスト戦略

### 概要

- **テスト総数:** 57テスト
- **フレームワーク:** pytest + pytest-asyncio
- **asyncio設定:** `pyproject.toml` に `asyncio_mode = "auto"` を設定
- **パス解決:** `conftest.py` で `sys.path.insert(0, ...)` により親ディレクトリを追加

### テストファイル一覧

| テストファイル | テスト数 | テスト対象 |
|-------------|---------|-----------|
| `test_state.py` | 2 | AttendanceState の生成と初期値 |
| `test_working_state.py` | 2 | WorkingStateNode のアクティブ/非アクティブ判定 |
| `test_pc_monitor.py` | 6 | PCMonitor のイベント記録・稼働判定・パージ・開始停止 |
| `test_calendar_check.py` | 5 | カレンダーサービスの祝日/平日/週末/フォールバック/キャッシュ |
| `test_calendar_check_node.py` | 2 | CalendarCheckNode の祝日/平日判定 |
| `test_time_gate.py` | 5 | TimeGateNode の全時間帯パターン |
| `test_stamp.py` | 4 | StampResult・打刻成功・リトライ |
| `test_stamp_node.py` | 4 | StampNode の出勤/退勤/失敗/出退勤同時 |
| `test_dummy_stamper.py` | 3 | DummyStamper の出勤/退勤/クローズ |
| `test_slack_client.py` | 5 | Slack/Console通知の送信・失敗・フォールバック |
| `test_slack_notify_node.py` | 4 | SlackNotifyNode の各アクション通知 |
| `test_state_update_node.py` | 3 | StateUpdateNode の同日/日付跨ぎ/エラークリア |
| `test_graph.py` | 7 | グラフ構築・全ルーティング関数 |
| `test_scheduler.py` | 2 | スケジューラの生成・開始停止 |
| `test_config_loader.py` | 3 | 設定ロード・ネスト・ファイル未存在 |

### モック戦略

全ての外部依存はモック可能な設計:

| サービス | モック方法 |
|---------|-----------|
| PCMonitor | `is_working()`, `get_recent_events()` をモック |
| CalendarService | `is_holiday()` の戻り値をモック |
| Stamper | `clock_in()`, `clock_out()` の `StampResult` をモック |
| Notifier | `send()`, `send_error()` をモック |
| 現在時刻 | `time_gate_node._now` をモンキーパッチ |
| 今日の日付 | `state_update_node._today_str` をモンキーパッチ |
| pynputリスナー | モジュールレベル変数 `mouse_listener_cls`, `keyboard_listener_cls` を差し替え |

### テスト実行

```bash
cd attendance-agent
python -m pytest tests/ -v
```

### 注意事項

- **祝日との重複:** テスト日付は日本の祝日と重複しないように選ぶ必要がある。例えば 2026-02-23 は天皇誕生日のため、平日テストには使用不可 (2026-02-24等を使用)。
- **jpholiday.is_holiday()** で事前に確認すること。

---

## 12. 拡張ポイント

### 新しい打刻サービスの追加

1. `StamperInterface` を継承した新クラスを `services/` に作成
2. `async def clock_in()`, `clock_out()`, `close()` を実装
3. `main.py` の `create_services()` に切り替え条件を追加
4. `config.yaml` の `browser.stamper` に新しい値を定義

```python
# 例: API打刻サービス
class APIStamper(StamperInterface):
    async def clock_in(self) -> StampResult:
        # REST API呼び出し
        ...
```

### 新しいノードの追加

1. `graph/nodes/` に新ノード関数を作成
2. `graph/graph.py` の `build_graph()` で `workflow.add_node()` を追加
3. 必要に応じて条件分岐エッジを追加/変更
4. `main.py` の `run_check()` にも同等のロジックを追加

### 設定パラメータの追加

1. `config.yaml` に新パラメータを追加
2. `config_loader.py` の `DEFAULT_CONFIG` にデフォルト値を追加
3. 対応するノード/サービスで `config` 辞書から値を読み出す

### 新しい通知サービスの追加

1. `send(message: str) -> bool` と `send_error(error: str) -> bool` を持つクラスを作成
2. `main.py` の `create_services()` に切り替え条件を追加

---

## 13. 関連ドキュメント

| ドキュメント | 場所 | 内容 |
|-------------|------|------|
| 仕様書 | `attendance_agent_spec.md` | プロジェクトの元仕様 |
| 既知の問題 | `docs/KNOWN_ISSUES.md` | 発見済み/解決済みのバグ |
| トラブルシューティング | `docs/TROUBLESHOOTING.md` | よくある問題と解決方法 |
| FAQ | `docs/FAQ.md` | よくある質問と回答 |
| 計画書 | `docs/plans/2026-02-22-attendance-agent.md` | 初期計画 |
