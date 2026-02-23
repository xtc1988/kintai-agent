# 勤怠管理エージェント (kintai-agent) 引き継ぎドキュメント

> **最終更新:** 2026-02-23
> **対象読者:** このプロジェクトの開発を引き継ぐAIまたは開発者
> **前提知識:** Python 3.10+, LangGraph, 非同期処理の基本

---

## 目次

1. [プロジェクト概要](#1-プロジェクト概要)
2. [現在の実装状況](#2-現在の実装状況)
3. [システムアーキテクチャ](#3-システムアーキテクチャ)
4. [重要な設計判断](#4-重要な設計判断)
5. [ファイル一覧と各ファイルの役割](#5-ファイル一覧と各ファイルの役割)
6. [環境構築手順](#6-環境構築手順)
7. [設定ファイルの詳細](#7-設定ファイルの詳細)
8. [テストの実行方法と注意事項](#8-テストの実行方法と注意事項)
9. [未実装・今後の作業](#9-未実装今後の作業)
10. [既知の問題と過去のトラブル](#10-既知の問題と過去のトラブル)
11. [開発の進め方の推奨](#11-開発の進め方の推奨)
12. [関連ドキュメント一覧](#12-関連ドキュメント一覧)

---

## 1. プロジェクト概要

### 何をするプロジェクトか

PC操作（マウス移動、キーボード操作）をリアルタイム監視し、社内勤怠システムへの打刻を自動で実行するエージェントです。「打刻忘れ」を防止することが主目的です。

### 基本情報

| 項目 | 内容 |
|------|------|
| **リポジトリ** | https://github.com/xtc1988/kintai-agent |
| **言語** | Python 3.10+ |
| **フレームワーク** | LangGraph（ステートマシンとして使用） |
| **AI/LLM使用** | **なし**（完全なルールベース実装） |
| **ライセンス** | Private（社内利用限定） |
| **作成日** | 2026-02-22 |

### 重要な前提

- LangGraphはAI/LLMのフレームワークとして有名だが、このプロジェクトではワークフロー管理（ステートマシン）の機能のみを使用している
- AI/LLM呼び出しは一切行っていない
- 全ての判定はルールベース（時刻判定、イベントカウント、祝日判定など）

### 技術スタック

| 役割 | ライブラリ | バージョン要件 |
|------|-----------|---------------|
| ワークフロー管理 | LangGraph | >=0.2.0 |
| PC操作監視 | pynput | >=1.7.6 |
| ブラウザ自動操作 | Playwright | >=1.40.0 |
| 定期実行 | APScheduler | >=3.10.0 |
| 設定管理 | PyYAML | >=6.0 |
| 環境変数 | python-dotenv | >=1.0.0 |
| Slack通知 | slack-sdk | >=3.27.0 |
| Google Calendar | google-api-python-client | >=2.100.0 |
| Google認証 | google-auth-oauthlib | >=1.2.0 |
| 祝日判定 | jpholiday | >=0.1.8 |
| テスト | pytest + pytest-asyncio + pytest-mock | (dev依存) |

---

## 2. 現在の実装状況

### 全17タスク完了済み

| # | タスク名 | 状態 | 主要ファイル |
|---|----------|------|-------------|
| 0 | プロジェクト初期化 | 完了 | pyproject.toml, config.yaml, .env.example |
| 1 | AttendanceState TypedDict | 完了 | graph/state.py |
| 2 | PCMonitor (pynput) | 完了 | services/pc_monitor.py |
| 3 | ConfigLoader (YAML) | 完了 | services/config_loader.py |
| 4 | WorkingStateNode | 完了 | graph/nodes/working_state_node.py |
| 5 | Calendar Service (Google + jpholiday) | 完了 | services/google_calendar.py |
| 6 | CalendarCheckNode | 完了 | graph/nodes/calendar_check_node.py |
| 7 | TimeGateNode | 完了 | graph/nodes/time_gate_node.py |
| 8 | AttendanceBrowser (Playwright) | 完了 | services/attendance_browser.py |
| 9 | StampNode | 完了 | graph/nodes/stamp_node.py |
| 10 | Slack通知サービス | 完了 | services/slack_client.py |
| 11 | SlackNotifyNode | 完了 | graph/nodes/slack_notify_node.py |
| 12 | StateUpdateNode | 完了 | graph/nodes/state_update_node.py |
| 13 | LangGraphグラフ定義 | 完了 | graph/graph.py |
| 14 | Scheduler (APScheduler) | 完了 | schedulers/scheduler.py |
| 15 | main.py エントリーポイント | 完了 | main.py |
| 16 | 全体テスト | 完了 | tests/ (全57テスト全パス) |

### 追加リファクタリング（実装計画外だが完了済み）

- **StamperInterface (ABC)** を導入して打刻処理をプラグイン化
- **DummyStamper** をデフォルト実装として追加（Playwrightなしでも動作可能）
- config.yaml の `browser.stamper` で `"dummy"` / `"playwright"` を切り替え可能

---

## 3. システムアーキテクチャ

### 動作フロー

APSchedulerにより5分間隔（デフォルト）で以下の6ノードのステートマシンが実行される。

```
WorkingStateNode (PC稼働判定)
    |
    | is_working=True の場合のみ次へ（Falseなら終了）
    v
CalendarCheckNode (祝日・有給判定)
    |
    | is_holiday=False の場合のみ次へ（Trueなら終了）
    v
TimeGateNode (時刻ルール判定)
    |
    | action_taken != "skipped" の場合のみ次へ（"skipped"なら終了）
    v
StampNode (打刻実行)
    |
    v
SlackNotifyNode (結果通知)
    |
    v
StateUpdateNode (状態更新・日付リセット)
```

### TimeGateルール表

TimeGateNodeは現在時刻と出勤打刻の状態に基づき、実行すべきアクションを決定する。

| 時間帯 | 出勤打刻済み | 判定結果 |
|--------|-------------|---------|
| 22:00以降 | どちらでも | `"skipped"`（打刻禁止時間帯） |
| 開始〜18:00 | False | `"clock_in"`（出勤打刻） |
| 開始〜18:00 | True | `"skipped"`（既に打刻済み） |
| 18:00〜22:00 | True | `"clock_out"`（退勤打刻） |
| 18:00〜22:00 | False | `"clock_in_and_out"`（出勤+退勤の両方実行） |

### レイヤー構成

```
main.py（エントリーポイント）
  |
  +-- schedulers/scheduler.py（APScheduler定期実行）
  |
  +-- graph/graph.py（LangGraph StateGraph定義）
  |     |
  |     +-- graph/state.py（AttendanceState TypedDict）
  |     |
  |     +-- graph/nodes/（6つのノード）
  |           |-- working_state_node.py
  |           |-- calendar_check_node.py
  |           |-- time_gate_node.py
  |           |-- stamp_node.py
  |           |-- slack_notify_node.py
  |           +-- state_update_node.py
  |
  +-- services/（実処理サービス層）
        |-- pc_monitor.py（pynput PC操作監視）
        |-- stamper_interface.py（打刻ABC）
        |-- dummy_stamper.py（ダミー打刻）
        |-- attendance_browser.py（Playwright打刻）
        |-- google_calendar.py（Google Calendar + jpholiday）
        |-- slack_client.py（Slack + Console通知）
        +-- config_loader.py（YAML設定読み込み）
```

### 状態管理 (AttendanceState)

```python
class AttendanceState(TypedDict):
    today: str                          # "YYYY-MM-DD" 形式の日付文字列
    is_holiday: bool                    # 祝日・有給フラグ
    holiday_reason: Optional[str]       # 理由（例: "山の日", "有給"）
    clock_in_done: bool                 # 出勤打刻済みフラグ
    clock_in_time: Optional[str]        # 出勤打刻時刻 "HH:MM"
    last_clock_out_time: Optional[str]  # 最終退勤打刻時刻 "HH:MM"
    is_working: bool                    # 現在PC作業中か
    operation_log: list[datetime]       # 直近の操作イベントリスト
    action_taken: Optional[str]         # "clock_in" / "clock_out" / "clock_in_and_out" / "skipped" / "error"
    error_message: Optional[str]        # エラー詳細
    extra: dict                         # 拡張用の任意データ
```

**注意:** 状態はメモリ上で保持される（`main.py` の `_state_store` グローバル辞書）。プロセスを再起動すると状態はリセットされる。

---

## 4. 重要な設計判断

### 4.1 フォールバック設計

全ての外部サービスにフォールバック実装が用意されており、外部APIが使えなくても全機能が動作する。

| サービス | 本番実装 | フォールバック | 切り替え方法 |
|----------|---------|---------------|-------------|
| 打刻 | AttendanceBrowser (Playwright) | DummyStamper (ログ出力のみ) | config.yaml `browser.stamper` |
| 通知 | SlackNotifier (slack-sdk) | ConsoleNotifier (標準出力) | .env の SLACK_BOT_TOKEN が空ならフォールバック |
| カレンダー | GoogleCalendarService (API) | LocalCalendarService (jpholiday) | config.yaml `calendar.fallback` |

### 4.2 StamperInterface パターン

打刻処理はABC（Abstract Base Class）でインターフェースを定義し、実装を差し替え可能にしている。

```python
# services/stamper_interface.py
class StamperInterface(ABC):
    @abstractmethod
    async def clock_in(self) -> StampResult: ...

    @abstractmethod
    async def clock_out(self) -> StampResult: ...

    @abstractmethod
    async def close(self) -> None: ...
```

新しい打刻方式を追加する手順:
1. `StamperInterface` を継承したクラスを作成
2. `clock_in()`, `clock_out()`, `close()` を実装
3. `main.py` の `create_services()` に分岐を追加
4. config.yaml の `browser.stamper` に新しい値を追加

### 4.3 ノード設計パターン

各ノードは純粋関数として設計されている:

```python
def some_node(state: AttendanceState, service=None, config=None) -> dict:
    # stateを読み取り、serviceを使って処理し、更新するdict部分だけ返す
    return {"key": "value"}  # stateの差分のみ
```

特徴:
- **サービスはキーワード引数で注入**: テスト時にモックに差し替え可能
- **戻り値はstateの差分のみ**: 変更したいキーだけ含むdictを返す
- **graph.py で functools.partial を使用**: LangGraphが要求する `(state) -> dict` シグネチャに変換

```python
# graph/graph.py での変換例
from functools import partial
working_state_wrapped = partial(working_state_node, monitor=monitor, config=config)
workflow.add_node("working_state", working_state_wrapped)
```

### 4.4 テスト時のモック可能な設計

時刻やシステム依存の処理はモジュールレベルの関数として切り出されている:

```python
# graph/nodes/time_gate_node.py
def _now() -> datetime:
    """テスト時にモック可能な現在時刻取得"""
    return datetime.now()

# graph/nodes/state_update_node.py
def _today_str() -> str:
    """テスト時にモック可能"""
    return date.today().isoformat()

# services/pc_monitor.py
mouse_listener_cls = mouse.Listener       # テスト時にモック差し替え可能
keyboard_listener_cls = keyboard.Listener  # テスト時にモック差し替え可能
```

テスト例:
```python
with patch("graph.nodes.time_gate_node._now", return_value=datetime(2026, 2, 22, 9, 0)):
    result = time_gate_node(state, config=config)
```

### 4.5 main.py の実行方式

`main.py` ではLangGraphのコンパイル済みグラフ（`build_graph()`）ではなく、ノードを順次呼び出す方式を採用している。

理由:
- 各ノードの実行結果に基づく早期リターンが容易
- asyncio.run() の呼び出しが1箇所に限定される
- デバッグ時にノード間の状態を確認しやすい

`graph/graph.py` の `build_graph()` はLangGraphのグラフとしてコンパイル可能な状態で維持されており、将来的にグラフベースの実行に移行することも可能。

---

## 5. ファイル一覧と各ファイルの役割

### プロジェクトルート（C:\AI\勤怠エージェント\）

```
C:\AI\勤怠エージェント\
├── attendance_agent_spec.md           # 元の仕様書（全体設計の原典）
├── README.md                          # プロジェクト概要・セットアップ手順
├── docs/
│   ├── HANDOVER.md                    # この引き継ぎドキュメント
│   ├── FAQ.md                         # よくある質問
│   ├── KNOWN_ISSUES.md                # 既知の問題（解決済み含む）
│   ├── TROUBLESHOOTING.md             # トラブルシューティングガイド
│   └── plans/
│       └── 2026-02-22-attendance-agent.md  # 元の実装計画（全17タスクの詳細）
└── attendance-agent/                  # メインのPythonパッケージ（以下が実装コード）
```

### attendance-agent/ ディレクトリ（実装コード）

| ファイル | 役割 | 詳細 |
|----------|------|------|
| **main.py** | エントリーポイント | `create_services()` でサービス生成、`run_check()` で1回のチェック実行、`main()` でスケジューラ起動 |
| **config.yaml** | 全動作設定 | チェック間隔、時刻ルール、ブラウザセレクタ、Slack設定、カレンダー設定 |
| **.env.example** | 環境変数テンプレート | 認証情報のテンプレート（コピーして .env を作成） |
| **pyproject.toml** | ビルド設定・依存関係 | setuptools.build_meta, pytest-asyncio asyncio_mode="auto" |
| **.gitignore** | Git除外設定 | .env, __pycache__, .session, credentials.json, token.json |

#### graph/ ディレクトリ

| ファイル | 役割 | 詳細 |
|----------|------|------|
| **state.py** | AttendanceState 型定義 | TypedDictで11フィールドを定義 |
| **graph.py** | LangGraph StateGraph定義 | `build_graph()` でグラフ構築、3つの条件分岐関数(`route_after_*`)、functools.partial でサービス注入 |

#### graph/nodes/ ディレクトリ

| ファイル | 役割 | 入力 | 出力 |
|----------|------|------|------|
| **working_state_node.py** | PC稼働判定 | PCMonitor + config | `{is_working, operation_log}` |
| **calendar_check_node.py** | 祝日・有給判定 | CalendarService | `{is_holiday, holiday_reason}` |
| **time_gate_node.py** | 時刻ルール判定 | config (time_rules) | `{action_taken}` |
| **stamp_node.py** | 打刻実行（async） | StamperInterface | `{clock_in_done, clock_in_time, last_clock_out_time, action_taken, error_message}` |
| **slack_notify_node.py** | Slack通知 | Notifier | `{}` (副作用のみ) |
| **state_update_node.py** | 日付リセット・状態保持 | なし（state自体を参照） | `{today, clock_in_done, ...}` |

#### services/ ディレクトリ

| ファイル | クラス | 役割 |
|----------|--------|------|
| **stamper_interface.py** | `StamperInterface` (ABC), `StampResult` (dataclass) | 打刻の抽象インターフェース |
| **dummy_stamper.py** | `DummyStamper` | ダミー打刻（ログ出力のみ、デフォルト） |
| **attendance_browser.py** | `AttendanceBrowser` | Playwright実装（本番用、セッション保存対応） |
| **pc_monitor.py** | `PCMonitor` | pynputでマウス・キーボード監視、スレッドセーフ、1秒デバウンス |
| **google_calendar.py** | `GoogleCalendarService`, `LocalCalendarService` | Google Calendar API + jpholidayローカルフォールバック |
| **slack_client.py** | `SlackNotifier`, `ConsoleNotifier` | Slack通知 + コンソールフォールバック |
| **config_loader.py** | `load_config()` | YAML読み込み + DEFAULT_CONFIGとの深いマージ |

#### schedulers/ ディレクトリ

| ファイル | クラス | 役割 |
|----------|--------|------|
| **scheduler.py** | `AttendanceScheduler` | APScheduler BackgroundSchedulerのラッパー、start/stop |

#### tests/ ディレクトリ（全57テスト）

| ファイル | テスト対象 | テスト数 |
|----------|-----------|---------|
| conftest.py | テスト共通設定 | - |
| test_state.py | AttendanceState型 | 2 |
| test_pc_monitor.py | PCMonitor | 6 |
| test_config_loader.py | config_loader | 3 |
| test_working_state.py | WorkingStateNode | 2 |
| test_calendar_check.py | CalendarService | 4 |
| test_calendar_check_node.py | CalendarCheckNode | 2 |
| test_time_gate.py | TimeGateNode | 5 |
| test_stamp.py | AttendanceBrowser / StampResult | 4 |
| test_stamp_node.py | StampNode | 4 |
| test_dummy_stamper.py | DummyStamper | (追加分) |
| test_slack_client.py | SlackNotifier / ConsoleNotifier | 5 |
| test_slack_notify_node.py | SlackNotifyNode | 4 |
| test_state_update_node.py | StateUpdateNode | 3 |
| test_graph.py | グラフ定義・ルーティング | 7 |
| test_scheduler.py | AttendanceScheduler | 2 |

---

## 6. 環境構築手順

### 前提条件

- Python 3.10以上
- pip
- Windows 11（開発環境）

### インストール手順

```bash
cd C:\AI\勤怠エージェント\attendance-agent

# 依存関係インストール（開発用含む）
pip install -e ".[dev]"

# Playwrightブラウザインストール（本番打刻を使う場合のみ）
playwright install chromium

# 環境変数ファイル作成
cp .env.example .env
# .env を編集して認証情報を設定
```

### 環境変数 (.env) の設定

```bash
# 勤怠システム（Playwright打刻で必要）
ATTENDANCE_URL=https://社内システムURL
ATTENDANCE_USER=ユーザーID
ATTENDANCE_PASS=パスワード

# Slack（SlackNotifierで必要）
SLACK_BOT_TOKEN=xoxb-...
SLACK_NOTIFY_CHANNEL=DXXXXXXXX

# Google Calendar（GoogleCalendarServiceで必要）
GOOGLE_CREDENTIALS_PATH=credentials.json
GOOGLE_TOKEN_PATH=token.json
HOLIDAY_CALENDAR_ID=ja.japanese#holiday@group.v.calendar.google.com
```

### 起動

```bash
cd C:\AI\勤怠エージェント\attendance-agent
python main.py
```

停止は `Ctrl+C` で行う。

### 重要な注意事項

- **Pythonバージョンの確認**: venvのPythonとシステムのPythonが異なる場合がある。`python --version` と `which python` で確認すること
- pyproject.toml の build-backend は `setuptools.build_meta` が正しい（仕様書には誤った値が記載されていた）
- setuptools の flat-layout では複数トップレベルパッケージがある場合、`[tool.setuptools.packages.find]` に `include` 指定が必須

---

## 7. 設定ファイルの詳細

### config.yaml の全項目

```yaml
# チェック間隔
scheduler:
  check_interval_minutes: 5        # 何分ごとにチェックを実行するか

# PC操作監視の閾値
working_state:
  window_minutes: 15               # 直近何分間の操作を見るか
  min_event_count: 2               # 最低何回の操作で「作業中」と判定するか

# 時刻ルール
time_rules:
  clock_out_time: "18:00"          # この時刻以降は退勤打刻対象
  cutoff_time: "22:00"             # この時刻以降は打刻禁止

# ブラウザ・打刻設定
browser:
  stamper: "dummy"                 # "dummy" = ダミー打刻, "playwright" = 実際に打刻
  headless: true                   # Playwrightのheadlessモード
  retry_count: 3                   # 打刻失敗時のリトライ回数
  session_storage_path: ".session" # セッション保存先
  selectors:                       # 社内システムのHTML要素セレクタ
    login_url: "https://your-system.example.com/login"
    username_field: "#username"
    password_field: "#password"
    login_button: "#login-btn"
    clock_in_button: "#clock-in"
    clock_out_button: "#clock-out"
    success_message: ".success-msg"

# Slack通知設定
slack:
  enabled: true                    # Slack通知の有効/無効
  notify_channel: "DXXXXXXXX"      # 通知先チャンネルまたはDMのID
  fallback: "console"              # フォールバック方式

# カレンダー設定
calendar:
  enabled: true                    # カレンダー判定の有効/無効
  fallback: "jpholiday"            # "jpholiday" = ローカル祝日判定
  holiday_calendar_id: "ja.japanese#holiday@group.v.calendar.google.com"
  vacation_keywords:               # 有給判定のキーワード
    - "有給"
    - "年休"
    - "休暇"
```

### config_loader.py のデフォルト値マージ

`config_loader.py` には `DEFAULT_CONFIG` が定義されており、config.yaml に記載されていないキーはデフォルト値で補完される。config.yaml が存在しない場合でもデフォルト設定で動作する。

---

## 8. テストの実行方法と注意事項

### 全テスト実行

```bash
cd C:\AI\勤怠エージェント\attendance-agent
python -m pytest tests/ -v
```

### ファイル単位で実行

```bash
python -m pytest tests/test_stamp.py -v
```

### 特定のテスト関数のみ実行

```bash
python -m pytest tests/test_stamp.py::test_stamp_clock_in_success -v
```

### テスト時の重要な注意事項

1. **テスト日付に祝日を使わないこと**
   - `jpholiday.is_holiday()` が True を返す日付を平日テストに使うとテストが失敗する
   - 例: 2026-02-23 は天皇誕生日のため使用不可
   - テスト日付を選ぶ前に `jpholiday.is_holiday(date(年, 月, 日))` で事前確認すること

2. **pytest-asyncio の設定**
   - pyproject.toml に `asyncio_mode = "auto"` が設定済み
   - これがないと `@pytest.mark.asyncio` をつけたテストが動作しない

3. **pynputの環境依存**
   - `pip install` 先がvenv(Python 3.12)とシステム(Python 3.10)で異なる場合がある
   - テスト実行時のPythonバージョンと一致する環境にインストールされていることを確認

---

## 9. 未実装・今後の作業

### 必須（本番運用に必要な作業）

#### 9.1 社内勤怠システムのセレクタ設定

config.yaml の `browser.selectors` に実際の社内システムのHTML要素IDを設定する必要がある。

**現在の状態:** プレースホルダー値（`#username`, `#clock-in` など）

**必要な作業:**
1. 社内勤怠システムのログインページをブラウザの開発者ツールで確認
2. 各要素のCSSセレクタを特定
3. config.yaml を更新

```yaml
browser:
  selectors:
    login_url: "https://実際のURL/login"
    username_field: "#実際のID"
    password_field: "#実際のID"
    login_button: "#実際のID"
    clock_in_button: "#実際のID"
    clock_out_button: "#実際のID"
    success_message: ".実際のクラス名"
```

#### 9.2 Playwright打刻の実機テスト

**手順:**
1. config.yaml の `browser.stamper` を `"playwright"` に変更
2. .env に正しい `ATTENDANCE_URL`, `ATTENDANCE_USER`, `ATTENDANCE_PASS` を設定
3. `playwright install chromium` を実行
4. headlessモードで動作確認（`browser.headless: true`）
5. 失敗する場合は headful モードで確認（`browser.headless: false`）
6. セッション保存（`.session` ディレクトリ）が正常に機能するか確認

#### 9.3 Slack API連携

**手順:**
1. Slack App を作成し、`chat:write` スコープを付与
2. Bot Token (`xoxb-...`) を取得
3. .env の `SLACK_BOT_TOKEN` に設定
4. 通知先チャンネルまたはDMのIDを `SLACK_NOTIFY_CHANNEL` に設定

**注意:**
- 社内Slack APIに制限がある可能性あり（IT部門に確認）
- 使えない場合は `ConsoleNotifier` がフォールバックとして自動的に使用される

#### 9.4 Google Calendar API連携

**手順:**
1. Google Cloud Console でプロジェクト作成
2. Calendar API を有効化
3. OAuth 2.0 クライアントIDを作成
4. `credentials.json` をダウンロードし `attendance-agent/` に配置
5. 初回実行時にブラウザで認証 → `token.json` が自動生成される
6. .env の `GOOGLE_CREDENTIALS_PATH` と `GOOGLE_TOKEN_PATH` を設定

**注意:**
- 使えない場合は `LocalCalendarService` (jpholiday + 土日判定) がフォールバックとして動作
- ローカルフォールバックでは個人カレンダーの有給イベントは検出できない

### 拡張（仕様書に記載の将来機能）

| 機能 | 実装方法 | 優先度 |
|------|---------|--------|
| 週次工数チェック | 新ノード `WeeklyWorkCheckNode` を追加、金曜にスケジュール | 中 |
| Slackからの有給登録 | `slack_client.py` にイベントハンドラ追加 | 中 |
| 打刻ログの永続化 | `StateUpdateNode` にDB/スプレッドシート書き込みを追加 | 高 |
| 複数人対応 | StateにユーザーID追加、グラフをマルチユーザー対応に | 低 |
| 複数社内システム対応 | StamperInterfaceの実装を増やす | 低 |

---

## 10. 既知の問題と過去のトラブル

### 解決済みの問題（再発防止のため記録）

| 問題 | 根本原因 | 解決方法 | 再発防止策 |
|------|---------|---------|-----------|
| pyproject.toml build-backendエラー | 仕様書の `setuptools.backends._legacy:_Backend` は存在しない | `setuptools.build_meta` に修正 | TROUBLESHOOTING.md に記録済み |
| setuptools flat-layout複数パッケージエラー | 複数トップレベルパッケージを自動検出不可 | `[tool.setuptools.packages.find]` にinclude追加 | TROUBLESHOOTING.md に記録済み |
| テスト日付が天皇誕生日と重複 | 2026-02-23は天皇誕生日 | テスト日付を2026-02-24に変更 | 祝日テストでは事前確認 |
| pynput未インストール | venvとシステムPythonのバージョン違い | 正しいPython環境にインストール | python --version で確認 |
| pytest-asyncio asyncio_mode未設定 | pyproject.tomlに設定がなかった | asyncio_mode = "auto" を追加 | pyproject.toml に設定済み |

### 詳細な記録

- `docs/KNOWN_ISSUES.md` -- 発見日、根本原因、解決方法、再発防止策を記録
- `docs/TROUBLESHOOTING.md` -- 症状、原因、解決コマンドを記録

---

## 11. 開発の進め方の推奨

### 作業開始前のチェックリスト

1. `python -m pytest tests/ -v` で全57テストがパスすることを確認
2. `docs/KNOWN_ISSUES.md` を確認して未解決の問題がないか把握
3. `docs/TROUBLESHOOTING.md` に関連するトラブル情報がないか確認

### 開発ルール

1. **TDD（テスト駆動開発）**: 変更前にテストを書く
2. **ノード単位の変更**: 各ノードは独立しているため、1ノードずつ変更・テストする
3. **サービス層の変更はインターフェースを守る**: StamperInterface, CalendarServiceの戻り値型を変えない
4. **ドキュメント更新**: 新しいバグや解決策は docs/ に記録する

### 新しいノードを追加する場合

1. `graph/nodes/` に新しいノードファイルを作成
2. `tests/` に対応するテストファイルを作成
3. `graph/graph.py` の `build_graph()` にノードとエッジを追加
4. `main.py` の `run_check()` に呼び出しを追加
5. 全テスト実行で既存機能への影響がないことを確認

### 新しいサービスを追加する場合

1. ABCインターフェースを定義（StamperInterfaceを参考に）
2. フォールバック実装を先に作成
3. 本番実装を作成
4. `main.py` の `create_services()` に分岐を追加
5. config.yaml に切り替え設定を追加

---

## 12. 関連ドキュメント一覧

| ドキュメント | パス | 内容 |
|-------------|------|------|
| README.md | `C:\AI\勤怠エージェント\README.md` | プロジェクト概要・セットアップ手順 |
| 仕様書 | `C:\AI\勤怠エージェント\attendance_agent_spec.md` | 元の仕様書（全体設計の原典） |
| 実装計画 | `C:\AI\勤怠エージェント\docs\plans\2026-02-22-attendance-agent.md` | 全17タスクの詳細な実装計画（コード付き） |
| FAQ | `C:\AI\勤怠エージェント\docs\FAQ.md` | よくある質問（実行方法、設定変更方法など） |
| 既知の問題 | `C:\AI\勤怠エージェント\docs\KNOWN_ISSUES.md` | 解決済み・未解決の問題一覧 |
| トラブルシューティング | `C:\AI\勤怠エージェント\docs\TROUBLESHOOTING.md` | ビルドエラー、実行時エラーの対処法 |
| 引き継ぎ | `C:\AI\勤怠エージェント\docs\HANDOVER.md` | このドキュメント |

---

## 補足: クイックスタートガイド

このプロジェクトを初めて触る場合の最短手順:

```bash
# 1. 環境構築
cd C:\AI\勤怠エージェント\attendance-agent
pip install -e ".[dev]"

# 2. テスト実行（動作確認）
python -m pytest tests/ -v
# → 全57テストがパスすることを確認

# 3. DummyStamperモードで起動（実際の打刻は行わない）
python main.py
# → Ctrl+C で停止

# 4. 本番運用へ移行する場合
# → 上記セクション9「未実装・今後の作業」の手順に従う
```

---

*このドキュメントは 2026-02-23 時点のプロジェクト状態を反映しています。*
